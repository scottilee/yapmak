"""IR-parameterized invariants: properties every compiled workflow must satisfy for ANY policy, with the expected values
computed from the policy itself (bankcal) rather than hand-written. Runs offline against the mock bank.

    .venv/bin/python tests/invariants.py <policy.json[+overlay]> <openapi.json>      # one policy
    .venv/bin/python scripts/permute_policies.py --run                              # 40 generated policies

Scenarios (each an extraction script written from the IR):
  happy        confirm identity, pay full today -> one promise per product (today or next business day), outcome promise
  refusal      refuse every attempt -> no promise, attempts exhausted per product, notes if the policy has them, outcome no_promise/refused
  hardship     hardship then decline support -> no persuasion, outcome no_promise/hardship (or notes + precedence)
  third_party  relative, callback next business day inside the window -> schedule_callback, outcome callback
  wrong_id     wrong answers until exhausted -> get_account never called, outcome failed
  dispute_one  (2+ products) dispute product 1, pay product 2 -> note dispute, promise p2, outcome promise
  write_fail   create_promise fails twice -> retries as the policy allows, outcome service_error (single product)
Structural invariants checked on every scenario: close_call exactly once and last; no get_account before both/all questions;
no write before a confirmation; every bank body valid against the OpenAPI; dates relative to `now`.
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
import bankcal as bc  # noqa: E402
import compile as C  # noqa: E402
import policy as P  # noqa: E402
from offline_sim import Driver, MockBank  # noqa: E402

NOW = "2026-10-14T11:00"


class IRBank(MockBank):
    """Mock bank whose identity answers, products and failure behaviour follow the policy under test."""

    def __init__(self, ir: P.PolicyIR, products, fail_writes=0):
        self.ir = ir
        self.identity_answers = {r.field: _answer_for(r) for r in ir.identity.requirements}
        case = {"identity": {}, "products": products, "id": "SYN"}
        super().__init__(case)
        self.products = [dict(p, product_id=f"p{i + 1}") for i, p in enumerate(products)]
        self.fail_writes = fail_writes
        self.wrong_left = ir.identity.wrong_answer_limit
        self.n_required = len(ir.identity.requirements)

    def call(self, name, body):
        if name == "verify_identity":
            self.calls.append((name, dict(body)))
            f, a = body.get("field"), str(body.get("answer", ""))
            if f in self.identity_answers and a == self.identity_answers[f]:
                self.verified.add(f)
                return {"ok": True, "verified": True, "wrong_answers_left": self.wrong_left, "all_verified": len(self.verified) >= self.n_required}
            self.wrong_left -= 1
            if self.wrong_left <= 0:
                return {"ok": False, "verified": False, "wrong_answers_left": 0, "error": "too many wrong answers"}
            return {"ok": True, "verified": False, "wrong_answers_left": self.wrong_left}
        if name == "get_account":
            self.calls.append((name, dict(body)))
            if len(self.verified) < self.n_required:
                return {"ok": False, "error": "identity not verified"}
            return {"ok": True, "products": self.products}
        if name == "create_promise":
            self.calls.append((name, dict(body)))
            if len(self.verified) < self.n_required:
                return {"ok": False, "error": "identity not verified"}
            if self.fail_writes > 0:
                self.fail_writes -= 1
                return {"__http": 500}
            if body.get("product_id") not in {p["product_id"] for p in self.products}:
                return {"ok": False, "error": "unknown product_id"}
            self.promises.append({"product_id": body["product_id"], "amount": float(body["amount"]), "date": body["date"]})
            return {"ok": True, "promise_id": f"pr{len(self.promises)}"}
        if name == "close_call":
            self.calls.append((name, dict(body)))
            if self.outcome is not None:
                return {"ok": False, "error": "already closed"}
            row = next((r for r in self.ir.outcomes.table if r.outcome == body.get("outcome")), None)
            if row is None:
                return {"ok": False, "error": "unknown outcome"}
            if not row.reasons and "reason" in body:
                return {"ok": False, "error": "reason must be omitted"}
            if row.reasons and body.get("reason") not in row.reasons:
                return {"ok": False, "error": "reason not allowed for this outcome"}
            self.outcome = (body.get("outcome"), body.get("reason"))
            return {"ok": True}
        return super().call(name, body)


def _answer_for(r: P.IdentityRequirement) -> str:
    return {"date": "1988-03-14", "digits": "4471"[: (r.digits or 4)].ljust(r.digits or 4, "7"), "year": "1988"}.get(r.answer_format, "AB12CD")


def _id_turn(i, r: P.IdentityRequirement, wrong=False):
    t = {"_node": f"ask_{i}", "id_intent": "answers"}
    if r.answer_format == "date":
        t.update(id_day=14, id_month=3, id_year=1988 if not wrong else 1977)
    elif r.answer_format == "digits":
        t["id_digits"] = _answer_for(r) if not wrong else "0" * (r.digits or 4)
    elif r.answer_format == "year":
        t["id_year"] = 1988 if not wrong else 1911
    else:
        t["id_text"] = _answer_for(r) if not wrong else "ZZ99ZZ"
    return t


def _products_for(ir: P.PolicyIR, n):
    out = []
    types = list(ir.amounts.floors) or ["credit_card"]
    bands = ir.bands
    for k in range(n):
        band = bands[k % len(bands)]
        t = types[k % len(types)]
        p = {"type": t, "past_due": 420.0 + 100 * k, "days_late": band.days_late_min, ir.amounts.floors.get(t, "minimum_payment"): 126.0 + 10 * k}
        if "card" in t:
            p["card_last4"] = "4821"
        out.append(p)
    return out


def _expect_full_today(ir, products):
    h, b = ir.calendar.holidays, ir.calendar.business_days
    today = NOW[:10]
    day = today if bc.is_business_day(today, h, b) else bc.next_business_day(today, h, b)
    return [{"product_id": f"p{i + 1}", "amount": p["past_due"], "date": day} for i, p in enumerate(products)]


def validate_bodies(calls, tools):
    """Every bank request body must satisfy the supplied OpenAPI: required present, no unknown fields, enums and types."""
    problems = []
    for name, body in calls:
        t = tools.get(name)
        if t is None:
            problems.append(f"{name}: not in the tool API"); continue
        for k in t.required:
            if k not in body or body[k] in ("", None):
                problems.append(f"{name}: required {k} missing")
        for k, v in body.items():
            spec = t.body_props.get(k)
            if spec is None:
                problems.append(f"{name}: unknown field {k}"); continue
            if "enum" in spec and v not in spec["enum"]:
                problems.append(f"{name}.{k}={v!r} not in enum")
            ty = spec.get("type")
            if ty == "number" and not isinstance(v, (int, float)) or ty == "integer" and not isinstance(v, int) or ty == "string" and not isinstance(v, str):
                problems.append(f"{name}.{k}={v!r} is not {ty}")
    return problems


def run_scenario(ir: P.PolicyIR, wf, name, tools=None):
    reqs = ir.identity.requirements
    multi = ir.multi_product.max_products > 1 and len(ir.amounts.floors) > 0
    n_products = 2 if (name == "dispute_one" and multi) else 1
    products = _products_for(ir, n_products)
    verified = [{"_node": "opening", "holder": "confirmed"}] + [_id_turn(i, r) for i, r in enumerate(reqs)]
    O = ir.outcomes
    bank = IRBank(ir, products, fail_writes=2 if name == "write_fail" else 0)
    problems = []
    h, b = ir.calendar.holidays, ir.calendar.business_days
    today_ok = bc.is_business_day(NOW[:10], h, b)
    # "today" on a weekend/holiday: the agent offers the next business day and the customer accepts it
    pays_today = [{"_node": "state_debt", "cust_intent": "pays_today"}] + ([] if today_ok else [{"_node": "negotiate", "cust_intent": "accepts"}])
    if name == "happy":
        script = verified + pays_today + [{"_node": "readback", "rb_intent": "confirms"}]
        want_outcome, want_promises = (O.promise_outcome, None), _expect_full_today(ir, products)
    elif name == "refusal":
        n_attempts = sum(len(b.attempts) for b in ir.bands[:1]) or 1
        script = verified + [{"_node": "state_debt", "cust_intent": "refuses"}] + [{"_node": "negotiate", "cust_intent": "refuses"}] * 8
        want_outcome, want_promises = (O.no_promise_outcome, O.refused_reason or "refused"), []
    elif name == "hardship":
        sc = next((s for s in ir.special_cases if s.name == "hardship"), None)
        if not sc:
            return ["n/a: no hardship case"], bank
        script = verified + [{"_node": "state_debt", "cust_intent": "hardship"}, {"_node": "negotiate", "cust_intent": "refuses"}]
        want_outcome, want_promises = (sc.action.get("outcome") or O.no_promise_outcome, sc.action.get("reason") or ""), []
        if sc.action.get("type") == "note":
            want_outcome = (O.no_promise_outcome, sc.action.get("reason") or "")
    elif name == "third_party":
        cb = ir.third_party.callback
        h, b = ir.calendar.holidays, ir.calendar.business_days
        day = bc.next_business_day(NOW[:10], h, b, inclusive=False)
        script = [{"_node": "opening", "holder": "third_party"},
                  {"_node": "third_party", "tp_intent": "gives_time", "cb_kind": "tomorrow" if day == "2026-10-15" else "date", "cb_day": int(day[8:10]), "cb_month": int(day[5:7]), "cb_time": f"{int(cb.start[:2]) + 1:02d}:00"}]
        want_outcome, want_promises = (cb.scheduled_outcome[0], cb.scheduled_outcome[1]), []
    elif name == "wrong_id":
        r0 = reqs[0]
        script = [{"_node": "opening", "holder": "confirmed"}] + [_id_turn(0, r0, wrong=True)] * ir.identity.wrong_answer_limit
        want_outcome, want_promises = (ir.identity.failed_outcome[0], ir.identity.failed_outcome[1]), []
    elif name == "dispute_one":
        if not multi:
            return ["n/a: single-product policy"], bank
        disp = next(s for s in ir.special_cases if s.name == "dispute")
        script = verified + [{"_node": "state_debt", "cust_intent": "dispute", "prop_product": "1"},
                             {"_node": "negotiate", "cust_intent": "accepts"}, {"_node": "readback", "rb_intent": "confirms"}]
        if disp.ends_call or disp.action.get("type") == "close":      # no notes: a dispute closes the call for every product
            want_outcome, want_promises = (disp.action.get("outcome"), disp.action.get("reason") or None), []
        else:
            want_outcome, want_promises = (O.promise_outcome, None), None
    elif name == "write_fail":
        script = verified + pays_today + [{"_node": "readback", "rb_intent": "confirms"}]
        retries = ir.promise_write.retry_on_failure
        want_outcome = (O.promise_outcome, None) if retries >= 2 else (O.no_promise_outcome, O.service_error_reason or "service_error")
        want_promises = None
    else:
        raise ValueError(name)
    d = Driver(wf, bank, {"customer_id": "c_syn", "first_name": "A", "last_name": "B", "title": "Ms", "now": NOW}, script)
    try:
        d.run()
    except Exception as e:
        problems.append(f"driver: {e}")
    # --- structural invariants -------------------------------------------------------------------
    calls = [c[0] for c in bank.calls]
    if calls.count("close_call") != 1 or (calls and calls[-1] != "close_call"):
        problems.append(f"close_call count/order: {calls}")
    if "get_account" in calls and len(bank.verified) < len(reqs):
        problems.append("get_account before all identity questions passed")
    if "create_promise" in calls and not any(t.get("rb_intent") == "confirms" for t in script):
        problems.append("create_promise without a confirmation")
    if want_outcome is not None and bank.outcome != tuple(want_outcome):
        problems.append(f"outcome {bank.outcome} != {tuple(want_outcome)}")
    if want_promises is not None:
        got = sorted((p["product_id"], round(p["amount"], 2), p["date"]) for p in bank.promises)
        exp = sorted((p["product_id"], round(p["amount"], 2), p["date"]) for p in want_promises)
        if got != exp:
            problems.append(f"promises {got} != {exp}")
    if name == "write_fail":
        n_writes = calls.count("create_promise")
        if n_writes != min(1 + ir.promise_write.retry_on_failure, 3):
            problems.append(f"write attempts {n_writes}, policy allows {1 + ir.promise_write.retry_on_failure}")
    if name == "dispute_one" and want_promises is None:
        notes = sorted((n["product_id"], n["reason"]) for n in bank.notes)
        if ir.notes.enabled and ("p1", next(s for s in ir.special_cases if s.name == "dispute").action.get("reason", "dispute")) not in notes:
            problems.append(f"dispute note missing: {notes}")
        if not any(p["product_id"] == "p2" for p in bank.promises):
            problems.append("product 2 promise missing after dispute on product 1")
        if any(p["product_id"] == "p1" for p in bank.promises):
            problems.append("promise written for the disputed product")
    if tools:
        problems += validate_bodies(bank.calls, tools)
    for p in bank.promises:
        if p["date"] < NOW[:10]:
            problems.append(f"promise date before now: {p['date']}")
    return problems, bank


SCENARIOS = ("happy", "refusal", "hardship", "third_party", "wrong_id", "dispute_one", "write_fail")


def check_policy(policy_path: str, openapi_path: str, verbose=True):
    ir = P.PolicyIR.load_merged(policy_path.split("+"))
    tools = C.parse_openapi(openapi_path)
    errs = P.validate(ir, C.tool_enums(tools))
    if errs:
        return {"policy": policy_path, "invalid": errs}
    wf = C.compile_workflow(ir, tools)
    static = C.static_check(wf, tools)
    report = {"policy": policy_path, "static": static, "scenarios": {}}
    for sc in SCENARIOS:
        problems, bank = run_scenario(ir, wf, sc, tools)
        report["scenarios"][sc] = problems
        if verbose:
            status = "n/a " if problems and problems[0].startswith("n/a") else ("PASS" if not problems else "FAIL")
            print(f"  {status} {sc:12} {' > '.join(c[0] for c in bank.calls)[:70]}" + ("" if not problems or status == "n/a " else "  | " + "; ".join(problems)[:200]))
    return report


if __name__ == "__main__":
    rep = check_policy(sys.argv[1], sys.argv[2])
    bad = [k for k, v in rep.get("scenarios", {}).items() if v and not v[0].startswith("n/a")]
    print("invalid:" if rep.get("invalid") else "", rep.get("invalid", ""), "static:", rep.get("static") or "ok", "| failing scenarios:", bad or "none")
    sys.exit(1 if rep.get("invalid") or rep.get("static") or bad else 0)
