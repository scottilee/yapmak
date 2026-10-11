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

import datetime
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
# the clock sweep: a mid-week day, a Friday (attempt dates near deadlines), a Saturday, and a month-end Friday
NOWS = ("2026-10-14T11:00", "2026-10-23T11:00", "2026-10-17T11:00", "2026-10-30T11:00")


class IRBank(MockBank):
    """Mock bank whose identity answers, products and failure behaviour follow the policy under test."""

    def __init__(self, ir: P.PolicyIR, products, fail_writes=0, slots=None, rslots=None):
        self.ir = ir
        self.slots = slots or {}          # {tool: {semantic argument: actual body field}} from compiler_openapi.request_slots
        self.rslots = rslots              # compiler_openapi.response_slots(tools): the API's own response field names
        self.identity_answers = {r.field: _answer_for(r) for r in ir.identity.requirements}
        case = {"identity": {}, "products": products, "id": "SYN"}
        super().__init__(case)
        self.products = [dict(p, product_id=f"p{i + 1}") for i, p in enumerate(products)]
        self.fail_writes = fail_writes
        self.wrong_left = ir.identity.wrong_answer_limit
        self.n_required = len(ir.identity.requirements)

    def call(self, name, body):
        self.raw_calls = getattr(self, "raw_calls", []); self.raw_calls.append((name, dict(body)))   # as sent, for schema validation
        if self.slots.get(name):
            body = {sem: body[actual] for sem, actual in self.slots[name].items() if actual in body}     # semantic view for the mock's logic
        return self._translate(name, self._call(name, body))

    def _translate(self, name, resp):
        """Answer in the API's own response field names (verify flags, product list and fields, success flags)."""
        R = self.rslots
        if not R or not isinstance(resp, dict) or "__http" in resp:
            return resp
        if name == "verify_identity":
            V = R["verify"]; out = {}
            for sem, key in (("ok", "ok"), ("verified", "verified"), ("all_verified", "all_verified"), ("wrong_answers_left", "remaining"), ("hint", "hint")):
                if sem in resp and V.get(key) and V[key] != "__none__":
                    out[V[key]] = resp[sem]
            if "error" in resp: out["error"] = resp["error"]
            return out
        if name == "get_account":
            A = R["account"]; out = {}
            okk = R["ok_by_tool"].get("get_account")
            if okk and "ok" in resp: out[okk] = resp["ok"]
            if "products" in resp:
                prods = []
                for p in resp["products"]:
                    q = {}
                    for sem, key in (("product_id", "id"), ("type", "type"), ("past_due", "past_due"), ("days_late", "days_late"), ("card_last4", "card_last4")):
                        if sem in p and A.get(key) and A[key] != "__none__":
                            q[A[key]] = p[sem]
                    for k, v in p.items():
                        if k not in ("product_id", "type", "past_due", "days_late", "card_last4"):
                            q[k] = v                 # floor fields keep the API's names (the IR refers to them)
                    prods.append(q)
                out[A["list"]] = prods
            if "error" in resp: out["error"] = resp["error"]
            return out
        okk = R["ok_by_tool"].get(name)
        if okk and "ok" in resp and okk != "ok":
            resp = dict(resp); resp[okk] = resp.pop("ok")
        return resp

    def _call(self, name, body):
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


def _floor_rule(ir: P.PolicyIR, t):
    rules = ir.amounts.floor_rules or {}
    rule = rules.get(t) or rules.get("*")
    if rule:
        return rule
    f = ir.amounts.floors.get(t)
    return {"kind": "field", "field": f} if f else None


def _floor_value(ir: P.PolicyIR, p):
    """The floor the agent must compute for product p, from the IR (mirrors workflow_runtime._floor_of)."""
    rule = _floor_rule(ir, p["type"]); full = p["past_due"]
    if not rule:
        return full
    if rule["kind"] == "field":
        return p.get(rule["field"], full)
    if rule["kind"] == "percent":
        return min(max(round(full * rule["percent"] / 100.0, 2), float(rule.get("min_amount") or 0)), full)
    if rule["kind"] == "max_of":
        pct = full * rule["percent"] / 100.0
        if rule.get("round") == "up_cent":
            cents = int(pct * 100 + 1e-9); pct = (cents + (1 if pct * 100 - cents > 1e-9 else 0)) / 100.0
        else:
            pct = round(pct, 2)
        return min(max(float(p.get(rule["field"], 0) or 0), pct), full)
    return min(float(rule["amount"]), full)


