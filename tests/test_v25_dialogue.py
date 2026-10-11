"""v25: dialogue fixes from the live 'unlike round' edge cases, reproduced offline."""
import copy
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
import compile as C  # noqa: E402
import policy as P  # noqa: E402
from offline_sim import Driver, MockBank, verified, YES_RB  # noqa: E402

CASES = {c["id"]: c for c in json.load(open(ROOT / "public-test-set.json"))}
TOOLS = C.parse_openapi(str(ROOT / "tools/openapi.json"))
C.COMPOUND_SCHEMA = "full"      # these tests exercise the full compound-sentence extraction; the shipped default may be smaller
WF_A = C.compile_workflow(P.PolicyIR.load(str(ROOT / "tests/fixtures/brief_a.policy.json")), TOOLS)
WF_B = C.compile_workflow(P.PolicyIR.load_merged([str(ROOT / "tests/fixtures/brief_a.policy.json"), str(ROOT / "tests/fixtures/brief_ab.policy.json")]), TOOLS)


def _run(wf, case_id, script, now="2026-10-14T11:00"):
    case = copy.deepcopy(CASES[case_id])
    bank = MockBank(case)
    drv = Driver(wf, bank, dict(case["variables"], customer_id="c1", now=now), script)
    drv.run()
    return bank, drv


def _promises(bank):
    return [(b["product_id"], b["amount"], b["date"]) for n, b in bank.calls if n == "create_promise"]


def test_two_amounts_for_two_products_in_one_sentence():
    # PUB-13 unlike: "Ninety on the card and three hundred on the personal loan, both on October thirtieth"
    case = CASES["PUB-13"]
    bank, drv = _run(WF_B, "PUB-13", verified(case) + [
        {"_node": "state_debt", "cust_intent": "proposes", "prop_amount": 90, "prop_product": "1", "prop_amount_2": 300, "prop_product_2": "2",
         "prop_kind": "date", "prop_day": 30, "prop_month": 10}, YES_RB])
    pr = _promises(bank)
    assert sorted(a for _, a, _ in pr) == [90.0, 300.0], pr
    assert [d for _, _, d in pr] == ["2026-10-30", "2026-10-23"] or sorted(d for _, _, d in pr) == ["2026-10-23", "2026-10-30"]


def test_readback_change_moves_card_to_loan_deadline_with_both_amounts():
    case = CASES["PUB-13"]
    bank, drv = _run(WF_B, "PUB-13", verified(case) + [
        {"_node": "state_debt", "cust_intent": "proposes", "prop_amount": 90, "prop_product": "1", "prop_amount_2": 300, "prop_product_2": "2",
         "prop_kind": "date", "prop_day": 30, "prop_month": 10},
        {"_node": "readback", "rb_intent": "changes", "prop_amount": 90, "prop_product": "1", "prop_amount_2": 300, "prop_product_2": "2",
         "prop_kind": "date", "prop_day": 23, "prop_month": 10},
        YES_RB])
    pr = _promises(bank)
    assert sorted(pr) == sorted([("p1", 90.0, "2026-10-23"), ("p2", 300.0, "2026-10-23")]), pr


def test_ineffective_change_twice_gets_a_clarifying_question_and_four_times_abandons():
    case = CASES["PUB-13"]
    same = {"_node": "readback", "rb_intent": "changes"}            # a change with no new value, repeatedly
    bank, drv = _run(WF_B, "PUB-13", verified(case) + [
        {"_node": "state_debt", "cust_intent": "pays_today", "prop_product": "all"}, same, same, same, same, same])
    texts = [t for n, t in drv.spoken if n == "readback"]
    assert any(t.startswith("I may have misunderstood the change") for t in texts), texts
    assert not _promises(bank)
    assert [b["outcome"] for n, b in bank.calls if n == "close_call"] == ["no_promise"]


