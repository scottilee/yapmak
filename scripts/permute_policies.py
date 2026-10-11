"""Generate N policy IRs by systematically permuting the practice policy's shape — generic permutations of public rule
kinds (bands, deadline kinds, calendars, identity sets, enum vocabularies, floors, attempts, notes, product counts),
never hidden content — with a matching mutated OpenAPI, and run the IR-parameterized invariants on each.

    .venv/bin/python scripts/permute_policies.py --run [--n 40] [--seed 7] [--out results/permutations]
"""
from __future__ import annotations

import argparse
import copy
import json
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
import policy as P  # noqa: E402

IDENTITY_SETS = [
    [("date_of_birth", "date"), ("phone_last4", "digits")],
    [("postcode", "text"), ("birth_year", "year")],
    [("company_number", "digits"), ("founded_year", "year"), ("postcode", "text")],
    [("birth_year", "year")],
    [("phone_last4", "digits"), ("date_of_birth", "date"), ("postcode", "text"), ("birth_year", "year")],
]
VOCABS = [
    {"promise": "promise", "paid": "paid", "transferred": "transferred", "no_promise": "no_promise", "not_verified": "not_verified", "not_reached": "not_reached",
     "refused": "refused", "hardship": "hardship", "dispute": "dispute", "service_error": "service_error", "failed": "failed", "declined": "declined",
     "callback": "callback", "no_callback": "no_callback", "wrong_number": "wrong_number", "deceased": "deceased", "unclear": "unclear",
     "restructuring": "restructuring", "human": "human", "support": "support", "general": "general"},
    {"promise": "arrangement", "paid": "settled", "transferred": "handed_over", "no_promise": "no_arrangement", "not_verified": "unverified", "not_reached": "unreached",
     "refused": "declined_payment", "hardship": "distress", "dispute": "disputed", "service_error": "system_error", "failed": "failed", "declined": "declined",
     "callback": "callback", "no_callback": "no_callback", "wrong_number": "wrong_number", "deceased": "deceased", "unclear": "unclear",
     "restructuring": "restructure", "human": "person", "support": "care", "general": "desk"},
    {"promise": "ptp-recorded", "paid": "already-paid", "transferred": "escalated", "no_promise": "no-ptp", "not_verified": "id-fail", "not_reached": "no-contact",
     "refused": "refuses", "hardship": "vulnerable", "dispute": "disputes", "service_error": "tool-error", "failed": "exhausted", "declined": "would-not-answer",
     "callback": "cb-set", "no_callback": "cb-none", "wrong_number": "wrong-no", "deceased": "deceased", "unclear": "unclear",
     "restructuring": "plans", "human": "agent", "support": "welfare", "general": "front-desk"},
]
PRODUCT_SETS = [
    {"credit_card": "minimum_payment", "personal_loan": "instalment_amount", "car_loan": "instalment_amount"},
    {"business_overdraft": "minimum_due", "equipment_loan": "scheduled_repayment"},
    {"mortgage": "monthly_instalment", "store_card": "minimum_payment", "overdraft": "minimum_due", "student_loan": "scheduled_repayment"},
]
CALENDARS = [
    {"holidays": ["2026-10-26", "2026-11-11", "2026-11-26", "2026-12-25", "2027-01-01"], "business_days": [0, 1, 2, 3, 4]},
    {"holidays": ["2026-10-19", "2026-11-02", "2026-12-24", "2026-12-25", "2026-12-31"], "business_days": [0, 1, 2, 3, 4]},
    {"holidays": ["2026-10-14", "2026-10-15"], "business_days": [0, 1, 2, 3, 4, 5]},     # today is a holiday; Saturday is a business day
    {"holidays": [], "business_days": [0, 1, 2, 3]},                                        # Mon-Thu week
]
DEADLINES = [
    {"kind": "nth_business_day", "n": 12}, {"kind": "nth_business_day", "n": 5}, {"kind": "nth_business_day", "n": 3},
    {"kind": "calendar_days", "n": 14, "adjustment": "following"}, {"kind": "calendar_days", "n": 9, "adjustment": "preceding"},
    {"kind": "end_of_month", "basis": "business", "adjustment": "preceding"}, {"kind": "end_of_month", "basis": "calendar", "adjustment": "following"},
    {"kind": "fixed_date", "date": "2026-11-30", "adjustment": "following"},
    {"kind": "day_of_month", "day": 15, "month_offset": 1, "adjustment": "following"}, {"kind": "end_of_month", "basis": "business", "adjustment": "none", "month_offset": 1},
]
FLOOR_RULE_SETS = [None, None, None, {"*": {"kind": "percent", "percent": 20, "min_amount": 50}}, {"*": {"kind": "fixed", "amount": 75}}]


