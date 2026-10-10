"""Generates out/brief-b.workflow.json (Brief A + Brief B agent)."""
import json, pathlib

BASE = "https://freya-bank-mock.freyavoice.workers.dev/v1/"
HDR = {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}}

SETUP_CODE = r'''
import datetime
HOL = ['2026-10-26', '2026-11-11', '2026-11-26', '2026-12-25', '2027-01-01']
DN = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
def isbd(d):
    return d.weekday() < 5 and d.isoformat() not in HOL
def nextbd(d):
    d = d + datetime.timedelta(days=1)
    while not isbd(d):
        d = d + datetime.timedelta(days=1)
    return d
def lab(d):
    return DN[d.weekday()] + ' ' + d.strftime('%d %B %Y') + ' (' + d.isoformat() + ')'
try:
    now = str(vars.get('now') or '')
    dt = datetime.datetime.fromisoformat(now[:16])
    today = dt.date()
    hm = dt.strftime('%H:%M')
    nb = nextbd(today)
    tom = today + datetime.timedelta(days=1)
    lines = ['Now: ' + lab(today) + ', time ' + hm + '.']
    if hm < '19:00':
        lines.append('Allowed callback: today ' + today.isoformat() + ' at a time later than ' + hm + ' and from 10:00 to 19:00 (both included).')
    else:
        lines.append('No callback is possible today any more.')
    lines.append('Allowed callback: ' + lab(nb) + ' at any time from 10:00 to 19:00 (both included).')
    if tom != nb:
        lines.append('Tomorrow, ' + lab(tom) + ', is NOT a business day and is not allowed.')
    else:
        lines.append('Tomorrow is ' + lab(tom) + '.')
    lines.append('Every other day, and every time before 10:00 or after 19:00, is outside the window.')
    vars['callback_rules'] = '\n'.join(lines)
except Exception:
    vars['callback_rules'] = 'Allowed callback: today or the next business day, from 10:00 to 19:00, later than now (' + str(vars.get('now')) + ').'
'''

