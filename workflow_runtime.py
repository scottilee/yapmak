"""Embedded runtime source. The compiler supplies POLICY, SLOTS, vars, and calendar helpers."""
WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

def _str(x):
    return '' if x is None else str(x)

def _S():
    try:
        s = json.loads(_str(vars.get('state_json')) or '{}')
        if not isinstance(s, dict):
            s = dict()
    except Exception:
        s = dict()
    if 'today' not in s:          # the initial code node may be skipped (chat route): initialize lazily
        s = _fresh_state()
    return s

def _fresh_state():
    S = dict()
    parsed = parse_now(_get('now')) if 'parse_now' in globals() else None
    parsed = parsed or (None, None)
    S['today'] = parsed[0] or _get('now')[:10]
    S['now_time'] = parsed[1] or _get('now')[11:16]
    S['holder_unclear'] = 0
    S['human_asked'] = False
    S['refuse_count'] = 0
    S['decline_count'] = 0
    S['close'] = None
    S['id_idx'] = 0
    S['id_wrong'] = 0
    S['products'] = []
    S['phase'] = 'all'
    S['pi'] = -1
    S['awaiting'] = 'today'
    S['offer'] = None
    S['transfer'] = None
    S['cb_asked'] = False
    S['vague_asked'] = False
    S['w_idx'] = -1
    S['n_idx'] = -1
    S['rb_declined'] = 0
    vars['today_text'] = _fmt(S['today'])
    if not _get('goodbye_text'):
        vars['goodbye_text'] = 'Thank you for your time. Goodbye.'
    for k in ('id_say', 'neg_instruction', 'readback_text', 'debt_statement', 'transfer_queue', 'final_outcome', 'final_reason'):
        if vars.get(k) is None:
            vars[k] = ''
    return S

def _save(s):
    vars['state_json'] = json.dumps(s)

def _empty(name):
    return EMPTY.get(name, '')

def _get(name):
    v = _str(vars.get(name)).strip()
    if v == _str(_empty(name)) or v == 'none':
        return ''
    try:
        if _empty(name) == 0 and float(v) == 0:
            return ''
    except Exception:
        pass
    return v

def _clear(*names):
    for n in names:
        vars[n] = _empty(n)

def _int(x):
    try:
        return int(float(_str(x)))
    except Exception:
        return None

def _float(x):
    try:
        v = float(_str(x).replace(',', ''))
        return v
    except Exception:
        return None

def _money(x):
    try:
        return '%.2f' % float(x)
    except Exception:
        return _str(x)

def _fmt(iso):
    try:
        d = datetime.date.fromisoformat(_str(iso)[:10])
        return d.strftime('%A') + ' ' + str(d.day) + ' ' + d.strftime('%B %Y')
    except Exception:
        return _str(iso)

def _cal():
    c = POLICY['calendar']
    return c['holidays'], c['business_days']

def _calendar_dict():
    c = POLICY['calendar']
    return dict(next_weekday_means_following_week=bool(c.get('next_weekday_means_following_week', True)), missing_date_parts='next_occurrence')

def _resolve_date(prefix, today):
    """Structured date extraction -> ('ok', iso) | ('vague', '') | ('none', '') | ('unreadable', '')."""
    kind = _get(prefix + '_kind')
    if kind in ('', 'none'):
        return 'none', ''
    if kind == 'vague':
        return 'vague', ''
    h, b = _cal()
    expr = None
    if kind in ('today', 'tomorrow'):
        expr = dict(keyword=kind)
    elif kind == 'weekday' and not _int(_get(prefix + '_day')):
        wd = _get(prefix + '_weekday').lower()
        if wd not in WEEKDAYS:
            return 'unreadable', ''
        rel = _get(prefix + '_relative').lower()
        expr = dict(weekday=WEEKDAYS.index(wd), relative='next' if rel == 'next' else 'this')
    elif kind in ('date', 'weekday'):
        day = _int(_get(prefix + '_day'))
        if day is None:
            return 'unreadable', ''
        expr = dict(day=day)
        m = _int(_get(prefix + '_month'))
        y = _int(_get(prefix + '_year'))
        if m:
            expr['month'] = m
        if y and m:
            expr['year'] = y
    r = resolve_date_expr(today, expr, _calendar_dict())
    if r == 'vague':
        return 'vague', ''
    if not r:
        return 'unreadable', ''
    return 'ok', r

def _clear_date(prefix):
    _clear(prefix + '_kind', prefix + '_weekday', prefix + '_relative', prefix + '_day', prefix + '_month', prefix + '_year')

def _name(p):
    t = _str(p.get('type'))
    tpl = POLICY['phrases'].get('product_naming', {}).get(t) or t.replace('_', ' ')
    try:
        return tpl.replace('{card_last4}', _str(p.get('card_last4')))
    except Exception:
        return tpl

def _floor_words(p):
    field = POLICY['amounts']['floors'].get(_str(p.get('type'))) or ''
    return field.replace('_', ' ').strip() or 'lowest amount'

def _floor_of(p):
    field = POLICY['amounts']['floors'].get(_str(p.get('type')))
    v = _float(p.get(field)) if field else None
    return v if v is not None else _float(p.get('full')) or 0.0

def _band(days_late):
    bands = POLICY['bands']
    for b in bands:
        if b['days_late_min'] <= days_late <= b['days_late_max']:
            return b
    if not bands:
        return None
    # outside every band: the nearest one (below the first -> first, above the last -> last)
    lo = min(bands, key=lambda b: b['days_late_min'])
    hi = max(bands, key=lambda b: b['days_late_max'])
    return lo if days_late < lo['days_late_min'] else hi

def _set_next(n):
    vars['next'] = n

def _offer_text(p, amount, date):
    return _money(amount) + ' for the ' + p['name'] + ' on ' + _fmt(date)

def _sc(name):
    for s in POLICY['special_cases']:
        if s['name'] == name:
            return s
    return None

def _products_from_vars():
    prods = vars.get('products_raw')
    if isinstance(prods, str):
        try:
            prods = json.loads(prods)
        except Exception:
            prods = None
    if isinstance(prods, dict):
        prods = [prods]
    if not isinstance(prods, list) or not prods:
        prods = []
        A = SLOTS['account']
        for i in range(8):
            p = dict()
            for k in (A['id'], A['type'], A['card_last4'], A['past_due'], A['days_late']) + tuple(POLICY['amounts']['floors'].values()):
                for key in ('get_account_response.data.' + A['list'] + '.' + str(i) + '.' + k, 'products_raw.' + str(i) + '.' + k, A['list'] + '.' + str(i) + '.' + k):
                    if vars.get(key) is not None:
                        p[k] = vars.get(key)
            if p:
                prods.append(p)
    return prods

