"""Generates out/brief-a.workflow.json for Brief A."""
import json, pathlib

BASE = "https://freya-bank-mock.freyavoice.workers.dev/v1/"
OUT = pathlib.Path(__file__).resolve().parent / "brief-a.workflow.json"


def api_tool(name, desc, fields, required, post=None, pre=None, retries=0):
    props = {"customer_id": {"type": "string", "default": "{{customer_id}}"}}
    props.update(fields)
    t = {
        "type": "function",
        "config": {"timeoutMs": 12000, "maxRetries": retries},
        "function": {
            "name": name,
            "handler": "__function__:api_call",
            "description": desc,
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "default": BASE + name},
                    "method": {"type": "string", "default": "POST"},
                    "headers": {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}},
                    "body": {"type": "object", "properties": props, "required": required},
                },
            },
        },
    }
    if post:
        t["post_process_code"] = post
    if pre:
        t["pre_process_code"] = pre
    return t


# ---------------------------------------------------------------- hooks
HOOK_HEAD = "try:\n    result.pop('header', None)\n    d = result.get('data') if isinstance(result, dict) else None\n    if not isinstance(d, dict):\n        d = dict()\n        result['data'] = d\n    sc = result.get('status_code')\n    good = (d.get('ok') is True) and (sc in (None, 200, '200'))\n"
HOOK_TAIL = "except Exception:\n    pass\n"

VERIFY_POST = HOOK_HEAD + """    left = d.get('wrong_answers_left')
    if d.get('all_verified') is True:
        d['what_to_do_next'] = 'Both security answers are correct. Now say only: Thank you. And in the same message call transition_to_gate. Do not say anything about the account yourself.'
    elif d.get('hint') == 'day_month_swapped':
        d['what_to_do_next'] = 'The day and the month seem swapped. This does NOT count as a wrong answer. Ask the customer to say their date of birth again with the month as a word, for example the fourteenth of March.'
    elif left == 0 or str(left) == '0':
        d['what_to_do_next'] = 'The identity check has FAILED after three wrong answers. Do not ask again and say nothing about any account or amount, even if asked. In one message: say you could not verify their identity, so you cannot continue, and that they can use the Freya Bank mobile app or visit a branch; thank them, say goodbye, and call close_call with outcome not_verified and reason failed.'
    elif not good:
        d['what_to_do_next'] = 'The answer could not be read and was not checked. It does not count as a wrong answer. Ask the customer to repeat it, the date of birth as day, month as a word, and year.'
    elif d.get('verified') is True:
        d['what_to_do_next'] = 'Correct. Now ask the next security question: the last four digits of the phone number on file. Then call verify_identity with field phone_last4.'
    else:
        d['what_to_do_next'] = 'That answer is WRONG. Wrong answers left: ' + str(left) + '. Tell the customer it does not match our records and ask the same question again.'
""" + HOOK_TAIL

PROMISE_POST = HOOK_HEAD + """    n = 0
    try:
        n = int(vars.get('promise_fail_n') or 0)
    except Exception:
        n = 0
    if good:
        d['what_to_do_next'] = 'The promise IS recorded. Tell the customer the promise is recorded and say exactly: You will receive a text message confirming this promise. Then thank them, say goodbye and call close_call with outcome promise.'
    else:
        n = n + 1
        try:
            vars['promise_fail_n'] = n
        except Exception:
            pass
        if n <= 1:
            d['what_to_do_next'] = 'The promise was NOT recorded (service error). Do NOT say it is recorded. Call create_promise again now, once, with exactly the same product_id, amount and date.'
        else:
            d['what_to_do_next'] = 'The promise was NOT recorded again (service error). Tell the customer you could not record the promise. Do not try again. Thank them, say goodbye and call close_call with outcome no_promise and reason service_error.'
""" + HOOK_TAIL

CALLBACK_POST = HOOK_HEAD + """    if good:
        d['what_to_do_next'] = 'The callback is booked. Tell the person we will call back then, thank them, say goodbye and call close_call with outcome not_reached and reason callback.'
    else:
        d['what_to_do_next'] = 'The callback could NOT be booked. Do not say it is booked. Check the date (YYYY-MM-DD) and time (HH:MM) against the allowed window and call schedule_callback once more, or if that is impossible thank them, say goodbye and call close_call with outcome not_reached and reason no_callback.'
""" + HOOK_TAIL