FACTS_CODE = r'''
import datetime, json
HOL = ['2026-10-26', '2026-11-11', '2026-11-26', '2026-12-25', '2027-01-01']
DN = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
def isbd(d):
    return d.weekday() < 5 and d.isoformat() not in HOL
def nextbd(d):
    d = d + datetime.timedelta(days=1)
    while not isbd(d):
        d = d + datetime.timedelta(days=1)
    return d
def nth_bd(d, n):
    for i in range(n):
        d = nextbd(d)
    return d
def lastbd_of_week(d):
    mon = d - datetime.timedelta(days=d.weekday())
    best = None
    for i in range(5):
        x = mon + datetime.timedelta(days=i)
        if isbd(x):
            best = x
    return best
def lab(d):
    return DN[d.weekday()] + ' ' + str(d.day) + ' ' + d.strftime('%B') + ' (' + d.isoformat() + ')'
def money(x):
    try:
        return '%.2f' % float(x)
    except Exception:
        return str(x)
def products():
    p = vars.get('products')
    if isinstance(p, str):
        try:
            p = json.loads(p)
        except Exception:
            p = None
    if isinstance(p, dict):
        p = [p]
    if isinstance(p, list) and p:
        return p
    out = []
    for i in range(6):
        q = dict()
        for k in ('product_id', 'type', 'card_last4', 'past_due', 'days_late', 'minimum_payment', 'instalment_amount'):
            for key in ('load_account_response.data.products.' + str(i) + '.' + k, 'get_account_response.data.products.' + str(i) + '.' + k, 'products.' + str(i) + '.' + k):
                if vars.get(key) is not None:
                    q[k] = vars.get(key)
        if q:
            out.append(q)
    return out
try:
    now = str(vars.get('now') or '')
    today = datetime.datetime.fromisoformat(now[:16]).date()
    a1 = lastbd_of_week(today)
    if a1 is None or a1 <= today:
        a1 = lastbd_of_week(today + datetime.timedelta(days=7))
    prods = products()
    lines = []
    say = []
    maxdl = today
    dls = []
    for i, p in enumerate(prods):
        t = str(p.get('type') or '')
        if t == 'credit_card':
            name = 'credit card ending ' + str(p.get('card_last4') or '')
            floor = p.get('minimum_payment')
        elif t == 'car_loan':
            name = 'car loan'
            floor = p.get('instalment_amount')
        else:
            name = 'personal loan'
            floor = p.get('instalment_amount')
        dl_ = int(float(p.get('days_late') or 0))
        if dl_ <= 7:
            band, n, att = 'early', 12, 1
        else:
            band, n, att = 'late', 7, 2
        dl = nth_bd(today, n)
        dls.append((name, dl))
        if dl > maxdl:
            maxdl = dl
        due = money(p.get('past_due'))
        say.append('Your ' + name + ' has a past-due amount of ' + due + ', ' + str(dl_) + ' days late.')
        s = ['PRODUCT ' + str(i + 1) + ': ' + name + ', product_id ' + str(p.get('product_id')) + '.',
             '  Full past-due amount: ' + due + '. Days late: ' + str(dl_) + ' (' + band + ' band).',
             '  Floor (lowest amount that can be recorded): ' + money(floor) + '.',
             '  Deadline (latest promise date): ' + lab(dl) + '.',
             '  Persuasion attempts allowed: ' + str(att) + '.',
             '  Attempt 1: the full amount ' + due + ' (or the floor ' + money(floor) + ' if the customer already said the full amount is too much) on ' + lab(a1) + '.']
        if att == 2:
            s.append('  Attempt 2: the floor ' + money(floor) + ' on the deadline ' + lab(dl) + '.')
        else:
            s.append('  No attempt 2 for this product (early band). After attempt 1 is refused, this product is refused.')
        lines.append('\n'.join(s))
    cal = []
    d = today
    end = maxdl + datetime.timedelta(days=10)
    while d <= end:
        tag = 'business day'
        if d.weekday() >= 5:
            tag = 'WEEKEND, not allowed; next business day is ' + lab(nextbd(d))
        elif d.isoformat() in HOL:
            tag = 'BANK HOLIDAY, not allowed; next business day is ' + lab(nextbd(d))
        if d == today:
            tag = 'TODAY, ' + tag
        late = [nm for (nm, x) in dls if d > x]
        if late:
            tag = tag + '; AFTER the deadline of: ' + ', '.join(late)
        cal.append('- ' + lab(d) + ': ' + tag)
        d = d + datetime.timedelta(days=1)
    mon = today - datetime.timedelta(days=today.weekday())
    wk = []
    for i in range(7):
        x = mon + datetime.timedelta(days=i)
        y = x + datetime.timedelta(days=7)
        wk.append('- "this ' + DN[i] + '" = ' + x.isoformat() + ('  (in the past, not allowed)' if x < today else '') + '; "next ' + DN[i] + '" = ' + y.isoformat())
    vars['n_products'] = str(len(prods))
    vars['account_facts'] = ('Today: ' + lab(today) + '.\n\n' + '\n\n'.join(lines) +
        '\n\nCALENDAR (use it for every date; never compute dates yourself):\n' + '\n'.join(cal) +
        '\n\nWEEKDAY WORDS:\n' + '\n'.join(wk))
    if len(prods) > 1:
        ask = 'Can you pay all of them today?'
    else:
        ask = 'Can you make this payment today?'
    vars['debt_statement'] = 'Thank you, you are verified. I am calling from the Freya Bank collections team about a late payment. ' + ' '.join(say) + ' ' + ask
except Exception as e:
    vars['n_products'] = '1'
    vars['account_facts'] = 'Account data could not be prepared: ' + str(e) + '. Raw: ' + str(vars.get('products'))
    vars['debt_statement'] = 'Thank you, you are verified. I am calling from the Freya Bank collections team about a late payment.'
'''