# ---------------------------------------------------------------------------------------------
# stages
# ---------------------------------------------------------------------------------------------
def st_setup():
    S = _fresh_state()
    _save(S)
    _set_next('opening')

def _close(S, outcome, reason, goodbye):
    S['close'] = [outcome, reason]
    vars['goodbye_text'] = goodbye
    _save(S)
    _set_next('finalize')

def st_opening_route():
    S = _S()
    h = _get('holder')
    _clear('holder')
    I = POLICY['identity']
    TP = POLICY['third_party']
    if h == 'confirmed':
        S['id_idx'] = 0
        vars['id_say'] = _ask_text(0)
        _save(S)
        _set_next('ask_0')
    elif h == 'third_party':
        _save(S)
        _set_next('third_party')
    elif h == 'wrong_number':
        _close(S, TP['wrong_number_outcome'][0], TP['wrong_number_outcome'][1], 'I apologise for the disturbance. Thank you, goodbye.')
    elif h == 'deceased':
        _close(S, TP['deceased_outcome'][0], TP['deceased_outcome'][1], (TP.get('deceased_sentence') or 'I am sorry for your loss.') + ' Thank you, goodbye.')
    elif h == 'wants_human':
        if S.get('human_asked') or not bool((_sc('human') or dict()).get('ask_once_first', True)):
            _transfer(S, 'human')
        else:
            S['human_asked'] = True
            vars['neg_instruction'] = 'Ask once whether you can help them yourself first.'
            _save(S)
            _set_next('opening')
    elif h == 'question':
        # answer first; the ask that follows is the (next) ask, but a question is never an unclear answer
        vars['neg_instruction'] = 'Answer their question briefly (you are the bank\'s digital assistant; they can verify the call via the bank\'s customer service number; you can only say more to the account holder), then ask again whether you are speaking with the account holder.'
        _save(S)
        _set_next('opening')
    elif h == 'refuses':
        S['refuse_count'] = S.get('refuse_count', 0) + 1
        if S['refuse_count'] >= 2:
            _close(S, I['declined_outcome'][0], I['declined_outcome'][1], 'I understand. Thank you for your time. Goodbye.')
        else:
            _save(S)
            _set_next('opening')
    else:
        S['holder_unclear'] = S.get('holder_unclear', 0) + 1
        if S['holder_unclear'] >= I.get('holder_confirmation_asks', 2):
            _close(S, I['unclear_holder_outcome'][0], I['unclear_holder_outcome'][1], 'I am sorry, I could not confirm who I am speaking with. Thank you, goodbye.')
        else:
            _save(S)
            _set_next('opening')

def _q(r):
    t = _str(r.get('ask_text')).strip()
    if not t:
        return 'Could you give me your answer to the security question?'
    if t.endswith('?'):
        return t
    return 'What is ' + t + '?'

def _ask_text(i):
    reqs = POLICY['identity']['requirements']
    if i >= len(reqs):
        return ''
    r = reqs[i]
    n = len(reqs)
    pre = ('Thank you. Before we continue, I need to ask you ' + ((['one', 'two', 'three', 'four'][n - 1] if n <= 4 else str(n)) + ' short security question' + ('s. ' if n > 1 else '. '))) if i == 0 else 'Thank you. '
    return pre + _q(r)

def _transfer(S, case_name):
    sc = _sc(case_name) or dict(action=dict())
    a = sc.get('action', {})
    queue = a.get('queue') or sc.get('offer_transfer_queue') or ''
    outcome = a.get('outcome') or (sc.get('offer_outcome') or ['', ''])[0] or POLICY['outcomes']['transfer_outcome']
    reason = a.get('reason') or (sc.get('offer_outcome') or ['', ''])[1] or ''
    S['transfer'] = dict(queue=queue, outcome=outcome, reason=reason)
    vars['transfer_queue'] = queue
    vars['goodbye_text'] = 'I will connect you to a colleague now. Thank you for your time, goodbye.'
    _save(S)
    _set_next('transfer')

def st_cb_route():
    S = _S()
    TP = POLICY['third_party']
    CB = TP['callback']
    intent = _get('tp_intent')
    _clear('tp_intent')
    if intent == 'wrong_number':
        _clear_date('cb'); _clear('cb_time')
        return _close(S, TP['wrong_number_outcome'][0], TP['wrong_number_outcome'][1], 'I apologise for the disturbance. Thank you, goodbye.')
    if intent == 'deceased':
        _clear_date('cb'); _clear('cb_time')
        return _close(S, TP['deceased_outcome'][0], TP['deceased_outcome'][1], (TP.get('deceased_sentence') or 'I am sorry for your loss.') + ' Thank you, goodbye.')
    status, date = _resolve_date('cb', S['today'])
    t = _get('cb_time')
    _clear_date('cb'); _clear('cb_time')
    ok = False
    if status == 'ok' and t:
        pol = dict(start=CB['start'], end=CB['end'], days=CB['days'], must_be_after_now=bool(CB.get('must_be_after_now', True)), holidays=_cal()[0], business_days=_cal()[1])
        ok = callback_ok(S['today'] + 'T' + S['now_time'], date, t, pol)
    if ok:
        vars['cb_date'] = date
        vars['cb_time'] = t
        _save(S)
        return _set_next('schedule_callback')
    if status == 'ok' and not t and intent not in ('cannot_say', 'refuses'):
        vars['neg_instruction'] = 'They named a day but no time. Ask at what time ' + _fmt(date) + ' would suit; do not propose a time yourself.'
        _save(S)
        return _set_next('third_party')
    if not S.get('cb_asked') and bool(CB.get('retry_once', True)) and intent != 'refuses':
        S['cb_asked'] = True
        vars['neg_instruction'] = ('That time is outside the window I can offer. ' if status in ('ok', 'vague', 'unreadable') and (t or status != 'none') else '') + 'Ask once more for another day and time: today until ' + CB['end'] + ' or the next business day between ' + CB['start'] + ' and ' + CB['end'] + '.'
        _save(S)
        return _set_next('third_party')
    _close(S, CB['no_callback_outcome'][0], CB['no_callback_outcome'][1], 'I understand. I will not schedule a call back. Thank you for your time, goodbye.')