TRANSFER_POST = HOOK_HEAD + """    if good:
        d['what_to_do_next'] = 'The transfer is done. Tell the customer you are connecting them to a colleague now, thank them, say goodbye and call close_call with outcome transferred and the reason that matches the queue (restructuring, support, or human for the general queue).'
    else:
        d['what_to_do_next'] = 'The transfer FAILED. Do not say they are being transferred. Tell the customer you could not connect them right now.'
""" + HOOK_TAIL

CLOSE_PRE = "try:\n    b = config.get('body')\n    if isinstance(b, dict):\n        r = str(b.get('reason') or '').strip()\n        if b.get('outcome') in ('promise', 'paid') or r in ('', 'none'):\n            b.pop('reason', None)\nexcept Exception:\n    pass\n"
CLOSE_POST = HOOK_HEAD + """    if good:
        try:
            vars['call_closed'] = 'yes'
        except Exception:
            pass
        d['what_to_do_next'] = 'The call is closed. Say nothing more.'
    else:
        d['what_to_do_next'] = 'close_call was rejected: ' + str(d.get('error')) + '. Call close_call again with a valid outcome and reason.'
""" + HOOK_TAIL

FALLBACK_PRE = "try:\n    done = str(vars.get('call_closed') or '') == 'yes' or str(vars.get('close_call_response.data.ok') or '').lower() == 'true'\n    if done:\n        config['url'] = 'https://example.com/'\n    b = config.get('body')\n    if isinstance(b, dict):\n        r = str(b.get('reason') or '').strip()\n        if b.get('outcome') in ('promise', 'paid') or r in ('', 'none'):\n            b.pop('reason', None)\nexcept Exception:\n    pass\n"

ALL_REASONS = ["none", "callback", "no_callback", "wrong_number", "deceased", "unclear", "failed", "declined",
               "restructuring", "human", "support", "refused", "hardship", "dispute", "service_error"]


def close_tool(outcomes, reasons, guide):
    return api_tool(
        "close_call",
        "Ends the call in the bank's records. CALL it exactly once, at the very end, in the same message as your short thank-you and goodbye. Never call it before you have said goodbye. " + guide,
        {
            "outcome": {"type": "string", "enum": outcomes, "default": "{{outcome}}", "description": "One of: " + ", ".join(outcomes) + "."},
            "reason": {"type": "string", "enum": reasons, "default": "{{reason}}", "description": "One of: " + ", ".join(reasons) + ". Use none for promise and paid."},
        },
        ["outcome", "reason"], post=CLOSE_POST, pre=CLOSE_PRE)


VERIFY = api_tool(
    "verify_identity",
    "Checks ONE security answer. CALL it every time the customer gives an answer to a security question, right away, before you say anything else.",
    {
        "field": {"type": "string", "enum": ["date_of_birth", "phone_last4"], "default": "{{field}}", "description": "date_of_birth or phone_last4."},
        "answer": {"type": "string", "default": "{{answer}}", "description": "For date_of_birth: YYYY-MM-DD, converted from what the customer said (a date said only as numbers is day, then month, then year). For phone_last4: exactly four digits."},
    },
    ["field", "answer"], post=VERIFY_POST)

PROMISE = api_tool(
    "create_promise",
    "Records the payment promise. CALL it only after you read back product, amount and date and the customer clearly said yes. Never say the promise is recorded before this returns ok.",
    {
        "product_id": {"type": "string", "default": "{{product_id}}", "description": "product_id from the account facts, for example p1."},
        "amount": {"type": "number", "default": "{{amount}}", "description": "The agreed amount, a number like 420.0."},
        "date": {"type": "string", "default": "{{date}}", "description": "The agreed payment date as YYYY-MM-DD."},
    },
    ["product_id", "amount", "date"], post=PROMISE_POST)

CALLBACK = api_tool(
    "schedule_callback",
    "Books a callback. CALL it when the person who answered gives a day and time inside the allowed callback window.",
    {
        "date": {"type": "string", "default": "{{date}}", "description": "Callback date as YYYY-MM-DD."},
        "time": {"type": "string", "default": "{{time}}", "description": "Callback time as HH:MM, 24 hour."},
    },
    ["date", "time"], post=CALLBACK_POST)


