"""v23: findings of the fresh review (results/audit/review-v22.md) reproduced offline, then fixed."""
import copy
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
import compile as C  # noqa: E402
import policy as P  # noqa: E402
from offline_sim import Driver, MockBank, verified, YES_RB, CONFIRM, dob, phone  # noqa: E402

CASES = {c["id"]: c for c in json.load(open(ROOT / "public-test-set.json"))}
TOOLS = C.parse_openapi(str(ROOT / "tools/openapi.json"))


def _a(**band_patch):
    d = json.load(open(ROOT / "tests/fixtures/brief_a.policy.json"))
    for k, v in band_patch.items():
        d["bands"][0][k] = v
    return d


def _run(d, case_id, script, now, overlay=None):
    ir = P.PolicyIR.from_dict(P.merge_overlay(d, overlay) if overlay else d)
    wf = C.compile_workflow(ir, TOOLS)
    case = copy.deepcopy(CASES[case_id])
    bank = MockBank(case)
    drv = Driver(wf, bank, dict(case["variables"], customer_id="c1", now=now), script)
    drv.run()
    return bank, drv


def test_attempt_date_never_after_deadline():
    # 3rd business day after Friday 23 Oct (26 Oct is a holiday) = Thu 29 Oct; attempt 1 "last business day this week or next" would be Fri 30 Oct
    case = CASES["PUB-01"]
    bank, drv = _run(_a(deadline={"kind": "nth_business_day", "n": 3}), "PUB-01",
                     verified(case) + [{"_node": "state_debt", "cust_intent": "refuses"}, {"_node": "negotiate", "cust_intent": "accepts"}, YES_RB], "2026-10-23T11:00")
    assert bank.promises == [{"product_id": "p1", "amount": 420.0, "date": "2026-10-29"}]
    assert bank.outcome == ("promise", None)


def test_identical_second_attempt_is_skipped():
    # both attempts would propose the same amount on the same (clamped) day: the second one is not re-proposed
    d = _a(deadline={"kind": "nth_business_day", "n": 3})
    d["bands"][0]["attempts"] = [{"amount": "full", "date": "last_business_day_this_week_or_next", "floor_if_full_refused": True}, {"amount": "full", "date": "deadline", "floor_if_full_refused": False}]
    case = CASES["PUB-01"]
    bank, drv = _run(d, "PUB-01", verified(case) + [{"_node": "state_debt", "cust_intent": "refuses"}, {"_node": "negotiate", "cust_intent": "refuses"}], "2026-10-23T11:00")
    assert bank.promises == [] and bank.outcome == ("no_promise", "refused")


def test_past_deadline_never_records_a_past_date():
    # month-end business deadline, preceding, with 30 Oct a holiday -> 29 Oct; now = 30 Oct
    d = _a(deadline={"kind": "end_of_month", "basis": "business", "adjustment": "preceding"})
    d["calendar"]["holidays"] = ["2026-10-30"]
    case = CASES["PUB-01"]
    bank, drv = _run(d, "PUB-01", verified(case) + [{"_node": "state_debt", "cust_intent": "refuses"}, {"_node": "negotiate", "cust_intent": "accepts"}, YES_RB], "2026-10-30T11:00")
    assert len(bank.promises) == 1 and bank.promises[0]["date"] >= "2026-10-30"
    assert bank.promises[0]["date"] == "2026-11-02"      # the first business day from today


def test_hardship_continue_marks_only_the_current_product():
    overlay = json.load(open(ROOT / "tests/fixtures/brief_ab.policy.json"))
    overlay["special_cases_override"]["hardship"] = {"ends_call": False}
    c = CASES["PUB-12"]
    script = [CONFIRM, dob(*reversed([int(x) for x in c["identity"]["date_of_birth"].split("-")])), phone("4401"), phone("4410"),
              {"_node": "state_debt", "cust_intent": "proposes", "prop_kind": "tomorrow", "prop_product": "1"},
              {"_node": "negotiate", "cust_intent": "hardship"},          # about the loan (product 2)
              {"_node": "negotiate", "cust_intent": "refuses"},           # declines the support transfer
              {"_node": "negotiate", "cust_intent": "accepts"},           # car loan attempt 1
              YES_RB]
    bank, drv = _run(json.load(open(ROOT / "tests/fixtures/brief_a.policy.json")), "PUB-12", script, "2026-10-14T11:00", overlay)
    assert sorted(p["product_id"] for p in bank.promises) == ["p1", "p3"]
    assert bank.notes == [{"product_id": "p2", "reason": "hardship"}]
    assert bank.outcome == ("promise", None)