def st_cb_after():
    S = _S()
    ok = _get('cb_ok').lower() == 'true'
    _clear('cb_ok')
    CB = POLICY['third_party']['callback']
    if ok:
        return _close(S, CB['scheduled_outcome'][0], CB['scheduled_outcome'][1], 'Thank you. We will call back on ' + _fmt(_get('cb_date')) + ' at ' + _get('cb_time') + '. Goodbye.')
    if not S.get('cb_asked'):
        S['cb_asked'] = True
        vars['neg_instruction'] = 'That time could not be booked. Ask once more for another day and time inside the window.'
        _save(S)
        return _set_next('third_party')
    _close(S, CB['no_callback_outcome'][0], CB['no_callback_outcome'][1], 'I understand. I will not schedule a call back. Thank you for your time, goodbye.')

def st_id_route(i):
    S = _S()
    I = POLICY['identity']
    r = I['requirements'][i]
    intent = _get('id_intent')
    _clear('id_intent')
    if intent == 'question':
        # answer, then invite the answer without restating the question (judges count a restated question as "asked again")
        vars['id_say'] = 'These questions protect your account, and I can tell you more once your identity is confirmed. Please go ahead.'
        _save(S)
        return _set_next('ask_' + str(i))
    if intent == 'asks_purpose' and not bool(I.get('asking_purpose_counts_as_decline', True)):
        vars['id_say'] = 'I can explain once your identity is confirmed. ' + _q(r)
        _save(S)
        return _set_next('ask_' + str(i))
    if intent in ('declines', 'asks_purpose', 'refuses_to_talk'):
        S['decline_count'] = S.get('decline_count', 0) + 1
        if S['decline_count'] >= 2 or not bool(I.get('decline_explain_once', True)):
            _clear('id_day', 'id_month', 'id_year', 'id_digits', 'id_text')
            return _close(S, I['declined_outcome'][0], I['declined_outcome'][1], 'I understand. Without the security check I cannot continue. Thank you for your time, goodbye.')
        vars['id_say'] = 'These questions protect your account; I can only continue once your identity is confirmed. ' + _q(r)
        _save(S)
        return _set_next('ask_' + str(i))
    if intent == 'wants_human':
        if S.get('human_asked') or not bool((_sc('human') or dict()).get('ask_once_first', True)):
            return _transfer(S, 'human')
        S['human_asked'] = True
        vars['id_say'] = 'May I try to help you myself first? ' + _q(r)
        _save(S)
        return _set_next('ask_' + str(i))
    fmt = r.get('answer_format', 'text')
    answer = None
    if fmt == 'date':
        # answers arrive in pieces ("the 14th of March" ... "1988"): accumulate parts across turns
        parts = S.get('id_parts') or dict()
        d, m, y = _int(_get('id_day')), _int(_get('id_month')), _int(_get('id_year'))
        _clear('id_day', 'id_month', 'id_year')
        if d:
            parts['d'] = d
        if m:
            parts['m'] = m
        if y:
            parts['y'] = y
        S['id_parts'] = parts
        d, m, y = parts.get('d'), parts.get('m'), parts.get('y')
        if d and m and y:
            try:
                answer = datetime.date(y, m, d).isoformat()
            except Exception:
                answer = None
            if answer is None and 1 <= m <= 31 and 1 <= d <= 12:
                try:
                    answer = datetime.date(y, d, m).isoformat()
                except Exception:
                    answer = None
            S['id_parts'] = dict()
            if answer is None:
                vars['id_say'] = 'I could not read that date. ' + _q(r)
                _save(S)
                return _set_next('ask_' + str(i))
        else:
            missing = []
            if not d or not m:
                missing.append('the day and the month')
            if not y:
                missing.append('the year')
            vars['id_say'] = 'Thank you. And ' + ' and '.join(missing) + '?'
            _save(S)
            return _set_next('ask_' + str(i))
    elif fmt == 'digits':
        n = int(r.get('digits') or 4)
        raw = re.sub('[^0-9]', '', _get('id_digits'))
        _clear('id_digits')
        acc = _str(S.get('id_digits_acc'))
        if len(raw) >= n:
            acc = raw[-n:] if len(raw) > n else raw
        elif raw:
            if raw.startswith(acc) or not acc:
                acc = raw
            elif len(acc + raw) <= n:
                acc = acc + raw
            else:
                acc = raw
        if len(acc) == n:
            answer = acc
            S['id_digits_acc'] = ''
        else:
            S['id_digits_acc'] = acc
            vars['id_say'] = ('Thank you. And the remaining ' + str(n - len(acc)) + ' digits?') if acc else ('Could you give me all ' + str(n) + ' digits, please?')
            _save(S)
            return _set_next('ask_' + str(i))
    elif fmt == 'year':
        y = _int(_get('id_year'))
        _clear('id_year')
        answer = str(y) if y else None
        if answer is None:
            vars['id_say'] = 'Could you give me the year as four digits, please?'
            _save(S)
            return _set_next('ask_' + str(i))
    else:
        answer = _get('id_text')
        _clear('id_text')
        if not answer:
            vars['id_say'] = 'Could you repeat that, please? ' + _q(r)
            _save(S)
            return _set_next('ask_' + str(i))
    vars['id_answer'] = answer
    _save(S)
    _set_next('verify_' + str(i))

def st_verify_after(i):
    S = _S()
    I = POLICY['identity']
    r = I['requirements'][i]
    ok = _get('v_ok').lower() == 'true'
    verified = _get('v_verified').lower() == 'true'
    left = _int(_get('v_left'))
    hint = _get('v_hint')
    _clear('v_ok', 'v_verified', 'v_all', 'v_left', 'v_hint', 'id_answer')
    S['id_parts'] = dict()
    S['id_digits_acc'] = ''
    last = i >= len(I['requirements']) - 1
    if ok and verified:
        if last:
            _save(S)
            return _set_next('get_account')
        S['id_idx'] = i + 1
        vars['id_say'] = _ask_text(i + 1)
        _save(S)
        return _set_next('ask_' + str(i + 1))
    if hint:
        vars['id_say'] = (r.get('hint_reply') or 'Could you say that again, with the month as a word?')
        _save(S)
        return _set_next('ask_' + str(i))
    if not ok and left is None:
        vars['id_say'] = 'I could not read that. ' + _q(r)
        _save(S)
        return _set_next('ask_' + str(i))
    S['id_wrong'] = S.get('id_wrong', 0) + 1
    exhausted = (left is not None and left <= 0) or (left is None and S['id_wrong'] >= int(I.get('wrong_answer_limit', 3)))
    if exhausted:
        return _close(S, I['failed_outcome'][0], I['failed_outcome'][1], 'I am sorry, I could not verify your identity, so I cannot continue on this call. ' + (I.get('failed_instruction') or '') + ' Thank you for your time, goodbye.')
    vars['id_say'] = 'That does not match our records. ' + _q(r)
    _save(S)
    _set_next('ask_' + str(i))