def transfer_tool(queues):
    return api_tool(
        "transfer_to_agent",
        "Hands the call to a human colleague. CALL it when a rule says to transfer: restructuring for a new payment plan or lower instalments, support for a customer in hardship who accepts the support team, general for a customer who insists on a human.",
        {"queue": {"type": "string", "enum": queues, "default": "{{queue}}", "description": "One of: " + ", ".join(queues) + "."}},
        ["queue"], post=TRANSFER_POST)


# ---------------------------------------------------------------- code
FACTS_CODE = r'''import datetime, json, ast
HOL = ['2026-10-26', '2026-11-11', '2026-11-26', '2026-12-25', '2027-01-01']
def fmt(d):
    return d.strftime('%A') + ' ' + str(d.day) + ' ' + d.strftime('%B %Y') + ' (' + d.isoformat() + ')'
def money(x):
    try:
        return '{:,.2f}'.format(float(x))
    except Exception:
        return str(x)
def isbiz(d):
    return d.weekday() < 5 and d.isoformat() not in HOL
try:
    raw = str(vars.get('now') or '')
    try:
        nowdt = datetime.datetime.fromisoformat(raw[:16])
    except Exception:
        nowdt = datetime.datetime(2026, 10, 14, 11, 0)
    today = nowdt.date()
    one = datetime.timedelta(days=1)
    def nth_biz(n):
        d = today
        k = 0
        while k < n:
            d = d + one
            if isbiz(d):
                k += 1
        return d
    def next_biz_after(d):
        d = d + one
        while not isbiz(d):
            d = d + one
        return d
    def last_biz_of_week(d):
        mon = d - datetime.timedelta(days=d.weekday())
        for i in range(4, -1, -1):
            x = mon + datetime.timedelta(days=i)
            if isbiz(x):
                return x
        return None
    lb = last_biz_of_week(today)
    if lb is None or lb <= today:
        lb = last_biz_of_week(today + datetime.timedelta(days=7 - today.weekday()))
    att1 = lb
    nb = next_biz_after(today)
    # callback window
    cb = []
    if nowdt.hour < 19:
        start = max(nowdt + datetime.timedelta(minutes=1), datetime.datetime(today.year, today.month, today.day, 10, 0))
        cb.append('today ' + fmt(today) + ' from ' + start.strftime('%H:%M') + ' to 19:00')
    cb.append('the next business day ' + fmt(nb) + ' from 10:00 to 19:00')
    vars['callback_facts'] = ('Now is ' + fmt(today) + ' ' + nowdt.strftime('%H:%M') + '. A callback may only be booked ' + ' or '.join(cb) + ' (both ends included, and later than now). Anything else is outside the window. Tomorrow is ' + fmt(today + one) + '.')
    # products
    prods = vars.get('products')
    if isinstance(prods, str):
        try:
            prods = json.loads(prods)
        except Exception:
            try:
                prods = ast.literal_eval(prods)
            except Exception:
                prods = None
    if isinstance(prods, dict):
        prods = [prods]
    if not isinstance(prods, list) or not prods:
        prods = []
        for i in range(3):
            p = dict()
            for k in ['product_id', 'type', 'card_last4', 'past_due', 'days_late', 'minimum_payment', 'instalment_amount']:
                for key in ['fetch_account_response.data.products.' + str(i) + '.' + k, 'products.' + str(i) + '.' + k, 'get_account_response.data.products.' + str(i) + '.' + k, 'products[' + str(i) + '].' + k]:
                    if vars.get(key) is not None:
                        p[k] = vars.get(key)
            if p:
                prods.append(p)
    p = prods[0] if prods else None
    if p:
        t = str(p.get('type'))
        if t == 'credit_card':
            name = 'credit card ending ' + str(p.get('card_last4'))
            floor = p.get('minimum_payment')
            fname = 'minimum payment'
        elif t == 'car_loan':
            name = 'car loan'
            floor = p.get('instalment_amount')
            fname = 'instalment amount'
        else:
            name = 'personal loan'
            floor = p.get('instalment_amount')
            fname = 'instalment amount'
        late = int(float(p.get('days_late') or 0))
        due = float(p.get('past_due') or 0)
        floor = float(floor or 0)
        if late <= 7:
            band = 'early'
            dl = nth_biz(12)
            attempts = 1
        else:
            band = 'late'
            dl = nth_biz(7)
            attempts = 2
        vars['product_id'] = str(p.get('product_id') or 'p1')
        vars['acct_state'] = 'ok'
        cal = []
        d = today
        while d <= dl + datetime.timedelta(days=4):
            wk = 'this week' if d.isocalendar()[1] == today.isocalendar()[1] else ('next week' if (d - datetime.timedelta(days=d.weekday())) == (today - datetime.timedelta(days=today.weekday()) + datetime.timedelta(days=7)) else 'later')
            if d > dl:
                st = 'AFTER THE DEADLINE, not allowed: offer the deadline ' + fmt(dl)
            elif not isbiz(d):
                st = ('bank holiday' if d.isoformat() in HOL else 'weekend') + ', not allowed: offer the next business day ' + fmt(next_biz_after(d))
            else:
                st = 'allowed'
            cal.append('- ' + fmt(d) + (' TODAY' if d == today else '') + ', ' + wk + ': ' + st)
            d = d + one
        a1amt = 'the full amount ' + money(due) + ' (or the floor ' + money(floor) + ' if the customer already said the full amount is too much)'
        lines = [
            'Product: ' + name + ' (product_id ' + vars['product_id'] + ').',
            'Full past-due amount: ' + money(due) + '. Days late: ' + str(late) + '. Band: ' + band + '.',
            'Floor (the ' + fname + ', the lowest amount you may record): ' + money(floor) + '.',
            'Today: ' + fmt(today) + ('' if isbiz(today) else ' (not a business day, so today cannot be a promise date)') + '.',
            'Deadline (latest promise date): ' + fmt(dl) + '.',
            'Persuasion attempts allowed: ' + str(attempts) + '.',
            'Floor offer, say it with these words when the customer says the full amount is too much: The lowest amount I can record is the ' + fname + ' of ' + money(floor) + ', and the rest of the past-due amount would stay overdue. Could you pay ' + money(floor) + '?',
            'Read-back, always in this form: To confirm, you will pay <amount> on your ' + name + ' on <weekday day month>. Do you confirm?',
            'Attempt 1: propose ' + a1amt + ' on ' + fmt(att1) + '.',
        ]
        if attempts == 2:
            lines.append('Attempt 2: propose the floor ' + money(floor) + ' on the deadline ' + fmt(dl) + '.')
        else:
            lines.append('There is no attempt 2 in this band. After attempt 1 is refused, close the call as no_promise / refused.')
        lines.append('Calendar for promise dates (any date not listed and after ' + dl.isoformat() + ' is after the deadline):')
        lines.extend(cal)
        vars['debt_facts'] = '\n'.join(lines)
        vars['debt_line'] = 'Thank you, that is confirmed. I am calling from the Freya Bank collections team about a late payment on your ' + name + '. The past-due amount is ' + money(due) + ', and the payment is ' + str(late) + ' days late. Can you make this payment today?'
    else:
        vars['acct_state'] = 'unknown'
        vars['product_id'] = 'p1'
        vars['debt_facts'] = 'The account facts could not be prepared. Use the get_account result in the conversation. Business days are Monday to Friday except 2026-10-26, 2026-11-11, 2026-11-26, 2026-12-25 and 2027-01-01. Today: ' + fmt(today) + '.'
        vars['debt_line'] = 'Thank you, that is confirmed. I am calling from the Freya Bank collections team about a late payment.'
except Exception as e:
    vars['acct_state'] = 'error'
    if not vars.get('debt_facts'):
        vars['debt_facts'] = 'The account facts could not be prepared. Use the get_account result in the conversation.'
    if not vars.get('debt_line'):
        vars['debt_line'] = 'Thank you, that is confirmed. I am calling from the Freya Bank collections team about a late payment.'
    if not vars.get('callback_facts'):
        vars['callback_facts'] = 'A callback may only be booked for today or the next business day, from 10:00 to 19:00, later than now (' + str(vars.get('now')) + ').'
    if not vars.get('product_id'):
        vars['product_id'] = 'p1'
'''
assert "{{" not in FACTS_CODE and "}}" not in FACTS_CODE