def test_hardship_default_still_closes_the_call():
    c = CASES["PUB-12"]
    script = [CONFIRM, dob(*reversed([int(x) for x in c["identity"]["date_of_birth"].split("-")])), phone("4401"), phone("4410"),
              {"_node": "state_debt", "cust_intent": "hardship"}, {"_node": "negotiate", "cust_intent": "refuses"}]
    bank, drv = _run(json.load(open(ROOT / "tests/fixtures/brief_a.policy.json")), "PUB-12", script, "2026-10-14T11:00", json.load(open(ROOT / "tests/fixtures/brief_ab.policy.json")))
    assert bank.promises == [] and bank.outcome == ("no_promise", "hardship") and len(bank.notes) == 3


@pytest.mark.parametrize("days,must,must_not", [
    ("today", "today between 10:00 and 19:00", "next business day"),
    ("next_business_day", "the next business day between", "today until"),
    ("today_or_next_business_day", "today until 19:00 or the next business day", "xx"),
])
def test_callback_retry_wording_follows_policy(days, must, must_not):
    d = json.load(open(ROOT / "tests/fixtures/brief_a.policy.json"))
    d["third_party"]["callback"]["days"] = days
    case = CASES["PUB-02"]
    bank, drv = _run(d, "PUB-02", [{"_node": "opening", "holder": "third_party"},
                                   {"_node": "third_party", "tp_intent": "gives_time", "cb_kind": "today", "cb_time": "22:00"},   # outside the window
                                   {"_node": "third_party", "tp_intent": "refuses"}], "2026-10-14T11:00")
    first = [s for n, s in drv.spoken if n == "third_party"] or [drv.vars.get("neg_instruction", "")]
    text = drv.trace and drv.vars.get("neg_instruction", "")
    assert must in text and must_not not in text, text
    assert bank.outcome == ("not_reached", "no_callback")


def test_callback_day_then_time_is_combined():
    case = CASES["PUB-02"]
    bank, drv = _run(json.load(open(ROOT / "tests/fixtures/brief_a.policy.json")), "PUB-02",
                     [{"_node": "opening", "holder": "third_party"},
                      {"_node": "third_party", "tp_intent": "gives_time", "cb_kind": "tomorrow"},
                      {"_node": "third_party", "tp_intent": "gives_time", "cb_time": "11:00"}], "2026-10-14T11:00")
    assert bank.callbacks == [{"date": "2026-10-15", "time": "11:00"}] and bank.outcome == ("not_reached", "callback")


def test_validate_rejects_bad_callback_values():
    d = json.load(open(ROOT / "tests/fixtures/brief_a.policy.json"))
    d["third_party"]["callback"].update(days="same_day", start="8:00")
    d["identity"]["requirements"][0]["numeric_date_order"] = "ymd"
    errs = P.validate(P.PolicyIR.from_dict(d), C.tool_enums(TOOLS))
    joined = " ".join(errs)
    assert "callback.days" in joined and "callback.start" in joined and "numeric_date_order" in joined


def test_extractor_falls_back_to_first_pass_when_audit_fails(tmp_path, monkeypatch):
    import shutil
    import extract as E
    ws = tmp_path
    (ws / "briefs").mkdir(); (ws / "briefs" / "a.md").write_text("brief"); shutil.copy(ROOT / "tools/openapi.json", ws / "openapi.json")
    fixture = (ROOT / "tests/fixtures/brief_a.policy.json").read_text()
    calls = []

    async def fake_query(prompt, purpose, trace, **kw):
        calls.append(purpose)
        if purpose == "policy_extraction":
            (ws / "out" / "s.policy.json").write_text(fixture)
            return {}
        raise TimeoutError("audit timed out")
    monkeypatch.setattr(E, "_query", fake_query)
    ir, audit = E._extract(["briefs/a.md"], "openapi.json", "s", None, ws)
    assert calls == ["policy_extraction", "policy_audit"]
    assert ir.bank_name and "audit pass failed" in audit["unresolved"][0]


