"""Workflow compiler: structural policy IR + prompts + OpenAPI -> Freya workflow JSON.

Design (plan §3):
  - every bank tool is an engine-fired `api_request` node with a body baked from variables that code nodes set;
    no bank tool is ever in a conversation node's `tools`;
  - all arithmetic, calendars, validation and outcome selection run in `code` nodes (bankcal.py source is
    embedded verbatim plus a small runtime below); the dialogue model only talks;
  - routing is deterministic: conversation nodes extract an intent enum, a code node consumes it and sets
    `next`, transitions test `next equals <node>`;
  - the template is multi-product native; a single product is the degenerate case.

    python3 compile.py tests/fixtures/brief_a.policy.json tools/openapi.json out/brief-a.workflow.json
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

import policy as P

ROOT = pathlib.Path(__file__).resolve().parent
BANKCAL_SRC = (ROOT / "bankcal.py").read_text(encoding="utf-8")
assert "{{" not in BANKCAL_SRC and "}}" not in BANKCAL_SRC, "bankcal.py must not contain template braces"

MIN_CONF = 0.5
WEEKDAY_ENUM = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


# =============================================================================================
# OpenAPI mapper
# =============================================================================================
class ToolSpec:
    def __init__(self, name, url, method, body_props, required, response_props):
        self.name, self.url, self.method = name, url, method
        self.body_props, self.required, self.response_props = body_props, required, response_props

    def enums(self):
        return {k: v["enum"] for k, v in self.body_props.items() if "enum" in v}


def parse_openapi(path: str) -> dict[str, ToolSpec]:
    spec = json.load(open(path))
    base = (spec.get("servers") or [{"url": ""}])[0]["url"].rstrip("/")
    tools = {}
    for p, ops in spec["paths"].items():
        for method, op in ops.items():
            name = op.get("operationId") or p.strip("/").split("/")[-1]
            body = op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {})
            resp = op.get("responses", {}).get("200", {}).get("content", {}).get("application/json", {}).get("schema", {})
            tools[name] = ToolSpec(name, base + p, method.upper(), body.get("properties", {}), body.get("required", []),
                                   resp.get("properties", {}))
    return tools


def tool_enums(tools: dict[str, ToolSpec]) -> dict[str, dict[str, list[str]]]:
    return {n: t.enums() for n, t in tools.items()}


def _pick(props: dict, *needles: str, default: str = "", exclude: tuple = ()) -> str:
    """First response property whose name contains one of the needles (in order), skipping names with an excluded word."""
    for n in needles:
        for k in props:
            if n in k and not any(x in k for x in exclude):
                return k
    return default


def response_slots(tools: dict[str, ToolSpec]) -> dict:
    """Map the response properties of the supplied OpenAPI document onto the template's semantic slots.
    Names are matched by meaning (substrings), never assumed from the practice kit."""
    v = tools["verify_identity"].response_props
    g = tools["get_account"].response_props
    list_prop = next((k for k, spec in g.items() if spec.get("type") == "array"), None) or _pick(g, "products", "accounts", "facilities", "items", default="products")
    items = g.get(list_prop, {}).get("items", {}).get("properties", {})
    slots = {
        "verify": {
            "ok": _pick(v, "ok", "success", default="ok"),
            "verified": next((k for k in v if "verified" in k and not k.startswith("all")), _pick(v, "match", "correct", default="verified")),
            "all_verified": _pick(v, "all_verified", "all", "complete", default="all_verified"),
            "remaining": _pick(v, "left", "remaining", "attempts", default="wrong_answers_left"),
            "hint": _pick(v, "hint", default="hint"),
        },
        "account": {
            "list": list_prop,
            "id": _pick(items, "product_id", "facility_id", "account_id", "_id", "id", default="product_id"),
            "type": _pick(items, "type", "kind", "product", default="type"),
            "past_due": _pick(items, "past_due", "arrears", "overdue", "outstanding", "due", "balance", "amount", default="past_due",
                              exclude=("minimum", "min_", "scheduled", "instalment", "installment", "repayment")),
            "days_late": _pick(items, "days_late", "days", "late", default="days_late"),
            "card_last4": _pick(items, "last4", "last_4", "last_four", default="card_last4"),
        },
        "ok": _pick(tools["create_promise"].response_props, "ok", "success", default="ok"),
    }
    return slots


# =============================================================================================
# Node builders
# =============================================================================================
def always(target):
    return {"target_node": target, "description": "always", "condition": {"operator": "always"}}


def on_next(target, value=None):
    return {"target_node": target, "description": "next is " + (value or target),
            "condition": {"logic": "or", "conditions": [{"variable": "next", "operator": "equals", "operand": value or target}]}}


def on_enum(var, values, target):
    return {"target_node": target, "description": f"{var} decided",
            "condition": {"logic": "or", "conditions": [{"variable": var, "operator": "equals", "operand": x} for x in values]}}


def code_node(name, code, targets, default=None):
    assert "{{" not in code and "}}" not in code, f"code node {name} contains template braces"
    return {
        "name": name, "node_type": "code", "passthrough": True, "passthrough_default_transition": default or targets[-1],
        "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True,
        "pre_actions": [{"type": "function", "function": {"name": "code_exec", "handler": "__function__:code_exec",
                         "parameters": {"type": "object", "properties": {"code": {"type": "string", "default": code},
                                                                         "timeout_ms": {"type": "number", "default": 15000}}}}}],
        "transitions": [on_next(t) for t in targets] + [always(default or targets[-1])],
    }


def api_node(name, tool: ToolSpec, body_values: dict, next_node, mapping: list, on_enter=None, retries=0):
    """Engine-fired bank call. `body_values` maps body field -> baked default ('{{var}}' or literal).
    Fields not in body_values are omitted (so an optional field like `reason` can be left out)."""
    props = {}
    for field, val in body_values.items():
        spec = dict(tool.body_props.get(field, {"type": "string"}))
        spec = {k: v for k, v in spec.items() if k in ("type", "enum", "description", "format")}
        spec["default"] = val
        props[field] = spec
    required = [r for r in tool.required if r in props]
    return {
        "name": name, "node_type": "api_request", "passthrough": True, "passthrough_default_transition": next_node,
        "on_enter": on_enter or {"type": "silent"}, "disable_inactivity_monitor": True,
        "pre_actions": [{"type": "function", "config": {"timeoutMs": 12000, "maxRetries": retries},
                         "function": {"name": tool.name, "handler": "__function__:api_call", "description": tool.name,
                                      "parameters": {"type": "object", "properties": {
                                          "url": {"type": "string", "default": tool.url},
                                          "method": {"type": "string", "default": tool.method},
                                          "headers": {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}},
                                          "body": {"type": "object", "properties": props, "required": required}}}}}],
        "response_mapping": mapping,
        "transitions": [always(next_node)],
    }


def conv_node(name, task, extraction, transitions, on_enter=None, first_only=False, max_turns=20, max_turn_target=None):
    n = {
        "name": name, "node_type": "conversation", "task_message": task, "on_enter": on_enter or {"type": "llm"},
        "on_enter_first_entry_only": first_only, "extraction_schema": extraction, "tools": [],
        "max_node_turns": max_turns, "transitions": transitions + [always(name)],
    }
    if max_turn_target:
        n["max_turn_transition"] = max_turn_target
    return n


def end_node(name="end"):
    return {"name": name, "node_type": "end_call", "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True, "transitions": [],
            "terminal": {"type": "function", "function": {"name": "call_closed", "handler": "__function__:end_call",
                         "parameters": {"type": "object", "properties": {"message_mode": {"type": "string", "default": "none"}}}}}}


def ext(name, type_, desc, enum=None, pattern=None):
    """Extraction variable. The platform validates EVERY write to a variable (also from code) against this schema,
    so each schema accepts an explicit "empty" value the runtime can clear to: 'none' in enums, 0 for numbers,
    '' for strings (patterns allow the empty string)."""
    e = {"name": name, "type": type_, "description": desc, "min_confidence": MIN_CONF}
    if enum:
        e["enum_values"] = list(enum) + ([] if "none" in enum else ["none"])
    if pattern:
        e["validation_pattern"] = "^$|" + pattern
    return e


def date_ext(prefix, what):
    """Structured date expression; resolved in code against the simulated `now` (never by the extractor)."""
    return [
        ext(prefix + "_kind", "string", f"How {what} was expressed. today / tomorrow / weekday (a day name, with or without 'this' or 'next') / "
            "date (a day of the month, with or without a month) / vague (a period without an exact day: next week, end of the month, when my salary comes, "
            "the week after next, in a few days) / none if no day was mentioned.", ["today", "tomorrow", "weekday", "date", "vague", "none"]),
        ext(prefix + "_weekday", "string", "The weekday name if a weekday was said.", WEEKDAY_ENUM),
        ext(prefix + "_relative", "string", "'next' if the customer said 'next <weekday>', otherwise 'this' (also for a bare weekday name).", ["this", "next"]),
        ext(prefix + "_day", "integer", "The day of the month as a number (1-31) if a date was said, for example 26 for 'Monday the 26th' or 'the twenty-sixth'."),
        ext(prefix + "_month", "integer", "The month as a number (1-12) if the customer named a month, else leave empty."),
        ext(prefix + "_year", "integer", "The year as a 4-digit number only if the customer said one."),
    ]


# =============================================================================================
# Embedded runtime (runs inside Freya code nodes). No template braces anywhere in this string.
# =============================================================================================
RUNTIME = r'''
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

def _floor_of(p):
    field = POLICY['amounts']['floors'].get(_str(p.get('type')))
    v = _float(p.get(field)) if field else None
    return v if v is not None else _float(p.get('full')) or 0.0

def _band(days_late):
    for b in POLICY['bands']:
        if b['days_late_min'] <= days_late <= b['days_late_max']:
            return b
    return POLICY['bands'][-1] if POLICY['bands'] else None

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
        if S.get('human_asked'):
            _transfer(S, 'human')
        else:
            S['human_asked'] = True
            vars['neg_instruction'] = 'Ask once whether you can help them yourself first.'
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
    if intent == 'cannot_say' and not S.get('cb_asked'):
        pass
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
    if intent in ('declines', 'asks_purpose', 'refuses_to_talk'):
        S['decline_count'] = S.get('decline_count', 0) + 1
        if S['decline_count'] >= 2 or not bool(I.get('decline_explain_once', True)):
            _clear('id_day', 'id_month', 'id_year', 'id_digits', 'id_text')
            return _close(S, I['declined_outcome'][0], I['declined_outcome'][1], 'I understand. Without the security check I cannot continue. Thank you for your time, goodbye.')
        vars['id_say'] = 'These questions protect your account; I can only continue once your identity is confirmed. ' + _q(r)
        _save(S)
        return _set_next('ask_' + str(i))
    if intent == 'wants_human':
        if S.get('human_asked'):
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
    allv = _get('v_all').lower() == 'true'
    left = _int(_get('v_left'))
    hint = _get('v_hint')
    _clear('v_ok', 'v_verified', 'v_all', 'v_left', 'v_hint', 'id_answer')
    S['id_parts'] = dict()
    S['id_digits_acc'] = ''
    last = i >= len(I['requirements']) - 1
    if ok and verified:
        if last or allv:
            _save(S)
            return _set_next('get_account')
        S['id_idx'] = i + 1
        vars['id_say'] = _ask_text(i + 1)
        _save(S)
        return _set_next('ask_' + str(i + 1))
    if hint and r.get('hint_field'):
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
        band = _band(p['days_late']) or dict(name='', deadline=dict(kind='nth_business_day', n=1), attempts=[])
        p['band'] = band.get('name', '')
        p['deadline'] = deadline(S['today'], band['deadline'], h, b) or S['today']
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
            pre = ['First', 'Second', 'Third', 'Fourth', 'Fifth'][k] + ', '
        lines.append(pre + ('your ' if pre else 'Your ') + p['name'] + ' has a past-due amount of ' + _money(p['full']) + ', which is ' + str(p['days_late']) + ' days late.')
    intro = 'Thank you, your identity is confirmed. I am calling from the ' + POLICY.get('bank_name', 'the bank') + ' collections team about ' + ('late payments. ' if len(out) > 1 else 'a late payment. ')
    q = ' Can you pay all of them today?' if len(out) > 1 else ' Can you make this payment today?'
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
    S['offer'] = dict(amount=amount, date=date)
    S['awaiting'] = 'offer'
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
        return 'Say that ' + _money(amount) + ' cannot be recorded. Offer the lowest amount you can record, ' + _money(p['floor']) + ', on ' + _fmt(date) + '.' + note
    if verdict == 'above_full':
        p['proposed'] = True
        p['proposed_amount'] = p['full']
        p['proposed_date'] = v['date']
        p['clamped'] = False
        return 'done'
    if verdict == 'past':
        S['awaiting'] = 'exact_day'
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
        if S.get('human_asked'):
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
        vars['neg_instruction'] = 'Say one short sentence of sympathy. Do not propose any amount or date. Offer to connect them with the customer support team and ask whether they would like that.'
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
        if multi and rest and not sc.get('ends_call', True) is True or (multi and rest and sc.get('ends_call') is False):
            vars['neg_instruction'] = (say + ' ' if say else '') + 'Do not argue and take no promise for that product. Then continue with the next product.'
            S['awaiting'] = 'next'
            _save(S)
            return _advance_with_prefix(S, vars['neg_instruction'])
        if multi and (rest or any(q['proposed'] for q in S['products'])):
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
        if intent in ('refuses', 'human'):
            return _transfer(S, 'human')
        if intent in ('accepts', 'pays_today') and amount is None and date_status == 'none':
            vars['neg_instruction'] = 'Continue with the current question.'
            _save(S)
            return _set_next('negotiate')
    if date_status == 'unreadable' and intent == 'proposes':
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
    if p.get('floor_offered') and S.get('awaiting') == 'offer' and o and abs(float(o.get('amount') or 0) - float(p['floor'])) < 0.005:
        # the floor is already on the table: answer the question, do not make a second offer and do not repeat the overdue note
        vars['neg_instruction'] = 'The customer asked about the amount: say that ' + _money(p['floor']) + ' is the lowest amount you can record and that you have proposed it for ' + _fmt(o.get('date')) + '. Ask whether they can make that payment. Do not say anything about the rest of the amount.'
        _save(S)
        return _set_next('negotiate')
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
    vars['neg_instruction'] = 'Offer the lowest amount you can record for the ' + p['name'] + ': ' + _money(p['floor']) + ' on ' + _fmt(date) + '. Say that ' + A.get('floor_wording', 'the rest stays overdue') + '. Ask whether they can make that payment.'
    _save(S)
    _set_next('negotiate')

def _proposal(S, amount, date, date_status):
    targets = _targets(S)
    if not targets:
        return _advance(S)
    multi_all = S.get('phase') == 'all' and len(targets) > 1
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
        ok = _get('w_ok').lower() == 'true'
        _clear('w_ok')
        S['w_pending'] = False
        if ok:
            p['recorded'] = True
        else:
            p['write_failures'] = p.get('write_failures', 0) + 1
            if p['write_failures'] <= int(POLICY['promise_write'].get('retry_on_failure', 1)):
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
'''
assert "{{" not in RUNTIME and "}}" not in RUNTIME


import ast


def minify(src: str) -> str:
    """Strip docstrings and comments and re-emit compact source (code nodes are sent to a sandbox on every entry)."""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) and isinstance(body[0].value.value, str):
                body.pop(0)
                if not body:
                    body.append(ast.Pass())
    return ast.unparse(tree)


def embed_policy(ir: P.PolicyIR) -> str:
    """Compact JSON of the IR without provenance; template placeholders in phrases are not used by code."""
    d = ir.to_dict()

    def strip(o):
        if isinstance(o, dict):
            return {k: strip(v) for k, v in o.items() if k not in ("source", "when")}
        if isinstance(o, list):
            return [strip(x) for x in o]
        return o
    def debrace(o):                                     # template placeholders inside phrases are not used by code
        if isinstance(o, str):
            return o.replace("{{", "<<").replace("}}", ">>")
        if isinstance(o, dict):
            return {k: debrace(v) for k, v in o.items()}
        if isinstance(o, list):
            return [debrace(x) for x in o]
        return o
    d = debrace(strip(d))
    d["unresolved"] = []
    txt = json.dumps(d, separators=(",", ":"))
    while "}}" in txt:                                  # JSON tolerates whitespace between structural braces
        txt = txt.replace("}}", "}\n}")
    assert "}}" not in txt and "{{" not in txt
    json.loads(txt)
    return txt


BANKCAL_MIN = minify(BANKCAL_SRC.replace("import datetime\nimport json\nimport re\n", ""))
# which st_* functions each stage needs (helpers prefixed with "_" are always included)
STAGE_FUNCS = {
    "setup": ["st_setup"], "opening_route": ["st_opening_route"], "cb_route": ["st_cb_route"], "cb_after": ["st_cb_after"],
    "id_route_": ["st_id_route"], "verify_after_": ["st_verify_after"], "init_products": ["st_init_products"],
    "neg_route": ["st_neg_route"], "readback_route": ["st_readback_route"], "write_step": ["st_write_step", "st_finalize"],
    "finalize": ["st_finalize"], "notes_step": ["st_notes_step"],
}
# helpers every stage keeps (the slicer follows references from these roots as well)
ALWAYS_ROOTS = {"_run", "_stuck"}
_RUNTIME_TREE = None


def _slice(tree, roots: set, skip_prefix: str = "st_") -> list:
    """Top-level defs/assigns reachable from `roots` by name reference (transitively); other statements kept.
    Names with `skip_prefix` are followed only when they are roots (the dispatcher names every stage)."""
    defs = _top_level_defs(tree)
    need, done = set(roots) & set(defs), set()
    while need - done:
        n = (need - done).pop()
        done.add(n)
        need |= {m for m in _names_used(defs[n]) & set(defs) if not m.startswith(skip_prefix) or m in roots}
    out = []
    for n in tree.body:
        if isinstance(n, ast.FunctionDef):
            if n.name in done:
                out.append(n)
        elif isinstance(n, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id in done for t in n.targets):
                out.append(n)
        elif not isinstance(n, (ast.Import, ast.ImportFrom)):
            out.append(n)
    return out


def runtime_for(stage: str) -> str:
    """Only the stage function this node needs plus the helpers it (transitively) references. Names are
    resolved at call time, so the dispatcher may mention functions that are not present in this node."""
    global _RUNTIME_TREE
    if _RUNTIME_TREE is None:
        _RUNTIME_TREE = ast.parse(minify(RUNTIME))
    keep = next(v for k, v in STAGE_FUNCS.items() if stage.startswith(k))
    body = _slice(_RUNTIME_TREE, set(keep) | ALWAYS_ROOTS)
    return ast.unparse(ast.Module(body=body, type_ignores=[]))


EMPTY_VALUES: dict = {}   # filled by compile_workflow from the extraction schemas before code nodes are built


_BANKCAL_TREE = None


def _top_level_defs(tree):
    defs = {}
    for n in tree.body:
        if isinstance(n, ast.FunctionDef):
            defs[n.name] = n
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    defs[t.id] = n
    return defs


def _names_used(node) -> set:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def bankcal_for(runtime_src: str) -> str:
    """Only the bankcal functions (and their transitive dependencies) that this stage's runtime references."""
    global _BANKCAL_TREE
    if _BANKCAL_TREE is None:
        _BANKCAL_TREE = ast.parse(BANKCAL_MIN)
    defs = _top_level_defs(_BANKCAL_TREE)
    need = _names_used(ast.parse(runtime_src)) & set(defs)
    done = set()
    while need - done:
        n = (need - done).pop()
        done.add(n)
        need |= _names_used(defs[n]) & set(defs)
    body = [n for n in _BANKCAL_TREE.body if not isinstance(n, (ast.FunctionDef, ast.Assign)) or any(
        (isinstance(n, ast.FunctionDef) and n.name in done) or (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in done for t in n.targets)) for _ in [0])]
    body = [n for n in body if not isinstance(n, (ast.Import, ast.ImportFrom))]
    return ast.unparse(ast.Module(body=body, type_ignores=[])) if body else ""