def code_node(name, target):
    return {
        "name": name, "node_type": "code", "passthrough": True, "passthrough_default_transition": target,
        "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True,
        "pre_actions": [{"type": "function", "function": {"name": "code_exec", "handler": "__function__:code_exec", "parameters": {"type": "object", "properties": {
            "code": {"type": "string", "default": FACTS_CODE}, "timeout_ms": {"type": "number", "default": 10000}}}}}],
        "transitions": [{"target_node": target, "description": "always", "condition": {"operator": "always"}}],
    }


def is_true(var):
    return [{"variable": var, "operator": "equals", "operand": "true"}, {"variable": var, "operator": "equals", "operand": "True"}]


CLOSED = {"target_node": "end", "description": "close_call succeeded", "condition": {"logic": "or", "conditions": is_true("close_call_response.data.ok") + [{"variable": "call_closed", "operator": "equals", "operand": "yes"}]}}


def stay(n):
    return {"target_node": n, "description": "stay", "condition": {"operator": "always"}}


SYSTEM = """You are Freya Bank's digital assistant, on an outbound phone call to {{title}} {{first_name}} {{last_name}}. Speak English. Keep every turn to one to three short sentences and ask one question at a time. Address the customer as {{title}} {{last_name}}.
The current date and time is {{now}}. Use it for every date. Never use any other clock.

Rules for every step:
- If asked whether you are a robot or an AI: say you are Freya Bank's digital assistant, then continue.
- If asked whether this is a scam: say they can verify this call by phoning Freya Bank's customer service number, then continue.
- If asked something the information you have does not answer: say you do not have that information. Never invent figures, dates, reasons or terms. Never offer a discount, a waiver, an instalment plan or any other arrangement.
- When a rule says to call a tool, CALL the tool. Saying you did something is not doing it. One tool call per message.
- After every tool result, read its what_to_do_next and follow it: speak to the customer or call the next tool. Never end a turn with nothing.
- Never say something is recorded, booked or done unless the tool result said ok.
- Ending the call: in ONE message, thank the customer and say goodbye, and call close_call in that same message. close_call is always the last thing you do, exactly once."""