def test_floor_offer_on_saturday_uses_next_business_day():
    # "too much" on Saturday 17 Oct: the floor must be offered for Monday 19 Oct, not for today
    case = CASES["PUB-06"]
    bank, drv = _run(json.load(open(ROOT / "tests/fixtures/brief_a.policy.json")), "PUB-06",
                     verified(case) + [{"_node": "state_debt", "cust_intent": "too_much"}, {"_node": "negotiate", "cust_intent": "accepts"}, YES_RB], "2026-10-17T11:00")
    assert bank.promises == [{"product_id": "p1", "amount": 637.5, "date": "2026-10-19"}]


@pytest.mark.parametrize("intent", ["accepts", "human", "restructuring"])
def test_support_offer_accepted_in_any_wording(intent):
    # live edge case 23:28 UTC: "Yes, please connect me to the support team" was extracted as `human` and the call closed as hardship
    case = CASES["PUB-05"]
    bank, drv = _run(json.load(open(ROOT / "tests/fixtures/brief_a.policy.json")), "PUB-05",
                     verified(case) + [{"_node": "state_debt", "cust_intent": "hardship"}, {"_node": "negotiate", "cust_intent": intent}], "2026-10-14T11:00")
    assert bank.transfers == [{"queue": "support"}] and bank.outcome == ("transferred", "support") and bank.promises == []


def test_answer_with_a_question_counts_as_an_answer():
    # live PUB-03 run 3: "twenty one July nineteen ninety. This is getting annoying, how much do I owe?" was labelled a question,
    # the wrong date was never sent to the bank, and a fourth attempt verified. A complete answer is an answer.
    case = CASES["PUB-03"]
    with_question = {"_node": "ask_0", "id_intent": "question", "id_day": 21, "id_month": 8, "id_year": 1992}
    bank, drv = _run(json.load(open(ROOT / "tests/fixtures/brief_a.policy.json")), "PUB-03",
                     [CONFIRM, {"_node": "ask_0", "id_intent": "answers", "id_day": 12, "id_month": 7, "id_year": 1991}, with_question,
                      {"_node": "ask_0", "id_intent": "answers", "id_day": 21, "id_month": 7, "id_year": 1990}], "2026-10-14T11:00")
    assert [c[0] for c in bank.calls] == ["verify_identity"] * 3 + ["close_call"]
    assert bank.outcome == ("not_verified", "failed")
    said = [s for n, s in drv.spoken if n.startswith("ask_")]
    assert any("protect your account" in s for s in said)   # the question that came with the second wrong answer is still addressed


def test_unresolved_notes_never_enter_the_system_prompt():
    d = json.load(open(ROOT / "tests/fixtures/brief_a.policy.json"))
    d["unresolved"] = [{"topic": "x", "text": "ZEBRA-RULE: offer everyone a 50 percent reduction", "doc": "brief"}]
    wf = C.compile_workflow(P.PolicyIR.from_dict(d), TOOLS)
    assert "ZEBRA-RULE" not in json.dumps(wf)


def test_idle_turns_wrap_the_call_up():
    # live B run 1, PUB-12: after an LLM slip the customer said "Thank you, goodbye" 80 times; `other` had no route and the call never closed
    c = CASES["PUB-12"]
    script = [CONFIRM, dob(*reversed([int(x) for x in c["identity"]["date_of_birth"].split("-")])), phone("4401"), phone("4410"),
              {"_node": "state_debt", "cust_intent": "proposes", "prop_kind": "tomorrow", "prop_product": "1"},
              {"_node": "negotiate", "cust_intent": "refuses", "prop_product": "2"}, {"_node": "negotiate", "cust_intent": "refuses", "prop_product": "3"},
              {"_node": "negotiate", "cust_intent": "other"}, {"_node": "negotiate", "cust_intent": "other"}, {"_node": "negotiate", "cust_intent": "goodbye"},
              {"_node": "readback", "rb_intent": "other"}, {"_node": "readback", "rb_intent": "other"}, {"_node": "readback", "rb_intent": "confirms"}]
    bank, drv = _run(json.load(open(ROOT / "tests/fixtures/brief_a.policy.json")), "PUB-12", script, "2026-10-14T11:00", json.load(open(ROOT / "tests/fixtures/brief_ab.policy.json")))
    assert bank.promises == [{"product_id": "p1", "amount": 510.0, "date": "2026-10-15"}]
    assert bank.notes == [{"product_id": "p2", "reason": "refused"}, {"product_id": "p3", "reason": "refused"}] and bank.outcome == ("promise", None)