def test_dispute_without_a_named_product_marks_only_one_product():
    # PUB-12 unlike: three claims in one sentence, the extractor places none -> never close every product on one claim
    case = CASES["PUB-12"]
    bank, drv = _run(WF_B, "PUB-12", verified(case) + [
        {"_node": "state_debt", "cust_intent": "dispute", "prop_product": "none"},
        {"_node": "negotiate", "cust_intent": "already_paid", "prop_product": "none"},
        {"_node": "negotiate", "cust_intent": "refuses"}, {"_node": "negotiate", "cust_intent": "refuses"}])
    notes = [(b["product_id"], b["reason"]) for n, b in bank.calls if n == "add_note"]
    assert notes == [("p1", "dispute"), ("p2", "paid"), ("p3", "refused")], notes


def test_support_request_after_hardship_offer_goes_to_support_queue():
    # PUB-05 unlike: declines the support offer, proposes, then at the read-back asks for the support team mentioned
    case = CASES["PUB-05"]
    bank, drv = _run(WF_A, "PUB-05", verified(case) + [
        {"_node": "state_debt", "cust_intent": "hardship"},
        {"_node": "negotiate", "cust_intent": "proposes", "prop_amount": 260, "prop_kind": "weekday", "prop_weekday": "friday", "prop_relative": "this"},
        {"_node": "readback", "rb_intent": "human"}])
    tr = [b for n, b in bank.calls if n == "transfer_to_agent"]
    assert tr and tr[0]["queue"] == "support", bank.calls
    assert [(b["outcome"], b.get("reason")) for n, b in bank.calls if n == "close_call"] == [("transferred", "support")]
    assert not _promises(bank)


def test_dictated_readback_with_placeholders_is_filled_in():
    d = json.load(open(ROOT / "tests/fixtures/brief_a.policy.json"))
    d["promise_write"]["confirm_phrase"] = "Amount {{payment_amount}}, on {{date}}. Save this arrangement?"
    wf = C.compile_workflow(P.PolicyIR.from_dict(d), TOOLS)
    case = CASES["PUB-01"]
    bank, drv = _run(wf, "PUB-01", verified(case) + [{"_node": "state_debt", "cust_intent": "pays_today"}, YES_RB])
    rb = [t for n, t in drv.spoken if n == "readback"]
    assert rb == ["Amount 420.00, on Wednesday 14 October 2026. Save this arrangement?"], rb
    assert _promises(bank) == [("p1", 420.0, "2026-10-14")]
    # several proposals: the list is spoken, only the placeholder-free sentence of the phrase follows
    d2 = json.load(open(ROOT / "tests/fixtures/brief_ab.policy.json"))
    ir2 = P.PolicyIR.from_dict(P.merge_overlay(d, d2))
    wf2 = C.compile_workflow(ir2, TOOLS)
    case = CASES["PUB-13"]
    bank, drv = _run(wf2, "PUB-13", verified(case) + [{"_node": "state_debt", "cust_intent": "pays_today", "prop_product": "all"}, YES_RB])
    rb = [t for n, t in drv.spoken if n == "readback"]
    assert rb and rb[0].startswith("To confirm: you will pay") and rb[0].endswith("Save this arrangement?") and "{{" not in rb[0], rb


def test_three_statements_in_one_sentence_pub11_unlike():
    # "The card gets 220 this Friday; the personal loan is not mine; the car loan I cannot pay, I lost my job" -> declines support
    case = CASES["PUB-11"]
    bank, drv = _run(WF_B, "PUB-11", verified(case) + [
        {"_node": "state_debt", "cust_intent": "hardship", "prop_product": "3", "prop_amount": 220, "prop_kind": "weekday", "prop_weekday": "friday", "prop_relative": "this",
         "cust_intent_2": "proposes", "prop_product_2": "1", "cust_intent_3": "dispute", "prop_product_3": "2"},
        {"_node": "negotiate", "cust_intent": "refuses"},          # "no thank you, just note the other two"
        YES_RB])
    assert _promises(bank) == [("p1", 220.0, "2026-10-16")], bank.calls
    notes = sorted((b["product_id"], b["reason"]) for n, b in bank.calls if n == "add_note")
    assert notes == [("p2", "dispute"), ("p3", "hardship")], notes
    assert not [b for n, b in bank.calls if n == "transfer_to_agent"]
    assert [(b["outcome"], b.get("reason")) for n, b in bank.calls if n == "close_call"] == [("promise", None)]