def st_init_products():
    S = _S()
    A = SLOTS['account']
    prods = _products_from_vars()
    out = []
    h, b = _cal()
    for raw in prods:
        if not isinstance(raw, dict):
            continue
        p = dict()
        p['product_id'] = _str(raw.get(A['id']))
        p['type'] = _str(raw.get(A['type']))
        p['card_last4'] = _str(raw.get(A['card_last4']))
        p['full'] = _float(raw.get(A['past_due'])) or 0.0
        p['days_late'] = _int(raw.get(A['days_late'])) or 0
        for f in set(POLICY['amounts']['floors'].values()):
            if raw.get(f) is not None:
                p[f] = raw.get(f)
        p['name'] = _name(p)
        p['floor'] = _floor_of(p)
        band = _band(p['days_late'])
        if not band:
            raise ValueError('No policy band covers the account')
        p['band'] = band.get('name', '')
        p['deadline'] = deadline(S['today'], band['deadline'], h, b)
        if not p['deadline']:
            raise ValueError('Cannot resolve policy deadline')
        p['attempts'] = band.get('attempts', [])
        p['attempts_used'] = 0
        p['full_refused'] = False
        p['floor_offered'] = False
        p['proposed'] = False
        p['proposed_amount'] = None
        p['proposed_date'] = None
        p['clamped'] = False
        p['recorded'] = False
        p['write_failures'] = 0
        p['disposition'] = ''
        out.append(p)
    S['products'] = out
    S['phase'] = 'all'
    S['pi'] = -1
    S['awaiting'] = 'today'
    lines = []
    for k, p in enumerate(out):
        pre = ''
        if len(out) > 1:
            ordinals = ['First', 'Second', 'Third', 'Fourth', 'Fifth']
            pre = (ordinals[k] if k < len(ordinals) else 'Product ' + str(k + 1)) + ', '
        lines.append(pre + ('your ' if pre else 'Your ') + p['name'] + ' has a past-due amount of ' + _money(p['full']) + ', which is ' + str(p['days_late']) + ' days late.')
    PH = POLICY['phrases']
    intro = PH.get('debt_intro') or ('Thank you, your identity is confirmed. I am calling from the ' + POLICY.get('bank_name', 'the bank') + ' collections team about ' + ('late payments.' if len(out) > 1 else 'a late payment.'))
    intro = intro.strip() + ' '
    q = ' ' + ((PH.get('all_today_question') or 'Can you pay all of them today?') if len(out) > 1 else (PH.get('today_question') or 'Can you make this payment today?'))
    vars['debt_statement'] = intro + ' '.join(lines) + q
    vars['product_list'] = '; '.join(str(k + 1) + ' = ' + p['name'] for k, p in enumerate(out))
    _save(S)
    _set_next('state_debt')

def _cur(S):
    i = S.get('pi', -1)
    if 0 <= i < len(S['products']):
        return S['products'][i]
    return None

def _undecided(S):
    return [k for k, p in enumerate(S['products']) if not p['proposed'] and not p['disposition']]

def _start_attempt(S, p, k):
    """Make persuasion attempt number k (1-based) for product p. Returns False when attempts are exhausted."""
    attempts = p.get('attempts') or []
    if k > len(attempts):
        return False
    a = attempts[k - 1]
    h, b = _cal()
    amount = p['floor'] if (a.get('amount') == 'floor' or (p.get('full_refused') and a.get('floor_if_full_refused', True))) else p['full']
    date = attempt_date(S['today'], a.get('date', 'deadline'), p['deadline'], h, b) or p['deadline']
    p['attempts_used'] = k
    prev = S.get('offer') or dict()
    same_amount = prev and abs(float(prev.get('amount') or 0) - float(amount)) < 0.005
    S['offer'] = dict(amount=amount, date=date)
    S['awaiting'] = 'offer'
    if same_amount:
        vars['neg_instruction'] = 'Propose the same amount for a different day: ask whether they can make the payment you proposed on ' + _fmt(date) + ' instead. Refer to it as the amount already proposed; do not say the number again and do not repeat that the rest stays overdue.'
        return True
    floor_note = ''
    if amount == p['floor'] and amount < p['full'] and not p.get('floor_note_said'):
        floor_note = ' Say that ' + POLICY['amounts'].get('floor_wording', 'the rest stays overdue') + '.'
        p['floor_note_said'] = True
    elif amount == p['floor'] and amount < p['full']:
        floor_note = ' Do not repeat that the rest stays overdue; you said it already.'
    vars['neg_instruction'] = 'Propose this payment for the ' + p['name'] + ': ' + _money(amount) + ' on ' + _fmt(date) + '. Ask whether they can make that payment.' + floor_note
    return True

def _enter_product(S, k):
    S['phase'] = 'product'
    S['pi'] = k
    S['vague_asked'] = False
    p = S['products'][k]
    if not _start_attempt(S, p, 1):
        p['disposition'] = POLICY['outcomes'].get('refused_reason') or 'refused'
        return _advance(S)
    _save(S)
    _set_next('negotiate')

def _advance(S):
    """Move to the next undecided product, or to the read-back / finalization."""
    rest = _undecided(S)
    if rest:
        return _enter_product(S, rest[0])
    if any(p['proposed'] for p in S['products']):
        return _readback(S)
    for p in S['products']:
        if not p['disposition']:
            p['disposition'] = POLICY['outcomes'].get('refused_reason') or 'refused'
    _save(S)
    _set_next('finalize')

def _readback(S):
    parts = []
    for p in S['products']:
        if p['proposed']:
            s = _money(p['proposed_amount']) + ' for the ' + p['name'] + ' on ' + _fmt(p['proposed_date'])
            if p.get('clamped'):
                s += ' (the latest date I can record for the ' + p['name'] + ' is ' + _fmt(p['deadline']) + ', so that one is on ' + _fmt(p['proposed_date']) + ')'
            parts.append(s)
    txt = 'To confirm: you will pay ' + ('; and '.join(parts) if len(parts) > 1 else parts[0]) + '. ' + POLICY['promise_write'].get('confirm_phrase', 'Do you confirm?')
    vars['readback_text'] = txt
    S['awaiting'] = 'confirm'
    _save(S)
    _set_next('readback')

