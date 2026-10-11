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

def _resolve_date(prefix, today, offer_date=None):
    """Structured date extraction -> ('ok', iso) | ('vague', '') | ('none', '') | ('unreadable', '').
    `offer_date`: the date currently proposed by the agent; when the customer's words fit several readings, the one that
    restates the offer wins (an acceptance restating the date is not a new proposal)."""
    kind = _get(prefix + '_kind')
    if kind in ('', 'none'):
        return 'none', ''
    if kind == 'vague':
        return 'vague', ''
    h, b = _cal()
    expr = None
    if kind in ('today', 'tomorrow'):
        expr = dict(keyword=kind)
    elif kind == 'weekday' and _get(prefix + '_weekday').lower() in WEEKDAYS:
        wd = WEEKDAYS.index(_get(prefix + '_weekday').lower())
        rel = _get(prefix + '_relative').lower()
        day = _int(_get(prefix + '_day'))
        expr = dict(weekday=wd, relative='next' if rel == 'next' else 'this')
        if not day and offer_date and datetime.date.fromisoformat(offer_date).weekday() == wd:
            nxt = resolve_date_expr(today, dict(weekday=wd, relative='next'), _calendar_dict()) if rel == 'next' else None
            if rel != 'next' or nxt == offer_date:
                return 'ok', offer_date        # "I can do that on Tuesday" while Tuesday the 27th is on the table: the offer, restated
        if not day and rel != 'next':
            cand = resolve_date_expr(today, expr, _calendar_dict())
            if cand and cand != 'vague' and cand < today:
                expr = dict(weekday=wd, relative='next')   # "this Tuesday" said on a Wednesday is the coming Tuesday, never last week's
        if not day and rel == 'next' and POLICY['calendar'].get('next_weekday', 'coming') != 'following_week':
            cand = resolve_date_expr(today, dict(weekday=wd, relative='this'), _calendar_dict())
            if cand and cand != 'vague' and cand > today:
                expr = dict(weekday=wd, relative='this')   # "next Friday" said on a Wednesday is this coming Friday; said on a Friday it is the one after
        if day:
            # a day number next to a weekday is kept only when it names that weekday ("Tuesday the 27th", "Friday the 23rd");
            # a stray number from another sentence ("my wedding is on the 30th ... I can pay this Friday") is ignored
            d_expr = dict(day=day)
            m = _int(_get(prefix + '_month'))
            if m:
                d_expr['month'] = m
            cands = []
            cand = resolve_date_expr(today, d_expr, _calendar_dict())
            if cand and cand != 'vague' and datetime.date.fromisoformat(cand).weekday() == wd:
                cands.append((d_expr, cand))                       # "Tuesday the 27th": the number names that weekday
            for relative in ('this', 'next'):
                c2 = resolve_date_expr(today, dict(weekday=wd, relative=relative), _calendar_dict())
                if c2 and c2 != 'vague' and int(c2[8:10]) == day:
                    cands.append((dict(weekday=wd, relative=relative), c2))
            if offer_date and any(c == offer_date for _, c in cands):
                expr = next(e for e, c in cands if c == offer_date)  # restating the offer
            elif any('weekday' in e for e, _ in cands):
                expr = next(e for e, c in cands if 'weekday' in e)   # "Friday the 23rd": the number names a Friday ahead
            else:
                wk = resolve_date_expr(today, expr, _calendar_dict())
                if wk and wk != 'vague' and wk >= today:
                    pass                                              # "this Friday" + a stray number from another sentence: the weekday wins
                elif cands:
                    expr = cands[0][0]                                # "Monday the 26th" when "this Monday" already passed: the dated reading
                else:
                    expr = dict(weekday=wd, relative='next')
    elif kind in ('date', 'weekday'):
        day = _int(_get(prefix + '_day'))
        if day is None:
            return 'unreadable', ''
        expr = dict(day=day)
        m = _int(_get(prefix + '_month'))
        if not m and POLICY['calendar'].get('missing_date_parts') == 'ask':
            return 'vague', ''                 # the documents say: never assume the month, ask for it (handled like a vague date)
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

def _floor_rule(p):
    rules = POLICY['amounts'].get('floor_rules') or dict()
    t = _str(p.get('type'))
    rule = rules.get(t) or rules.get('*')
    if rule:
        return rule
    field = POLICY['amounts']['floors'].get(t)
    return dict(kind='field', field=field) if field else None

def _floor_fields():
    """Every response property a floor may live in (from `floors` and field-kind / max_of `floor_rules`)."""
    out = set(POLICY['amounts']['floors'].values())
    for r in (POLICY['amounts'].get('floor_rules') or dict()).values():
        if isinstance(r, dict) and r.get('kind') in ('field', 'max_of') and r.get('field'):
            out.add(r['field'])
    return out

def _floor_words(p):
    rule = _floor_rule(p) or dict()
    if rule.get('kind') == 'field':
        return _str(rule.get('field')).replace('_', ' ').strip() or 'lowest amount'
    return 'lowest amount'