def test_three_statements_pub12_unlike_paid_dispute_refuse():
    case = CASES["PUB-12"]
    bank, drv = _run(WF_B, "PUB-12", verified(case) + [
        {"_node": "state_debt", "cust_intent": "already_paid", "prop_product": "3", "cust_intent_2": "dispute", "prop_product_2": "2", "cust_intent_3": "refuses", "prop_product_3": "1"},
        {"_node": "negotiate", "cust_intent": "refuses"}, {"_node": "negotiate", "cust_intent": "refuses"}])
    notes = sorted((b["product_id"], b["reason"]) for n, b in bank.calls if n == "add_note")
    assert notes == [("p1", "refused"), ("p2", "dispute"), ("p3", "paid")], notes
    assert [(b["outcome"], b.get("reason")) for n, b in bank.calls if n == "close_call"] == [("no_promise", "refused")]


def test_readback_move_card_onto_the_loans_date():
    case = CASES["PUB-13"]
    bank, drv = _run(WF_B, "PUB-13", verified(case) + [
        {"_node": "state_debt", "cust_intent": "proposes", "prop_amount": 90, "prop_product": "1", "prop_amount_2": 300, "prop_product_2": "2",
         "prop_kind": "date", "prop_day": 30, "prop_month": 10},
        {"_node": "readback", "rb_intent": "changes", "prop_product": "1", "prop_date_like": "2"},     # "put the card on that earlier loan deadline too"
        YES_RB])
    assert sorted(_promises(bank)) == sorted([("p1", 90.0, "2026-10-23"), ("p2", 300.0, "2026-10-23")]), _promises(bank)


def test_next_friday_on_a_wednesday_is_the_coming_friday_and_on_a_friday_the_one_after():
    case = CASES["PUB-01"]
    say_next_friday = [{"_node": "state_debt", "cust_intent": "proposes", "prop_kind": "weekday", "prop_weekday": "friday", "prop_relative": "next"}, YES_RB]
    bank, drv = _run(WF_A, "PUB-01", verified(case) + say_next_friday, "2026-10-14T11:00")
    assert _promises(bank) == [("p1", 420.0, "2026-10-16")], _promises(bank)
    bank, drv = _run(WF_A, "PUB-01", verified(case) + say_next_friday, "2026-10-16T11:00")
    assert _promises(bank) == [("p1", 420.0, "2026-10-23")], _promises(bank)


def test_talkative_relative_gets_three_asks_before_no_callback():
    case = CASES["PUB-02"]
    script = [{"_node": "opening", "holder": "third_party"},
              {"_node": "third_party", "tp_intent": "cannot_say"}, {"_node": "third_party", "tp_intent": "cannot_say"},
              {"_node": "third_party", "tp_intent": "gives_time", "cb_kind": "tomorrow", "cb_time": "11:00"}]
    bank, drv = _run(WF_A, "PUB-02", script, "2026-10-14T11:00")
    cbs = [(b["date"], b["time"]) for n, b in bank.calls if n == "schedule_callback"]
    assert cbs == [("2026-10-15", "11:00")], bank.calls
    bank, drv = _run(WF_A, "PUB-02", script[:1] + [{"_node": "third_party", "tp_intent": "cannot_say"}] * 3, "2026-10-14T11:00")
    assert [(b["outcome"], b.get("reason")) for n, b in bank.calls if n == "close_call"] == [("not_reached", "no_callback")]


def test_hardship_with_a_proposal_records_it_after_the_offer_is_declined():
    # "I lost my job last month, but I can pay the minimum on Friday" -> sympathy + support offer -> "No, thank you" -> the floor on Friday
    case = CASES["PUB-05"]
    bank, drv = _run(WF_A, "PUB-05", verified(case) + [
        {"_node": "state_debt", "cust_intent": "hardship", "prop_minimum": "yes", "prop_kind": "weekday", "prop_weekday": "friday", "prop_relative": "this"},
        {"_node": "negotiate", "cust_intent": "refuses"}, YES_RB], "2026-10-14T11:00")
    assert _promises(bank) == [("p1", 260.0, "2026-10-16")], (_promises(bank), bank.calls)
    assert not [b for n, b in bank.calls if n == "transfer_to_agent"]