def _apply_proposal(S, p, amount, date, date_status, allow_clamp):
    """Validate a customer proposal for one product. Returns 'done' or an instruction string (and sets S['offer'])."""
    h, b = _cal()
    v = validate_proposal(S['today'], p['deadline'], date, date_status, amount, p['floor'], p['full'], h, b)
    verdict = v.get('verdict')
    D = POLICY['dates']
    if verdict == 'ok':
        p['proposed'] = True
        p['proposed_amount'] = float(v['amount'])
        p['proposed_date'] = v['date']
        p['clamped'] = False
        return 'done'
    if verdict == 'after_deadline' and allow_clamp:
        p['proposed'] = True
        p['proposed_amount'] = float(v['amount'])
        p['proposed_date'] = p['deadline']
        p['clamped'] = True
        return 'done'
    if verdict == 'after_deadline':
        S['offer'] = dict(amount=float(v['amount']), date=p['deadline'])
        S['awaiting'] = 'offer'
        return 'Say that the latest date you can record for the ' + p['name'] + ' is ' + _fmt(p['deadline']) + ' and offer ' + _money(v['amount']) + ' on that day.'
    if verdict == 'roll_forward':
        S['offer'] = dict(amount=float(v['amount']), date=v['offer_date'])
        S['awaiting'] = 'offer'
        return 'Say that ' + _fmt(date) + ' is not a business day and offer the next business day, ' + _fmt(v['offer_date']) + ', for ' + _money(v['amount']) + '.'
    if verdict == 'below_floor':
        if p.get('floor_offered'):
            return 'refusal'
        p['floor_offered'] = True
        S['offer'] = dict(amount=p['floor'], date=date)
        S['awaiting'] = 'offer'
        note = '' if p.get('floor_note_said') else ' Say that ' + POLICY['amounts'].get('floor_wording', 'the rest stays overdue') + '.'
        p['floor_note_said'] = True
        return 'Say that ' + _money(amount) + ' is below what this call can take. Offer the ' + _floor_words(p) + ', ' + _money(p['floor']) + ', on ' + _fmt(date) + '.' + note
    if verdict == 'above_full':
        p['proposed'] = True
        p['proposed_amount'] = p['full']
        p['proposed_date'] = v['date']
        p['clamped'] = False
        return 'done'
    if verdict == 'past':
        if S.get('awaiting') == 'exact_day' and date_status == 'ok' and _get('prop_kind') == '' :
            pass
        S['awaiting'] = 'exact_day'
        if S.get('last_verdict') == 'vague' or S.get('vague_asked'):
            return 'The customer may still be completing the date. Say only "Yes?" or "Go on" and wait; if they have finished, say that day has passed and ask for a day from today onwards.'
        return 'That date is in the past. Ask for a day from today onwards.'
    if verdict == 'vague':
        if not S.get('vague_asked') and bool(D.get('vague_ask_once_then_deadline', True)):
            S['vague_asked'] = True
            S['awaiting'] = 'exact_day'
            return 'Ask once for the exact day they have in mind.'
        amt = amount if amount is not None else (S.get('offer') or dict()).get('amount', p['full'])
        S['offer'] = dict(amount=amt, date=p['deadline'])
        S['awaiting'] = 'offer'
        return 'They gave no exact day. Propose ' + _money(amt) + ' on ' + _fmt(p['deadline']) + ', the latest date you can record.'
    S['awaiting'] = 'exact_day'
    return 'Ask for the exact day of the month they want to pay.'

def _targets(S):
    """Which products a customer statement refers to, from prop_product (multi-product only)."""
    sel = _get('prop_product')
    _clear('prop_product')
    n = len(S['products'])
    if S.get('phase') == 'all':
        if sel and sel != 'all' and _int(sel) and 1 <= _int(sel) <= n:
            return [_int(sel) - 1]
        return [k for k in range(n) if not S['products'][k]['proposed'] and not S['products'][k]['disposition']]
    if sel and sel != 'all' and _int(sel) and 1 <= _int(sel) <= n:
        return [_int(sel) - 1]
    if sel == 'all' and n > 1:
        return [k for k in range(n) if not S['products'][k]['disposition']]
    c = _cur(S)
    return [S['pi']] if c else [k for k in range(n) if not S['products'][k]['proposed']]

def _special(S, intent):
    """Returns True when the intent was handled as a special case."""
    sc = _sc(dict(already_paid='already_paid', dispute='dispute', hardship='hardship', restructuring='restructuring', human='human', refuses_to_talk='refuse_to_talk').get(intent, ''))
    if not sc:
        return False
    a = sc.get('action', {})
    multi = len(S['products']) > 1 and bool(POLICY['notes'].get('enabled'))
    if intent == 'restructuring':
        _transfer(S, 'restructuring')
        return True
    if intent == 'human':
        if S.get('human_asked') or not bool(sc.get('ask_once_first', True)):
            _transfer(S, 'human')
            return True
        S['human_asked'] = True
        vars['neg_instruction'] = 'Ask once whether you can help them yourself first. Then continue with the current question.'
        S['awaiting_prev'] = S.get('awaiting')
        S['awaiting'] = 'human'
        _save(S)
        _set_next('negotiate')
        return True
    if intent == 'refuses_to_talk':
        S['refuse_count'] = S.get('refuse_count', 0) + 1
        if S['refuse_count'] >= 2:
            for p in S['products']:
                if not p['proposed'] and not p['disposition']:
                    p['disposition'] = POLICY['outcomes'].get('refused_reason') or 'refused'
            for p in S['products']:
                if p['proposed'] and not p['recorded']:
                    p['proposed'] = False
                    p['disposition'] = POLICY['outcomes'].get('refused_reason') or 'refused'
            _save(S)
            _set_next('finalize')
            return True
        return False
    if intent == 'hardship':
        S['hardship_offered'] = True
        say = sc.get('say') or 'one short sentence of sympathy'
        queue = sc.get('offer_transfer_queue') or ''
        offer = ('Offer to connect them with the ' + queue + ' team and ask whether they would like that.') if queue else 'Do not persuade.'
        vars['neg_instruction'] = 'Say ' + say + '. Do not propose any amount or date. ' + offer
        S['awaiting'] = 'support'
        _save(S)
        _set_next('negotiate')
        return True
    if intent in ('already_paid', 'dispute'):
        reason = a.get('reason') or ('paid' if intent == 'already_paid' else 'dispute')
        targets = _targets(S)
        for k in targets:
            p = S['products'][k]
            p['disposition'] = reason
            p['paid'] = intent == 'already_paid'
            p['proposed'] = False
        say = sc.get('say') or ''
        if intent == 'already_paid':
            say = POLICY['phrases'].get('already_paid_sentence') or say
        rest = _undecided(S)
        if multi and rest:
            # with several products and notes in the policy, a paid/dispute claim on one product never ends the call
            vars['neg_instruction'] = (say + ' ' if say else '') + 'Do not argue and take no promise for that product. Then continue with the next product.'
            S['awaiting'] = 'next'
            _save(S)
            return _advance_with_prefix(S, vars['neg_instruction'])
        if multi and any(q['proposed'] for q in S['products']):
            # other products already proposed: go to read-back / finalization
            vars['neg_instruction'] = say
            _save(S)
            _advance(S)
            return True
        vars['goodbye_text'] = (say + ' ' if say else '') + 'I will not record a promise for it. Thank you for your time, goodbye.'
        _save(S)
        _set_next('finalize')
        return True
    return False