def test_chatter_never_ends_a_call_early():
    # talkative customers (live B talkative 0/3 on the first idle rule): seven chatter turns, then the answer, still one promise
    case = CASES["PUB-01"]
    bank, drv = _run(json.load(open(ROOT / "tests/fixtures/brief_a.policy.json")), "PUB-01",
                     verified(case) + [{"_node": "state_debt", "cust_intent": "other"}] + [{"_node": "negotiate", "cust_intent": "other"}] * 6 + [{"_node": "negotiate", "cust_intent": "pays_today"}, YES_RB], "2026-10-14T11:00")
    assert bank.promises == [{"product_id": "p1", "amount": 420.0, "date": "2026-10-14"}] and bank.outcome == ("promise", None)


def test_human_request_after_a_proposal_transfers_without_recording():
    # brief A: a promise is recorded only after confirmation; a transfer requested before that keeps nothing (auditor probe P12)
    c = CASES["PUB-13"]
    script = verified(c) + [{"_node": "state_debt", "cust_intent": "pays_today", "prop_product": "1"},
                            {"_node": "negotiate", "cust_intent": "human"}, {"_node": "negotiate", "cust_intent": "human"}]   # asked once whether it can help, then insists
    bank, drv = _run(json.load(open(ROOT / "tests/fixtures/brief_a.policy.json")), "PUB-13", script, "2026-10-14T11:00", json.load(open(ROOT / "tests/fixtures/brief_ab.policy.json")))
    assert bank.promises == [] and bank.transfers == [{"queue": "general"}] and bank.outcome == ("transferred", "human") and bank.notes == []


def test_stray_day_number_does_not_override_this_friday():
    # live B talkative PUB-11: "my cousin's wedding is on the thirtieth. I can pay all three this Friday" -> prop_day=30 + weekday friday
    c = CASES["PUB-11"]
    script = verified(c) + [{"_node": "state_debt", "cust_intent": "proposes", "prop_kind": "weekday", "prop_weekday": "friday", "prop_relative": "this", "prop_day": 30, "prop_product": "all"}, YES_RB]
    bank, drv = _run(json.load(open(ROOT / "tests/fixtures/brief_a.policy.json")), "PUB-11", script, "2026-10-14T11:00", json.load(open(ROOT / "tests/fixtures/brief_ab.policy.json")))
    assert sorted(p["date"] for p in bank.promises) == ["2026-10-16"] * 3


def test_friday_the_23rd_resolves_to_next_friday():
    case = CASES["PUB-01"]
    bank, drv = _run(json.load(open(ROOT / "tests/fixtures/brief_a.policy.json")), "PUB-01",
                     verified(case) + [{"_node": "state_debt", "cust_intent": "proposes", "prop_kind": "weekday", "prop_weekday": "friday", "prop_relative": "this", "prop_day": 23}, YES_RB], "2026-10-14T11:00")
    assert bank.promises == [{"product_id": "p1", "amount": 420.0, "date": "2026-10-23"}]


def test_too_much_first_then_floor_refused_runs_the_attempt_ladder():
    # brief A rule 26: the floor is offered once (not an attempt); refusing it is the flat refusal -> attempt 1 (floor, Friday) -> attempt 2 (floor, deadline)
    case = CASES["PUB-06"]
    bank, drv = _run(json.load(open(ROOT / "tests/fixtures/brief_a.policy.json")), "PUB-06",
                     verified(case) + [{"_node": "state_debt", "cust_intent": "too_much"}, {"_node": "negotiate", "cust_intent": "refuses"},
                                       {"_node": "negotiate", "cust_intent": "accepts"}, YES_RB], "2026-10-14T11:00")
    assert bank.promises == [{"product_id": "p1", "amount": 637.5, "date": "2026-10-23"}]     # the floor (Friday) refused -> attempt 2: floor on the deadline