def _products_for(ir: P.PolicyIR, n, past_due_name=""):
    """Mock products; a floor rule's field gets its own synthetic value unless that field IS the API's past-due field
    (then the floor is the full amount and no second value exists)."""
    out = []
    types = [t for t in list(ir.amounts.floors) + list(ir.amounts.floor_rules or {}) if t != "*"] or ["credit_card"]
    bands = ir.bands
    for k in range(n):
        band = bands[k % len(bands)]
        t = types[k % len(types)]
        p = {"type": t, "past_due": 420.0 + 100 * k, "days_late": band.days_late_min}
        rule = _floor_rule(ir, t)
        if rule and rule["kind"] in ("field", "max_of") and rule["field"] not in ("past_due", past_due_name):
            p[rule["field"]] = 126.0 + 10 * k
        if "card" in t:
            p["card_last4"] = "4821"
        out.append(p)
    return out


def _expect_full_today(ir, products, now=NOW):
    h, b = ir.calendar.holidays, ir.calendar.business_days
    today = now[:10]
    if not ir.dates.promise_today_allowed:
        day = bc.next_business_day(today, h, b, inclusive=False)       # no promise for today: the next business day is offered
    else:
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
            if spec is None and k in (t.required or []):
                continue                      # a required name the schema lists without a property: sent as an alias, nothing to type-check
            if spec is None:
                problems.append(f"{name}: unknown field {k}"); continue
            if "enum" in spec and v not in spec["enum"]:
                problems.append(f"{name}.{k}={v!r} not in enum")
            ty = spec.get("type")
            if ty == "number" and not isinstance(v, (int, float)) or ty == "integer" and not isinstance(v, int) or ty == "string" and not isinstance(v, str):
                problems.append(f"{name}.{k}={v!r} is not {ty}")
    return problems