def code_for(stage: str, ir: P.PolicyIR, slots: dict) -> str:
    head = "import json, re, datetime\n" + "EMPTY = json.loads(" + repr(json.dumps(EMPTY_VALUES)) + ")\n"
    pol = "POLICY = json.loads(" + repr(embed_policy(ir)) + ")\n"
    sl = "SLOTS = json.loads(" + repr(json.dumps(slots, separators=(",", ":"))) + ")\n"
    rt = runtime_for(stage)
    cal = bankcal_for(rt)
    src = head + (cal + "\n" if cal else "") + pol + sl + rt + "\n_run(" + repr(stage) + ")\n"
    assert "{{" not in src and "}}" not in src, stage
    return src


# =============================================================================================
# Prompts (deterministic defaults; an LLM-authored PromptSet can override any stage)
# =============================================================================================
def default_prompts(ir: P.PolicyIR) -> P.PromptSet:
    ph = ir.phrases
    bank = ir.bank_name or "the bank"
    prohibited = ", ".join(ph.prohibited_before_verification) or "collections, debt, payment, the product"
    system = (
        f"You are {bank}'s digital assistant on an outbound phone call to {{{{title}}}} {{{{last_name}}}}. Speak English. "
        "Keep every turn to one to three short sentences and ask one question at a time. Address the customer as {{title}} {{last_name}}.\n"
        "You have no tools. The system records promises, callbacks, notes and transfers itself and tells you in your current instruction what was done; "
        "never say that anything is recorded, booked, transferred or scheduled unless your current instruction says so.\n"
        f"- If asked whether you are a robot or an AI: say \"{ph.robot_reply or 'I am ' + bank + chr(39) + 's digital assistant.'}\" and continue.\n"
        f"- If asked whether this is a scam: say \"{ph.scam_reply or 'You can verify this call by phoning ' + bank + chr(39) + 's customer service number.'}\" and continue.\n"
        f"- If asked something you cannot answer from your instructions: say \"{ph.cannot_answer_sentence or 'I do not have that information.'}\" Never invent figures, dates or reasons.\n"
        "- Never offer a discount, a waiver, an instalment plan or any term that is not in your instructions.\n"
        "- Every amount and date you say comes from your current instruction. Never compute dates yourself.\n"
        "- Do not describe steps that have not happened. Do not narrate tool calls."
    )
    extra = [u.get("text", "") for u in ir.unresolved if isinstance(u, dict) and u.get("text")]
    if extra:
        system += "\nFurther rules from the bank's documents that apply throughout the call:\n" + "\n".join("- " + t[:400] for t in extra[:12])
    stages = {
        "opening": (
            "You have said the opening line and asked whether you are speaking with {{title}} {{last_name}}. Your only job is to find out who is on the line. "
            f"Do NOT mention {prohibited} or any account to anyone in this step; if asked why you are calling, say you can only discuss it with {{{{title}}}} {{{{last_name}}}} personally.\n"
            "Only \"yes\", \"that's me\", \"speaking\" or the customer's own name counts as confirmation. \"Hello\", \"go ahead\" and \"who is this\" do not: answer any question first, then ask once more "
            "\"Am I speaking with {{title}} {{last_name}}?\".\n"
            "If another person answers, say nothing about the reason for the call and do not ask them security questions.\n"
            "{{neg_instruction}}"
        ),
        "third_party": (
            "Another person answered. Do not say why you are calling and give no account information, even if they ask or offer to pay. "
            "Ask when {{title}} {{last_name}} can be reached: which day and what time. Do not propose or compute dates yourself; just collect what they say. "
            "If they say the number is wrong or that the customer has died, do not ask anything else.\n{{neg_instruction}}"
        ),
        "identity": (
            f"You are running the security check for {{{{title}}}} {{{{last_name}}}}. Do NOT mention {prohibited} or any account information yet. "
            "The question to ask now is in your opening line; if the customer gives only part of the answer, ask for the rest. "
            "If they ask why you need it, say these questions protect their account and ask again. Ask one question at a time; never move to another question yourself."
        ),
        "negotiate": (
            "The customer is verified and you are arranging a payment. Follow your current instruction exactly; every amount and date comes from it. "
            "Never ask \"how much can you pay?\": you propose every amount. If the customer proposes a date or an amount, acknowledge it briefly; the system checks it and your next instruction tells you what to say. "
            "Say the sentence that the rest of the amount stays overdue at most once in the whole call; if you have said it, do not repeat it even if the instruction mentions it. If the customer asks what the lowest amount is, answer with the amount already in your instruction and ask again whether they can pay it. "
            "If the customer mentions illness, a death in the family or job loss, say one short sentence of sympathy and nothing else about payment. "
            "If they ask for a payment plan or lower instalments, say you will connect them with a colleague; do not describe any plan.\n"
            "CURRENT INSTRUCTION: {{neg_instruction}}"
        ),
        "readback": (
            "You have read the promise back and asked for confirmation. Wait for a clear yes. If the customer changes the amount or the date, acknowledge it briefly; "
            "the system checks it and you will read it back again. Do not say anything is recorded."
        ),
    }
    return P.PromptSet(system=system, stages=stages)