VERIFY_POST = r'''
try:
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        if not isinstance(d, dict):
            d = dict()
            result['data'] = d
        left = d.get('wrong_answers_left')
        try:
            left = int(left)
        except Exception:
            left = None
        if str(d.get('all_verified')).lower() == 'true':
            t = 'Both answers are correct. The customer is verified.'
        elif d.get('hint') == 'day_month_swapped':
            t = 'Day and month look swapped. This does NOT count as a wrong answer. Ask the customer to say the date of birth again with the month as a word, then call verify_identity again.'
        elif str(d.get('verified')).lower() == 'true':
            t = 'Correct. Now ask the second question: the last four digits of the phone number on file.'
        elif left is not None and left <= 0:
            t = 'Wrong answer. That was the third wrong answer: the identity check has FAILED. Do not ask any more questions and say nothing about the account. Tell the customer to use the Freya Bank mobile app or visit a branch. Then thank them, say goodbye and call close_call with outcome not_verified and reason failed.'
        elif str(d.get('ok')).lower() != 'true' or result.get('status_code') not in (200, '200', None):
            t = 'The answer could not be checked (unreadable value or service error). It is not counted as wrong. Ask the customer to repeat the answer, then call verify_identity again.'
        else:
            t = 'Wrong answer. Tell the customer it does not match and ask the SAME question again (do not go back to a question that already passed).'
        d['what_to_do_next'] = t
except Exception:
    pass
'''

PROMISE_POST = r'''
try:
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        if not isinstance(d, dict):
            d = dict()
            result['data'] = d
        if str(d.get('ok')).lower() == 'true' and d.get('promise_id'):
            d['what_to_do_next'] = 'RECORDED. This promise is now recorded. If other confirmed promises still need create_promise, call it for the next one now. When all are done, tell the customer the promise(s) are recorded and say: "You will receive a text message confirming this promise."'
        else:
            d['ok'] = False
            d['what_to_do_next'] = 'NOT RECORDED. Do not say it is recorded. If this is the first failure for this product, call create_promise again right now with exactly the same values. If it already failed once before for this product, do not try again: tell the customer you could not record this promise.'
except Exception:
    pass
'''

SIMPLE_POST = r'''
try:
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        if not isinstance(d, dict):
            d = dict()
            result['data'] = d
        if str(d.get('ok')).lower() == 'true':
            d['what_to_do_next'] = 'Done. Continue with the next step: speak to the customer or call the next tool.'
        else:
            d['ok'] = False
            d['what_to_do_next'] = 'FAILED, nothing was recorded. Call the same tool once more with the same values. Never say it worked unless ok is true.'
except Exception:
    pass
'''

CLOSE_PRE = r'''
try:
    b = config.get('body')
    if isinstance(b, dict):
        R = dict(restructuring='transferred', human='transferred', support='transferred',
                 refused='no_promise', hardship='no_promise', dispute='no_promise', service_error='no_promise',
                 failed='not_verified', declined='not_verified',
                 callback='not_reached', no_callback='not_reached', wrong_number='not_reached', deceased='not_reached', unclear='not_reached')
        r = str(b.get('reason') or '').strip()
        if r == 'paid':
            b['outcome'] = 'paid'
        elif r in R and b.get('outcome') != 'promise':
            b['outcome'] = R[r]
        elif r in R and b.get('outcome') == 'promise' and R[r] == 'transferred':
            b['outcome'] = 'transferred'
        if b.get('outcome') in ('promise', 'paid') or not r or r == 'paid':
            b.pop('reason', None)
except Exception:
    pass
'''
CLOSE_POST = r'''
try:
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        if not isinstance(d, dict):
            d = dict()
            result['data'] = d
        if str(d.get('ok')).lower() != 'true':
            d['ok'] = False
            d['what_to_do_next'] = 'close_call was NOT accepted: ' + str(d.get('error')) + '. Correct the outcome and reason according to the outcome table and call close_call again now, without speaking.'
except Exception:
    pass
'''