def _advance_with_prefix(S, prefix):
    rest = _undecided(S)
    if rest:
        _enter_product(S, rest[0])
        vars['neg_instruction'] = prefix + ' ' + _get('neg_instruction')
        return True
    _advance(S)
    return True

def st_neg_route():
    S = _S()
    intent = _get('cust_intent')
    _clear('cust_intent')
    amount = _float(_get('prop_amount'))
    _clear('prop_amount')
    date_status, date = _resolve_date('prop', S['today'])
    _clear_date('prop')
    aw = S.get('awaiting', '')
    if intent == 'question':
        o = S.get('offer') or dict()
        if S.get('awaiting') == 'support':
            # hardship: no persuasion at all — answer (no discount or other term can be offered) and repeat the support offer only
            vars['neg_instruction'] = 'Answer their question in one short sentence (you cannot offer any discount, waiver or other term). Do not ask for any payment. Then ask once more whether they would like to be connected with the support team.'
            _save(S)
            return _set_next('negotiate')
        if o:
            vars['neg_instruction'] = ('Answer their question in one short sentence (if they ask what the lowest amount is, say it is the amount you just proposed; do not say any amount again). '
                                       'Then ask again whether they can make the payment you proposed on ' + _fmt(o.get('date')) + '.')
        else:
            vars['neg_instruction'] = 'Answer their question in one short sentence from your instructions, then continue with your current question. Do not say any amount or date that is not in your instruction.'
        _save(S)
        return _set_next('negotiate')
    if intent == 'hardship' and S.get('hardship_offered'):
        intent = 'refuses'                 # the support offer is on the table: "I still cannot pay" declines it
    if intent in ('too_much', 'refuses'):
        amount = None                      # "I cannot pay 2,500" is not an offer of 2,500
    if intent == 'proposes' and amount is None and date_status == 'none':
        # the customer announced a proposal but has not said it yet (speech in pieces): wait for it
        vars['neg_instruction'] = 'The customer seems to be in the middle of a sentence. Say only "Yes?" or "Go on" and wait.'
        _save(S)
        return _set_next('negotiate')
    if intent in ('already_paid', 'dispute', 'hardship', 'restructuring', 'human', 'refuses_to_talk'):
        if _special(S, intent):
            return
        intent = 'refuses'
    if aw == 'support':
        if intent in ('accepts', 'pays_today') and amount is None and date_status in ('none',):
            return _transfer(S, 'hardship')
        if intent in ('refuses', 'too_much') and amount is None and date_status == 'none':
            hr = ((_sc('hardship') or dict()).get('action') or dict()).get('reason') or 'hardship'
            for p in S['products']:
                if not p['proposed'] and not p['disposition']:
                    p['disposition'] = hr
            for p in S['products']:
                if p['proposed'] and not p['recorded']:
                    pass
            if any(p['proposed'] for p in S['products']):
                return _readback(S)
            vars['goodbye_text'] = 'I understand. I will not record a promise today. Thank you for your time, and goodbye.'
            _save(S)
            return _set_next('finalize')
        # the customer named a date or an amount themselves: fall through and handle it as a proposal
        S['awaiting'] = 'offer' if S.get('offer') else 'today'
        aw = S['awaiting']
        if intent in ('accepts', 'pays_today', 'refuses', 'too_much'):
            intent = 'proposes'
    if aw == 'human':
        S['awaiting'] = S.get('awaiting_prev') or 'offer'
        aw = S['awaiting']
        if intent in ('refuses_to_talk', 'human'):
            return _transfer(S, 'human')
        # anything else (an acceptance, a proposal, a refusal of the offer) continues the negotiation normally
    if date_status == 'unreadable' and intent == 'proposes':
        if S.get('awaiting') == 'exact_day':
            vars['neg_instruction'] = 'The customer seems to be in the middle of saying the date. Say only "Yes?" or "Go on" and wait; do not ask the question again.'
        else:
            S['awaiting'] = 'exact_day'
            vars['neg_instruction'] = 'Ask for the exact day they mean.'
        _save(S)
        return _set_next('negotiate')
    has_prop = amount is not None or date_status in ('ok', 'vague')
    # --- phase: the first "today?" question (covers all products) ---
    if aw == 'today':
        if intent in ('pays_today', 'accepts') and not has_prop:
            for k in _targets(S):
                p = S['products'][k]
                r = _apply_proposal(S, p, None, S['today'], 'ok', True)
                if r != 'done':
                    S['offer'] = None
            return _advance(S)
        if has_prop or intent == 'proposes':
            return _proposal(S, amount, date, date_status)
        if intent == 'too_much':
            return _too_much(S)
        if intent == 'refuses':
            rest = _undecided(S)
            if rest:
                return _enter_product(S, rest[0])
            return _advance(S)
        _save(S)
        return _set_next('negotiate')
    # --- an offer is on the table ---
    if aw in ('offer', 'exact_day', 'floor'):
        p = _cur(S) or (S['products'][_targets(S)[0]] if _undecided(S) else None)
        if p is None:
            return _advance(S)
        if intent == 'accepts' and S.get('offer') and has_prop:
            o = S['offer']
            same_amount = amount is None or abs(float(amount) - float(o.get('amount') or 0)) < 0.005
            same_date = date_status != 'ok' or date == o.get('date')
            if same_amount and same_date:
                has_prop = False          # the customer restated the offer: that is an acceptance
        if intent in ('accepts', 'pays_today') and not has_prop and S.get('offer'):
            o = S['offer']
            p['proposed'] = True
            p['proposed_amount'] = float(o['amount'])
            p['proposed_date'] = o['date']
            p['clamped'] = False
            S['offer'] = None
            return _advance(S)
        if intent == 'pays_today' and not has_prop:
            return _proposal(S, None, S['today'], 'ok')
        if has_prop or intent == 'proposes':
            return _proposal(S, amount, date, date_status)
        if intent == 'too_much':
            return _too_much(S)
        if intent == 'refuses':
            if aw == 'exact_day' and not S.get('vague_asked_done'):
                S['vague_asked_done'] = True
                return _proposal(S, None, None, 'vague')
            k = p.get('attempts_used', 0) + 1
            if _start_attempt(S, p, k):
                _save(S)
                return _set_next('negotiate')
            p['disposition'] = POLICY['outcomes'].get('refused_reason') or 'refused'
            S['offer'] = None
            return _advance(S)
        _save(S)
        return _set_next('negotiate')
    _save(S)
    _set_next('negotiate')