def run_scenario(ir: P.PolicyIR, wf, name, tools=None, now=NOW):
    reqs = ir.identity.requirements
    multi = ir.multi_product.max_products > 1 and (len(ir.amounts.floors) > 0 or len(ir.amounts.floor_rules or {}) > 0)
    n_products = 2 if (name == "dispute_one" and multi) else 1
    import compiler_openapi as CO
    past_due_name = CO.response_slots(tools, ir.api_fields)["account"]["past_due"] if tools else ""
    products = _products_for(ir, n_products, past_due_name)
    verified = [{"_node": "opening", "holder": "confirmed"}] + [_id_turn(i, r) for i, r in enumerate(reqs)]
    O = ir.outcomes
    bank = IRBank(ir, products, fail_writes=2 if name == "write_fail" else 0, slots=CO.request_slots(tools, ir.api_fields) if tools else None, rslots=CO.response_slots(tools, ir.api_fields) if tools else None)
    problems = []
    h, b = ir.calendar.holidays, ir.calendar.business_days
    if ir.dates.past_deadline == "no_promise":
        for q in products:
            band = ir.band_for(q["days_late"])
            dl = bc.deadline(now[:10], band.deadline, h, b) if band else None
            if dl and dl < now[:10]:
                return [f"n/a: deadline {dl} already passed on {now[:10]} and the policy takes no promise then"], bank
    today_ok = bc.is_business_day(now[:10], h, b) and ir.dates.promise_today_allowed
    # "today" on a weekend/holiday: the agent offers the next business day and the customer accepts it
    pays_today = [{"_node": "state_debt", "cust_intent": "pays_today"}] + ([] if today_ok else [{"_node": "negotiate", "cust_intent": "accepts"}])
    if name == "happy":
        script = verified + pays_today + [{"_node": "readback", "rb_intent": "confirms"}]
        want_outcome, want_promises = (O.promise_outcome, None), _expect_full_today(ir, products, now)
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
        if sc.action.get("type") == "continue" and not sc.action.get("reason"):
            want_outcome = (O.no_promise_outcome, O.refused_reason or "refused")   # no hardship treatment: "still cannot pay" is a refusal
    elif name == "hardship_accept":
        sc = next((s for s in ir.special_cases if s.name == "hardship"), None)
        if not sc or not sc.offer_transfer_queue:
            return ["n/a: no support offer"], bank
        script = verified + [{"_node": "state_debt", "cust_intent": "hardship"}, {"_node": "negotiate", "cust_intent": "human"}]   # "yes, connect me" often extracts as human
        want_outcome, want_promises = (sc.offer_outcome[0] or O.transfer_outcome, sc.offer_outcome[1] or None), []
    elif name == "third_party":
        cb = ir.third_party.callback
        if cb.enabled is False:
            script = [{"_node": "opening", "holder": "third_party"}]
            oc = cb.no_callback_outcome if cb.no_callback_outcome[0] else ir.third_party.wrong_number_outcome
            want_outcome, want_promises = (oc[0], oc[1] or None), []
            d = Driver(wf, bank, {"customer_id": "c_syn", "first_name": "A", "last_name": "B", "title": "Ms", "now": now}, script)
            try:
                d.run()
            except Exception as e:
                problems.append(f"driver: {e}")
            calls = [c[0] for c in bank.calls]
            if calls != ["close_call"] or bank.outcome != tuple(want_outcome):
                problems.append(f"no-callback policy: calls {calls} outcome {bank.outcome} != {tuple(want_outcome)}")
            return problems, bank
        h, b = ir.calendar.holidays, ir.calendar.business_days
        if cb.days == "today":
            if not bc.is_business_day(now[:10], h, b) or f"{int(cb.start[:2]) + 1:02d}:00" <= now[11:16]:
                return ["n/a: today-only callbacks and today is closed or the window has passed"], bank
            day, kind = now[:10], "today"
        else:
            day = bc.next_business_day(now[:10], h, b, inclusive=False)
            kind = "tomorrow" if day == (datetime.date.fromisoformat(now[:10]) + datetime.timedelta(days=1)).isoformat() else "date"
        script = [{"_node": "opening", "holder": "third_party"},
                  {"_node": "third_party", "tp_intent": "gives_time", "cb_kind": kind, "cb_day": int(day[8:10]), "cb_month": int(day[5:7]), "cb_time": f"{int(cb.start[:2]) + 1:02d}:00"}]
        want_outcome, want_promises = (cb.scheduled_outcome[0], cb.scheduled_outcome[1]), []
    elif name == "wrong_id":
        r0 = reqs[0]
        script = [{"_node": "opening", "holder": "confirmed"}] + [_id_turn(0, r0, wrong=True)] * ir.identity.wrong_answer_limit
        want_outcome, want_promises = (ir.identity.failed_outcome[0], ir.identity.failed_outcome[1]), []
    elif name == "dispute_one":
        if not multi:
            return ["n/a: single-product policy"], bank
        if not any(s.name == "dispute" for s in ir.special_cases):
            return ["n/a: no dispute rule"], bank
        b2 = ir.band_for(products[1]["days_late"])
        if b2 is not None and not b2.attempts:
            return ["n/a: product 2's band has no persuasion attempts (nothing is proposed after the dispute note)"], bank
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
    elif name in ("too_much_floor", "below_floor_twice", "after_deadline", "readback_change", "weekend_named", "between"):
        p0 = products[0]
        floor, full = _floor_value(ir, p0), p0["past_due"]
        band = ir.band_for(p0["days_late"])
        dl = bc.deadline(now[:10], band.deadline, h, b)
        if dl < now[:10]:
            dl = bc.next_business_day(now[:10], h, b)
        def dmy(iso):
            return {"prop_kind": "date", "prop_day": int(iso[8:10]), "prop_month": int(iso[5:7]), "prop_year": int(iso[:4])}
        today_bd = bc.next_business_day(now[:10], h, b)                      # today, or the first business day after a weekend/holiday
        if not ir.dates.promise_today_allowed:
            today_bd = bc.next_business_day(now[:10], h, b, inclusive=False)   # no promise for today
        if name == "too_much_floor":           # full too much -> the floor is offered once -> accepted
            script = verified + [{"_node": "state_debt", "cust_intent": "too_much"}, {"_node": "negotiate", "cust_intent": "accepts"}, {"_node": "readback", "rb_intent": "confirms"}]
            want_outcome, want_promises = (O.promise_outcome, None), "floor"
            if not ir.amounts.floor_offered_once:   # no counter-offer policy: "too much" is a refusal, the call closes without a promise
                script = verified + [{"_node": "state_debt", "cust_intent": "too_much"}] + [{"_node": "negotiate", "cust_intent": "refuses"}] * 3
                want_outcome, want_promises = (O.no_promise_outcome, O.refused_reason or "refused"), []
        elif name == "below_floor_twice":      # half the floor -> floor offered -> refuses everything -> no promise
            script = verified + [{"_node": "state_debt", "cust_intent": "proposes", "prop_amount": round(floor / 2, 2), **dmy(today_bd)}] + [{"_node": "negotiate", "cust_intent": "refuses"}] * 8
            want_outcome, want_promises = (O.no_promise_outcome, O.refused_reason or "refused"), []
        elif name == "after_deadline":         # a date 10 days after the deadline -> the deadline is offered -> accepted
            if not ir.dates.after_deadline_offer_deadline:
                return ["n/a: the policy names the deadline but offers nothing (after_deadline_offer_deadline false)"], bank
            late = (datetime.date.fromisoformat(dl) + datetime.timedelta(days=10)).isoformat()
            script = verified + [{"_node": "state_debt", "cust_intent": "proposes", **dmy(late)}, {"_node": "negotiate", "cust_intent": "accepts"}, {"_node": "readback", "rb_intent": "confirms"}]
            want_outcome, want_promises = (O.promise_outcome, None), [{"product_id": "p1", "amount": full, "date": dl}]
        elif name == "readback_change":        # pays today, changes the day at the read-back to the next business day -> one promise on that day
            nb = bc.next_business_day(today_bd, h, b, inclusive=False)
            if nb > dl:
                return ["n/a: next business day is after the deadline"], bank
            script = verified + pays_today + [{"_node": "readback", "rb_intent": "changes", **dmy(nb)}, {"_node": "readback", "rb_intent": "confirms"}]
            want_outcome, want_promises = (O.promise_outcome, None), [{"product_id": "p1", "amount": full, "date": nb}]
        elif name == "weekend_named":          # names the first non-business day ahead -> rolled to the next business day -> accepted
            if not ir.dates.weekend_or_holiday_roll_forward:
                return ["n/a: the policy asks for another day instead of rolling forward (weekend_or_holiday_roll_forward false)"], bank
            d0 = datetime.date.fromisoformat(now[:10])
            off = next((d0 + datetime.timedelta(days=i) for i in range(1, 10) if not bc.is_business_day((d0 + datetime.timedelta(days=i)).isoformat(), h, b)), None)
            if off is None or off.isoformat() > dl:
                return ["n/a: no non-business day before the deadline"], bank
            rolled = bc.next_business_day(off.isoformat(), h, b)
            if rolled > dl:
                return ["n/a: rolled date after the deadline"], bank
            script = verified + [{"_node": "state_debt", "cust_intent": "proposes", **dmy(off.isoformat())}, {"_node": "negotiate", "cust_intent": "accepts"}, {"_node": "readback", "rb_intent": "confirms"}]
            want_outcome, want_promises = (O.promise_outcome, None), [{"product_id": "p1", "amount": full, "date": rolled}]
        else:                                  # an amount between floor and full on the first business day -> accepted as is
            amt = round((floor + full) / 2, 2)
            script = verified + [{"_node": "state_debt", "cust_intent": "proposes", "prop_amount": amt, **dmy(today_bd)}, {"_node": "readback", "rb_intent": "confirms"}]
            want_outcome, want_promises = (O.promise_outcome, None), [{"product_id": "p1", "amount": amt, "date": today_bd}]
    else:
        raise ValueError(name)
    d = Driver(wf, bank, {"customer_id": "c_syn", "first_name": "A", "last_name": "B", "title": "Ms", "now": now}, script)
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
    if want_outcome is not None and not want_outcome[1] and tools and "close_call" in tools:
        # the API requires a reason on every close (or the table allows exactly one): the agent sends the outcome's table reason
        req = CO.request_slots(tools, ir.api_fields)["close_call"].get("reason") in (tools["close_call"].required or [])
        row = next((r for r in ir.outcomes.table if r.outcome == want_outcome[0]), None)
        if row and row.reasons and (req or len(row.reasons) == 1):
            want_outcome = (want_outcome[0], row.reasons[0])
    if want_outcome is not None and bank.outcome != tuple(want_outcome):
        problems.append(f"outcome {bank.outcome} != {tuple(want_outcome)}")
    if want_promises == "floor":
        p0 = products[0]
        floor = _floor_value(ir, p0)
        if len(bank.promises) != 1 or abs(bank.promises[0]["amount"] - floor) > 0.005:
            problems.append(f"floor path: promises {bank.promises} != one promise of the floor {floor}")
        want_promises = None
    if want_promises is not None:
        got = sorted((p["product_id"], round(p["amount"], 2), p["date"]) for p in bank.promises)
        exp = sorted((p["product_id"], round(p["amount"], 2), p["date"]) for p in want_promises)
        if got != exp:
            problems.append(f"promises {got} != {exp}")
    if name == "hardship_accept":
        if [t["queue"] for t in bank.transfers] != [next(s for s in ir.special_cases if s.name == "hardship").offer_transfer_queue]:
            problems.append(f"transfer queue {bank.transfers}")
        if bank.notes:
            problems.append(f"notes on a transfer: {bank.notes}")
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
        problems += validate_bodies(getattr(bank, "raw_calls", bank.calls), tools)
    h, b = ir.calendar.holidays, ir.calendar.business_days
    for p in bank.promises:
        if p["date"] < now[:10]:
            problems.append(f"promise date before now: {p['date']}")
        prod = next((q for q in products if f"p{products.index(q) + 1}" == p["product_id"]), None)
        band = ir.band_for(prod["days_late"]) if prod else None
        dl = bc.deadline(now[:10], band.deadline, h, b) if band else None
        if dl and dl >= now[:10] and p["date"] > dl:
            problems.append(f"promise date {p['date']} after the band deadline {dl}")
        if not bc.is_business_day(p["date"], h, b):
            problems.append(f"promise date {p['date']} is not a business day")
    return problems, bank