def api_tool(name, desc, fields, required, post=None, pre=None):
    props = {"customer_id": {"type": "string", "default": "{{customer_id}}"}}
    for f, spec in fields.items():
        s = dict(spec)
        s["default"] = "{{%s_%s}}" % (name, f)  # no variable of that name exists: model fills it
        props[f] = s
    t = {
        "type": "function",
        "config": {"timeoutMs": 12000, "maxRetries": 0},
        "function": {
            "name": name,
            "handler": "__function__:api_call",
            "description": desc,
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string", "default": BASE + name},
                "method": {"type": "string", "default": "POST"},
                "headers": HDR,
                "body": {"type": "object", "properties": props, "required": required},
            }},
        },
    }
    if post:
        t["post_process_code"] = post
    if pre:
        t["pre_process_code"] = pre
    return t


VERIFY = api_tool("verify_identity",
    "CALL it every time the customer gives an answer to a security question, one answer per call. Then follow what_to_do_next in the result.",
    {"field": {"type": "string", "enum": ["date_of_birth", "phone_last4"], "description": "Which question was answered: date_of_birth or phone_last4."},
     "answer": {"type": "string", "description": "date_of_birth: always YYYY-MM-DD, converted from what the customer said (a date said only in numbers is day, then month, then year). phone_last4: exactly four digits."}},
    ["field", "answer"], post=VERIFY_POST)
CALLBACK = api_tool("schedule_callback",
    "CALL it when the person who answered (not the customer) gives a day and time inside the allowed callback window to reach the customer.",
    {"date": {"type": "string", "description": "YYYY-MM-DD"}, "time": {"type": "string", "description": "HH:MM, 24 hour"}},
    ["date", "time"], post=SIMPLE_POST)
TRANSFER = api_tool("transfer_to_agent",
    "CALL it to hand the call to a person: queue restructuring (customer asks for a new payment plan or lower instalments), support (hardship customer accepted the support team), general (customer insists on a human).",
    {"queue": {"type": "string", "enum": ["restructuring", "general", "support"], "description": "One of: restructuring, general, support."}},
    ["queue"], post=SIMPLE_POST)
PROMISE = api_tool("create_promise",
    "CALL it only after the customer said a clear yes to the read-back. One call per product. Then follow what_to_do_next in the result.",
    {"product_id": {"type": "string", "description": "product_id from the product facts, e.g. p1."},
     "amount": {"type": "number", "description": "Agreed amount, a number like 365.0."},
     "date": {"type": "string", "description": "Agreed date, YYYY-MM-DD."}},
    ["product_id", "amount", "date"], post=PROMISE_POST)
NOTE = api_tool("add_note",
    "ONLY when the account has more than one product: CALL it once for each product that ends without a recorded promise, before close_call. Never call it after or around a transfer.",
    {"product_id": {"type": "string", "description": "product_id, e.g. p2."},
     "reason": {"type": "string", "enum": ["refused", "hardship", "dispute", "paid", "service_error"], "description": "One of: refused, hardship, dispute, paid, service_error."},
     "text": {"type": "string", "description": "One short sentence why."}},
    ["product_id", "reason"], post=SIMPLE_POST)
CLOSE = api_tool("close_call",
    "CALL it exactly once, as the very last tool call, in the same message in which you thank the customer and say goodbye.",
    {"outcome": {"type": "string", "enum": ["promise", "paid", "transferred", "no_promise", "not_verified", "not_reached"], "description": "One of: promise, paid, transferred, no_promise, not_verified, not_reached."},
     "reason": {"type": "string", "enum": ["", "restructuring", "human", "support", "refused", "hardship", "dispute", "service_error", "failed", "declined", "callback", "no_callback", "wrong_number", "deceased", "unclear"],
                "description": "Empty for promise and paid. transferred: restructuring/human/support. no_promise: refused/hardship/dispute/service_error. not_verified: failed/declined. not_reached: callback/no_callback/wrong_number/deceased/unclear."}},
    ["outcome"], pre=CLOSE_PRE, post=CLOSE_POST)