def permute(base: dict, rng: random.Random, k: int) -> dict:
    ir = copy.deepcopy(base)
    v = rng.choice(VOCABS)
    # identity
    idset = rng.choice(IDENTITY_SETS)
    ir["identity"]["requirements"] = [{"field": f, "ask_text": f"your {f.replace('_', ' ')}", "answer_format": fmt, "digits": rng.choice([4, 6, 8]) if fmt == "digits" else 0,
                                       "numeric_date_order": rng.choice(["dmy", "mdy"])} for f, fmt in idset]
    ir["identity"]["wrong_answer_limit"] = rng.choice([2, 3, 4, 5])
    ir["identity"]["remaining_slot"] = "wrong_answers_left"
    ir["identity"]["failed_outcome"] = [v["not_verified"], v["failed"]]
    ir["identity"]["declined_outcome"] = [v["not_verified"], v["declined"]]
    ir["identity"]["unclear_holder_outcome"] = [v["not_reached"], v["unclear"]]
    # calendar and bands
    ir["calendar"].update(rng.choice(CALENDARS))
    n_bands = rng.choice([1, 2, 3])
    edges = sorted(rng.sample(range(2, 60), n_bands - 1)) if n_bands > 1 else []
    lo, bands = 1, []
    for i in range(n_bands):
        hi = (edges[i] - 1) if i < len(edges) else max(lo + 4, rng.choice([45, 60, 90]))
        attempts = [{"amount": "full", "date": "last_business_day_this_week_or_next", "floor_if_full_refused": True}]
        if rng.random() < 0.6:
            attempts.append({"amount": "floor", "date": "deadline", "floor_if_full_refused": True})
        bands.append({"name": f"band{i + 1}", "days_late_min": lo, "days_late_max": hi, "deadline": rng.choice(DEADLINES), "attempts": attempts})
        lo = hi + 1
    ir["bands"] = bands
    # products / floors / notes / multi
    ir["amounts"]["floors"] = rng.choice(PRODUCT_SETS)
    fr = rng.choice(FLOOR_RULE_SETS)
    if fr:   # the floor is a rule, not a bank field: keep the product types, drop the field mapping
        ir["amounts"]["floor_rules"] = {t: dict(next(iter(fr.values()))) for t in ir["amounts"]["floors"]}
        ir["amounts"]["floors"] = {}
    else:
        ir["amounts"]["floor_rules"] = {}
    ir["multi_product"]["max_products"] = rng.choice([1, 2, 3, 4])
    notes_on = ir["multi_product"]["max_products"] > 1 and rng.random() < 0.8
    ir["notes"]["enabled"] = notes_on
    ir["notes"]["reasons"] = [v["refused"], v["hardship"], v["dispute"], v["paid"], v["service_error"]] if notes_on else []
    # outcomes
    ir["outcomes"].update({"promise_outcome": v["promise"], "paid_outcome": v["paid"], "transfer_outcome": v["transferred"], "no_promise_outcome": v["no_promise"],
                           "service_error_reason": v["service_error"], "refused_reason": v["refused"],
                           "table": [{"outcome": v["promise"], "reasons": []}, {"outcome": v["paid"], "reasons": []},
                                     {"outcome": v["transferred"], "reasons": [v["restructuring"], v["human"], v["support"]]},
                                     {"outcome": v["no_promise"], "reasons": [v["refused"], v["hardship"], v["dispute"], v["service_error"]]},
                                     {"outcome": v["not_verified"], "reasons": [v["failed"], v["declined"]]},
                                     {"outcome": v["not_reached"], "reasons": [v["callback"], v["no_callback"], v["wrong_number"], v["deceased"], v["unclear"]]}]})
    # third party
    cb = ir["third_party"]["callback"]
    cb.update({"days": rng.choice(["today_or_next_business_day", "next_business_day"]), "start": rng.choice(["09:00", "10:00", "12:00"]), "end": rng.choice(["17:30", "19:00", "18:00"]),
               "scheduled_outcome": [v["not_reached"], v["callback"]], "no_callback_outcome": [v["not_reached"], v["no_callback"]]})
    ir["third_party"]["wrong_number_outcome"] = [v["not_reached"], v["wrong_number"]]
    ir["third_party"]["deceased_outcome"] = [v["not_reached"], v["deceased"]]
    # special cases: keep names, translate every outcome/reason/queue through the vocabulary, vary note-vs-close
    def tr(x):
        return v.get(x, x) if isinstance(x, str) else x
    for sc in ir["special_cases"]:
        sc["action"] = {k: tr(x) for k, x in sc["action"].items()}
        sc["offer_transfer_queue"] = tr(sc.get("offer_transfer_queue", ""))
        sc["offer_outcome"] = [tr(x) for x in sc.get("offer_outcome", ["", ""])]
        if sc["name"] == "already_paid":
            sc["action"] = {"type": "note", "reason": v["paid"]} if notes_on else {"type": "close", "outcome": v["paid"], "reason": ""}
            sc["ends_call"] = not notes_on
        elif sc["name"] == "dispute":
            sc["action"] = {"type": "note", "reason": v["dispute"]} if notes_on else {"type": "close", "outcome": v["no_promise"], "reason": v["dispute"]}
            sc["ends_call"] = not notes_on
        elif sc["name"] == "human":
            sc["ask_once_first"] = rng.random() < 0.6
    ir["promise_write"]["retry_on_failure"] = rng.choice([0, 1, 2])
    ir["phrases"]["product_naming"] = {t: t.replace("_", " ") for t in (ir["amounts"]["floors"] or ir["amounts"]["floor_rules"])}
    # --- subtractive dimension: hidden briefs may simply not have some of brief A's rules ---
    minimal = rng.random() < 0.4
    if minimal:
        drop = set(rng.sample(["hardship", "restructuring", "already_paid", "dispute", "refuse_to_talk"], rng.choice([1, 2, 3])))
        ir["special_cases"] = [sc for sc in ir["special_cases"] if sc["name"] not in drop]
        if rng.random() < 0.5:
            ir["third_party"]["callback"]["enabled"] = False
        if rng.random() < 0.5:
            ir["bands"][-1]["attempts"] = []            # a plain no ends it for that band
        if rng.random() < 0.4:
            ir["amounts"]["floors"] = {}
            ir["amounts"]["floor_rules"] = {t: {"kind": "percent", "percent": 100} for t in ir["phrases"]["product_naming"]}   # only the full amount is acceptable
        if rng.random() < 0.5:
            ir["identity"]["requirements"] = ir["identity"]["requirements"][:1]
    ir["_minimal"] = minimal
    ir["bank_name"] = f"Bank {k}"
    ir["phrases"]["opening"] = f"Good day, this is the automated assistant of Bank {k}. We record this call."

    ir.pop("_minimal", None)
    ir["source_docs"] = [f"synthetic permutation {k}" + (" (minimal)" if minimal else "")]
    ir["unresolved"] = []
    return ir, v