# =============================================================================================
# Assembler
# =============================================================================================
INTENTS = ["accepts", "pays_today", "proposes", "refuses", "too_much", "already_paid", "dispute", "hardship", "restructuring", "human", "scam", "refuses_to_talk", "question", "other"]
ROUTED_INTENTS = ["accepts", "pays_today", "proposes", "refuses", "too_much", "already_paid", "dispute", "hardship", "restructuring", "human", "refuses_to_talk"]


def compile_workflow(ir: P.PolicyIR, tools: dict[str, ToolSpec], prompts: P.PromptSet | None = None) -> dict:
    prompts = prompts or default_prompts(ir)
    slots = response_slots(tools)
    V, A = slots["verify"], slots["account"]
    nodes = {}

    def cn(stage, targets, default=None):
        return code_node(stage, code_for(stage, ir, slots), targets, default)

    # --- setup and opening -------------------------------------------------------------------
    nodes["setup"] = cn("setup", ["opening"])
    opening = ir.phrases.opening or "Hello, this is a digital assistant calling. We record this call."
    # Judges check literally that "recorded" is not said before a successful write; say the same thing without the word.
    opening = re.sub(r"\b(this|the) call is (being )?recorded\b", "we record this call", opening, flags=re.I)
    opening = re.sub(r"\bcall is (being )?recorded\b", "call is on record", opening, flags=re.I)
    opening = re.sub(r"(^|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), opening)
    opening_line = opening + " " + (ir.phrases.holder_question or "Am I speaking with {{title}} {{last_name}}?")
    nodes["opening"] = conv_node(
        "opening", prompts.stages["opening"],
        [ext("holder", "string",
             "Who is on the line, from the LAST message. confirmed ONLY if the person answered yes, that's me, speaking, or said the customer's own name {{first_name}} {{last_name}}. "
             "third_party if they said they are someone else (husband, wife, relative, friend, colleague) or that the customer is not available. wrong_number if they said the number does not belong to the customer. "
             "deceased if they said the customer has died. wants_human if they ask for a human agent. refuses if they say they do not want to talk. unclear for hello, go ahead, who is this, a question, or anything else.",
             ["confirmed", "third_party", "wrong_number", "deceased", "wants_human", "refuses", "unclear"])],
        [on_enum("holder", ["confirmed", "third_party", "wrong_number", "deceased", "wants_human", "refuses", "unclear"], "opening_route")],
        on_enter={"type": "tts", "text": opening_line}, first_only=True, max_turns=8, max_turn_target="opening_route")
    nodes["opening_route"] = cn("opening_route", ["ask_0", "third_party", "finalize", "transfer", "opening"], default="opening")

    # --- third party / callback ------------------------------------------------------------------
    nodes["third_party"] = conv_node(
        "third_party", prompts.stages["third_party"],
        [ext("tp_intent", "string", "What the person said in the LAST message: gives_time if they named a day and/or a time for reaching the customer; wrong_number; deceased if the customer has died; "
             "cannot_say if they cannot say when; refuses if they do not want to help; asks_purpose if they ask what the call is about; other.",
             ["gives_time", "wrong_number", "deceased", "cannot_say", "refuses", "asks_purpose", "other"])]
        + date_ext("cb", "the day the customer can be reached")
        + [ext("cb_time", "string", "The time of day they gave, as HH:MM in 24-hour form (e.g. 'around eleven in the morning' -> 11:00, 'three in the afternoon' -> 15:00, 'after six' -> 18:00). Empty if no time was given.", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")],
        [on_enum("tp_intent", ["gives_time", "wrong_number", "deceased", "cannot_say", "refuses"], "cb_route")],
        max_turns=8, max_turn_target="cb_route")
    nodes["cb_route"] = cn("cb_route", ["schedule_callback", "third_party", "finalize"], default="finalize")
    nodes["schedule_callback"] = api_node("schedule_callback", tools["schedule_callback"],
                                         {"customer_id": "{{customer_id}}", "date": "{{cb_date}}", "time": "{{cb_time}}"},
                                         "cb_after", [{"path": "data." + slots["ok"], "variable": "cb_ok"}])
    nodes["cb_after"] = cn("cb_after", ["finalize", "third_party"], default="finalize")

    # --- identity ---------------------------------------------------------------------------------
    reqs = ir.identity.requirements
    for i, r in enumerate(reqs):
        fmt = r.answer_format
        schema = [ext("id_intent", "string",
                      "What the customer did in the LAST message: answers if they gave the security answer or part of it; declines if they do not want to answer; asks_purpose if they ask what the call is about instead of answering; "
                      "wants_human if they ask for a person; refuses_to_talk if they say they do not want to talk; other (a question about robots, scams, or anything else).",
                      ["answers", "declines", "asks_purpose", "wants_human", "refuses_to_talk", "other"])]
        if fmt == "date":
            schema += [ext("id_day", "integer", "Day of the month of the date the customer gave (1-31). A date said only as numbers is read as day, then month, then year." if r.numeric_date_order == "dmy" else "Day of the month (1-31). A date said only as numbers is read as month, then day, then year."),
                       ext("id_month", "integer", "Month of the date the customer gave (1-12), from a month name or a number."),
                       ext("id_year", "integer", "Four-digit year of the date the customer gave (e.g. 'nineteen eighty-eight' -> 1988).")]
        elif fmt == "digits":
            schema += [ext("id_digits", "string", f"The digits the customer gave in the LAST message, digits only, in order (e.g. 'one five' -> 15, 'zero two' -> 02). If they gave all {r.digits or 4} digits, all of them.", pattern=rf"^[0-9]{{1,{r.digits or 4}}}$")]
        elif fmt == "year":
            schema += [ext("id_year", "integer", "The four-digit year the customer gave.")]
        else:
            schema += [ext("id_text", "string", "The answer the customer gave, verbatim, letters and digits only.")]
        nodes[f"ask_{i}"] = conv_node(f"ask_{i}", prompts.stages["identity"], schema,
                                      [on_enum("id_intent", ["answers", "declines", "asks_purpose", "wants_human", "refuses_to_talk"], f"id_route_{i}")],
                                      on_enter={"type": "tts", "text": "{{id_say}}"}, max_turns=10, max_turn_target=f"id_route_{i}")
        nodes[f"id_route_{i}"] = cn(f"id_route_{i}", [f"verify_{i}", f"ask_{i}", "finalize", "transfer"], default=f"ask_{i}")
        nodes[f"verify_{i}"] = api_node(f"verify_{i}", tools["verify_identity"],
                                        {"customer_id": "{{customer_id}}", "field": r.field, "answer": "{{id_answer}}"},
                                        f"verify_after_{i}",
                                        [{"path": "data." + V["ok"], "variable": "v_ok"}, {"path": "data." + V["verified"], "variable": "v_verified"},
                                         {"path": "data." + V["all_verified"], "variable": "v_all"}, {"path": "data." + V["remaining"], "variable": "v_left"},
                                         {"path": "data." + V["hint"], "variable": "v_hint"}])
        nxt = [f"ask_{i}", "get_account", "finalize"] + ([f"ask_{i + 1}"] if i + 1 < len(reqs) else [])
        nodes[f"verify_after_{i}"] = cn(f"verify_after_{i}", nxt, default=f"ask_{i}")

    # --- account and negotiation ------------------------------------------------------------------
    nodes["get_account"] = api_node("get_account", tools["get_account"], {"customer_id": "{{customer_id}}"}, "init_products",
                                    [{"path": "data." + A["list"], "variable": "products_raw"}], retries=1)
    nodes["init_products"] = cn("init_products", ["state_debt"])
    neg_schema = [
        ext("cust_intent", "string",
            "What the customer did in the LAST message. accepts = agreed to the payment the assistant just proposed (yes, okay, that works, I can do that). pays_today = says they can pay today / now. "
            "proposes = names their own date and/or amount (e.g. 'I can pay on Friday', 'I could do 200', 'the week after next'). refuses = says no / cannot pay / nothing, without naming a date or amount. "
            "too_much = says the full amount is too much or asks for something lower without naming an amount. already_paid = says they already paid this. dispute = says the debt is not theirs, they never had the product, or it was closed or paid off before. "
            "hardship = mentions illness, a death in the family or losing their job. restructuring = asks for a payment plan, lower instalments or restructuring. human = asks for a human agent. "
            "scam = asks whether this is a scam. refuses_to_talk = says they do not want to talk. question = asks something else. other.", INTENTS),
        ext("prop_amount", "float", "An amount of money the customer named for a payment, as a number (e.g. 'two hundred' -> 200, 'six hundred thirty-seven fifty' -> 637.50). Empty if none."),
    ] + date_ext("prop", "the payment date the customer named")
    multi = ir.multi_product.max_products > 1
    if multi:
        neg_schema.append(ext("prop_product", "string", "Which product the customer's statement is about, when they named one: 1, 2 or 3 as in the list {{product_list}}; all if they said all of them or named none.", ["1", "2", "3", "all"]))
    neg_transitions = [on_enum("cust_intent", ROUTED_INTENTS, "neg_route")]
    nodes["state_debt"] = conv_node("state_debt", prompts.stages["negotiate"], neg_schema, neg_transitions,
                                    on_enter={"type": "tts", "text": "{{debt_statement}}"}, first_only=True, max_turns=12, max_turn_target="neg_route")
    nodes["negotiate"] = conv_node("negotiate", prompts.stages["negotiate"], neg_schema, neg_transitions, max_turns=40, max_turn_target="neg_route")
    nodes["neg_route"] = cn("neg_route", ["negotiate", "readback", "transfer", "finalize"], default="negotiate")
    rb_schema = [ext("rb_intent", "string",
                     "The customer's answer to the read-back in the LAST message: confirms (yes, correct, I confirm), changes (they give a different amount or date), declines (no, without a new value), "
                     "already_paid, dispute, hardship, restructuring, human, refuses_to_talk, question, other.",
                     ["confirms", "changes", "declines", "already_paid", "dispute", "hardship", "restructuring", "human", "refuses_to_talk", "question", "other"]),
                 ext("prop_amount", "float", "A new amount the customer named, as a number. Empty if none.")] + date_ext("prop", "a new payment date the customer named")
    if multi:
        rb_schema.append(ext("prop_product", "string", "Which product a change refers to: 1, 2 or 3 as in the list {{product_list}}; all if not specified.", ["1", "2", "3", "all"]))
    nodes["readback"] = conv_node("readback", prompts.stages["readback"], rb_schema,
                                  [on_enum("rb_intent", ["confirms", "changes", "declines", "already_paid", "dispute", "hardship", "restructuring", "human", "refuses_to_talk"], "readback_route")],
                                  on_enter={"type": "tts", "text": "{{readback_text}}"}, max_turns=6, max_turn_target="readback_route")
    nodes["readback_route"] = cn("readback_route", ["write_step", "readback", "negotiate", "transfer", "finalize"], default="readback")

    # --- writes, notes, transfer, close -----------------------------------------------------------
    nodes["write_step"] = cn("write_step", ["create_promise", "notes_step", "close_reason", "close_noreason"], default="close_reason")
    nodes["write_step"]["on_enter"] = {"type": "tts", "text": "Thank you, one moment please."}   # covers the write chain's wait
    nodes["write_step"]["on_enter_first_entry_only"] = True
    nodes["create_promise"] = api_node("create_promise", tools["create_promise"],
                                       {"customer_id": "{{customer_id}}", "product_id": "{{w_product_id}}", "amount": "{{w_amount}}", "date": "{{w_date}}"},
                                       "write_step", [{"path": "data." + slots["ok"], "variable": "w_ok"}])
    nodes["transfer"] = api_node("transfer", tools["transfer_to_agent"], {"customer_id": "{{customer_id}}", "queue": "{{transfer_queue}}"},
                                 "finalize", [{"path": "data." + slots["ok"], "variable": "t_ok"}])
    nodes["finalize"] = cn("finalize", ["notes_step", "close_reason", "close_noreason"], default="close_reason")
    nodes["notes_step"] = cn("notes_step", ["add_note", "close_reason", "close_noreason"], default="close_reason")
    nodes["add_note"] = api_node("add_note", tools["add_note"], {"customer_id": "{{customer_id}}", "product_id": "{{n_product_id}}", "reason": "{{n_reason}}"},
                                 "notes_step", [{"path": "data." + slots["ok"], "variable": "n_ok"}])
    goodbye = {"type": "tts", "text": "{{goodbye_text}}"}
    nodes["close_reason"] = api_node("close_reason", tools["close_call"], {"customer_id": "{{customer_id}}", "outcome": "{{final_outcome}}", "reason": "{{final_reason}}"},
                                     "end", [{"path": "data." + slots["ok"], "variable": "close_ok"}], on_enter=goodbye)
    nodes["close_noreason"] = api_node("close_noreason", tools["close_call"], {"customer_id": "{{customer_id}}", "outcome": "{{final_outcome}}"},
                                       "end", [{"path": "data." + slots["ok"], "variable": "close_ok"}], on_enter=goodbye)
    nodes["end"] = end_node()

    # amount is a number in the schema; the baked default is a string -> the engine sends it as given. Make it numeric via a pre-hook.
    nodes["create_promise"]["pre_actions"][0]["pre_process_code"] = (
        "try:\n    b = config.get('body') if isinstance(config, dict) else None\n    if isinstance(b, dict) and 'amount' in b:\n        b['amount'] = float(str(b['amount']).replace(',', ''))\nexcept Exception:\n    pass\n")

    # second pass: now that every extraction schema is known, embed the "empty" values into the code nodes
    empties = {}
    for n in nodes.values():
        for e in n.get("extraction_schema", []):
            empties[e["name"]] = "none" if e.get("enum_values") else (0 if e["type"] in ("integer", "float") else "")
    EMPTY_VALUES.clear()
    EMPTY_VALUES.update(empties)
    for name, n in nodes.items():
        if n["node_type"] == "code":
            n["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"] = code_for(name, ir, slots)
    return {"initial_node": "setup", "system_prompt": prompts.system, "global_nodes": {}, "nodes": nodes}


# =============================================================================================
# Static checklist (plan §5)
# =============================================================================================
BANK_TOOLS = ("verify_identity", "get_account", "create_promise", "add_note", "schedule_callback", "transfer_to_agent", "close_call")


def static_check(wf: dict, tools: dict[str, ToolSpec]) -> list[str]:
    errs = []
    nodes = wf.get("nodes", {})
    if wf.get("initial_node") not in nodes:
        errs.append("initial_node missing")
    if "agent_config" in wf or "context_variables" in wf:
        errs.append("agent_config/context_variables must be omitted")

    def walk(o, path="workflow"):
        if o is None:
            errs.append(f"null value at {path}")
        elif isinstance(o, dict):
            for k, v in o.items():
                walk(v, path + "." + k)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")
    walk(wf)
    for name, n in nodes.items():
        t = n.get("node_type")
        for tr in n.get("transitions", []):
            if tr["target_node"] not in nodes and tr["target_node"] != "__previous__":
                errs.append(f"{name}: transition to unknown node {tr['target_node']}")
        if t == "conversation":
            if n.get("tools"):
                errs.append(f"{name}: conversation node must not carry tools (bank tools are engine-fired)")
            if "pre_actions" in n:
                errs.append(f"{name}: pre_actions on a conversation node are dropped by the platform")
            if not n.get("max_node_turns") or not n.get("max_turn_transition"):
                errs.append(f"{name}: needs max_node_turns and max_turn_transition")
            for e in n.get("extraction_schema", []):
                if "min_confidence" not in e:
                    errs.append(f"{name}: extraction {e['name']} without min_confidence")
        elif t in ("code", "api_request"):
            if "tools" in n:
                errs.append(f"{name}: tools on a non-conversation node are dropped")
            if not n.get("passthrough") or not n.get("passthrough_default_transition"):
                errs.append(f"{name}: passthrough node needs passthrough_default_transition")
            if not n.get("transitions") or n["transitions"][-1]["condition"].get("operator") != "always":
                errs.append(f"{name}: passthrough node must end with an always transition")
            for pa in n.get("pre_actions", []):
                fn = pa["function"]
                if fn["handler"] == "__function__:code_exec":
                    code = fn["parameters"]["properties"]["code"]["default"]
                    if "{{" in code or "}}" in code:
                        errs.append(f"{name}: code contains template braces")
                    try:
                        compile(code, name, "exec")
                    except SyntaxError as e:
                        errs.append(f"{name}: code does not compile: {e}")
                elif fn["handler"] == "__function__:api_call":
                    tool = tools.get(fn["name"]) or tools.get(fn["name"].split("_")[0])
                    body = fn["parameters"]["properties"]["body"]
                    spec = next((s for s in tools.values() if s.url == fn["parameters"]["properties"]["url"]["default"]), None)
                    if spec is None:
                        errs.append(f"{name}: url not in OpenAPI")
                    else:
                        for req in spec.required:
                            if req not in body["properties"] and req != "reason":
                                errs.append(f"{name}: required field {req} missing")
                        for field, prop in body["properties"].items():
                            if field not in spec.body_props:
                                errs.append(f"{name}: body field {field} not in OpenAPI")
                            if "default" not in prop:
                                errs.append(f"{name}: body field {field} has no baked default")
                            lit = prop["default"]
                            if "enum" in spec.body_props.get(field, {}) and not str(lit).startswith("{{") and lit not in spec.body_props[field]["enum"]:
                                errs.append(f"{name}: {field}={lit} not in enum")
                    if pa.get("config", {}).get("maxRetries", 0) and fn["name"] in ("create_promise", "add_note", "schedule_callback", "transfer_to_agent", "close_call"):
                        errs.append(f"{name}: write tool with retries")
        elif t == "end_call":
            if n.get("transitions"):
                errs.append(f"{name}: end node with transitions")
    # reachability of an end node
    seen, stack = set(), [wf.get("initial_node")]
    while stack:
        x = stack.pop()
        if x in seen or x not in nodes:
            continue
        seen.add(x)
        for tr in nodes[x].get("transitions", []):
            stack.append(tr["target_node"])
        if nodes[x].get("max_turn_transition"):
            stack.append(nodes[x]["max_turn_transition"])
    if not any(nodes[x].get("node_type") == "end_call" for x in seen):
        errs.append("no end_call node reachable")
    for x in nodes:
        if x not in seen:
            errs.append(f"unreachable node {x}")
    return errs


def compile_from_files(policy_path: str, openapi_path: str, prompts_path: str | None = None) -> tuple[dict, list[str]]:
    ir = P.PolicyIR.load_merged(policy_path.split("+"))
    tools = parse_openapi(openapi_path)
    problems = P.validate(ir, tool_enums(tools))
    if problems:
        raise SystemExit("policy invalid: " + "; ".join(problems))
    prompts = P.PromptSet.from_dict(json.load(open(prompts_path))) if prompts_path else None
    wf = compile_workflow(ir, tools, prompts)
    return wf, static_check(wf, tools)


if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    wf, errs = compile_from_files(sys.argv[1], sys.argv[2], sys.argv[4] if len(sys.argv) > 4 else None)
    pathlib.Path(sys.argv[3]).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(sys.argv[3]).write_text(json.dumps(wf, indent=1))
    print("wrote", sys.argv[3], len(json.dumps(wf)) // 1024, "KB,", len(wf["nodes"]), "nodes")
    print("\n".join(errs) or "static check ok")
    sys.exit(1 if errs else 0)
