"""Pure runtime unit probes against committed v22/v23 source; no model, network or workflow writes.
Run from the repository root with .venv/bin/python -B results/audit/v23-independent-70ce3b4/reproduce.py
"""
import copy
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import bankcal
import policy
import compile as compiler

BASE = json.loads((ROOT / "tests/fixtures/brief_a.policy.json").read_text())
CASES = {c["id"]: c for c in json.loads((ROOT / "public-test-set.json").read_text())}
SLOTS = compiler.response_slots(compiler.parse_openapi(str(ROOT / "tools/openapi.json")))
REVS = ("e870198", "70ce3b4")


def env(rev, now="2026-10-14T11:00", patch=None):
    p = copy.deepcopy(BASE)
    if patch:
        patch(p)
    e = dict(bankcal.__dict__)
    e.update(POLICY=policy.PolicyIR.from_dict(p).to_dict(), SLOTS=SLOTS,
             EMPTY={}, vars={"now": now})
    source = subprocess.check_output(["git", "show", rev + ":workflow_runtime.py"], cwd=ROOT, text=True)
    exec(compile(source, rev + ":workflow_runtime.py", "exec"), e)
    return e


def initialized(rev, case="PUB-01", now="2026-10-14T11:00", patch=None):
    e = env(rev, now, patch)
    e["vars"]["products_raw"] = [dict(p, product_id="p" + str(i + 1)) for i, p in enumerate(CASES[case]["products"])]
    e["st_init_products"]()
    return e


def route(e, intent, **values):
    e["vars"].update(cust_intent=intent, **values)
    e["st_neg_route"]()
    s = e["_S"]()
    return dict(next=e["vars"].get("next"), instruction=e["vars"].get("neg_instruction"),
                transfer=s.get("transfer"), proposed=[dict(id=p["product_id"], amount=p.get("proposed_amount"), date=p.get("proposed_date")) for p in s["products"] if p.get("proposed")])


def main():
    result = {}
    for rev in REVS:
        rows = {}
        e = env(rev)
        e["vars"].update(prop_kind="weekday", prop_weekday="saturday", prop_day=16, prop_month=10, prop_year=2027)
        rows["explicit_year_with_weekday"] = dict(actual=e["_resolve_date"]("prop", "2026-10-14"),
            expected=bankcal.resolve_date_expr("2026-10-14", dict(day=16, month=10, year=2027), e["POLICY"]["calendar"]))
        def expired(p):
            p["bands"][0]["deadline"] = dict(kind="end_of_month", basis="business", adjustment="preceding")
            p["calendar"]["holidays"] = ["2026-10-30"]
        e = initialized(rev, now="2026-10-30T11:00", patch=expired)
        p = e["POLICY"]
        rows["expired_deadline"] = dict(policy_deadline=bankcal.deadline("2026-10-30", p["bands"][0]["deadline"], p["calendar"]["holidays"], p["calendar"]["business_days"]), effective_deadline=e["_S"]()["products"][0]["deadline"])
        e = initialized(rev, case="PUB-05")
        route(e, "hardship")
        rows["different_human_after_support_offer"] = route(e, "human")
        e = initialized(rev)
        rows["other_with_payment_fields"] = route(e, "other", prop_amount=200, prop_kind="tomorrow")
        e = initialized(rev)
        route(e, "pays_today")
        e["vars"].update(rb_intent="goodbye")
        e["st_readback_route"]()
        rows["goodbye_at_readback"] = dict(next=e["vars"].get("next"), instruction=e["vars"].get("neg_instruction"), proposed=e["_S"]()["products"][0]["proposed"])
        result[rev] = rows
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
