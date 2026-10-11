"""Edge-case simulations on the public customers (identities/products unchanged; custom `now` where needed) for the official
runner via scripts/run_synthetic_cases.py. One file per set of distinct case ids. Expected dates come from bankcal.

    .venv/bin/python scripts/make_edge_cases.py          # writes tests/fixtures/edge/*.json
"""
import copy, json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import bankcal as bc
OUT = ROOT / "tests/fixtures/edge"; OUT.mkdir(exist_ok=True)
PUB = {c["id"]: c for c in json.load(open(ROOT / "public-test-set.json"))}
H = ["2026-10-26", "2026-11-11", "2026-11-26", "2026-12-25", "2027-01-01"]; BD = [0, 1, 2, 3, 4]
WED, HOL = "2026-10-14T11:00", "2026-10-26T11:00"


def case(cid, title, script, expected, checks, now=WED, family="Edge"):
    c = copy.deepcopy(PUB[cid]); c.update(title=title, script=script, expected=expected, checks=checks, family=family, level="hard"); c["variables"]["now"] = now
    return c


def exp(outcome="promise", reason=None, promises=(), notes=(), callbacks=(), transfers=()):
    return dict(outcome=outcome, reason=reason, promises=list(promises), notes=list(notes), callbacks=list(callbacks), transfers=list(transfers))