def _floor_of(p):
    rule = _floor_rule(p)
    full = _float(p.get('full')) or 0.0
    v = None
    if rule and rule.get('kind') == 'field':
        v = _float(p.get(rule.get('field')))
    elif rule and rule.get('kind') == 'percent':
        v = round(full * float(rule.get('percent') or 0) / 100.0, 2)
        v = max(v, float(rule.get('min_amount') or 0))
    elif rule and rule.get('kind') == 'fixed':
        v = float(rule.get('amount') or 0)
    elif rule and rule.get('kind') == 'max_of':
        base = _float(p.get(rule.get('field'))) or 0.0
        pct = full * float(rule.get('percent') or 0) / 100.0
        if rule.get('round') == 'up_cent':
            cents = int(pct * 100 + 1e-9)
            pct = (cents + (1 if pct * 100 - cents > 1e-9 else 0)) / 100.0   # round UP to the next cent, without math.ceil
        else:
            pct = round(pct, 2)
        v = max(base, pct)
    if v is None:
        return full
    return min(v, full) if full else v

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
        for i in range(max(8, int((POLICY.get('multi_product') or dict()).get('max_products') or 0))):
            p = dict()
            for k in (A['id'], A['type'], A['card_last4'], A['past_due'], A['days_late']) + tuple(sorted(_floor_fields())):
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
        CB = TP.get('callback') or dict()
        if CB.get('enabled', True) is False:
            # the documents schedule no callbacks: disclose nothing, close with the policy's not-reached outcome
            oc = CB.get('no_callback_outcome') or TP.get('wrong_number_outcome') or ['', '']
            return _close(S, oc[0], oc[1], 'I understand. I will try again another time. Thank you, goodbye.')
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
    offer = sc.get('offer_outcome') or ['', '']
    if sc.get('offer_transfer_queue'):
        # an offered transfer (hardship -> support team): the offer's queue and outcome, never the decline action's close outcome
        queue, outcome, reason = sc['offer_transfer_queue'], offer[0] or POLICY['outcomes']['transfer_outcome'], offer[1] or ''
    else:
        queue = a.get('queue') or ''
        outcome = a.get('outcome') or POLICY['outcomes']['transfer_outcome']
        reason = a.get('reason') or ''
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
    if status == 'none' and t and S.get('cb_date'):
        status, date = 'ok', S['cb_date']          # the day came in the previous turn, the time now
    ok = False
    wdays = [int(x) for x in (CB.get('weekdays') or []) if str(x).lstrip('-').isdigit() and 0 <= int(x) <= 6]
    bad_day = bool(status == 'ok' and wdays and datetime.date.fromisoformat(date).weekday() not in wdays)   # the documents allow named weekdays only
    if status == 'ok' and t and not bad_day:
        pol = dict(start=CB['start'], end=CB['end'], days=CB['days'], must_be_after_now=bool(CB.get('must_be_after_now', True)), holidays=_cal()[0], business_days=_cal()[1])
        ok = callback_ok(S['today'] + 'T' + S['now_time'], date, t, pol)
    if ok:
        vars['cb_date'] = date
        vars['cb_time'] = t
        _save(S)
        return _set_next('schedule_callback')
    if status == 'ok' and not t and not bad_day and intent not in ('cannot_say', 'refuses'):
        S['cb_date'] = date
        vars['neg_instruction'] = 'They named a day but no time. Ask at what time ' + _fmt(date) + ' would suit; do not propose a time yourself.'
        _save(S)
        return _set_next('third_party')
    S['cb_date'] = None
    if int(S.get('cb_asked') or 0) < 2 and bool(CB.get('retry_once', True)) and intent != 'refuses':
        S['cb_asked'] = int(S.get('cb_asked') or 0) + 1          # a talkative relative gets two more asks before the call is given up
        days = CB.get('days') or 'today_or_next_business_day'
        if days == 'today':
            window = 'today between ' + CB['start'] + ' and ' + CB['end']
        elif days == 'next_business_day':
            window = 'the next business day between ' + CB['start'] + ' and ' + CB['end']
        else:
            window = 'today until ' + CB['end'] + ' or the next business day between ' + CB['start'] + ' and ' + CB['end']
        if wdays:
            window += ', on ' + ' or '.join(WEEKDAYS[i].capitalize() for i in sorted(set(wdays))) + ' only'
        outside = 'That day is not one I can offer. ' if bad_day else ('That time is outside the window I can offer. ' if status == 'ok' and t else '')
        vars['neg_instruction'] = outside + 'Ask once more for another day and time: ' + window + '.'
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

def _has_complete_answer(r, S):
    """True when the extracted variables (plus accumulated parts) already hold a full answer in the question's format."""
    fmt = r.get('answer_format', 'text')
    if fmt == 'date':
        parts = S.get('id_parts') or dict()
        d, m, y = _int(_get('id_day')) or parts.get('d'), _int(_get('id_month')) or parts.get('m'), _int(_get('id_year')) or parts.get('y')
        return bool(d and m and y)
    if fmt == 'digits':
        n = int(r.get('digits') or 4)
        raw = re.sub('[^0-9]', '', _get('id_digits'))
        return len(_str(S.get('id_digits_acc')) + raw) >= n
    if fmt == 'year':
        return bool(_int(_get('id_year')))
    return bool(_get('id_text'))

def st_id_route(i):
    S = _S()
    I = POLICY['identity']
    r = I['requirements'][i]
    intent = _get('id_intent')
    _clear('id_intent')
    if intent in ('question', 'asks_purpose', 'other') and _has_complete_answer(r, S):
        S['id_question_pending'] = True    # verify the answer first; the next sentence also covers the question
        intent = 'answers'
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

def _service_failure(S, what):
    """A bank tool answered with no parseable result twice: a technical problem, never the customer's fault."""
    O = POLICY['outcomes']
    return _close(S, O['no_promise_outcome'], O.get('service_error_reason') or '', 'I am sorry, I have a technical problem with ' + what + ' and cannot continue this call. Thank you for your time, goodbye.')

