"""Layer B: extraction accuracy on generated policies. Renders permuted IRs (scripts/permute_policies.py) as documents —
a clean single-file brief, or a raw pack (cover mail with obsolete quotes, stale base policy, signed memo that overrides
it, code list) — runs extract.py on them, and diffs the extracted IR against the generator's IR on every operative field.
It also compiles the extracted IR and runs the IR-parameterized invariants with the generator's IR as the truth, so the
report says both "which fields differ" and "would the agent still behave as the policy says".

    .venv/bin/python scripts/layer_b.py render  --perm 0 --style clean|raw [--out results/layer-b]
    .venv/bin/python scripts/layer_b.py run     --perms 0:clean,3:clean,10:clean,20:clean,4:raw,6:raw,14:raw,26:raw [--lanes 2]
    .venv/bin/python scripts/layer_b.py diff    --perm 0 --policy out/lb-00.policy.json

Claude-only (no Freya calls). Each extraction is ~4-5 minutes and ~$1.5.
"""
from __future__ import annotations

import argparse
import copy
import datetime
import json
import pathlib
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
import policy as P  # noqa: E402

PERM_DIR = ROOT / "results/permutations"
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
ORD = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth", 11: "eleventh", 12: "twelfth", 14: "fourteenth", 15: "fifteenth"}


# ---------------------------------------------------------------------------------------------------------- rendering
def _ordinal(n):
    return ORD.get(n, f"{n}th")