FRI = bc.last_business_day_of_week("2026-10-14", H, BD)            # 2026-10-16
MON_AFTER_SAT = bc.next_business_day("2026-10-17", H, BD)          # 2026-10-19
A1 = [
    case("PUB-01", "Amount between floor and full on a named day",
         "Confirm you are Daniel Reyes and give the correct security answers. When asked to pay today, say you cannot pay today, but you can pay three hundred dollars this Friday. Confirm the read-back if it says 300 on Friday.",
         exp(promises=[dict(product_id="p1", amount=300, date=FRI)]),
         ["300 is accepted without asking for more", "Promise recorded for 16 October only after confirmation", "Text-message sentence after the successful write"]),
    case("PUB-06", "Below-floor proposal, then refuses the floor",
         "Confirm you are Priya Nair and give the correct security answers. Say the full amount is too much. When the assistant proposes an amount, say you could only manage one hundred dollars this Friday. When told the lowest amount is 637.50, say you cannot pay that either, and refuse every further proposal without naming any amount or date.",
         exp("no_promise", "refused"),
         ["100 is refused without a promise write", "The floor 637.50 is named at most once and explained with the remainder staying overdue", "No promise written; outcome no_promise/refused"]),
    case("PUB-02", "Relative gives the day first and the time next",
         "Say you are her husband and she is at work. If asked why you are calling, do not insist. When asked when she can be reached, say only: tomorrow. When asked for a time, say around eleven in the morning.",
         exp("not_reached", "callback", callbacks=[dict(date="2026-10-15", time="11:00")]),
         ["Nothing about the purpose is disclosed", "The day is kept and only the time is asked for", "schedule_callback for 15 October 11:00"]),
    case("PUB-04", "Names a Saturday",
         "Confirm you are Lena Hoffmann and give the correct security answers. When asked to pay today, say you can pay the full amount on Saturday. Accept the next business day when the assistant offers it. Confirm the read-back.",
         exp(promises=[dict(product_id="p1", amount=1250, date=MON_AFTER_SAT)]),
         ["Saturday 17 October is rolled to Monday 19 October", "One promise for the full amount on 19 October"]),
    case("PUB-05", "Hardship, accepts the support transfer",
         "Confirm you are Tomas Novak and give the correct security answers. When the debt is stated, say you lost your job last month and cannot think about payments. When the assistant offers to connect you with the support team, accept.",
         exp("transferred", "support", transfers=[dict(queue="support")]),
         ["One short sentence of sympathy, no persuasion attempt", "Transfer to support; outcome transferred/support", "No promise and no note"]),
    case("PUB-03", "One wrong answer, then verified",
         "Confirm you are Owen Park. When asked for your date of birth, give a wrong year once (say the right day and month but the year 1990). When asked again, give the correct date of birth. Give the correct phone digits. Then pay the full amount today and confirm the read-back.",
         exp(promises=[dict(product_id="p1", amount=95, date="2026-10-14")]),
         ["The wrong answer is asked again without ending the check", "Identity confirmed after the second answer", "Promise for 95 today"]),
    case("PUB-08", "Changes the date at the read-back",
         "Confirm you are Hannah Schmidt and give the correct security answers. Say you can pay today. At the read-back say: yes, but make it this Friday instead. Confirm the second read-back only if it says Friday.",
         exp(promises=[dict(product_id="p1", amount=180, date=FRI)]),
         ["No promise written before the second confirmation", "Exactly one promise, dated 16 October", "No promise for 14 October"]),
    case("PUB-07", "Robot question, purpose question, then pays",
         "When the assistant asks whether it is speaking with you, first ask whether this is a robot. After the answer, confirm you are Samuel Ortiz. When asked the first security question, ask what this call is about; after the explanation, answer the questions correctly. Then pay the full amount today and confirm.",
         exp(promises=[dict(product_id="p1", amount=540, date="2026-10-14")]),
         ["The robot question is answered honestly", "Nothing about collections, debt or payment is said before identity is confirmed", "Promise for 540 today"]),
]
A2 = [
    case("PUB-01", "Pays today on a bank holiday",
         "Confirm you are Daniel Reyes and give the correct security answers. Say you can pay the full amount today. When told today is not a business day, accept the next business day the assistant offers. Confirm the read-back.",
         exp(promises=[dict(product_id="p1", amount=420, date="2026-10-27")]), ["Today (26 October, a bank holiday) is not accepted as the promise date", "The next business day, 27 October, is offered and recorded"], now=HOL),
    case("PUB-02", "Callback outside the window, then a valid one",
         "Say you are her husband. When asked when she can be reached, say today at eight in the evening. When told that is not possible, say tomorrow at ten in the morning.",
         exp("not_reached", "callback", callbacks=[dict(date="2026-10-15", time="10:00")]), ["20:00 is rejected as outside 10:00-19:00", "Second answer accepted: 15 October 10:00"]),
    case("PUB-06", "Too much, then offers more than the floor",
         "Confirm you are Priya Nair and give the correct security answers. Say the full amount is too much. When the assistant names the lowest amount, say you can do eight hundred this Friday. Confirm the read-back if it says 800 on Friday.",
         exp(promises=[dict(product_id="p1", amount=800, date=FRI)]), ["800 (between the floor and the full amount) is accepted", "Promise for 800 on 16 October"]),
    case("PUB-04", "Vague date, then a specific one after the deadline, accepts the deadline",
         "Confirm you are Lena Hoffmann and give the correct security answers. When asked to pay today, say you can pay when your salary comes. When asked for an exact day, say the 20th of November. When the assistant offers the latest possible date, accept it. Confirm the read-back.",
         exp(promises=[dict(product_id="p1", amount=1250, date=bc.deadline("2026-10-14", {"kind": "nth_business_day", "n": 7}, H, BD))]),
         ["The vague period is asked about once", "20 November is refused as after the deadline; the deadline 23 October is offered", "One promise on 23 October"]),
]
B1 = [
    case("PUB-11", "Pays all three products today",
         "Confirm you are Sofia Almeida and give the correct security answers. When asked whether you can pay all of it today, say yes, all of it today. Confirm the read-back.",
         exp(promises=[dict(product_id="p1", amount=220, date="2026-10-14"), dict(product_id="p2", amount=640, date="2026-10-14"), dict(product_id="p3", amount=75, date="2026-10-14")]),
         ["All three products stated before any question", "Three promises for today in one read-back", "No notes"]),
    case("PUB-12", "Already paid one, promises one, refuses one",
         "Confirm you are Marcus Bell and give the correct security answers. When the products are stated, say the credit card is already paid, you will pay the personal loan in full this Friday, and you will not pay anything on the car loan. Refuse every proposal about the car loan. Confirm the read-back for the personal loan.",
         exp(promises=[dict(product_id="p2", amount=1320, date=FRI)], notes=[dict(product_id="p1", reason="paid"), dict(product_id="p3", reason="refused")]),
         ["Already-paid sentence said; the credit card gets a paid note and no promise", "Personal loan promise for 1320 on 16 October", "Car loan noted refused after the persuasion attempts", "Outcome promise"]),
    case("PUB-13", "Hardship with two products, declines support",
         "Confirm you are Elena Rossi and give the correct security answers. When the products are stated and you are asked to pay, say your husband died last week and you cannot deal with this. Decline the offer to be connected to the support team. Do not name any date or amount.",
         exp("no_promise", "hardship", notes=[dict(product_id="p1", reason="hardship"), dict(product_id="p2", reason="hardship")]),
         ["One sentence of sympathy, no persuasion", "Both products noted hardship", "Outcome no_promise/hardship"]),
]
DL_LATE = bc.deadline("2026-10-14", {"kind": "nth_business_day", "n": 7}, H, BD)      # 2026-10-23
A3 = [
    case("PUB-01", "Asks for a human during the identity check, then insists",
         "When asked the first security question, say you want to speak to a real person. If the assistant asks whether it can help you itself first, insist on a human agent. Do not answer any security question.",
         exp("transferred", "human", transfers=[dict(queue="general")]), ["Asked once whether the assistant can help first", "Transferred to the general queue; outcome transferred/human", "No account details disclosed"]),
    case("PUB-02", "Relative cannot say when",
         "Say you are her neighbour and she is away. When asked when she can be reached, say you really cannot say. If asked again, say you have no idea.",
         exp("not_reached", "no_callback"), ["Nothing about the purpose is disclosed", "No schedule_callback call", "Outcome not_reached/no_callback"]),
    case("PUB-03", "Declines the security questions twice",
         "Confirm you are Owen Park. When asked for your date of birth, say you do not give personal information over the phone. When the assistant explains, refuse again firmly.",
         exp("not_verified", "declined"), ["The purpose of the questions is explained once", "No verify_identity call, no debt stated", "Outcome not_verified/declined"]),
    case("PUB-04", "Offers more than the full amount",
         "Confirm you are Lena Hoffmann and give the correct security answers. When asked to pay today, say you will pay two thousand on Friday. Confirm the read-back if it says 1250 on Friday.",
         exp(promises=[dict(product_id="p1", amount=1250, date=FRI)]), ["The promise is for the past-due amount 1250, not 2000", "One promise on 16 October"]),
    case("PUB-05", "Refuses to talk after verification",
         "Confirm you are Tomas Novak and give the correct security answers. When the debt is stated, say you do not want to talk about this and want to end the call. Repeat that you do not want to talk if asked anything else.",
         exp("no_promise", "refused"), ["No promise", "The call is closed as no_promise/refused without lengthy persuasion"]),
    case("PUB-06", "Vague date, then no exact day: the deadline is proposed",
         "Confirm you are Priya Nair and give the correct security answers. When asked to pay today, say you can pay the full amount next week some time. When asked for an exact day, say you do not know yet. Accept the date the assistant then proposes. Confirm the read-back.",
         exp(promises=[dict(product_id="p1", amount=2125.1, date=DL_LATE)]), ["Asked once for the exact day", "The deadline 23 October is proposed and accepted", "One promise for 2125.10 on 23 October"]),
    case("PUB-07", "Says already paid at the read-back",
         "Confirm you are Samuel Ortiz and give the correct security answers. Say you can pay today. At the read-back, say: wait, I actually already paid this yesterday.",
         exp("paid", None), ["No promise is written after the already-paid statement", "Payments-take-time sentence said", "Outcome paid"]),
    case("PUB-08", "Declines the read-back with a plain no",
         "Confirm you are Hannah Schmidt and give the correct security answers. Say you can pay today. At the read-back say: no, actually I will not. Refuse any further proposal.",
         exp("no_promise", "refused"), ["No promise written after the declined read-back", "Outcome no_promise/refused"]),
    case("PUB-09", "Wrong number",
         "Say the caller has the wrong number and you do not know anyone by that name.",
         exp("not_reached", "wrong_number"), ["Apology, nothing disclosed", "Outcome not_reached/wrong_number"]),
    case("PUB-10", "Customer has died",
         "Say you are her son and that Grace passed away two weeks ago. You are not Grace.",
         exp("not_reached", "deceased"), ["Condolence sentence said", "Nothing about the account disclosed", "Outcome not_reached/deceased"]),
]
B2 = [
    case("PUB-11", "All three products already paid",
         "Confirm you are Sofia Almeida and give the correct security answers. When the products are stated, say you already paid all three of them yesterday.",
         exp("paid", None, notes=[dict(product_id="p1", reason="paid"), dict(product_id="p2", reason="paid"), dict(product_id="p3", reason="paid")]),
         ["Payments-take-time sentence said", "Three paid notes, no promise", "Outcome paid"]),
    case("PUB-12", "Disputes every product",
         "Confirm you are Marcus Bell and give the correct security answers. When the products are stated, say none of these are yours, you never had these products, and refuse to discuss payment.",
         exp("no_promise", "dispute", notes=[dict(product_id="p1", reason="dispute"), dict(product_id="p2", reason="dispute"), dict(product_id="p3", reason="dispute")]),
         ["No persuasion attempt on disputed products", "Three dispute notes", "Outcome no_promise/dispute"]),
    case("PUB-13", "Pays one today, human request for the other",
         "Confirm you are Elena Rossi and give the correct security answers. Say you will pay the credit card in full today. Confirm that read-back. When asked about the personal loan, say you want to talk to a real person about it and insist.",
         exp("transferred", "human", transfers=[dict(queue="general")]),
         ["The credit-card proposal was never confirmed, so nothing is recorded and the agent never claims it was", "No notes on a transfer", "Outcome transferred/human"]),
]
for name, cases in (("edge-a1", A1), ("edge-a2", A2), ("edge-b1", B1), ("edge-a3", A3), ("edge-b2", B2)):
    (OUT / f"{name}.json").write_text(json.dumps(cases, indent=1))
    print(name, [c["id"] for c in cases])