OPENING_TASK = """The opening line has been said: you are a digital assistant calling from Freya Bank, we record this call, and you asked "Am I speaking with {{title}} {{last_name}}?".
Your only job here is to find out who is on the line. Do NOT mention collections, a debt, a payment, an amount, an account or a product to anyone in this step. If asked why you are calling, say you can only discuss it with {{title}} {{last_name}} personally.

- Confirmation counts only if the person says yes, that's me, speaking, or says the customer's own name. "Hello", "go ahead", "who is this" are not confirmation. If unclear, answer any question they asked first (rules on robot and scam), then ask once more "Am I speaking with {{title}} {{last_name}}?". If it is still unclear after this second ask, thank them, say goodbye and call close_call with outcome not_reached, reason unclear.
- If the person says the number does not belong to the customer / wrong number: thank them, say goodbye and call close_call with not_reached, wrong_number.
- If the person says the customer has died: say exactly "I am sorry for your loss.", ask nothing else, say goodbye and call close_call with not_reached, deceased.
- If someone else answers (a relative or anyone else): say nothing about why you call, even if they ask or offer to pay. Never ask them security questions. Ask when {{title}} {{last_name}} can be reached.
  {{callback_facts}}
  If they give a day and time inside that window, call schedule_callback with the date (YYYY-MM-DD) and time (HH:MM). If they give only a vague time like "tomorrow morning around eleven", use that exact time (11:00). If what they offer is outside the window, ask once for another time. If the second answer is also outside the window, or they cannot say, do not schedule: thank them, say goodbye and call close_call with not_reached, no_callback.
- If the person refuses to talk, explain once that you can only discuss this with {{title}} {{last_name}}; if they refuse a second time, say goodbye and call close_call with not_verified, declined.
- If the person asks for a human: ask once whether you can help first. If they insist, call transfer_to_agent with queue general, then say goodbye and call close_call with transferred, human.
Do not call verify_identity or get_account here."""