def test_next_product_instruction_forbids_noted_claims_while_a_proposal_is_pending():
    # live edge-b2 PUB-13: "I have noted that you will pay the credit card today" about an unconfirmed proposal was judged as a recording claim
    c = CASES["PUB-13"]
    ir = P.PolicyIR.from_dict(P.merge_overlay(json.load(open(ROOT / "tests/fixtures/brief_a.policy.json")), json.load(open(ROOT / "tests/fixtures/brief_ab.policy.json"))))
    wf = C.compile_workflow(ir, TOOLS); bank = MockBank(copy.deepcopy(c))
    drv = Driver(wf, bank, dict(c["variables"], customer_id="c1", now="2026-10-14T11:00"), verified(c) + [{"_node": "state_debt", "cust_intent": "pays_today", "prop_product": "1"}])
    with pytest.raises(RuntimeError, match="script exhausted in node negotiate"):
        drv.run()
    assert "noted or recorded" in drv.vars["neg_instruction"] and bank.promises == []


def test_not_verified_without_a_counter_counts_as_wrong():
    # external package aster: the API has no remaining-attempts field and the policy counts in code (limit 2);
    # the agent said "I could not read that" and re-asked for ever instead of counting the refusal
    d = json.load(open(ROOT / "tests/fixtures/brief_a.policy.json")); d["identity"]["wrong_answer_limit"] = 2; d["identity"]["wrong_count_source"] = "code"; d["identity"]["remaining_slot"] = ""
    ir = P.PolicyIR.from_dict(d); wf = C.compile_workflow(ir, TOOLS)
    case = CASES["PUB-03"]
    class NoCounter(MockBank):
        def call(self, name, body):
            r = super().call(name, body)
            if name == "verify_identity":
                r = {"ok": bool(r.get("verified")), "verified": bool(r.get("verified"))}
            return r
    bank = NoCounter(copy.deepcopy(case))
    drv = Driver(wf, bank, dict(case["variables"], customer_id="c1", now="2026-10-14T11:00"),
                 [CONFIRM, {"_node": "ask_0", "id_intent": "answers", "id_day": 1, "id_month": 1, "id_year": 1990}, {"_node": "ask_0", "id_intent": "answers", "id_day": 2, "id_month": 2, "id_year": 1991}])
    drv.run()
    assert [c[0] for c in bank.calls] == ["verify_identity", "verify_identity", "close_call"] and bank.outcome == ("not_verified", "failed")


def test_common_holiday_date_rolls_one_product_and_clamps_the_other():
    # other agent's live case (codex-1 PUB-13): "the 26th for both" -> p1 (early band) rolls to Tue 27 Oct, p2 (late band, deadline 23 Oct) is clamped to 23 Oct;
    # before: the loop stopped at p1's roll-forward question and p2 later got a fresh attempt-1 proposal (16 Oct)
    c = CASES["PUB-13"]
    script = verified(c) + [{"_node": "state_debt", "cust_intent": "proposes", "prop_kind": "date", "prop_day": 26, "prop_month": 10, "prop_product": "all"},
                            {"_node": "negotiate", "cust_intent": "accepts"}, YES_RB]
    bank, drv = _run(json.load(open(ROOT / "tests/fixtures/brief_a.policy.json")), "PUB-13", script, "2026-10-14T11:00", json.load(open(ROOT / "tests/fixtures/brief_ab.policy.json")))
    assert sorted((p["product_id"], p["date"]) for p in bank.promises) == [("p1", "2026-10-27"), ("p2", "2026-10-23")]
    assert bank.outcome == ("promise", None)


def test_attempt_instruction_keeps_the_llm_on_the_current_product():
    # live PUB-12 (three times tonight): after "I will not pay that loan" the LLM skipped the loan's second attempt and moved to the car loan
    c = CASES["PUB-12"]
    ir = P.PolicyIR.from_dict(P.merge_overlay(json.load(open(ROOT / "tests/fixtures/brief_a.policy.json")), json.load(open(ROOT / "tests/fixtures/brief_ab.policy.json"))))
    wf = C.compile_workflow(ir, TOOLS); bank = MockBank(copy.deepcopy(c))
    drv = Driver(wf, bank, dict(c["variables"], customer_id="c1", now="2026-10-14T11:00"),
                 [CONFIRM, dob(*reversed([int(x) for x in c["identity"]["date_of_birth"].split("-")])), phone("4401"), phone("4410"),
                  {"_node": "state_debt", "cust_intent": "proposes", "prop_kind": "tomorrow", "prop_product": "1"}, {"_node": "negotiate", "cust_intent": "refuses", "prop_product": "2"}])
    with pytest.raises(RuntimeError, match="script exhausted in node negotiate"):
        drv.run()
    ins = drv.vars["neg_instruction"]
    assert "440.00" in ins and "personal loan" in ins and "Stay on the personal loan" in ins