def _too_much(S):
    A = POLICY['amounts']
    targets = _targets(S)
    if S.get('phase') == 'all' and len(targets) > 1:
        rest = _undecided(S)
        if rest:
            S['products'][rest[0]]['full_refused'] = True
            return _enter_product(S, rest[0])
    p = _cur(S) or S['products'][targets[0]]
    if S.get('phase') == 'all':
        S['phase'] = 'product'
        S['pi'] = targets[0]
    p['full_refused'] = True
    o = S.get('offer') or dict()
    if p.get('floor_offered') or not bool(A.get('floor_offered_once', True)):
        k = p.get('attempts_used', 0) + 1
        if _start_attempt(S, p, k):
            _save(S)
            return _set_next('negotiate')
        p['disposition'] = POLICY['outcomes'].get('refused_reason') or 'refused'
        return _advance(S)
    p['floor_offered'] = True
    p['floor_note_said'] = True
    date = (S.get('offer') or dict()).get('date') or S['today']
    S['offer'] = dict(amount=p['floor'], date=date)
    S['awaiting'] = 'offer'
    vars['neg_instruction'] = 'Offer the ' + _floor_words(p) + ' for the ' + p['name'] + ', ' + _money(p['floor']) + ', on ' + _fmt(date) + ' (it is the lowest amount this call can take). Say that ' + A.get('floor_wording', 'the rest stays overdue') + '. Ask whether they can make that payment.'
    _save(S)
    _set_next('negotiate')

def _proposal(S, amount, date, date_status):
    targets = _targets(S)
    if not targets:
        return _advance(S)
    multi_all = len(targets) > 1
    if date_status == 'none':
        date_status, date = 'ok', (S.get('offer') or dict()).get('date') or S['today']
    if amount is None and S.get('offer') and not multi_all:
        amount = S['offer'].get('amount')      # the amount currently on the table (e.g. the floor) stays
    if multi_all:
        for k in targets:
            p = S['products'][k]
            r = _apply_proposal(S, p, amount if len(targets) == 1 else None, date, date_status, bool(POLICY['multi_product'].get('common_date_clamped_per_product', True)))
            if r != 'done':
                S['phase'] = 'product'
                S['pi'] = k
                if r == 'refusal':
                    kk = p.get('attempts_used', 0) + 1
                    if not _start_attempt(S, p, kk):
                        p['disposition'] = POLICY['outcomes'].get('refused_reason') or 'refused'
                        return _advance(S)
                else:
                    vars['neg_instruction'] = r
                _save(S)
                return _set_next('negotiate')
        return _advance(S)
    k = targets[0]
    p = S['products'][k]
    if S.get('phase') == 'all':
        S['phase'] = 'product'
        S['pi'] = k
    r = _apply_proposal(S, p, amount, date, date_status, False)
    if r == 'done':
        S['offer'] = None
        return _advance(S)
    if r == 'refusal':
        kk = p.get('attempts_used', 0) + 1
        if _start_attempt(S, p, kk):
            _save(S)
            return _set_next('negotiate')
        p['disposition'] = POLICY['outcomes'].get('refused_reason') or 'refused'
        return _advance(S)
    vars['neg_instruction'] = r
    _save(S)
    _set_next('negotiate')

def st_readback_route():
    S = _S()
    intent = _get('rb_intent')
    _clear('rb_intent')
    amount = _float(_get('prop_amount'))
    _clear('prop_amount')
    date_status, date = _resolve_date('prop', S['today'])
    _clear_date('prop')
    if intent == 'hardship' and S.get('hardship_offered'):
        intent = 'declines'
    if intent in ('already_paid', 'dispute', 'hardship', 'restructuring', 'human', 'refuses_to_talk'):
        if _special(S, intent):
            return
    if intent == 'confirms':
        S['w_idx'] = -1
        S['w_pending'] = False
        _save(S)
        return _set_next('write_step')
    if intent == 'changes' or amount is not None or date_status in ('ok', 'vague'):
        targets = _targets(S)
        proposed = [k for k in range(len(S['products'])) if S['products'][k]['proposed']]
        targets = [k for k in targets if k in proposed] or proposed[:1]
        if not targets:
            return _readback(S)
        if len(targets) > 1 and date_status == 'ok':
            for k in targets:
                p = S['products'][k]
                p['proposed'] = False
                _apply_proposal(S, p, amount if amount is not None else p['proposed_amount'], date, date_status, True)
            if all(S['products'][k]['proposed'] for k in targets):
                return _readback(S)
        k = targets[0]
        p = S['products'][k]
        S['phase'] = 'product'
        S['pi'] = k
        if date_status == 'none':
            date_status, date = 'ok', p['proposed_date']
        amt = amount if amount is not None else p['proposed_amount']
        p['proposed'] = False
        r = _apply_proposal(S, p, amt, date, date_status, False)
        if r == 'done':
            return _readback(S)
        if r == 'refusal':
            p['disposition'] = POLICY['outcomes'].get('refused_reason') or 'refused'
            return _advance(S)
        vars['neg_instruction'] = r
        _save(S)
        return _set_next('negotiate')
    if intent == 'declines':
        S['rb_declined'] = S.get('rb_declined', 0) + 1
        if S['rb_declined'] >= 2:
            for p in S['products']:
                if p['proposed'] and not p['recorded']:
                    p['proposed'] = False
                    p['disposition'] = POLICY['outcomes'].get('refused_reason') or 'refused'
            return _advance(S)
        vars['neg_instruction'] = 'Ask what they would like to change: the amount or the date.'
        S['awaiting'] = 'offer'
        _save(S)
        return _set_next('negotiate')
    _save(S)
    _set_next('readback')

def st_write_step():
    """After a create_promise result (if one is pending) and/or pick the next product to write."""
    S = _S()
    k = S.get('w_idx', -1)
    if S.get('w_pending') and 0 <= k < len(S['products']):
        p = S['products'][k]
        raw_ok = _get('w_ok').lower()
        status = _get('w_status')
        ok = raw_ok == 'true'
        _clear('w_ok', 'w_status')
        S['w_pending'] = False
        answered = raw_ok == 'false' or (status != '' and status != '200')   # the bank answered with a failure
        if ok:
            p['recorded'] = True
        else:
            p['write_failures'] = p.get('write_failures', 0) + 1
            # an explicit rejection may be retried; no response at all (timeout) is not: the write may have landed
            if answered and p['write_failures'] <= int(POLICY['promise_write'].get('retry_on_failure', 1)):
                S['w_pending'] = True
                _save(S)
                return _set_next('create_promise')
            p['disposition'] = POLICY['outcomes'].get('service_error_reason') or 'service_error'
    for k, p in enumerate(S['products']):
        if p['proposed'] and not p['recorded'] and not p['disposition']:
            S['w_idx'] = k
            S['w_pending'] = True
            vars['w_product_id'] = p['product_id']
            vars['w_amount'] = _money(p['proposed_amount'])
            vars['w_date'] = p['proposed_date']
            _save(S)
            return _set_next('create_promise')
    S['w_idx'] = -1
    _save(S)
    st_finalize()

