"""v24: floors that are not a bank field (percent / fixed) and the day_of_month / month_offset deadline kinds."""
import copy
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tests"))
import bankcal as bc  # noqa: E402
import compile as C  # noqa: E402
import policy as P  # noqa: E402
from offline_sim import Driver, MockBank, verified, YES_RB  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
H = ["2026-10-26", "2026-11-11", "2026-11-26", "2026-12-25", "2027-01-01"]; BD = [0, 1, 2, 3, 4]
CASES = {c["id"]: c for c in json.load(open(ROOT / "public-test-set.json"))}
TOOLS = C.parse_openapi(str(ROOT / "tools/openapi.json"))


def test_day_of_month_and_month_offset_deadlines():
    assert bc.deadline("2026-10-14", {"kind": "day_of_month", "day": 15, "month_offset": 1, "adjustment": "following"}, H, BD) == "2026-11-16"   # 15 Nov is a Sunday
    assert bc.deadline("2026-10-14", {"kind": "day_of_month", "day": 31, "month_offset": 1, "adjustment": "preceding"}, H, BD) == "2026-11-30"   # November has 30 days
    assert bc.deadline("2026-10-14", {"kind": "end_of_month", "basis": "business", "adjustment": "none", "month_offset": 1}, H, BD) == "2026-11-30"
    assert bc.deadline("2026-10-14", {"kind": "end_of_month", "basis": "calendar", "adjustment": "following", "month_offset": 1}, H, BD) == "2026-11-30"
    assert bc.deadline("2026-12-14", {"kind": "day_of_month", "day": 15, "month_offset": 1, "adjustment": "following"}, H, BD) == "2027-01-15"
    assert bc.deadline("2026-10-14", {"kind": "day_of_month", "day": 0, "month_offset": 1, "adjustment": "following"}, H, BD) is None
    assert bc.deadline("2026-10-14", {"kind": "end_of_month", "basis": "business", "adjustment": "none"}, H, BD) == "2026-10-30"   # unchanged default


def _policy(floor_rules, deadline=None):
    d = json.load(open(ROOT / "tests/fixtures/brief_a.policy.json"))
    d["amounts"]["floors"] = {}
    d["amounts"]["floor_rules"] = floor_rules
    if deadline:
        for b in d["bands"]:
            b["deadline"] = deadline
    return d


def _floor_path(d, case_id, now="2026-10-14T11:00"):
    ir = P.PolicyIR.from_dict(d)
    assert not P.validate(ir, C.tool_enums(TOOLS))
    wf = C.compile_workflow(ir, TOOLS)
    case = copy.deepcopy(CASES[case_id]); bank = MockBank(case)
    Driver(wf, bank, dict(case["variables"], customer_id="c1", now=now),
           verified(case) + [{"_node": "state_debt", "cust_intent": "too_much"}, {"_node": "negotiate", "cust_intent": "accepts"}, YES_RB]).run()
    return bank


def test_percent_floor():
    bank = _floor_path(_policy({"*": {"kind": "percent", "percent": 20, "min_amount": 50}}), "PUB-06")   # 2125.10 * 20% = 425.02
    assert bank.promises == [{"product_id": "p1", "amount": 425.02, "date": "2026-10-16"}]


def test_percent_floor_with_minimum():
    bank = _floor_path(_policy({"credit_card": {"kind": "percent", "percent": 10, "min_amount": 100}, "*": {"kind": "fixed", "amount": 60}}), "PUB-08")   # 180 * 10% = 18 -> min 100
    assert bank.promises == [{"product_id": "p1", "amount": 100.0, "date": "2026-10-16"}]


def test_fixed_floor_capped_at_full():
    bank = _floor_path(_policy({"*": {"kind": "fixed", "amount": 500}}), "PUB-03")   # full is 95 -> floor cannot exceed full
    assert bank.promises == [{"product_id": "p1", "amount": 95.0, "date": "2026-10-16"}]