def test_robot_question_asked_with_an_acceptance_is_answered_before_the_readback():
    # live PUB-04 / PUB-07 (four times tonight): "Yes, that works. Are you a robot?" -> the read-back is fixed speech, so the question was never answered
    case = CASES["PUB-01"]
    bank, drv = _run(json.load(open(ROOT / "tests/fixtures/brief_a.policy.json")), "PUB-01",
                     verified(case) + [{"_node": "state_debt", "cust_intent": "pays_today", "aside": "robot"}, YES_RB], "2026-10-14T11:00")
    rb = [s for n, s in drv.spoken if n == "readback"][0]
    assert rb.startswith("I am Freya Bank's digital assistant.") and "To confirm" in rb
    assert bank.promises == [{"product_id": "p1", "amount": 420.0, "date": "2026-10-14"}]


def test_scam_question_asked_with_a_refusal_is_answered_in_the_next_instruction():
    case = CASES["PUB-01"]
    ir = P.PolicyIR.from_dict(json.load(open(ROOT / "tests/fixtures/brief_a.policy.json"))); wf = C.compile_workflow(ir, TOOLS); bank = MockBank(copy.deepcopy(case))
    drv = Driver(wf, bank, dict(case["variables"], customer_id="c1", now="2026-10-14T11:00"), verified(case) + [{"_node": "state_debt", "cust_intent": "refuses", "aside": "scam"}])
    with pytest.raises(RuntimeError, match="script exhausted in node negotiate"):
        drv.run()
    ins = drv.vars["neg_instruction"]
    assert ins.startswith('First answer their question in one sentence: "You can verify this call') and "Propose this payment" in ins


def test_weekday_naming_the_offer_restates_it_and_bare_weekday_is_never_in_the_past():
    # live PUB-07 (04 UTC): offer Tuesday 27 Oct; "I can do that on Tuesday" extracted as weekday tuesday/this -> was resolved to LAST Tuesday
    case = CASES["PUB-07"]
    bank, drv = _run(json.load(open(ROOT / "tests/fixtures/brief_a.policy.json")), "PUB-07",
                     verified(case) + [{"_node": "state_debt", "cust_intent": "proposes", "prop_kind": "vague"},
                                       {"_node": "negotiate", "cust_intent": "proposes", "prop_kind": "date", "prop_day": 26},
                                       {"_node": "negotiate", "cust_intent": "accepts", "prop_kind": "weekday", "prop_weekday": "tuesday", "prop_relative": "this"}, YES_RB], "2026-10-14T11:00")
    assert bank.promises == [{"product_id": "p1", "amount": 540.0, "date": "2026-10-27"}]
    case = CASES["PUB-01"]
    bank, drv = _run(json.load(open(ROOT / "tests/fixtures/brief_a.policy.json")), "PUB-01",
                     verified(case) + [{"_node": "state_debt", "cust_intent": "proposes", "prop_kind": "weekday", "prop_weekday": "tuesday", "prop_relative": "this"}, YES_RB], "2026-10-14T11:00")
    assert bank.promises == [{"product_id": "p1", "amount": 420.0, "date": "2026-10-20"}]   # the coming Tuesday, not 13 October


def test_goodbye_at_the_readback_closes_once_without_writing():
    case = CASES["PUB-01"]
    bank, drv = _run(json.load(open(ROOT / "tests/fixtures/brief_a.policy.json")), "PUB-01",
                     verified(case) + [{"_node": "state_debt", "cust_intent": "pays_today"}, {"_node": "readback", "rb_intent": "goodbye"}], "2026-10-14T11:00")
    assert bank.promises == [] and bank.outcome == ("no_promise", "refused") and [c[0] for c in bank.calls].count("close_call") == 1