VERIFY_TASK = """The person confirmed they are {{title}} {{last_name}}. Now run the security check. Do NOT mention collections, a debt, a payment, an amount or a product yet.
1. Ask for their date of birth. When they answer, call verify_identity with field date_of_birth and the date as YYYY-MM-DD, whatever way they said it (a date said only as numbers is day, then month, then year). If they give only part of it, ask for the rest before calling.
2. When the date of birth passes, ask for the last four digits of the phone number on file, and call verify_identity with field phone_last4.
- Ask one question at a time. Follow what_to_do_next in every verify_identity result. A wrong answer may be asked again; the service counts wrong answers.
- When verify_identity says both answers are correct: say only "Thank you." and call transition_to_gate in the same message.
- If the customer asks "why do you need that?", explain that these questions protect their account and ask again; that alone is not a refusal.
- If the customer will not answer, or asks what the call is about instead of answering: explain once that these questions protect their account, and ask again. If they refuse again or ask again what it is about, thank them, say goodbye and call close_call with outcome not_verified, reason declined.
- If they ask whether this is a scam: say they can verify the call by phoning Freya Bank's customer service number, then ask the question again.
- If they ask for a human: ask once whether you can help first. If they insist, call transfer_to_agent with queue general, then say goodbye and call close_call with transferred, human.
- Never tell them any account information here."""

NEGOTIATE_TASK = """The customer is verified and you have just stated the debt and asked "Can you make this payment today?".

ACCOUNT FACTS (all dates and amounts come from here, never compute your own):
{{debt_facts}}

YOUR JOB: get a payment promise that follows these rules, record it, and close the call.

A. Special situations (check these first, every turn):
- Already paid ("I already paid", paid in the app, etc.): say payments can take one business day to appear, take no promise, thank them, say goodbye and call close_call with outcome paid, reason none.
- Dispute ("not my debt", "I never had this product", "the card/loan was closed or paid off long ago"): do not argue, take no promise, thank them, goodbye, close_call no_promise, dispute.
- Asks for a new payment plan, a restructuring, or lower instalments: do not describe any plan. Call transfer_to_agent with queue restructuring, then goodbye and close_call transferred, restructuring.
- Mentions illness, a death in the family or losing their job: say ONE short sentence of sympathy, make NO persuasion attempt and propose no date or amount. Offer to connect them with the customer support team. If they accept: transfer_to_agent queue support, then goodbye and close_call transferred, support. If they decline: thank them, goodbye, close_call no_promise, hardship. (If they themselves still name a date or amount, handle it with section B and C.) A request for a discount is answered with: you cannot offer one.
- Asks for a human: ask once whether you can help first. If they insist: transfer_to_agent queue general, then goodbye and close_call transferred, human.
- Says twice they do not want to talk: thank them, goodbye, close_call no_promise, refused.

B. Dates (look every date up in the calendar above):
- "allowed" date: accept it.
- Weekend or bank holiday not after the deadline: say it is not a business day and offer the next business day shown in the calendar.
- After the deadline: say the latest date you can record is the deadline, and offer the deadline. If they refuse the deadline, that is a flat refusal (section D).
- Vague period ("next week", "end of the month", "when my salary comes", "the week after next"): ask once for the exact day. If they still give no exact day, propose the deadline.
- "this <weekday>" = that weekday in the current week; "next <weekday>" = that weekday in the following calendar week (use the week labels in the calendar).
- A date or an amount the customer proposes is never a refusal.

C. Amounts (you propose every amount; NEVER ask "how much can you pay?"):
- Start with the full past-due amount.
- If they say the full amount is too much: offer the floor once, using the floor offer sentence from the account facts word for word (it says that the rest stays overdue). If they refuse the floor, that is a flat refusal (section D).
- If they propose an amount from the floor up to the full amount: accept it. Below the floor: say it cannot be recorded and offer the floor once; if they do not accept, that is a flat refusal.
- If they answer "you tell me", propose the amount yourself.

D. Flat refusal or non-answer (for example "no" to paying today with no date and no amount): it uses one persuasion attempt. Use the attempts exactly as in the account facts: attempt 1, then (late band only) attempt 2. Never repeat an offer the customer already refused. When the allowed attempts are used up and refused: stop, thank them, goodbye, close_call no_promise, refused.

E. Confirming and recording:
- When amount and date are agreed, read back the product, the amount and the date using the read-back form from the account facts, ending with "Do you confirm?". Always name the product.
- Only after a clear yes, call create_promise with product_id, the amount as a number and the date as YYYY-MM-DD. If they change the date or amount, check it again under B and C and read it back again.
- Follow what_to_do_next in the create_promise result. Only when it says the promise is recorded: say it is recorded, then say exactly "You will receive a text message confirming this promise.", thank them, say goodbye and call close_call with outcome promise, reason none.
- If create_promise fails, call it once more with the same values. If it fails again, say you could not record the promise, then goodbye and close_call no_promise, service_error.
- One promise only. A recorded promise cannot be changed in this call: if asked, say they can change it in the mobile app."""