def test_floor_rules_validation():
    d = _policy({"*": {"kind": "percent", "percent": 150}})
    assert any("percent" in e for e in P.validate(P.PolicyIR.from_dict(d), C.tool_enums(TOOLS)))
    d = _policy({"*": {"kind": "bogus"}})
    assert any("kind" in e for e in P.validate(P.PolicyIR.from_dict(d), C.tool_enums(TOOLS)))
    d = json.load(open(ROOT / "tests/fixtures/brief_a.policy.json")); d["bands"][0]["deadline"] = {"kind": "day_of_month", "day": 40, "month_offset": 1, "adjustment": "following"}
    assert any("day_of_month" in e for e in P.validate(P.PolicyIR.from_dict(d), C.tool_enums(TOOLS)))


def test_field_floor_still_works_via_floor_rules():
    bank = _floor_path(_policy({"credit_card": {"kind": "field", "field": "minimum_payment"}, "personal_loan": {"kind": "field", "field": "instalment_amount"}, "car_loan": {"kind": "field", "field": "instalment_amount"}}), "PUB-06")
    assert bank.promises == [{"product_id": "p1", "amount": 637.5, "date": "2026-10-16"}]


def test_next_month_deadline_in_a_compiled_policy():
    d = json.load(open(ROOT / "tests/fixtures/brief_a.policy.json"))
    for b in d["bands"]:
        b["deadline"] = {"kind": "day_of_month", "day": 15, "month_offset": 1, "adjustment": "following"}
    ir = P.PolicyIR.from_dict(d); wf = C.compile_workflow(ir, TOOLS); case = copy.deepcopy(CASES["PUB-04"]); bank = MockBank(case)
    # proposes 20 November (after the 16 Nov deadline) -> the deadline is offered and accepted
    Driver(wf, bank, dict(case["variables"], customer_id="c1", now="2026-10-14T11:00"),
           verified(case) + [{"_node": "state_debt", "cust_intent": "proposes", "prop_kind": "date", "prop_day": 20, "prop_month": 11}, {"_node": "negotiate", "cust_intent": "accepts"}, YES_RB]).run()
    assert bank.promises == [{"product_id": "p1", "amount": 1250.0, "date": "2026-11-16"}]


def test_earliest_of_two_deadlines_and_max_of_floor():
    rule = {"kind": "earliest", "rules": [{"kind": "nth_business_day", "n": 6}, {"kind": "end_of_month", "basis": "business", "adjustment": "none"}]}
    assert bc.deadline("2026-10-14", rule, H, BD) == "2026-10-22"          # 6th business day (22 Oct) is before month end (30 Oct)
    assert bc.deadline("2026-10-28", rule, H, BD) == "2026-10-30"          # month end comes first
    d = _policy({"*": {"kind": "max_of", "field": "minimum_payment", "percent": 25, "round": "up_cent"}})
    bank = _floor_path(d, "PUB-06")                                          # max(637.50, ceil(2125.10*25%)=531.28) = 637.50
    assert bank.promises[0]["amount"] == 637.5
    d = _policy({"*": {"kind": "max_of", "field": "minimum_payment", "percent": 40, "round": "up_cent"}})
    bank = _floor_path(d, "PUB-06")                                          # 2125.10*40% = 850.04 > 637.50
    assert bank.promises[0]["amount"] == 850.04


def test_past_deadline_no_promise_policy():
    d = json.load(open(ROOT / "tests/fixtures/brief_a.policy.json"))
    d["bands"][0]["deadline"] = {"kind": "fixed_date", "date": "2026-10-01", "adjustment": "following"}
    d["dates"]["past_deadline"] = "no_promise"
    ir = P.PolicyIR.from_dict(d); assert not P.validate(ir, C.tool_enums(TOOLS)); wf = C.compile_workflow(ir, TOOLS)
    case = copy.deepcopy(CASES["PUB-01"]); bank = MockBank(case)
    Driver(wf, bank, dict(case["variables"], customer_id="c1", now="2026-10-14T11:00"), verified(case) + [{"_node": "state_debt", "cust_intent": "pays_today"}, {"_node": "negotiate", "cust_intent": "refuses"}]).run()
    assert bank.promises == [] and bank.outcome == ("no_promise", "refused")