def test_too_low_after_the_floor_gets_the_floor_once_more_on_their_date():
    # too much -> floor on Friday 16; "two hundred this Friday" -> the floor again on Friday 16 (not the deadline ladder); accepted
    case = CASES["PUB-06"]
    bank, drv = _run(WF_A, "PUB-06", verified(case) + [
        {"_node": "state_debt", "cust_intent": "too_much"},
        {"_node": "negotiate", "cust_intent": "proposes", "prop_amount": 200, "prop_kind": "weekday", "prop_weekday": "friday", "prop_relative": "this"},
        {"_node": "negotiate", "cust_intent": "accepts"}, YES_RB], "2026-10-14T11:00")
    assert _promises(bank) == [("p1", 637.5, "2026-10-16")], (_promises(bank), [t for n, t in drv.spoken if n == "negotiate"])


def test_no_promise_today_offers_the_next_business_day():
    d = json.load(open(ROOT / "tests/fixtures/brief_a.policy.json"))
    d["dates"]["promise_today_allowed"] = False
    wf = C.compile_workflow(P.PolicyIR.from_dict(d), TOOLS)
    case = CASES["PUB-01"]
    bank, drv = _run(wf, "PUB-01", verified(case) + [{"_node": "state_debt", "cust_intent": "pays_today"}, {"_node": "negotiate", "cust_intent": "accepts"}, YES_RB], "2026-10-14T11:00")
    assert _promises(bank) == [("p1", 420.0, "2026-10-15")], (_promises(bank), [t for n, t in drv.spoken if n == "negotiate"])


def test_following_week_rule_for_next_weekday():
    d = json.load(open(ROOT / "tests/fixtures/brief_a.policy.json"))
    d["calendar"]["next_weekday"] = "following_week"
    wf = C.compile_workflow(P.PolicyIR.from_dict(d), TOOLS)
    case = CASES["PUB-01"]
    bank, drv = _run(wf, "PUB-01", verified(case) + [{"_node": "state_debt", "cust_intent": "proposes", "prop_kind": "weekday", "prop_weekday": "friday", "prop_relative": "next"}, YES_RB], "2026-10-14T11:00")
    assert _promises(bank) == [("p1", 420.0, "2026-10-23")], _promises(bank)


def test_close_reason_sent_when_the_api_requires_it():
    import copy
    spec = json.load(open(ROOT / "tools/openapi.json"))
    body = spec["paths"]["/close_call"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    body["required"] = sorted(set(body.get("required", [])) | {"reason"})      # the practice reason field has no enum
    import tempfile, pathlib as pl
    dd = pl.Path(tempfile.mkdtemp()); (dd / "api.json").write_text(json.dumps(spec))
    tools = C.parse_openapi(str(dd / "api.json"))
    d = json.load(open(ROOT / "tests/fixtures/brief_a.policy.json"))
    for row in d["outcomes"]["table"]:
        if row["outcome"] == "promise":
            row["reasons"] = ["recorded"]
    wf = C.compile_workflow(P.PolicyIR.from_dict(d), tools)
    assert not C.static_check(wf, tools)
    case = CASES["PUB-01"]
    bank, drv = _run(wf, "PUB-01", verified(case) + [{"_node": "state_debt", "cust_intent": "pays_today"}, YES_RB])
    closes = [(b["outcome"], b.get("reason")) for n, b in bank.calls if n == "close_call"]
    assert closes and closes[0] == ("promise", "recorded"), closes      # (the offline mock rejects a reason on promise, so retries follow)


def test_cut_off_number_next_to_an_acceptance_is_ignored():
    # "Yes, I accept the minimum payment of six" (cut off) -> accepts with amount 6: the offer on the table is accepted
    case = CASES["PUB-06"]
    bank, drv = _run(WF_A, "PUB-06", verified(case) + [
        {"_node": "state_debt", "cust_intent": "too_much"},
        {"_node": "negotiate", "cust_intent": "accepts", "prop_amount": 6},
        {"_node": "readback", "rb_intent": "confirms", "prop_amount": 630}], "2026-10-14T11:00")
    assert _promises(bank) == [("p1", 637.5, "2026-10-16")], (_promises(bank), [t for n, t in drv.spoken if n in ("negotiate", "readback")])