def mutate_openapi(base: dict, ir: dict, v: dict) -> dict:
    spec = copy.deepcopy(base)
    P_ = spec["paths"]

    def props(path):
        return P_[path]["post"]["requestBody"]["content"]["application/json"]["schema"]["properties"]

    def resp(path):
        return P_[path]["post"]["responses"]["200"]["content"]["application/json"]["schema"]["properties"]
    props("/verify_identity")["field"]["enum"] = [r["field"] for r in ir["identity"]["requirements"]]
    items = resp("/get_account")["products"]["items"]["properties"]
    items["type"]["enum"] = list(ir["amounts"]["floors"] or ir["amounts"]["floor_rules"])
    for old in ("minimum_payment", "instalment_amount"):
        items.pop(old, None)
    for f in set(ir["amounts"]["floors"].values()):
        items[f] = {"type": "number"}
    props("/add_note")["reason"]["enum"] = ir["notes"]["reasons"] or [v["refused"], v["hardship"], v["dispute"], v["paid"], v["service_error"]]
    props("/transfer_to_agent")["queue"]["enum"] = [v["restructuring"], v["general"], v["support"]]
    props("/close_call")["outcome"]["enum"] = [row["outcome"] for row in ir["outcomes"]["table"]]
    return spec


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=40); ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="results/permutations"); ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    rng = random.Random(a.seed)
    base = json.load(open(ROOT / "tests/fixtures/brief_a.policy.json"))
    base = P.merge_overlay(base, json.load(open(ROOT / "tests/fixtures/brief_ab.policy.json")))
    api = json.load(open(ROOT / "tools/openapi.json"))
    out = ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)
    summary = []
    for k in range(a.n):
        ir, v = permute(base, rng, k)
        spec = mutate_openapi(api, ir, v)
        pp, op = out / f"perm-{k:02d}.policy.json", out / f"perm-{k:02d}.openapi.json"
        pp.write_text(json.dumps(ir, indent=1)); op.write_text(json.dumps(spec, indent=1))
        if a.run:
            import invariants as I
            print(f"== perm-{k:02d}: identity={[r['field'] for r in ir['identity']['requirements']]} bands={[(b['days_late_min'], b['days_late_max'], b['deadline']['kind']) for b in ir['bands']]} "
                  f"cal={ir['calendar']['business_days']}/{len(ir['calendar']['holidays'])}h products={ir['multi_product']['max_products']} notes={ir['notes']['enabled']} retry={ir['promise_write']['retry_on_failure']}")
            rep = I.check_policy(str(pp), str(op))
            bad = [s for s, p in rep.get("scenarios", {}).items() if p and not p[0].startswith("n/a")]
            summary.append({"perm": k, "invalid": rep.get("invalid"), "static": rep.get("static"), "failing": bad})
    if a.run:
        (out / "summary.json").write_text(json.dumps(summary, indent=1))
        n_bad = sum(1 for s in summary if s["invalid"] or s["static"] or s["failing"])
        print(f"\n{a.n - n_bad} / {a.n} permutations pass every applicable invariant; details in {out}/summary.json")
        sys.exit(1 if n_bad else 0)


if __name__ == "__main__":
    main()