def code_node(name, code, nxt):
    return {
        "name": name, "node_type": "code", "passthrough": True, "passthrough_default_transition": nxt,
        "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True,
        "pre_actions": [{"type": "function", "function": {"name": "code_exec", "handler": "__function__:code_exec",
            "parameters": {"type": "object", "properties": {"code": {"type": "string", "default": code}, "timeout_ms": {"type": "number", "default": 10000}}}}}],
        "transitions": [{"target_node": nxt, "description": "always", "condition": {"operator": "always"}}],
    }


def cond_or(*conds):
    return {"logic": "or", "conditions": list(conds)}


CLOSED = {"target_node": "end", "description": "close_call was made",
          "condition": cond_or({"variable": "close_call_response.data.ok", "operator": "equals", "operand": "true"},
                                  {"variable": "close_call_response.data.ok", "operator": "equals", "operand": "True"})}

SYSTEM = """You are Freya Bank's digital assistant, on an outbound phone call to {{title}} {{first_name}} {{last_name}}. Speak English. One or two short sentences per turn. Address the customer as {{title}} {{last_name}}.

Always:
- Call one tool per message. After every tool result, either speak to the customer or call the next tool. Never end a turn with nothing. When a tool result has what_to_do_next, do what it says.
- Never say something is recorded, scheduled or transferred unless the tool result has ok true.
- If asked whether you are a robot or an AI: say you are Freya Bank's digital assistant, then continue.
- If asked "is this a scam?": say they can verify this call by phoning Freya Bank's customer service number, then continue.
- If the customer asks for a human: ask once whether you can help first. If they insist, call transfer_to_agent with queue general, then close_call with outcome transferred, reason human.
- Never invent figures, dates or reasons. If you cannot answer from the facts you have, say you do not have that information.
- Never offer a discount, a waiver, an instalment plan or any other term. Never ask the customer how much they can pay.
- Ending: thank the customer and say goodbye, and call close_call in that same message. close_call is always the last tool call. Never say anything after it."""

IDENTIFY_TASK = """You opened the call already with: "Hello, I am a digital assistant calling from Freya Bank, and this call is recorded. Am I speaking with {{title}} {{last_name}}?"
Until identity is verified, NEVER say "collections", "debt", "payment", "late", any amount or any product, to anyone. If asked what the call is about, say you can only tell that to {{title}} {{last_name}} after a short security check.

STEP 1, who is on the line:
- Only "yes", "that's me", "speaking" or the customer's own name counts as confirmation. "Hello", "go ahead", "who is this" do not. Answer a question first if they ask one, then ask again "Am I speaking with {{title}} {{last_name}}?". If after the second ask it is still unclear, close: outcome not_reached, reason unclear.
- Someone else answers (a relative, a colleague...): do not say why you are calling and give no account information, even if they offer to pay or to answer questions. Ask when {{title}} {{last_name}} can be reached.
  Callback window:
{{callback_rules}}
  If the day and time are inside the window, call schedule_callback (date YYYY-MM-DD, time HH:MM), then close: not_reached, callback. "Morning" without a time: ask for the time. If the offer is outside the window, ask once for another time; if that is outside too, do not schedule and close: not_reached, no_callback.
- The number does not belong to the customer: close: not_reached, wrong_number.
- The customer has died: say exactly "I am sorry for your loss.", ask nothing else, close: not_reached, deceased.

STEP 2, security questions (only after the customer confirmed who they are), one at a time:
- First ask for the date of birth. Call verify_identity with field date_of_birth and the date as YYYY-MM-DD (a date said only in numbers is day, then month, then year).
- When it passes, ask for the last four digits of the phone number on file. Call verify_identity with field phone_last4.
- Follow what_to_do_next in every verify_identity result.
- If the customer does not want to answer, or asks what the call is about instead of answering: explain once that these questions protect their account, and ask again. If they refuse again or ask again, close: not_verified, declined.
- If the customer says twice that they do not want to talk: close: not_verified, declined.

To close: thank them, say goodbye and call close_call with the outcome and reason, in one message."""