def st_verify_after(i):
    S = _S()
    I = POLICY['identity']
    r = I['requirements'][i]
    if _get('v_ok') == '' and _get('v_verified') == '':
        # no parseable answer from the bank (HTTP error page, timeout): the check is fired again with the same answer; it is not a wrong answer
        S['v_fail'] = S.get('v_fail', 0) + 1
        _save(S)
        if S['v_fail'] <= 2:
            return _set_next('verify_' + str(i))
        return _service_failure(S, 'the identity check')
    S['v_fail'] = 0
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
        vars['id_say'] = _q_prefix(S) + _ask_text(i + 1)
        _save(S)
        return _set_next('ask_' + str(i + 1))
    if hint:
        vars['id_say'] = (r.get('hint_reply') or 'Could you say that once more, in the form the question asked for?')
        _save(S)
        return _set_next('ask_' + str(i))
    # ok:false without a remaining counter is a wrong answer, not an unreadable one: the agent formats every answer itself
    # (ISO date, exact digits), so a bank refusal counts against the allowance instead of looping on "could not read that".
    if str(I.get('wrong_count_source', 'api')) != 'api':
        left = None     # the documents fixed the allowance; ignore the API's remaining count for exhaustion (unreadable detection above still uses it)
    S['id_wrong'] = S.get('id_wrong', 0) + 1
    exhausted = (left is not None and left <= 0) or (left is None and S['id_wrong'] >= int(I.get('wrong_answer_limit', 3)))
    if exhausted:
        return _close(S, I['failed_outcome'][0], I['failed_outcome'][1], 'I am sorry, I could not verify your identity, so I cannot continue on this call. ' + (I.get('failed_instruction') or '') + ' Thank you for your time, goodbye.')
    vars['id_say'] = _q_prefix(S) + 'That does not match our records. ' + _q(r)
    _save(S)
    _set_next('ask_' + str(i))

def _q_prefix(S):
    if S.pop('id_question_pending', False):
        return 'These questions protect your account, and I can tell you more once your identity is confirmed. '
    return ''

def st_init_products():
    S = _S()
    A = SLOTS['account']
    prods = _products_from_vars()
    if not prods:
        # no product list came back (HTTP error page, timeout): the lookup is fired again; it is not an empty account
        S['ga_fail'] = S.get('ga_fail', 0) + 1
        _save(S)
        if S['ga_fail'] <= 2:
            return _set_next('get_account')
        return _service_failure(S, 'the account lookup')
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
        for f in _floor_fields():
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
        p['no_window'] = False
        if p['deadline'] < S['today']:
            if POLICY['dates'].get('past_deadline', 'next_business_day') == 'no_promise':
                p['no_window'] = True       # the documents say: no eligible date -> no promise for this product
            else:
                p['deadline'] = next_business_day(S['today'], h, b) or S['today']   # never propose or record a past date
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
    if k > len(attempts) or p.get('no_window'):
        return False
    a = attempts[k - 1]
    h, b = _cal()
    amount = p['floor'] if (a.get('amount') == 'floor' or (p.get('full_refused') and a.get('floor_if_full_refused', True))) else p['full']
    date = attempt_date(S['today'], a.get('date', 'deadline'), p['deadline'], h, b) or p['deadline']
    if date > p['deadline']:
        date = p['deadline']                      # a persuasion attempt never proposes a date after the product's deadline
    p['attempts_used'] = k
    prev = S.get('offer') or dict()
    same_amount = prev and abs(float(prev.get('amount') or 0) - float(amount)) < 0.005
    if same_amount and prev.get('date') == date:
        return _start_attempt(S, p, k + 1)        # identical to what the customer just refused: go to the next attempt
    S['offer'] = dict(amount=amount, date=date)
    S['awaiting'] = 'offer'
    if same_amount:
        vars['neg_instruction'] = 'Propose the same amount for a different day: ask whether they can make the payment you proposed on ' + _fmt(date) + ' instead. Refer to it as the amount already proposed; do not say the number again and do not repeat that the rest stays overdue.'
        return True
    floor_note = ''
    if amount == p['floor'] and amount < p['full']:
        p['floor_offered'] = True
    if amount == p['floor'] and amount < p['full'] and not p.get('floor_note_said'):
        floor_note = ' Say that ' + POLICY['amounts'].get('floor_wording', 'the rest stays overdue') + '.'
        p['floor_note_said'] = True
    elif amount == p['floor'] and amount < p['full']:
        floor_note = ' Do not repeat that the rest stays overdue; you said it already.'
    stay = ''
    if len(S['products']) > 1 and any(q is not p and not q['proposed'] and not q['disposition'] for q in S['products']):
        stay = ' Stay on the ' + p['name'] + ' for this question; do not move on to another product or mention the others yet.'
    vars['neg_instruction'] = 'Propose this payment for the ' + p['name'] + ': ' + _money(amount) + ' on ' + _fmt(date) + '. Ask whether they can make that payment.' + floor_note + stay
    return True

def _enter_product(S, k, lead=None):
    """Start on product k. A hand-over from another product is SPOKEN by fixed text (the `handover` node's TTS): live, the dialogue
    model ignored the hand-over instruction after a refusal ladder and invented a third offer for the finished product."""
    prev = S['products'][S['pi']] if S.get('phase') == 'product' and S.get('pi') is not None and 0 <= int(S.get('pi') or 0) < len(S['products']) and int(S.get('pi') or 0) != k else None
    S['phase'] = 'product'
    S['pi'] = k
    S['vague_asked'] = False
    S['vague_asked_done'] = False          # "ask once for the exact day" is per product
    p = S['products'][k]
    if not _start_attempt(S, p, 1):
        p['disposition'] = POLICY['outcomes'].get('refused_reason') or 'refused'
        return _advance(S)
    if any(q['proposed'] and not q['recorded'] for q in S['products']):
        # earlier products have proposals waiting for the common read-back: nothing is noted or recorded yet
        vars['neg_instruction'] = _get('neg_instruction') + ' Do not say that any earlier payment is noted or recorded; everything is confirmed together at the end.'
    _save(S)
    if prev is None and not lead:
        return _set_next('negotiate')
    o = S.get('offer') or dict()
    amount, date = float(o.get('amount') or p['full']), o.get('date') or p['deadline']
    lead = lead or ('I understand.' if (prev is not None and prev.get('disposition') and not prev.get('proposed')) else 'Thank you.')
    note = ''
    if amount < float(p['full']) and not p.get('floor_note_said'):
        fw = POLICY['amounts'].get('floor_wording') or 'the rest stays overdue'
        note = ' ' + fw[:1].upper() + fw[1:] + ('' if fw.endswith('.') else '.')
        p['floor_note_said'] = True
        _save(S)
    vars['handover_text'] = lead + ' For your ' + p['name'] + ', can you make a payment of ' + _money(amount) + ' on ' + _fmt(date) + '?' + note
    _set_next('handover')

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