def test_floor_at_the_first_question_rides_on_attempt_one_date():
    # public PUB-06 ledger: "too much" straight away -> floor 637.50 on Friday 16 Oct (asks_back persona says it at the first question)
    case = CASES["PUB-06"]
    bank, drv = _run(json.load(open(ROOT / "tests/fixtures/brief_a.policy.json")), "PUB-06",
                     verified(case) + [{"_node": "state_debt", "cust_intent": "too_much"}, {"_node": "negotiate", "cust_intent": "accepts"}, YES_RB], "2026-10-14T11:00")
    assert bank.promises == [{"product_id": "p1", "amount": 637.5, "date": "2026-10-16"}]


def test_monday_the_26th_with_a_this_relative_is_the_26th():
    # live A asks_back PUB-07: "Monday the 26th" extracted as weekday monday / this + day 26 -> was last Monday (past), three re-asks
    case = CASES["PUB-07"]
    bank, drv = _run(json.load(open(ROOT / "tests/fixtures/brief_a.policy.json")), "PUB-07",
                     verified(case) + [{"_node": "state_debt", "cust_intent": "proposes", "prop_kind": "weekday", "prop_weekday": "monday", "prop_relative": "this", "prop_day": 26},
                                       {"_node": "negotiate", "cust_intent": "accepts"}, YES_RB], "2026-10-14T11:00")
    assert bank.promises == [{"product_id": "p1", "amount": 540.0, "date": "2026-10-27"}]      # 26 Oct is a holiday -> rolled to the 27th and accepted


def test_aside_with_the_confirmation_is_spoken_before_the_recorded_sentence():
    case = CASES["PUB-01"]
    bank, drv = _run(json.load(open(ROOT / "tests/fixtures/brief_a.policy.json")), "PUB-01",
                     verified(case) + [{"_node": "state_debt", "cust_intent": "pays_today"}, {"_node": "readback", "rb_intent": "confirms", "aside": "robot"}], "2026-10-14T11:00")
    said = " ".join(s for n, s in drv.spoken)
    assert "I am Freya Bank's digital assistant." in said and bank.promises and bank.outcome == ("promise", None)


def test_explicit_next_tuesday_is_not_folded_into_a_later_offer():
    # offer Tuesday 27 Oct on the table; "next Tuesday" from Wednesday 14 Oct is the 20th and stays the 20th
    case = CASES["PUB-07"]
    bank, drv = _run(json.load(open(ROOT / "tests/fixtures/brief_a.policy.json")), "PUB-07",
                     verified(case) + [{"_node": "state_debt", "cust_intent": "proposes", "prop_kind": "vague"},
                                       {"_node": "negotiate", "cust_intent": "proposes", "prop_kind": "date", "prop_day": 26},
                                       {"_node": "negotiate", "cust_intent": "proposes", "prop_kind": "weekday", "prop_weekday": "tuesday", "prop_relative": "next"}, YES_RB], "2026-10-14T11:00")
    assert bank.promises == [{"product_id": "p1", "amount": 540.0, "date": "2026-10-20"}]


def test_no_window_blocks_the_floor_offer_and_direct_acceptance():
    d = json.load(open(ROOT / "tests/fixtures/brief_a.policy.json"))
    d["bands"][1]["deadline"] = {"kind": "fixed_date", "date": "2026-10-01", "adjustment": "following"}; d["dates"]["past_deadline"] = "no_promise"
    case = CASES["PUB-06"]
    bank, drv = _run(d, "PUB-06", verified(case) + [{"_node": "state_debt", "cust_intent": "too_much"}, {"_node": "negotiate", "cust_intent": "accepts"}], "2026-10-14T11:00")
    assert bank.promises == [] and bank.outcome == ("no_promise", "refused")


def test_composite_deadline_children_are_validated():
    d = json.load(open(ROOT / "tests/fixtures/brief_a.policy.json"))
    d["bands"][0]["deadline"] = {"kind": "earliest", "rules": [{"kind": "nth_business_day", "n": 6}, {"kind": "calendar_days", "n": 9}]}   # child lacks adjustment
    errs = P.validate(P.PolicyIR.from_dict(d), C.tool_enums(TOOLS))
    assert any("adjustment" in e for e in errs)