SCENARIOS = ("happy", "refusal", "hardship", "hardship_accept", "third_party", "wrong_id", "dispute_one", "write_fail",
             "too_much_floor", "below_floor_twice", "after_deadline", "readback_change", "weekend_named", "between")


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
        for now in NOWS:
            problems, bank = run_scenario(ir, wf, sc, tools, now)
            key = sc if now == NOWS[0] else f"{sc}@{now[:10]}"
            report["scenarios"][key] = problems
            if verbose and (now == NOWS[0] or (problems and not problems[0].startswith("n/a"))):
                status = "n/a " if problems and problems[0].startswith("n/a") else ("PASS" if not problems else "FAIL")
                print(f"  {status} {key:23} {' > '.join(c[0] for c in bank.calls)[:60]}" + ("" if not problems or status == "n/a " else "  | " + "; ".join(problems)[:200]))
    return report


if __name__ == "__main__":
    rep = check_policy(sys.argv[1], sys.argv[2])
    bad = [k for k, v in rep.get("scenarios", {}).items() if v and not v[0].startswith("n/a")]
    print("invalid:" if rep.get("invalid") else "", rep.get("invalid", ""), "static:", rep.get("static") or "ok", "| failing scenarios:", bad or "none")
    sys.exit(1 if rep.get("invalid") or rep.get("static") or bad else 0)