def _fmt_date(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%B')} {d.year}"


def _id_format(r):
    f = r["answer_format"]
    if f == "date":
        order = "day, then month, then year" if r.get("numeric_date_order", "dmy") == "dmy" else "month, then day, then year"
        return f"Format date, sent as YYYY-MM-DD; a date given only as numbers is read {order}."
    if f == "digits":
        return f"Format digits, exactly {r['digits']} digits including leading zeros."
    if f == "year":
        return "Format year, four digits."
    return "Format text: letters and digits, spaces removed."


def _deadline_text(dl):
    k = dl["kind"]
    if k == "nth_business_day":
        return f"the {_ordinal(dl['n'])} business day after today"
    if k == "calendar_days":
        adj = "the next business day" if dl["adjustment"] == "following" else "the previous business day"
        return f"today plus {dl['n']} calendar days; if that day is not a business day, {adj}"
    if k == "end_of_month":
        month = {0: "the current calendar month", 1: "next month"}.get(dl.get("month_offset", 0), f"the month {dl.get('month_offset')} months ahead")
        if dl["basis"] == "business":
            return f"the last business day of {month}"
        adj = "the next business day" if dl["adjustment"] == "following" else "the previous business day"
        return f"the last calendar day of {month}; if that day is not a business day, {adj}"
    if k == "fixed_date":
        adj = "the next business day" if dl["adjustment"] == "following" else "the previous business day"
        return f"{_fmt_date(dl['date'])} for everyone; if that day is not a business day, {adj}"
    if k == "day_of_month":
        when = {0: "this month", 1: "next month"}.get(dl.get("month_offset", 0), f"{dl.get('month_offset')} months ahead")
        adj = "the next business day" if dl["adjustment"] == "following" else "the previous business day"
        return f"the {_ordinal(dl['day'])} of {when}; if that day is not a business day, {adj}"
    raise ValueError(k)


def _attempts_text(n):
    s = ("Attempt 1: propose the full past-due amount on the last business day of this week; if today is that day, the last business day of next week. "
         "If the customer already said the full amount is too much, attempt 1 proposes the floor instead.")
    if n > 1:
        s += " Attempt 2: propose the floor amount on the deadline."
    return s


def _vocab(ir):
    O = ir["outcomes"]
    return {r["outcome"]: r["reasons"] for r in O["table"]}


def _sc(ir, name):
    return next(s for s in ir["special_cases"] if s["name"] == name)


def _bdays(days):
    names = [WEEKDAYS[d] for d in days]
    return names[0] + " to " + names[-1] if days == list(range(days[0], days[-1] + 1)) else ", ".join(names)


def render_clean(ir, bank, idreqs=None, limit=None, bands=None, retry=None, human_ask=None, cb_days=None, header=None):
    """One self-contained brief. The keyword overrides let the raw pack render a *stale* base policy."""
    idreqs = idreqs or ir["identity"]["requirements"]
    limit = ir["identity"]["wrong_answer_limit"] if limit is None else limit
    bands = bands or ir["bands"]
    retry = ir["promise_write"]["retry_on_failure"] if retry is None else retry
    human = _sc(ir, "human"); human_ask = human.get("ask_once_first", False) if human_ask is None else human_ask
    cb = ir["third_party"]["callback"]; cb_days = cb_days or cb["days"]
    I, O, V = ir["identity"], ir["outcomes"], _vocab(ir)
    hard, restr, paid, disp, rtt = _sc(ir, "hardship"), _sc(ir, "restructuring"), _sc(ir, "already_paid"), _sc(ir, "dispute"), _sc(ir, "refuse_to_talk")
    floors, naming = ir["amounts"]["floors"], ir["phrases"]["product_naming"]
    if not floors and ir["amounts"].get("floor_rules"):
        floors = {t: "" for t in ir["amounts"]["floor_rules"] if t != "*"}
    notes = ir["notes"]
    mp = ir["multi_product"]["max_products"]
    L = [header or f"Collection-call brief for {bank}. Sole policy authority.", "", f"# {bank} — outbound collection calls", ""]
    L += ["## 1. Opening and the person on the line",
          f"1. First sentence: say you are the automated assistant of {bank} and that the call is recorded. Then ask whether you are speaking with the customer, using title and last name.",
          "2. Before the identity check is complete, never say the words collections, debt, payment, credit card or loan, and do not say why you are calling.",
          "3. Only a clear yes, \"speaking\" or the customer's own name counts as confirmation. \"Hello\", \"go ahead\" and \"who is this\" do not. Ask once more; if it is still unclear after the second ask, close as "
          f"`{I['unclear_holder_outcome'][0]}` / `{I['unclear_holder_outcome'][1]}`.",
          f"4. If asked whether this is a robot: say \"I am {bank}'s digital assistant.\" If the person suspects a scam: say they can verify the call by phoning {bank}'s customer service number, and continue.",
          "5. Someone other than the customer (relative, colleague, friend): say nothing about the purpose. Ask when the customer can be reached.",
          f"6. A callback is for {'today or the next business day' if cb_days == 'today_or_next_business_day' else 'the next business day only, never today'}, from {cb['start']} to {cb['end']}, both included, and later than `now`. "
          f"Call `schedule_callback` with the date and the time, then close as `{cb['scheduled_outcome'][0]}` / `{cb['scheduled_outcome'][1]}`.",
          f"7. If the person names a time outside that window, say so and ask once more. If no valid time results, close as `{cb['no_callback_outcome'][0]}` / `{cb['no_callback_outcome'][1]}`.",
          f"8. Wrong number: apologise and close as `{ir['third_party']['wrong_number_outcome'][0]}` / `{ir['third_party']['wrong_number_outcome'][1]}`.",
          f"9. The customer has died: say \"{ir['third_party']['deceased_sentence']}\" and close as `{ir['third_party']['deceased_outcome'][0]}` / `{ir['third_party']['deceased_outcome'][1]}`.",
          f"10. The customer refuses to talk: close as `{rtt['action']['outcome']}` / `{rtt['action']['reason']}`.", ""]
    L += ["## 2. Identity check",
          f"11. Ask {len(idreqs)} security question{'s' if len(idreqs) > 1 else ''}, one at a time, in this order. Call `verify_identity` with the field name and the answer after each one:"]
    for i, r in enumerate(idreqs, 1):
        L.append(f"    {i}. `{r['field']}` — ask for {r['ask_text']}. {_id_format(r)}")
    L += [f"12. A wrong answer may be asked again. {limit} wrong answers in total end the check, whichever question they were on; the API's `wrong_answers_left` is the count to use.",
          f"13. After {limit} wrong answers, do not state the debt. Say \"{I['failed_instruction']}\" and close as `{I['failed_outcome'][0]}` / `{I['failed_outcome'][1]}`.",
          f"14. If the customer declines to answer or asks what the call is about before answering, explain once that the questions protect their account. A second refusal closes as `{I['declined_outcome'][0]}` / `{I['declined_outcome'][1]}`.",
          f"15. A request for a human agent during the identity check: {'ask once whether you can help first; if they insist, ' if human_ask else ''}call `transfer_to_agent` with queue `{human['action']['queue']}` and close as `{human['action']['outcome']}` / `{human['action']['reason']}`.", ""]
    L += ["## 3. Calendar",
          f"16. Use the call variable `now` as the clock, never the machine clock. Business days are {_bdays(ir['calendar']['business_days'])}, except {bank} holidays: {', '.join(ir['calendar']['holidays']) or 'none this season'}.",
          "17. \"Next <weekday>\" means that weekday of the following week, even when today is that weekday; \"this <weekday>\" means the coming one.", ""]
    L += ["## 4. Products, amounts and deadlines",
          f"18. After verification say you are calling from the {bank} collections team about a late payment. `get_account` returns up to {mp} product{'s' if mp > 1 else ''}. State {'every product' if mp > 1 else 'the product'} with its past-due amount and days late"
          + (", all before asking anything; then ask once whether they can pay all of it today." if mp > 1 else "; then ask \"Can you make this payment today?\"."),
          "19. Product types and the lowest amount this call may accept (the floor) per type, as returned by `get_account`:"]
    for t, prop in floors.items():
        L.append(f"    - `{t}` (say \"{naming.get(t, t.replace('_', ' '))}\"): floor is the `{prop}` field; the full amount is `past_due`." if prop else f"    - `{t}` (say \"{naming.get(t, t.replace('_', ' '))}\").")
    rules = ir["amounts"].get("floor_rules") or {}
    if rules:
        r0 = next(iter(rules.values()))
        if r0["kind"] == "percent":
            L[-len(floors) - 1:] = ["19. Product types, as returned by `get_account`: " + ", ".join(f"`{t}` (say \"{naming.get(t, t.replace('_', ' '))}\")" for t in floors or rules if t != "*") + ". The full amount is `past_due`. "
                                   f"The lowest amount this call may accept (the floor) is {r0['percent']} percent of the past-due amount" + (f", and never less than {r0['min_amount']:.2f}" if r0.get("min_amount") else "") + "; no bank field carries it, you compute it."]
        elif r0["kind"] == "fixed":
            L[-len(floors) - 1:] = ["19. Product types, as returned by `get_account`: " + ", ".join(f"`{t}` (say \"{naming.get(t, t.replace('_', ' '))}\")" for t in floors or rules if t != "*") + ". The full amount is `past_due`. "
                                   f"The lowest amount this call may accept (the floor) is a fixed {r0['amount']:.2f} for every product (or the full amount when that is lower); no bank field carries it."]
    L += ["20. Ask for the full past-due amount first. Never ask \"how much can you pay?\". Any amount between the floor and the full amount is accepted; an amount below the floor is refused, and the floor is offered once per product with the words \"the rest stays overdue\". "
          "If the customer refuses the floor too, there is nothing to record for that product.",
          "21. A promise date must be today or later, a business day, and not after the deadline. A weekend day or holiday rolls to the next business day. A vague date (next week, when I get paid): ask once for the exact day; if none follows, propose the deadline. "
          "A date after the deadline: offer the deadline instead.",
          "22. The deadline depends on how late the product is:", "",
          "| Days late | Band | Deadline | Persuasion attempts |", "|---|---|---|---|"]
    for b in bands:
        L.append(f"| {b['days_late_min']} to {b['days_late_max']} | {b['name']} | {_deadline_text(b['deadline'])} | {len(b['attempts'])} |")
    L += ["", "23. A flat refusal or a non-answer uses one persuasion attempt per product. " + _attempts_text(max(len(b["attempts"]) for b in bands)) + " Bands with one attempt stop after attempt 1.",
          f"24. When the attempts for a product are used up without a promise, that product gets no promise{' and is noted `' + O['refused_reason'] + '`' if notes['enabled'] else ''}.", ""]
    L += ["## 5. Special cases (these win over persuasion)",
          f"25. Already paid: say \"{paid.get('say', 'Payments can take one business day to appear.')}\". " + (f"Note the product as `{paid['action']['reason']}` and continue with the other products." if paid["action"]["type"] == "note" else f"Close as `{paid['action']['outcome']}`."),
          "26. Dispute (not their debt, never had the product, closed or paid off before): " + (f"note the product as `{disp['action']['reason']}` and continue with the other products." if disp["action"]["type"] == "note" else f"close as `{disp['action']['outcome']}` / `{disp['action']['reason']}`."),
          f"27. Hardship (illness, a death in the family, job loss): say one short sentence of sympathy, make no persuasion attempt, and offer a transfer to the `{hard['offer_transfer_queue']}` team. If they accept, call `transfer_to_agent` with queue `{hard['offer_transfer_queue']}` and close as `{hard['offer_outcome'][0]}` / `{hard['offer_outcome'][1]}`. "
          f"If they decline, close as `{hard['action']['outcome']}` / `{hard['action']['reason']}`. A customer in hardship may still name a date and amount; record it.",
          f"28. Restructuring (a payment plan, lower instalments, changing the terms): call `transfer_to_agent` with queue `{restr['action']['queue']}` and close as `{restr['action']['outcome']}` / `{restr['action']['reason']}`. Promises already recorded on this call stay recorded.",
          f"29. A request for a human after verification: {'ask once whether you can help first; if they insist, ' if human_ask else 'do not ask whether you can help; '}transfer to `{human['action']['queue']}` and close as `{human['action']['outcome']}` / `{human['action']['reason']}`.", ""]
    L += ["## 6. Recording a promise",
          "30. Read the product, the amount and the date back and ask \"Do you confirm?\". Call `create_promise` only after a clear yes; one promise per product. A change at the read-back is a new proposal: validate it and read it back again.",
          "31. After a successful write say \"You will receive a text message confirming this promise.\" Never say a promise is recorded before the API confirmed it.",
          f"32. If `create_promise` fails, " + ("do not retry: " if retry == 0 else f"try {'once' if retry == 1 else str(retry) + ' more times'} more; if it still fails, ") + f"say you could not record it and close as `{O['no_promise_outcome']}` / `{O['service_error_reason']}`" + (f" (note the product `{O['service_error_reason']}`)." if notes["enabled"] else "."),
          "33. If the customer asks whether a recorded promise can be changed: say \"You can change it in the mobile app.\"", ""]
    if mp == 1:
        L += ["## 7. Several products", "34. A customer has one product; the rules above apply to it alone.", "35. `add_note` is never used.", ""]
    else:
        L += ["## 7. Several products",
              "34. Every product is handled on the same call: a common date is checked against each product's own deadline and clamped to it; one read-back covers all pending promises; a transfer after a recorded promise keeps the promise.",
              ("35. Before closing a call that is not a transfer, add exactly one note (`add_note`) for each product without a promise, with the reason that applies: " + ", ".join(f"`{r}`" for r in notes["reasons"]) + ". No notes on a transfer.") if notes["enabled"] else "35. `add_note` is never used.", ""]
    L += ["## 8. Closing",
          "36. Thank the customer and say goodbye before `close_call`, which is the last tool call. Outcomes and reasons (`close_call` takes `outcome` and, where listed, `reason`):", ""]
    for o, rs in V.items():
        L.append(f"- `{o}`: " + (", ".join(f"`{r}`" for r in rs) if rs else "(no reason)"))
    L += ["", f"37. At least one promise recorded: `{O['promise_outcome']}`. A transfer: `{O['transfer_outcome']}` with the transfer's reason, even after a promise. "
          + (f"All products already paid: `{O['paid_outcome']}`. No promise: `{O['no_promise_outcome']}` with the reason of the first product in `get_account` order that is not paid." if mp > 1 else f"Already paid: `{O['paid_outcome']}`. No promise: `{O['no_promise_outcome']}` with the reason that applies."), ""]
    return "\n".join(L)


def render_raw(ir, bank, k):
    """Cover mail (quotes obsolete settings) + stale base policy + signed memo (the truth for the overridden rules) + code list."""
    I = ir["identity"]
    reqs = I["requirements"]
    stale_reqs = reqs[1:] + reqs[:1] if len(reqs) > 1 else reqs
    stale_limit = I["wrong_answer_limit"] + 1 if I["wrong_answer_limit"] < 5 else I["wrong_answer_limit"] - 1
    bands = copy.deepcopy(ir["bands"])
    stale_bands = copy.deepcopy(bands)
    stale_bands[-1]["deadline"] = {"kind": "nth_business_day", "n": 6}
    retry = ir["promise_write"]["retry_on_failure"]
    stale_retry = 1 if retry != 1 else 2
    human_ask = _sc(ir, "human").get("ask_once_first", False)
    cb_days = ir["third_party"]["callback"]["days"]
    stale_cb = "today_or_next_business_day" if cb_days == "next_business_day" else "next_business_day"
    memo_id = f"M{k + 40}"
    policy = render_clean(ir, bank, idreqs=stale_reqs, limit=stale_limit, bands=stale_bands, retry=stale_retry, human_ask=not human_ask, cb_days=stale_cb,
                          header=f"Legacy operating policy P{k + 10} for {bank}, effective 1 October 2026; subject to signed memo {memo_id}.")
    policy = policy.replace("## 8. Closing", "## 8. Closing\n(Valid outcome, reason and queue codes are listed in the code list C; this policy repeats them for convenience.)")
    order = ", ".join(f"`{r['field']}` {'FIRST' if i == 0 else 'SECOND' if i == 1 else 'THIRD' if i == 2 else 'FOURTH'}" for i, r in enumerate(reqs))
    memo = "\n".join([
        f"SIGNED MEMO {memo_id} — 10 October 2026, 12:00 UTC", f"Approved: Operations and Customer Care, {bank}", "",
        f"This memo replaces these P{k + 10} settings and nothing else:",
        f"A. Security asks in this order: {order}. Keep each question's wording and format. {I['wrong_answer_limit']} wrong answers TOTAL across the whole check, not {stale_limit}.",
        f"B. For days late {bands[-1]['days_late_min']}–{bands[-1]['days_late_max']} only, the deadline is no longer the sixth business day after today but {_deadline_text(bands[-1]['deadline'])}. The other band{'s' if len(bands) > 2 else ''} keep{'s' if len(bands) == 2 else ''} P{k + 10}.",
        "C. " + ("Zero retries after a failed create_promise; the service-error outcome applies after the first failure." if retry == 0 else f"After a failed create_promise retry {'once' if retry == 1 else str(retry) + ' times'}, not {stale_retry}." ),
        "D. Human requests " + ("transfer immediately, without asking whether the assistant can help." if not human_ask else "are handled by first asking once whether the assistant can help; transfer only if they insist."),
        "E. Callbacks are " + ("for the next business day ONLY, never today" if cb_days == "next_business_day" else "for today or the next business day") + "; the existing window remains.",
        "", f"All remaining P{k + 10} wording, holidays, notes and outcome precedence remain effective. Old statements in the cover email are historical quotations."])
    mail = "\n".join([
        f"From: rollout@{bank.lower().replace(' ', '')}.example.invalid", "Date: 10 October 2026 12:05 UTC", f"Subject: Sunday handover bundle — apply signed {memo_id}", "",
        f"Read the attached P{k + 10} policy, signed {memo_id} memo, and code list C together. {memo_id} overrides only its named P{k + 10} rules; all other rules remain. "
        "The code list is the sole valid outcome/reason/queue vocabulary. This message quotes old settings for history only.", "",
        f"> Forwarded 1 October: use {stale_limit + 1} wrong answers, retry {stale_retry + 1} failed saves, ask {stale_reqs[0]['field']} first, and the fourth business day for the latest band. "
        f"{'No callbacks on the same day' if stale_cb == 'next_business_day' else 'Same-day callbacks are fine'}.", "",
        "Those quoted settings are obsolete wherever the memo or the policy says otherwise. Do not restore them."])
    V = _vocab(ir)
    codes = ["CODE LIST C — authoritative enum combinations", ""] + [f"{o}: " + (" | ".join(rs) if rs else "(omit reason)") for o, rs in V.items()]
    codes += ["", "Transfer queues: " + ", ".join(sorted({_sc(ir, 'restructuring')['action']['queue'], _sc(ir, 'human')['action']['queue'], _sc(ir, 'hardship')['offer_transfer_queue']})),
              "add_note reasons: " + (", ".join(ir["notes"]["reasons"]) if ir["notes"]["enabled"] else "(add_note is not used)"), "Only these combinations are allowed; omit reason where stated."]
    return {"01-mail.txt": mail, "02-policy.md": policy, "03-memo.txt": memo, "04-codes.txt": "\n".join(codes)}


def render_thread(ir, bank, k):
    """One mail thread (oldest first): a stale policy summary, a memo that changes several rules but gets one of them wrong,
    and a later correction that reverses that one change. The generator IR is the state after the last mail."""
    I = ir["identity"]; reqs = I["requirements"]
    stale_reqs = reqs[1:] + reqs[:1] if len(reqs) > 1 else reqs
    stale_limit = I["wrong_answer_limit"] + 1 if I["wrong_answer_limit"] < 5 else I["wrong_answer_limit"] - 1
    bands = copy.deepcopy(ir["bands"]); stale_bands = copy.deepcopy(bands); stale_bands[-1]["deadline"] = {"kind": "nth_business_day", "n": 6}
    retry = ir["promise_write"]["retry_on_failure"]; wrong_retry = (retry + 2) % 3
    cb_days = ir["third_party"]["callback"]["days"]; stale_cb = "today_or_next_business_day" if cb_days == "next_business_day" else "next_business_day"
    human_ask = _sc(ir, "human").get("ask_once_first", False)
    base = render_clean(ir, bank, idreqs=stale_reqs, limit=stale_limit, bands=stale_bands, retry=retry, human_ask=not human_ask, cb_days=stale_cb,
                        header=f"Operating rules of {bank} as circulated on 1 October 2026 (see the later messages in this thread for changes).")
    order = ", ".join(f"`{r['field']}`" for r in reqs)
    mail2 = "\n".join([f"From: operations@{bank.lower().replace(' ', '')}.example.invalid", "Date: 7 October 2026 09:40 UTC", "Subject: RE: collection-call rules — changes effective immediately", "",
                        "Team, four changes to the rules below, everything else stands:",
                        f"1. Security questions in this order: {order}. Question wording and formats unchanged. {I['wrong_answer_limit']} wrong answers in total end the check (was {stale_limit}).",
                        f"2. Days late {bands[-1]['days_late_min']}–{bands[-1]['days_late_max']}: the deadline is {_deadline_text(bands[-1]['deadline'])} (no longer the sixth business day).",
                        f"3. After a failed create_promise: {'no retry at all' if wrong_retry == 0 else 'retry ' + ('once' if wrong_retry == 1 else str(wrong_retry) + ' times')}.",
                        f"4. Callbacks: {'next business day only, never today' if cb_days == 'next_business_day' else 'today or the next business day'}. Human requests: "
                        + ("ask once whether you can help first." if human_ask else "transfer immediately, do not ask whether you can help."), "", "— Operations"])
    mail3 = "\n".join([f"From: compliance@{bank.lower().replace(' ', '')}.example.invalid", "Date: 9 October 2026 16:15 UTC", "Subject: RE: RE: collection-call rules — correction to point 3", "",
                        f"Correction to Operations' message of 7 October, point 3 only: after a failed create_promise the agent "
                        + ("must NOT retry; the service-error outcome applies after the first failure." if retry == 0 else f"retries {'once' if retry == 1 else str(retry) + ' times'}, not {'zero times' if wrong_retry == 0 else str(wrong_retry)}.")
                        + " Points 1, 2 and 4 of that message stand. The 1 October rules apply wherever the 7 October message did not change them.", "", "— Compliance"])
    thread = "\n\n" + ("=" * 70) + "\n\n".join(["", mail3, mail2, "From: policy@" + bank.lower().replace(" ", "") + ".example.invalid\nDate: 1 October 2026 08:00 UTC\nSubject: collection-call rules\n\n" + base])
    return {"thread.txt": "Mail thread, newest first.\n" + thread}


def render(perm: int, style: str, out_dir: pathlib.Path) -> list[pathlib.Path]:
    ir = json.load(open(PERM_DIR / f"perm-{perm:02d}.policy.json"))
    bank = ir["bank_name"]
    d = out_dir / f"lb-{perm:02d}"
    d.mkdir(parents=True, exist_ok=True)
    spec = json.load(open(PERM_DIR / f"perm-{perm:02d}.openapi.json"))
    def scrub(o):
        if isinstance(o, dict):
            for k in ("summary", "description"):
                o.pop(k, None)
            for v in o.values():
                scrub(v)
        elif isinstance(o, list):
            for v in o:
                scrub(v)
    scrub(spec["paths"])
    (d / "openapi.json").write_text(json.dumps(spec, indent=1))
    (d / "truth.policy.json").write_text(json.dumps(ir, indent=1))
    if style == "clean":
        (d / "brief.md").write_text(render_clean(ir, bank))
        return [d / "brief.md"]
    files = render_raw(ir, bank, perm) if style == "raw" else render_thread(ir, bank, perm)
    for n, t in files.items():
        (d / n).write_text(t)
    return [d / n for n in files]


# -------------------------------------------------------------------------------------------------------------- diff
def _floor_rules_key(ir: dict) -> dict:
    """Canonical floor rules: a "*" rule is expanded to every product type; numbers normalised."""
    rules = ir["amounts"].get("floor_rules") or {}
    types = sorted({t for t in list(ir["amounts"].get("floors") or {}) + list(rules) + list(ir.get("phrases", {}).get("product_naming") or {}) if t != "*"})
    out = {}
    for t in types:
        r = rules.get(t) or rules.get("*")
        if r:
            out[t] = {k: (float(v) if isinstance(v, (int, float)) else v) for k, v in r.items() if k in ("kind", "field", "percent", "min_amount", "amount", "round") and v not in (None, 0, "")}
    return out


def _deadline_key(dl: dict) -> dict:
    """Canonical deadline: the adjustment is meaningless for a business-basis month end or an nth business day."""
    d = {k: v for k, v in dl.items()}
    if d.get("kind") == "nth_business_day" or (d.get("kind") == "end_of_month" and d.get("basis") == "business"):
        d.pop("adjustment", None)
    if d.get("month_offset") in (0, None):
        d.pop("month_offset", None)
    return d


def operative(ir: dict) -> dict:
    """The fields that change behaviour; prose fields are left out."""
    I, C, O, N, cb = ir["identity"], ir["calendar"], ir["outcomes"], ir["notes"], ir["third_party"]["callback"]
    sc = {s["name"]: s for s in ir["special_cases"]}
    def scv(name):
        s = sc.get(name)
        if not s:
            return None
        a = s["action"]
        return {"type": a.get("type"), "outcome": a.get("outcome") or "", "reason": a.get("reason") or "", "queue": a.get("queue") or "",
                "ends_call": bool(s.get("ends_call", True)), "offer_queue": s.get("offer_transfer_queue") or "", "offer_outcome": list(s.get("offer_outcome") or ["", ""]),
                "ask_once_first": bool(s.get("ask_once_first", False))}
    return {
        "identity.fields": [(r["field"], r["answer_format"], int(r.get("digits") or 0) if r["answer_format"] == "digits" else 0, r.get("numeric_date_order", "dmy") if r["answer_format"] == "date" else "") for r in I["requirements"]],
        "identity.wrong_answer_limit": I["wrong_answer_limit"],
        "identity.outcomes": {k: list(I[k]) for k in ("failed_outcome", "declined_outcome", "unclear_holder_outcome")},
        "callback": {"days": cb["days"], "start": cb["start"], "end": cb["end"], "scheduled": list(cb["scheduled_outcome"]), "no_callback": list(cb["no_callback_outcome"])},
        "third_party.outcomes": {"wrong_number": list(ir["third_party"]["wrong_number_outcome"]), "deceased": list(ir["third_party"]["deceased_outcome"])},
        "calendar": {"holidays": sorted(C["holidays"]), "business_days": sorted(C["business_days"])},
        "bands": [(b["days_late_min"], b["days_late_max"], _deadline_key(b["deadline"]), len(b["attempts"])) for b in sorted(ir["bands"], key=lambda b: b["days_late_min"])],
        "floors": dict(ir["amounts"]["floors"]),
        "floor_rules": _floor_rules_key(ir),
        "max_products": ir["multi_product"]["max_products"],
        "notes": {"enabled": N["enabled"], "reasons": sorted(N["reasons"]) if N["enabled"] else []},
        "outcomes": {"promise": O["promise_outcome"], "paid": O["paid_outcome"], "transfer": O["transfer_outcome"], "no_promise": O["no_promise_outcome"],
                     "service_error": O["service_error_reason"], "refused": O["refused_reason"], "table": {r["outcome"]: sorted(r["reasons"]) for r in O["table"]}},
        "special.already_paid": scv("already_paid"), "special.dispute": scv("dispute"), "special.hardship": scv("hardship"),
        "special.restructuring": scv("restructuring"), "special.human": scv("human"), "special.refuse_to_talk": scv("refuse_to_talk"),
        "retry_on_failure": ir["promise_write"]["retry_on_failure"],
    }


def diff(truth: dict, got: dict) -> list[dict]:
    a, b = operative(truth), operative(got)
    out = []
    for k in a:
        if json.dumps(a[k], sort_keys=True, default=str) != json.dumps(b.get(k), sort_keys=True, default=str):
            out.append({"field": k, "truth": a[k], "extracted": b.get(k)})
    return out


def functional(truth_path, policy_path, openapi_path) -> dict:
    """Compile the extracted IR; run the invariant scenarios with the generator's IR as the truth."""
    import compile as C
    import invariants as I
    truth = P.PolicyIR.load(str(truth_path))
    got = P.PolicyIR.load(str(policy_path))
    tools = C.parse_openapi(str(openapi_path))
    errs = P.validate(got, C.tool_enums(tools))
    if errs:
        return {"invalid": errs}
    wf = C.compile_workflow(got, tools)
    static = C.static_check(wf, tools)
    res = {}
    for sc in I.SCENARIOS:
        try:
            problems, bank = I.run_scenario(truth, wf, sc, tools)
        except Exception as e:  # a script mismatch (e.g. different identity order) shows up here
            problems = [f"driver: {e}"]
        res[sc] = problems
    return {"static": static, "scenarios": res}


# --------------------------------------------------------------------------------------------------------------- run
def run_one(perm, style, out_dir, log):
    docs = render(perm, style, out_dir)
    slot = f"lb-{perm:02d}"
    cmd = [str(ROOT / ".venv/bin/python"), str(ROOT / "extract.py"), ",".join(str(p.relative_to(ROOT)) for p in docs), str((out_dir / slot / "openapi.json").relative_to(ROOT)), slot]
    t0 = time.time()
    with open(out_dir / slot / "extract.log", "w") as f:
        r = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, timeout=1800)
    dt = time.time() - t0
    rec = {"perm": perm, "style": style, "slot": slot, "exit": r.returncode, "seconds": round(dt)}
    pol = ROOT / "out" / f"{slot}.policy.json"
    if r.returncode == 0 and pol.exists():
        truth = json.load(open(out_dir / slot / "truth.policy.json"))
        got = json.load(open(pol))
        rec["diff"] = diff(truth, got)
        rec["functional"] = functional(out_dir / slot / "truth.policy.json", pol, out_dir / slot / "openapi.json")
        rec["unresolved"] = got.get("unresolved", [])
        aud = ROOT / "out" / f"{slot}.audit.json"
        if aud.exists():
            a = json.load(open(aud)); rec["audit_fixed"] = a.get("fixed", []); rec["audit_unresolved"] = a.get("unresolved", [])
    (out_dir / slot / "result.json").write_text(json.dumps(rec, indent=1, default=str))
    print(f"[{slot} {style}] exit={r.returncode} {dt:.0f}s diffs={len(rec.get('diff', []))} functional={ {k: len(v) for k, v in rec.get('functional', {}).get('scenarios', {}).items() if v and not v[0].startswith('n/a')} }", file=log, flush=True)
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["render", "run", "diff"])
    ap.add_argument("--perm", type=int); ap.add_argument("--style", default="clean", choices=["clean", "raw", "thread"])
    ap.add_argument("--perms", default="0:clean,3:clean,10:clean,20:clean,4:raw,6:raw,14:raw,26:raw")
    ap.add_argument("--policy"); ap.add_argument("--out", default="results/layer-b"); ap.add_argument("--lanes", type=int, default=2)
    a = ap.parse_args()
    out_dir = ROOT / a.out
    if a.cmd == "render":
        for p in render(a.perm, a.style, out_dir):
            print(p)
        return
    if a.cmd == "diff":
        truth = json.load(open(out_dir / f"lb-{a.perm:02d}" / "truth.policy.json"))
        got = json.load(open(a.policy))
        print(json.dumps(diff(truth, got), indent=1, default=str))
        return
    jobs = [(int(x.split(":")[0]), x.split(":")[1]) for x in a.perms.split(",")]
    out_dir.mkdir(parents=True, exist_ok=True)
    log = open(out_dir / "run.log", "a")
    print(f"== layer B run {datetime.datetime.utcnow():%Y-%m-%dT%H:%M}Z: {jobs}", file=log, flush=True)
    with ThreadPoolExecutor(max_workers=a.lanes) as ex:
        recs = list(ex.map(lambda j: run_one(j[0], j[1], out_dir, log), jobs))
    (out_dir / "summary.json").write_text(json.dumps(recs, indent=1, default=str))
    ok = sum(1 for r in recs if r.get("exit") == 0 and not r.get("diff"))
    print(f"{ok}/{len(recs)} extractions match the generator IR on every operative field; summary in {out_dir}/summary.json")


if __name__ == "__main__":
    main()