wf = {
    "initial_node": "setup",
    "system_prompt": SYSTEM,
    "test_variables": {"customer_id": "c_test", "first_name": "Daniel", "last_name": "Reyes", "title": "Mr", "now": "2026-10-14T11:00"},
    "global_nodes": {},
    "tools": [
        {
            "type": "function",
            "config": {"timeoutMs": 12000, "maxRetries": 0, "alwaysRunsAt": ["end_of_call"]},
            "function": {
                "name": "close_call_fallback",
                "handler": "__function__:api_call",
                "description": "Record how the call ended, from the conversation, only if it was not closed already.",
                "parameters": {"type": "object", "properties": {
                    "url": {"type": "string", "default": BASE + "close_call"},
                    "method": {"type": "string", "default": "POST"},
                    "headers": {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}},
                    "body": {"type": "object", "required": ["outcome"], "properties": {
                        "customer_id": {"type": "string", "default": "{{customer_id}}"},
                        "outcome": {"type": "string", "enum": ["promise", "paid", "transferred", "no_promise", "not_verified", "not_reached"], "default": "{{fallback_outcome}}",
                                    "description": "promise: a promise was recorded. paid: customer said already paid. transferred: handed to a person. no_promise: verified, no promise. not_verified: identity check failed or declined. not_reached: the customer was not on the line."},
                        "reason": {"type": "string", "enum": ALL_REASONS, "default": "{{fallback_reason}}", "description": "none for promise and paid. transferred: restructuring, human, support. no_promise: refused, hardship, dispute, service_error. not_verified: failed, declined. not_reached: callback, no_callback, wrong_number, deceased, unclear."},
                    }},
                }},
            },
            "pre_process_code": FALLBACK_PRE,
        }
    ],
    "nodes": {
        "setup": code_node("setup", "opening"),
        "opening": {
            "name": "opening", "node_type": "conversation",
            "on_enter": {"type": "tts", "text": "Hello, I am a digital assistant calling from Freya Bank. Please note that we record this call. Am I speaking with {{title}} {{last_name}}?"},
            "on_enter_first_entry_only": True,
            "task_message": OPENING_TASK,
            "tools": [CALLBACK, transfer_tool(["general"]),
                      close_tool(["not_reached", "not_verified", "transferred"], ["callback", "no_callback", "wrong_number", "deceased", "unclear", "declined", "human"],
                                 "not_reached: callback, no_callback, wrong_number, deceased, unclear. not_verified: declined. transferred: human.")],
            "extraction_schema": [
                {"name": "speaker", "type": "string", "enum_values": ["customer_confirmed", "someone_else", "unclear"], "min_confidence": 0.6,
                 "description": "Who is on the line. customer_confirmed ONLY if the person answered the question 'Am I speaking with {{title}} {{last_name}}?' with yes, that's me, speaking, or the customer's own name. someone_else if they said they are another person (relative, friend, colleague) or that the customer is not there. unclear for hello, go ahead, who is this, or anything else."},
                {"name": "other_person", "type": "string", "enum_values": ["yes"], "min_confidence": 0.6,
                 "description": "Set to yes only if at any point in the conversation the person on the line said they are NOT {{first_name}} {{last_name}} (for example a husband, wife, relative or someone who took the phone), or that this is a wrong number, or that the customer has died. Leave empty otherwise."},
            ],
            "max_node_turns": 30, "max_turn_transition": "end",
            "transitions": [
                CLOSED,
                {"target_node": "verify", "description": "The customer confirmed who they are",
                 "condition": {"logic": "or", "conditions": [{"logic": "and", "conditions": [
                     {"variable": "speaker", "operator": "equals", "operand": "customer_confirmed"},
                     {"variable": "other_person", "operator": "is_not_set"},
                     {"variable": "schedule_callback_response.status", "operator": "is_not_set"}]}]}},
                stay("opening"),
            ],
        },
        "verify": {
            "name": "verify", "node_type": "conversation",
            "on_enter": {"type": "tts", "text": "Thank you. Before we continue, I need to ask you two short security questions. What is your date of birth?"},
            "on_enter_first_entry_only": True,
            "task_message": VERIFY_TASK,
            "tools": [VERIFY, transfer_tool(["general"]),
                      close_tool(["not_verified", "transferred"], ["declined", "failed", "human"], "not_verified: declined or failed. transferred: human.")],
            "max_node_turns": 30, "max_turn_transition": "end",
            "transitions": [
                CLOSED,
                {"target_node": "fetch_account", "description": "Both security answers passed",
                 "condition": {"logic": "or", "conditions": is_true("verify_identity_response.data.all_verified")}},
                {"target_node": "gate", "description": "Call this only when the last verify_identity result says all_verified true (both security answers correct).", "is_tool_call": True,
                 "condition": {"operator": "matches_intent", "description": "verify_identity reported that both security answers are correct"}},
                {"target_node": "verify_failed", "description": "Three wrong answers",
                 "condition": {"logic": "or", "conditions": [{"variable": "verify_identity_response.data.wrong_answers_left", "operator": "equals", "operand": "0"}]}},
                stay("verify"),
            ],
        },
        "verify_failed": {
            "name": "verify_failed", "node_type": "api_request", "passthrough": True, "passthrough_default_transition": "end",
            "on_enter": {"type": "tts", "text": "I am sorry, but I could not verify your identity, so I cannot discuss anything further on this call. Please use the Freya Bank mobile app or visit a branch. Thank you for your time, goodbye."},
            "disable_inactivity_monitor": True,
            "pre_actions": [api_tool("close_call", "Close the call.", {
                "outcome": {"type": "string", "default": "not_verified"}, "reason": {"type": "string", "default": "failed"}}, ["outcome", "reason"])],
            "response_mapping": [{"path": "data.ok", "variable": "failed_close_ok"}],
            "transitions": [{"target_node": "end", "description": "always", "condition": {"operator": "always"}}],
        },
        "gate": {
            "name": "gate", "node_type": "code", "passthrough": True, "passthrough_default_transition": "verify",
            "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True,
            "pre_actions": [{"type": "function", "function": {"name": "code_exec", "handler": "__function__:code_exec", "parameters": {"type": "object", "properties": {
                "code": {"type": "string", "default": "vars['gate_seen'] = 'yes'\n"}, "timeout_ms": {"type": "number", "default": 5000}}}}}],
            "transitions": [
                {"target_node": "fetch_account", "description": "verified", "condition": {"logic": "or", "conditions": is_true("verify_identity_response.data.all_verified")}},
                {"target_node": "verify", "description": "always", "condition": {"operator": "always"}}],
        },
        "fetch_account": {
            "name": "fetch_account", "node_type": "api_request", "passthrough": True, "passthrough_default_transition": "facts",
            "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True,
            "pre_actions": [api_tool("get_account", "Get the late products.", {}, [], retries=1)],
            "response_mapping": [{"path": "data.products", "variable": "products"}],
            "transitions": [{"target_node": "facts", "description": "always", "condition": {"operator": "always"}}],
        },
        "facts": code_node("facts", "negotiate"),
        "negotiate": {
            "name": "negotiate", "node_type": "conversation",
            "on_enter": {"type": "tts", "text": "{{debt_line}}"},
            "on_enter_first_entry_only": True,
            "task_message": NEGOTIATE_TASK,
            "tools": [PROMISE, transfer_tool(["restructuring", "support", "general"]),
                      close_tool(["promise", "paid", "transferred", "no_promise"], ["none", "restructuring", "support", "human", "refused", "hardship", "dispute", "service_error"],
                                 "promise and paid: reason none. transferred: restructuring, support or human. no_promise: refused, hardship, dispute or service_error.")],
            "max_node_turns": 40, "max_turn_transition": "end",
            "transitions": [CLOSED, stay("negotiate")],
        },
        "end": {
            "name": "end", "node_type": "end_call", "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True, "transitions": [],
            "terminal": {"type": "function", "function": {"name": "call_closed", "handler": "__function__:end_call",
                                                          "parameters": {"type": "object", "properties": {"message_mode": {"type": "string", "default": "none"}}}}},
        },
    },
}

# the verify_failed close also marks the call closed for the fallback
wf["nodes"]["verify_failed"]["pre_actions"][0]["post_process_code"] = CLOSE_POST

OUT.write_text(json.dumps(wf, indent=1))
print("wrote", OUT)