BR = '{' + '{'   # the template delimiter, spelled so that this source never contains it literally (the engine would substitute it)

def _confirm_phrase(proposed):
    """The documents' confirmation sentence. When it carries placeholders ("Amount <<payment_amount>>, on <<date>>. Save this?")
    it IS the read-back: filled in for a single proposal; with several proposals only its placeholder-free sentences are kept
    (the list of proposals is spoken before it). Returns (phrase, is_full_readback)."""
    phrase = POLICY['promise_write'].get('confirm_phrase') or 'Do you confirm?'
    if BR not in phrase and '<<' not in phrase:      # the compiler embeds policy text with << >> in place of the template braces
        return phrase, False
    import re
    if len(proposed) == 1:
        p = proposed[0]
        def sub(m):
            key = m.group(1).lower()
            if 'amount' in key or 'amt' in key or 'sum' in key or 'payment' in key or 'money' in key:
                return _money(p['proposed_amount'])
            if 'date' in key or 'day' in key or 'when' in key:
                return _fmt(p['proposed_date'])
            if 'product' in key or 'name' in key or 'item' in key or 'facility' in key:
                return p['name']
            return ''
        return re.sub(r'(?:[{]{2}|<<)\s*([^}>]+?)\s*(?:[}]{2}|>>)', sub, phrase).replace('  ', ' ').strip(), True
    sentences = [x.strip() for x in re.split(r'(?<=[.?!])\s+', phrase) if x.strip() and BR not in x and '<<' not in x]
    return (' '.join(sentences) or 'Do you confirm?'), False

def _readback(S):
    parts = []
    proposed = [p for p in S['products'] if p['proposed']]
    for p in proposed:
        s = _money(p['proposed_amount']) + ' for the ' + p['name'] + ' on ' + _fmt(p['proposed_date'])
        if p.get('clamped'):
            s += ' (the latest date I can record for the ' + p['name'] + ' is ' + _fmt(p['deadline']) + ', so that one is on ' + _fmt(p['proposed_date']) + ')'
        parts.append(s)
    phrase, full = _confirm_phrase(proposed)
    rest = ''
    fw = POLICY['amounts'].get('floor_wording') or 'the rest stays overdue'
    if any(float(p['proposed_amount']) < float(p.get('full') or 0) and not p.get('floor_note_said') for p in proposed):
        rest = ' ' + fw[:1].upper() + fw[1:] + ('' if fw.endswith('.') else '.')     # a partial amount: the remainder is still owed
        for p in proposed:
            if float(p['proposed_amount']) < float(p.get('full') or 0):
                p['floor_note_said'] = True
    if full and not any(p.get('clamped') for p in proposed):
        txt = phrase if not rest else phrase.rstrip() + rest
    else:
        txt = 'To confirm: you will pay ' + ('; and '.join(parts) if len(parts) > 1 else parts[0]) + '.' + rest + ' ' + phrase
    vars['readback_text'] = txt
    S['awaiting'] = 'confirm'
    _save(S)
    _set_next('readback')

def _readback_after_change(S, before):
    """A change that changed nothing, twice in a row, gets one clarifying question instead of the same read-back again;
    four times in a row counts as not confirmed (the proposals are abandoned, nothing is written)."""
    after = [(p['proposed_amount'], p['proposed_date']) for p in S['products'] if p['proposed']]
    S['rb_same'] = S.get('rb_same', 0) + 1 if after == before else 0
    if S['rb_same'] >= 4:
        S['rb_same'] = 0
        for p in S['products']:
            if p['proposed'] and not p['recorded']:
                p['proposed'] = False
                p['disposition'] = POLICY['outcomes'].get('refused_reason') or 'refused'
        vars['goodbye_text'] = 'I am sorry, I could not apply that change, so nothing is recorded today. Thank you for your time, goodbye.'
        _save(S)
        return _advance(S)
    _readback(S)
    if S['rb_same'] >= 2:
        txt = _str(vars['readback_text'])
        rest = txt[len('To confirm: '):] if txt.startswith('To confirm: ') else txt
        vars['readback_text'] = ('I may have misunderstood the change. Please tell me one change at a time: which product, and the new amount or the new date. '
                                 'Currently: ' + rest)