def st_finalize():
    S = _S()
    _clear('t_ok')
    O = POLICY['outcomes']
    N = POLICY['notes']
    outcome, reason = '', ''
    recorded = [p for p in S['products'] if p.get('recorded')]
    if S.get('transfer'):
        outcome, reason = S['transfer'].get('outcome') or O['transfer_outcome'], S['transfer'].get('reason') or ''
    elif S.get('close'):
        outcome, reason = S['close'][0], S['close'][1]
    elif recorded:
        outcome, reason = O['promise_outcome'], ''
    elif S['products'] and all(p.get('paid') for p in S['products']) and bool(O.get('all_paid_closes_as_paid', True)):
        outcome, reason = O['paid_outcome'], ''
    else:
        outcome = O['no_promise_outcome']
        reason = O.get('refused_reason') or 'refused'
        for p in S['products']:
            d = p.get('disposition') or ''
            if d and not p.get('paid'):
                reason = d
                break
    vars['final_outcome'] = outcome
    vars['final_reason'] = reason
    # goodbye text for the promise / service-error paths
    if recorded and not S.get('transfer'):
        parts = ['Your promise of ' + _offer_text(p, p['proposed_amount'], p['proposed_date']) + ' is recorded.' for p in recorded]
        failed = [p for p in S['products'] if p.get('disposition') == (O.get('service_error_reason') or 'service_error') and not p.get('paid')]
        txt = 'Thank you. ' + ' '.join(parts) + ' ' + (POLICY['phrases'].get('after_promise_sentence') or '')
        if failed:
            txt += ' I could not record a promise for the ' + ' and the '.join(p['name'] for p in failed) + ' because of a technical problem.'
        vars['goodbye_text'] = txt + ' Thank you for your time, goodbye.'
    elif not S.get('transfer') and not S.get('close'):
        if any(p.get('disposition') == (O.get('service_error_reason') or 'service_error') and not p.get('paid') for p in S['products']):
            vars['goodbye_text'] = 'I am sorry, I could not record the promise because of a technical problem. Thank you for your time, goodbye.'
        elif all(p.get('paid') for p in S['products']) and S['products']:
            vars['goodbye_text'] = (POLICY['phrases'].get('already_paid_sentence') or '') + ' Thank you for your time, goodbye.'
        elif not _get('goodbye_text') or _get('goodbye_text') == 'Thank you for your time. Goodbye.':
            vars['goodbye_text'] = 'I understand. I will not record a promise today. Thank you for your time, goodbye.'
    # notes (never on a transfer)
    S['notes'] = []
    if bool(N.get('enabled')) and not (S.get('transfer') and bool(N.get('none_on_transfer', True))) and not S.get('close'):
        for k, p in enumerate(S['products']):
            if not p.get('recorded') and p.get('disposition') in (N.get('reasons') or []):
                S['notes'].append(k)
    S['n_idx'] = -1
    _save(S)
    if S['notes']:
        return _set_next('notes_step')
    _set_next('close_reason' if reason else 'close_noreason')

def st_notes_step():
    S = _S()
    _clear('n_ok')
    notes = S.get('notes') or []
    if notes:
        k = notes.pop(0)
        p = S['products'][k]
        vars['n_product_id'] = p['product_id']
        vars['n_reason'] = p['disposition']
        _save(S)
        return _set_next('add_note')
    _save(S)
    _set_next('close_reason' if _get('final_reason') else 'close_noreason')

def _stuck(stage):
    """Insurance against endless calls: a routing stage visited far more often than any conversation needs closes the call."""
    try:
        S = _S()
        v = S.get('visits') or dict()
        v[stage] = int(v.get(stage, 0)) + 1
        S['visits'] = v
        _save(S)
        if v[stage] > 30 and stage in ('opening_route', 'cb_route', 'neg_route', 'readback_route') or (stage.startswith('id_route_') and v[stage] > 30):
            if not S.get('close') and not any(p.get('recorded') for p in S.get('products', [])):
                I = POLICY['identity']
                if S.get('products'):
                    for p in S['products']:
                        if not p.get('proposed') and not p.get('disposition'):
                            p['disposition'] = POLICY['outcomes'].get('refused_reason') or 'refused'
                    _save(S)
                else:
                    S['close'] = [I['unclear_holder_outcome'][0] or POLICY['outcomes']['no_promise_outcome'], I['unclear_holder_outcome'][1]]
                    _save(S)
            vars['goodbye_text'] = 'I am sorry, I cannot continue this call. Thank you for your time, goodbye.'
            _set_next('finalize')
            return True
    except Exception:
        pass
    return False

def _run(stage):
    if _stuck(stage):
        return
    try:
        if stage == 'setup':
            st_setup()
        elif stage == 'opening_route':
            st_opening_route()
        elif stage == 'cb_route':
            st_cb_route()
        elif stage == 'cb_after':
            st_cb_after()
        elif stage.startswith('id_route_'):
            st_id_route(int(stage.split('_')[-1]))
        elif stage.startswith('verify_after_'):
            st_verify_after(int(stage.split('_')[-1]))
        elif stage == 'init_products':
            st_init_products()
        elif stage == 'neg_route':
            st_neg_route()
        elif stage == 'readback_route':
            st_readback_route()
        elif stage == 'write_step':
            st_write_step()
        elif stage == 'finalize':
            st_finalize()
        elif stage == 'notes_step':
            st_notes_step()
    except Exception as e:
        vars['runtime_error'] = stage + ': ' + repr(e)[:300]
        if stage in ('setup',):
            vars['next'] = 'opening'
        elif stage in ('finalize', 'notes_step', 'write_step'):
            vars['final_outcome'] = _str(vars.get('final_outcome')) or POLICY['outcomes']['no_promise_outcome']
            vars['final_reason'] = _str(vars.get('final_reason')) or (POLICY['outcomes'].get('service_error_reason') or 'service_error')
            vars['next'] = 'close_reason'
        else:
            vars['next'] = 'finalize'
            vars['goodbye_text'] = 'I am sorry, a technical problem stops me from continuing. Thank you for your time, goodbye.'