NEGOTIATE_TASK = """The customer is verified. You already told them the debt and asked whether they can pay today.

ACCOUNT FACTS (computed by the bank, always use these):
{{account_facts}}

Number of products: {{n_products}}.

HOW TO GET A PROMISE
- With more than one product: the first question covers all of them ("Can you pay all of them today?"). If not, go through the products one by one in the listed order. Do not ask about today again for each product. Each product starts at its attempt 1 and has its own attempts, floor and deadline.
- The full past-due amount is asked first. You propose every amount. Never ask "how much can you pay?".
- A date or an amount the customer proposes is never a refusal: check it.
  Date: must be today or later, a business day per the CALENDAR, and not after that product's deadline. Weekend or holiday not after the deadline: offer the next business day from the CALENDAR. After the deadline: say the latest date you can record is the deadline and offer it; if they refuse the deadline, that is a flat refusal. Vague period ("next week", "end of the month", "when my salary comes"): ask once for the exact day; if they still give none, propose the deadline. "this/next <weekday>": use WEEKDAY WORDS.
  Amount: from the floor up to the full amount (both included): accept. Below the floor: say it cannot be recorded and offer the floor once; if not accepted, flat refusal. "The full amount is too much": offer the floor once and say the rest stays overdue; if they refuse the floor, flat refusal.
  With several products, one date named for everything that is after one product's deadline: that product goes on its own deadline (say so), the others keep the named date.
- Once the customer said the full amount is too much, every later offer for that product uses the floor, never the full amount again. If they say they cannot pay the floor TODAY, that is not a refusal of the floor: make attempt 1 with the floor on the attempt 1 date.
- Flat refusal or non-answer (a no to paying today with no date and no amount is a flat refusal): uses one persuasion attempt of the current product. Make the next attempt exactly as listed in the product facts (attempt 1, then attempt 2 only for late band). Never repeat an offer already refused. When the attempts of a product are used up, that product is refused: move to the next product, or finish.
- Hardship (illness, a death in the family, job loss): one short sentence of sympathy, NO persuasion attempt, offer to connect them with the customer support team. Accepts: call transfer_to_agent queue support, then close transferred, support. Declines: the product(s) end as hardship. If they still name a date or amount themselves, handle it as a promise.
- "I already paid" (this past-due amount): say payments can take one business day to appear; no promise for that product.
- "Not my debt" / "I never had this product" / "it was closed or paid off long ago": do not argue, no promise for that product (dispute).
- New payment plan or lower instalments: describe no plan; call transfer_to_agent queue restructuring, then close transferred, restructuring. Agreed but unconfirmed/unrecorded promises are NOT recorded then.
- Customer says twice they do not want to talk: close no_promise, refused.

CONFIRMING AND RECORDING
- Read back the product, the amount and the date of every agreed promise (all products together, one read-back) and ask "Do you confirm?". If they change a value, check it again and read back again.
- Only after a clear yes: call create_promise, one call per product, with product_id, amount and date (YYYY-MM-DD). Follow what_to_do_next. A failed call is retried once; if it fails twice, tell the customer you could not record it.
- A recorded promise cannot be changed or cancelled in this call; say they can change it in the mobile app.
- After the promise(s) are recorded say: "You will receive a text message confirming this promise."

FINISHING
- Only if there is MORE THAN ONE product and there was no transfer: before close_call, call add_note once for each product without a recorded promise, with reason refused, hardship, dispute, paid or service_error (failed twice). With one product never call add_note. After a transfer never call add_note.
- close_call outcome and reason:
  - transfer happened: transferred with that transfer's reason (restructuring, support, human), even if a promise was recorded.
  - at least one promise recorded: promise (no reason).
  - no promise, every product paid (customer already paid): outcome paid (no reason). Never no_promise for an already-paid single product.
  - otherwise no_promise with the reason of the first product (in listed order) that is not paid: refused, hardship, dispute or service_error.
- Thank the customer, say goodbye and call close_call in the same message."""