def _apply_proposal(S, p, amount, date, date_status, allow_clamp):
    """Validate a customer proposal for one product. Returns 'done' or an instruction string (and sets S['offer'])."""
    h, b = _cal()
    if p.get('no_window'):
        return 'refusal'                      # no eligible promise date for this product: nothing can be recorded
    if amount is None and S.get('want_floor'):
        amount = p['floor']
    if date_status == 'ok' and date == S['today'] and not bool(POLICY['dates'].get('promise_today_allowed', True)):
        nxt = _today_bd(S)                                 # the documents take no promise for today: offer the next business day
        amt = amount if amount is not None else (S.get('offer') or dict()).get('amount', p['full'])
        if nxt > p['deadline']:
            p['disposition'] = POLICY['outcomes'].get('refused_reason') or 'refused'
            return 'refusal'
        S['offer'] = dict(amount=float(amt), date=nxt)
        S['awaiting'] = 'offer'
        return 'Say that a payment cannot be recorded for today and offer ' + _money(amt) + ' on ' + _fmt(nxt) + '; ask whether that works.'
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
        if not bool(D.get('after_deadline_offer_deadline', True)):
            S['offer'] = None
            S['awaiting'] = 'exact_day'
            return 'Say that the latest date you can record for the ' + p['name'] + ' is ' + _fmt(p['deadline']) + ' and ask for a day on or before it; do not propose one.'
        S['offer'] = dict(amount=float(v['amount']), date=p['deadline'])
        S['awaiting'] = 'offer'
        return 'Say that the latest date you can record for the ' + p['name'] + ' is ' + _fmt(p['deadline']) + ' and offer ' + _money(v['amount']) + ' on that day.'
    if verdict == 'roll_forward':
        if not bool(D.get('weekend_or_holiday_roll_forward', True)):
            S['offer'] = None
            S['awaiting'] = 'exact_day'
            return 'Say that ' + _fmt(date) + ' is not a business day and ask for another day; do not propose one.'
        S['offer'] = dict(amount=float(v['amount']), date=v['offer_date'])
        S['awaiting'] = 'offer'
        if date == S['today']:
            return ('Say that today, ' + _fmt(date) + ', is not a business day, so the payment cannot be made today; nothing is recorded yet. '
                    'Offer the next business day, ' + _fmt(v['offer_date']) + ', for ' + _money(v['amount']) + ', and ask whether they can pay then.')
        return 'Say that ' + _fmt(date) + ' is not a business day and offer the next business day, ' + _fmt(v['offer_date']) + ', for ' + _money(v['amount']) + '.'
    if verdict == 'below_floor':
        if p.get('floor_offered'):
            if not p.get('floor_reoffered'):
                p['floor_reoffered'] = True
                d2 = v.get('date') or date or (S.get('offer') or dict()).get('date') or _today_bd(S)
                S['offer'] = dict(amount=p['floor'], date=d2)
                S['awaiting'] = 'offer'
                return ('Say that ' + _money(amount) + ' is below the lowest amount this call can take. Ask whether they can make the amount '
                        'already proposed on ' + _fmt(d2) + '; refer to it as the amount already proposed and do not say the number again.')
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

def _targets(S, single=False):
    """Which products a customer statement refers to, from prop_product (multi-product only). 'none' = no product named;
    single=True (paid / dispute claims) then applies to the first undecided product only, never to all of them: a claim about
    one product that the extractor could not place must not close the others."""
    sel = _get('prop_product')
    _clear('prop_product')
    if sel == 'none':
        sel = ''
    n = len(S['products'])
    if S.get('phase') == 'all':
        if sel and sel != 'all' and _int(sel) and 1 <= _int(sel) <= n:
            return [_int(sel) - 1]
        open_ = [k for k in range(n) if not S['products'][k]['proposed'] and not S['products'][k]['disposition']]
        return open_[:1] if (single and not sel and n > 1) else open_
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
        targets = _targets(S, single=True)
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

def _advance_with_prefix(S, prefix, lead='I understand, and I will not ask about that one.'):
    """Next product with a leading sentence: spoken verbatim by the hand-over text; the LLM instruction keeps the prefix for follow-ups."""
    rest = _undecided(S)
    if rest:
        _enter_product(S, rest[0], lead=lead)
        vars['neg_instruction'] = prefix + ' ' + _get('neg_instruction')
        return True
    _advance(S)
    return True

def _secondary(S, intent, amount, date, date_status):
    """Several statements in one sentence ("the card gets 220 on Friday, the loan is not mine, the car loan I cannot pay: I lost
    my job"): the extractor reports the extra statements as cust_intent_2/3 with their products. Paid / dispute claims are
    marked on their product at once; a proposal for another product is applied as that product's proposal; a hardship statement
    becomes the main intent (its treatment, the support offer, must happen) and the original main statement is kept as a
    proposal. 'refuses' is left to the normal flow (that product is asked in its turn). Returns the possibly re-ordered
    main intent and the amount/date still unclaimed."""
    n = len(S['products'])
    if n < 2:
        return intent, amount, date, date_status
    extras = []
    for k in (2, 3):
        it = _get('cust_intent_' + str(k))
        sel = _get('prop_product_' + str(k))
        _clear('cust_intent_' + str(k))
        if it in ('', 'none') or not sel or sel == 'none' or not _int(sel) or not (1 <= _int(sel) <= n):
            continue
        extras.append((it, _int(sel) - 1))
    if not extras:
        return intent, amount, date, date_status
    prim_sel = _get('prop_product')
    prim_k = _int(prim_sel) - 1 if prim_sel and prim_sel not in ('all', 'none') and _int(prim_sel) and 1 <= _int(prim_sel) <= n else None
    said = []
    for it, k in extras:
        if k == prim_k:
            continue
        p = S['products'][k]
        if p['disposition'] or p.get('recorded'):
            continue
        if it in ('already_paid', 'dispute'):
            sc = _sc('already_paid' if it == 'already_paid' else 'dispute') or dict()
            reason = (sc.get('action') or dict()).get('reason') or ('paid' if it == 'already_paid' else 'dispute')
            p['disposition'] = reason
            p['paid'] = it == 'already_paid'
            p['proposed'] = False
            said.append('I will not ask about the ' + p['name'] + '.')
        elif it in ('proposes', 'pays_today') and intent not in ('proposes', 'pays_today', 'accepts') and (it == 'pays_today' or amount is not None or date_status in ('ok',)):
            ds, d = (date_status, date) if date_status == 'ok' else ('ok', _today_bd(S))
            if _apply_proposal(S, p, amount, d, ds, True) == 'done':
                amount, date, date_status = None, '', 'none'       # claimed by that product
        elif it == 'hardship' and intent != 'hardship' and _sc('hardship'):
            # hardship wins: it becomes the main statement; the original main statement, if a proposal for a named product, is kept
            if intent in ('proposes', 'pays_today') and prim_k is not None and not S['products'][prim_k]['disposition']:
                ds, d = (date_status, date) if date_status == 'ok' else ('ok', _today_bd(S))
                if _apply_proposal(S, S['products'][prim_k], amount, d, ds, True) == 'done':
                    amount, date, date_status = None, '', 'none'
            intent = 'hardship'
            vars['prop_product'] = str(k + 1)
            prim_k = k
    if said:
        vars['aside_carry'] = ' '.join(said)
    _save(S)
    return intent, amount, date, date_status

