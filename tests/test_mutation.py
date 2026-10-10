"""Mutating the policy IR must change the compiled agent's behaviour without any code change (plan §6).
Uses the offline state-machine driver with the public scripts and recomputed expectations."""
import copy
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import compile as C  # noqa: E402
import policy as P  # noqa: E402
from offline_sim import Driver, MockBank, SCRIPTS  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
CASES = {c["id"]: c for c in json.load(open(ROOT / "public-test-set.json"))}
TOOLS = C.parse_openapi(str(ROOT / "tools" / "openapi.json"))


def run(wf, case_id):
    case = CASES[case_id]
    bank = MockBank(case, fail_promise_first=(case_id == "PUB-10"))
    d = Driver(wf, bank, dict(case["variables"], customer_id="c_test"), SCRIPTS[case_id](case))
    d.run()
    return bank


def base_ir():
    return P.PolicyIR.load(str(ROOT / "tests/fixtures/brief_a.policy.json"))


def test_holiday_change_moves_rolled_promise():
    ir = base_ir()
    ir.calendar.holidays.append("2026-10-27")            # the day PUB-07 used to land on is now a holiday
    wf = C.compile_workflow(ir, TOOLS)
    assert not C.static_check(wf, TOOLS)
    case = CASES["PUB-07"]
    script = SCRIPTS["PUB-07"](case)
    script[-2] = {"_node": "negotiate", "cust_intent": "accepts"}      # the customer would accept the 28th, not restate the 27th
    bank = MockBank(case)
    Driver(wf, bank, dict(case["variables"], customer_id="c_test"), script).run()
    assert bank.promises[0]["date"] == "2026-10-28"


def test_deadline_rule_change_moves_clamped_promise():
    ir = base_ir()
    late = next(b for b in ir.bands if b.name == "late")
    late.deadline = {"kind": "nth_business_day", "n": 5}  # was 7 -> 23 Oct; now 21 Oct
    wf = C.compile_workflow(ir, TOOLS)
    bank = run(wf, "PUB-04")
    assert bank.promises[0]["date"] == "2026-10-21"


def test_calendar_days_deadline_rule():
    ir = base_ir()
    late = next(b for b in ir.bands if b.name == "late")
    late.deadline = {"kind": "calendar_days", "n": 3, "adjustment": "following"}   # 17 Oct (Sat) -> Mon 19 Oct
    wf = C.compile_workflow(ir, TOOLS)
    bank = run(wf, "PUB-04")
    assert bank.promises[0]["date"] == "2026-10-19"


def test_outcome_names_follow_the_policy():
    ir = base_ir()
    o = ir.outcomes
    o.no_promise_outcome, o.refused_reason = "no_promise", "refused"
    sc = next(s for s in ir.special_cases if s.name == "hardship")
    sc.action = {"type": "close", "outcome": "no_promise", "reason": "service_error"}   # a different (allowed) reason
    wf = C.compile_workflow(ir, TOOLS)
    bank = run(wf, "PUB-05")
    assert bank.outcome == ("no_promise", "service_error")


def test_single_attempt_in_late_band_changes_refusal_flow():
    ir = base_ir()
    late = next(b for b in ir.bands if b.name == "late")
    late.attempts = late.attempts[:1]                      # only one persuasion attempt now
    ab = P.PolicyIR.from_dict(P.merge_overlay(ir.to_dict(), json.load(open(ROOT / "tests/fixtures/brief_ab.policy.json"))))
    wf = C.compile_workflow(ab, TOOLS)
    case = CASES["PUB-12"]
    bank = MockBank(case)
    script = SCRIPTS["PUB-12"](case)
    script = [t for t in script if not (t.get("cust_intent") == "refuses" and script.count(t) > 1)]  # fewer refusals needed
    # loan: one attempt; car loan: one attempt; then read-back
    script = script[:5] + [{"_node": "negotiate", "cust_intent": "refuses"}, {"_node": "negotiate", "cust_intent": "refuses"}, {"_node": "readback", "rb_intent": "confirms"}]
    d = Driver(wf, bank, dict(case["variables"], customer_id="c_test"), script)
    d.run()
    assert sorted(n["product_id"] for n in bank.notes) == ["p2", "p3"]
    assert bank.outcome == ("promise", None)


def test_identity_requirements_are_generated_from_policy():
    ir = base_ir()
    ir.identity.requirements = ir.identity.requirements[:1]   # a single security question
    wf = C.compile_workflow(ir, TOOLS)
    assert "ask_1" not in wf["nodes"] and "ask_0" in wf["nodes"]
    assert wf["nodes"]["ask_0"]["on_enter"]["text"] == "{{id_say}}"