wf = {
    "initial_node": "setup",
    "system_prompt": SYSTEM,
    "test_variables": {"customer_id": "c_test", "first_name": "Daniel", "last_name": "Reyes", "title": "Mr", "now": "2026-10-14T11:00"},
    "global_nodes": {},
    "nodes": {
        "setup": code_node("setup", SETUP_CODE, "identify"),
        "identify": {
            "name": "identify", "node_type": "conversation",
            "on_enter": {"type": "tts", "text": "Hello, I am a digital assistant calling from Freya Bank, and this call is recorded. Am I speaking with {{title}} {{last_name}}?"},
            "on_enter_first_entry_only": True,
            "task_message": IDENTIFY_TASK,
            "tools": [VERIFY, CALLBACK, TRANSFER, CLOSE],
            "max_node_turns": 60,
            "transitions": [
                CLOSED,
                {"target_node": "load_account", "description": "both security answers verified",
                 "condition": cond_or({"variable": "verify_identity_response.data.all_verified", "operator": "equals", "operand": "true"},
                                      {"variable": "verify_identity_response.data.all_verified", "operator": "equals", "operand": "True"})},
            ],
        },
        "load_account": {
            "name": "load_account", "node_type": "api_request", "passthrough": True,
            "passthrough_default_transition": "facts", "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True,
            "suppress_tool_results": True,
            "pre_actions": [{"type": "function", "config": {"timeoutMs": 12000, "maxRetries": 2}, "function": {
                "name": "get_account", "handler": "__function__:api_call", "description": "Get the late products.",
                "parameters": {"type": "object", "properties": {
                    "url": {"type": "string", "default": BASE + "get_account"},
                    "method": {"type": "string", "default": "POST"}, "headers": HDR,
                    "body": {"type": "object", "properties": {"customer_id": {"type": "string", "default": "{{customer_id}}"}}, "required": []}}}}}],
            "response_mapping": [{"path": "data.products", "variable": "products"}],
            "transitions": [{"target_node": "facts", "description": "always", "condition": {"operator": "always"}}],
        },
        "facts": dict(code_node("facts", FACTS_CODE, "negotiate"), transitions=[
            {"target_node": "facts_retry", "description": "facts missing", "condition": cond_or({"variable": "debt_statement", "operator": "is_not_set"})},
            {"target_node": "negotiate", "description": "always", "condition": {"operator": "always"}}]),
        "facts_retry": code_node("facts_retry", FACTS_CODE, "negotiate"),
        "negotiate": {
            "name": "negotiate", "node_type": "conversation",
            "on_enter": {"type": "tts", "text": "{{debt_statement}}"},
            "on_enter_first_entry_only": True,
            "task_message": NEGOTIATE_TASK,
            "tools": [PROMISE, NOTE, TRANSFER, CLOSE],
            "max_node_turns": 80,
            "transitions": [CLOSED],
        },
        "end": {
            "name": "end", "node_type": "end_call", "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True,
            "transitions": [],
            "terminal": {"type": "function", "function": {"name": "call_closed", "handler": "__function__:end_call",
                "parameters": {"type": "object", "properties": {"message_mode": {"type": "string", "default": "none"}}}}},
        },
    },
}

assert "{{" not in CLOSE_POST + SETUP_CODE + FACTS_CODE + VERIFY_POST + PROMISE_POST + SIMPLE_POST + CLOSE_PRE
pathlib.Path(__file__).with_name("brief-b.workflow.json").write_text(json.dumps(wf, indent=1))
print("ok")