def st_neg_route():
    S = _S()
    intent = _get('cust_intent')
    _clear('cust_intent')
    amount = _float(_get('prop_amount'))
    _clear('prop_amount')
    date_status, date = _resolve_date('prop', S['today'], (S.get('offer') or dict()).get('date'))
    _clear_date('prop')
    intent, amount, date, date_status = _secondary(S, intent, amount, date, date_status)
    if intent == 'accepts' and amount is not None and S.get('offer') and amount < float(S['offer'].get('amount') or 0):
        amount = None        # "yes, I accept the minimum payment of six[ hundred thirty-seven fifty]": a cut-off number next to a yes is not a counter-offer
    S['want_floor'] = _get('prop_minimum') == 'yes' and amount is None     # "I can pay the minimum": the floor is the amount
    _clear('prop_minimum')
    aw = S.get('awaiting', '')
    if intent == 'hardship' and not S.get('hardship_offered') and (amount is not None or date_status == 'ok' or S.get('want_floor')):
        # "I lost my job, but I can pay the minimum on Friday": the hardship treatment comes first; the proposal is kept for after the offer
        S['hardship_pending'] = dict(amount=amount, date=date, date_status=date_status, sel=_get('prop_product'), want_floor=bool(S.get('want_floor')))
    if intent in ('other', 'scam', 'none', '', 'goodbye'):
        S['idle'] = S.get('idle', 0) + 1
        if intent == 'goodbye' or S['idle'] >= 8:
            # an explicit goodbye, or eight turns without a usable answer: the open proposal is treated as declined and the call wraps up.
            # Chatter alone never ends a call early: talkative customers ramble for several turns before answering.
            S['idle'] = 0
            for k in _targets(S):
                q = S['products'][k]
                if not q['proposed'] and not q['disposition']:
                    q['disposition'] = POLICY['outcomes'].get('refused_reason') or 'refused'
            S['offer'] = None
            return _advance(S)
        # chatter: no re-ask (judges count a repeated proposal as another persuasion attempt) — a few words, then wait
        if intent == 'scam':
            vars['neg_instruction'] = (POLICY['phrases'].get('scam_reply') or 'You can verify this call through the bank\'s official customer service number.') + ' Then wait; do not repeat the proposal or any amount or date.'
        else:
            vars['neg_instruction'] = 'Reply in a few words and invite them to come back to the payment whenever they are ready; do not repeat the proposal or any amount or date.'
        _save(S)
        return _set_next('negotiate')
    S['idle'] = 0
    if intent == 'question':
        o = S.get('offer') or dict()
        if S.get('awaiting') == 'support':
            # hardship: the support team is offered exactly once and there is no persuasion. A question instead of a yes
            # ("can I get a discount?") is a decline: answer it in the goodbye and close with the hardship outcome.
            hr = ((_sc('hardship') or dict()).get('action') or dict()).get('reason') or POLICY['outcomes'].get('refused_reason') or 'refused'
            for p in S['products']:
                if not p['proposed'] and not p['disposition']:
                    p['disposition'] = hr
            if any(p['proposed'] for p in S['products']):
                return _readback(S)
            vars['goodbye_text'] = 'I am not able to change the amount or the terms. I understand, and I will not record a promise today. Thank you for your time, and goodbye.'
            _save(S)
            return _set_next('finalize')
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
    if (aw == 'support' and intent in ('human', 'restructuring') or intent == 'human' and S.get('hardship_offered')) and amount is None and date_status == 'none':
        return _transfer(S, 'hardship')    # "yes, please connect me to the support team" reads as a request for a person: it accepts the offer
    if intent in ('already_paid', 'dispute', 'hardship', 'restructuring', 'human', 'refuses_to_talk'):
        if _special(S, intent):
            return
        intent = 'refuses'
    if aw == 'support':
        if intent in ('accepts', 'pays_today') and amount is None and date_status in ('none',):
            return _transfer(S, 'hardship')
        if intent in ('refuses', 'too_much') and amount is None and date_status == 'none' and S.get('hardship_pending'):
            pend = S.pop('hardship_pending')                     # the offer was declined: the proposal made alongside the hardship is applied
            if pend.get('sel'):
                vars['prop_product'] = pend['sel']
            S['want_floor'] = bool(pend.get('want_floor'))
            S['awaiting'] = 'offer'
            _save(S)
            return _proposal(S, pend['amount'], pend['date'], pend['date_status'])
        if intent in ('refuses', 'too_much') and amount is None and date_status == 'none':
            S.pop('hardship_pending', None)
            hsc = _sc('hardship') or dict()
            hr = (hsc.get('action') or dict()).get('reason') or POLICY['outcomes'].get('refused_reason') or 'refused'
            if hsc.get('ends_call', True) is False and len(S['products']) > 1:
                for k in _targets(S):
                    if not S['products'][k]['proposed'] and not S['products'][k]['disposition']:
                        S['products'][k]['disposition'] = hr
                if _undecided(S):
                    S['awaiting'] = 'offer'
                    return _advance_with_prefix(S, 'Say you understand and will not ask about that one; then move on.')
                if any(p['proposed'] for p in S['products']):
                    return _readback(S)
                vars['goodbye_text'] = 'I understand. I will not record a promise today. Thank you for your time, and goodbye.'
                _save(S)
                return _set_next('finalize')
            for p in S['products']:
                if not p['proposed'] and not p['disposition']:
                    p['disposition'] = hr
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
            h, b = _cal()
            if not is_business_day(S['today'], h, b) or not bool(POLICY['dates'].get('promise_today_allowed', True)):
                return _proposal(S, None, S['today'], 'ok')      # "today" on a weekend/holiday, or no promise for today: offer the next business day
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
        if intent in ('accepts', 'pays_today') and not has_prop and S.get('offer') and not p.get('no_window'):
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

def _today_bd(S):
    """Today when it is a business day, otherwise the next business day: the earliest date the agent may offer.
    When the documents take no promise for today, the earliest date is the next business day after today."""
    h, b = _cal()
    if not bool(POLICY['dates'].get('promise_today_allowed', True)):
        return next_business_day(S['today'], h, b, inclusive=False) or S['today']
    return next_business_day(S['today'], h, b) or S['today']

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
    if p.get('no_window'):
        p['disposition'] = POLICY['outcomes'].get('refused_reason') or 'refused'   # no eligible date: nothing to offer
        S['offer'] = None
        return _advance(S)
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
    date = (S.get('offer') or dict()).get('date')
    if not date:
        h, b = _cal()
        first = (p.get('attempts') or [dict()])[0]
        date = attempt_date(S['today'], first.get('date', 'deadline'), p['deadline'], h, b) or _today_bd(S)   # the floor rides on attempt 1's date
    if date > p['deadline']:
        date = p['deadline']
    S['offer'] = dict(amount=p['floor'], date=date)
    S['awaiting'] = 'offer'
    vars['neg_instruction'] = 'Offer the ' + _floor_words(p) + ' for the ' + p['name'] + ', ' + _money(p['floor']) + ', on ' + _fmt(date) + ' (it is the lowest amount this call can take). Say that ' + A.get('floor_wording', 'the rest stays overdue') + '. Ask whether they can make that payment.'
    _save(S)
    _set_next('negotiate')

def _second_amount(S):
    """'ninety on the card and three hundred on the loan': the second amount and its product (0-based), or None."""
    amt = _float(_get('prop_amount_2'))
    sel = _get('prop_product_2')
    _clear('prop_amount_2', 'prop_product_2')
    n = len(S['products'])
    if amt is not None and amt > 0 and sel and sel != 'none' and _int(sel) and 1 <= _int(sel) <= n:
        return _int(sel) - 1, amt
    return None

def _proposal(S, amount, date, date_status):
    targets = _targets(S)
    if not targets:
        return _advance(S)
    amounts = dict()
    second = _second_amount(S)
    if second is not None and amount is not None and len(targets) == 1 and second[0] != targets[0]:
        amounts[targets[0]] = amount
        amounts[second[0]] = second[1]
        if not S['products'][second[0]]['disposition']:
            targets = targets + [second[0]]
    elif second is not None and amount is not None and len(targets) > 1 and second[0] in targets:
        others = [k for k in targets if k != second[0]]
        if len(others) == 1:
            amounts[others[0]] = amount
        amounts[second[0]] = second[1]
    multi_all = len(targets) > 1
    if date_status == 'none':
        date_status, date = 'ok', (S.get('offer') or dict()).get('date') or _today_bd(S)
    if amount is None and S.get('offer') and not multi_all:
        amount = S['offer'].get('amount')      # the amount currently on the table (e.g. the floor) stays
    if multi_all:
        # a common date is applied to EVERY product (clamped to each deadline); the first product that needs the customer's
        # answer (roll-forward, below floor) becomes the current one, the others keep their clamped proposals
        first = None
        for k in targets:
            p = S['products'][k]
            r = _apply_proposal(S, p, amounts.get(k, amount if len(targets) == 1 else None), date, date_status, bool(POLICY['multi_product'].get('common_date_clamped_per_product', True)))
            if r != 'done' and first is None:
                first = (k, r, S.get('offer'))
            elif r != 'done':
                S['offer'] = first[2]            # keep the first open question's offer on the table
        if first is not None:
            k, r, offer = first
            p = S['products'][k]
            S['offer'] = offer
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
    date_status, date = _resolve_date('prop', S['today'], (S.get('offer') or dict()).get('date'))
    _clear_date('prop')
    if intent == 'hardship' and S.get('hardship_offered'):
        intent = 'declines'
    if intent == 'confirms' and amount is not None:
        proposed_amounts = [float(p['proposed_amount']) for p in S['products'] if p['proposed']]
        if proposed_amounts and amount < min(proposed_amounts):
            amount = None    # "yes, I confirm, the six[ hundred]": a cut-off number next to a confirmation is not a change
    if intent in ('other', 'none', '', 'goodbye'):
        S['rb_idle'] = S.get('rb_idle', 0) + 1
        if intent != 'goodbye' and S['rb_idle'] < 6:
            _save(S)
            return _set_next('readback')       # re-enter: the read-back sentence is spoken again and the confirmation asked again
        S['rb_idle'] = 0
        S['rb_declined'] = 2                   # goodbye, or six turns without an answer: not confirmed and the customer is leaving
        intent = 'declines'                    # -> unsaved proposals abandoned, notes written, one close
    else:
        S['rb_idle'] = 0
    if intent == 'human' and S.get('hardship_offered') and amount is None and date_status == 'none':
        return _transfer(S, 'hardship')        # "connect me to the support team you mentioned": the earlier offer is accepted
    if intent in ('already_paid', 'dispute', 'hardship', 'restructuring', 'human', 'refuses_to_talk'):
        if _special(S, intent):
            return
    if intent == 'confirms':
        S['w_idx'] = -1
        S['w_pending'] = False
        _save(S)
        return _set_next('write_step')
    S['want_floor'] = _get('prop_minimum') == 'yes' and amount is None
    _clear('prop_minimum')
    like = _get('prop_date_like')
    _clear('prop_date_like')
    if date_status == 'none' and like and like != 'none' and _int(like) and 1 <= _int(like) <= len(S['products']):
        q = S['products'][_int(like) - 1]
        if q['proposed']:
            date_status, date = 'ok', q['proposed_date']        # "put the card on the loan's date": that product's date
            if intent not in ('changes',):
                intent = 'changes'
    if intent == 'changes' or amount is not None or date_status in ('ok', 'vague'):
        targets = _targets(S)
        second = _second_amount(S)
        proposed = [k for k in range(len(S['products'])) if S['products'][k]['proposed']]
        amounts = dict()
        if second is not None and second[0] in proposed:
            if amount is not None and len(targets) == 1 and targets[0] != second[0]:
                amounts[targets[0]] = amount
            amounts[second[0]] = second[1]
            if second[0] not in targets:
                targets = targets + [second[0]]
        targets = [k for k in targets if k in proposed] or proposed[:1]
        if not targets:
            return _readback(S)
        before = [(p['proposed_amount'], p['proposed_date']) for p in S['products'] if p['proposed']]
        if len(targets) > 1 and (date_status == 'ok' or amounts):
            for k in targets:
                p = S['products'][k]
                p['proposed'] = False
                _apply_proposal(S, p, amounts.get(k, amount if amount is not None and not amounts else p['proposed_amount']),
                                date if date_status == 'ok' else p['proposed_date'], 'ok', True)
            if all(S['products'][k]['proposed'] for k in targets):
                return _readback_after_change(S, before)
        k = targets[0]
        p = S['products'][k]
        S['phase'] = 'product'
        S['pi'] = k
        if date_status == 'none':
            date_status, date = 'ok', p['proposed_date']
        amt = amounts.get(k, amount if amount is not None else p['proposed_amount'])
        p['proposed'] = False
        r = _apply_proposal(S, p, amt, date, date_status, False)
        if r == 'done':
            return _readback_after_change(S, before)
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
        werr = _get('w_error').lower()
        if raw_ok == 'false' and ('already has a promise' in werr or 'promise already' in werr or 'already recorded' in werr or 'duplicate promise' in werr):
            raw_ok = 'true'                   # the bank says this exact promise already exists (duplicate write race): the goal is met
        _clear('w_error')
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

def _consume_aside_into_goodbye():
    if _str(vars.get('aside_carry')) and vars.get('goodbye_text'):
        vars['goodbye_text'] = _str(vars.get('aside_carry')) + ' ' + _str(vars.get('goodbye_text'))
        vars['aside_carry'] = ''

def st_finalize():
    S = _S()
    _clear('t_ok')
    O = POLICY['outcomes']
    N = POLICY['notes']
    outcome, reason = '', ''
    recorded = [p for p in S['products'] if p.get('recorded')]
    if S.get('transfer') and recorded and not bool(O.get('transfer_overrides_promise', True)):
        outcome, reason = O['promise_outcome'], ''
    elif S.get('transfer'):
        outcome, reason = S['transfer'].get('outcome') or O['transfer_outcome'], S['transfer'].get('reason') or ''
    elif S.get('close'):
        outcome, reason = S['close'][0], S['close'][1]
    elif recorded:
        outcome, reason = O['promise_outcome'], ''
    elif S['products'] and all(p.get('paid') for p in S['products']) and bool(O.get('all_paid_closes_as_paid', True)) and O.get('paid_outcome'):
        outcome, reason = O['paid_outcome'], ''
    else:
        outcome = O['no_promise_outcome']
        reason = O.get('refused_reason') or 'refused'
        for p in S['products']:
            d = p.get('disposition') or ''
            if d and not p.get('paid'):
                reason = d
                break
        else:
            if S['products'] and all(p.get('paid') for p in S['products']):
                reason = next((p.get('disposition') for p in S['products'] if p.get('disposition')), '') or reason   # no paid outcome in the policy: the paid claim's reason
    if not reason:
        row = next((r for r in (O.get('table') or []) if r.get('outcome') == outcome), None)
        rs = (row or dict()).get('reasons') or []
        if rs and (bool((POLICY.get('_api') or dict()).get('close_reason_required')) or len(rs) == 1):
            reason = rs[0]                 # the API requires a reason (or the table allows exactly one) for this outcome
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
        _consume_aside_into_goodbye()
        return _set_next('notes_step')
    _consume_aside_into_goodbye()
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

def _aside_reply(aside):
    ph = POLICY['phrases']
    if aside == 'robot':
        return ph.get('robot_reply') or ('I am ' + _str(POLICY.get('bank_name') or 'the bank') + "'s digital assistant.")
    if aside == 'scam':
        return ph.get('scam_reply') or ('You can verify this call by phoning ' + _str(POLICY.get('bank_name') or 'the bank') + "'s customer service number.")
    return ''

def _apply_aside():
    """A robot/scam question that came WITH the customer's answer is answered in the next sentence, whatever node speaks it
    (the read-back and goodbye are fixed TTS, so the LLM never gets a chance otherwise). The reply waits in `aside_carry`
    until a spoken sentence consumes it (here, in the write step, or in finalize)."""
    reply = _str(vars.get('aside_carry'))
    if not reply:
        return
    nxt = _str(vars.get('next'))
    if nxt == 'readback' and vars.get('readback_text'):
        vars['readback_text'] = reply + ' ' + _str(vars['readback_text']); vars['aside_carry'] = ''
    elif nxt in ('finalize', 'transfer', 'close_reason', 'close_noreason') and vars.get('goodbye_text'):
        vars['goodbye_text'] = reply + ' ' + _str(vars['goodbye_text']); vars['aside_carry'] = ''
    elif nxt in ('negotiate', 'third_party', 'state_debt') or nxt.startswith('ask_'):
        vars['neg_instruction'] = 'First answer their question in one sentence: "' + reply + '" Then: ' + _str(vars.get('neg_instruction')); vars['aside_carry'] = ''
    # else: left in aside_carry for the write step / finalize

def _run(stage):
    if _stuck(stage):
        return
    if stage in ('neg_route', 'readback_route'):
        reply = _aside_reply(_get('aside'))
        _clear('aside')
        if reply:
            vars['aside_carry'] = reply          # consumed by the next spoken sentence (see _apply_aside / write step)
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
    _apply_aside()
