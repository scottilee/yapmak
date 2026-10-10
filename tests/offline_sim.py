"""Offline driver for a compiled workflow: runs the deterministic part (code nodes, routing, engine-fired API
nodes) against a mock bank, with the conversation nodes replaced by scripted extraction values.

It does NOT test the dialogue model or the extractor. It tests that, given what the extractor returns, the
state machine calls the right tools with the right arguments and closes with the right outcome.

    .venv/bin/python tests/offline_sim.py out/gen-a.workflow.json
"""
from __future__ import annotations

import datetime
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class MockBank:
    """Mirrors tools/openapi.json semantics for the public cases."""

    def __init__(self, case: dict, fail_promise_first=False):
        self.case = case
        self.calls = []
        self.promises, self.notes, self.callbacks, self.transfers = [], [], [], []
        self.outcome = None
        self.wrong_left = 3
        self.verified = set()
        self.fail_promise_first = fail_promise_first
        self.products = [dict(p, product_id=f"p{i + 1}") for i, p in enumerate(case["products"])]

    def call(self, name, body):
        self.calls.append((name, dict(body)))
        ident = self.case["identity"]
        if name == "verify_identity":
            f, a = body.get("field"), str(body.get("answer", ""))
            if f == "date_of_birth":
                try:
                    datetime.date.fromisoformat(a)
                except Exception:
                    return {"ok": False, "error": "unreadable date"}
                exp = ident["date_of_birth"]
                if a == exp:
                    self.verified.add(f)
                    return {"ok": True, "verified": True, "wrong_answers_left": self.wrong_left, "all_verified": len(self.verified) == 2}
                y, m, d = a.split("-")
                if f"{y}-{d}-{m}" == exp and int(d) <= 12:
                    return {"ok": True, "verified": False, "wrong_answers_left": self.wrong_left, "hint": "day_month_swapped"}
            else:
                if a == ident["phone_last4"]:
                    self.verified.add(f)
                    return {"ok": True, "verified": True, "wrong_answers_left": self.wrong_left, "all_verified": len(self.verified) == 2}
            self.wrong_left -= 1
            if self.wrong_left <= 0:
                return {"ok": False, "verified": False, "wrong_answers_left": 0, "error": "too many wrong answers"}
            return {"ok": True, "verified": False, "wrong_answers_left": self.wrong_left}
        if name == "get_account":
            if len(self.verified) < 2:
                return {"ok": False, "error": "identity not verified"}
            return {"ok": True, "products": self.products}
        if name == "create_promise":
            if len(self.verified) < 2:
                return {"ok": False, "error": "identity not verified"}
            if self.fail_promise_first:
                self.fail_promise_first = False
                return {"__http": 500}                       # the practice mock answers PUB-10's first write with HTTP 500 (no body fields)
            if body.get("product_id") not in {p["product_id"] for p in self.products}:
                return {"ok": False, "error": "unknown product_id"}
            self.promises.append({"product_id": body["product_id"], "amount": float(body["amount"]), "date": body["date"]})
            return {"ok": True, "promise_id": f"pr{len(self.promises)}"}
        if name == "add_note":
            self.notes.append({"product_id": body["product_id"], "reason": body["reason"]})
            return {"ok": True}
        if name == "schedule_callback":
            self.callbacks.append({"date": body["date"], "time": body["time"]})
            return {"ok": True}
        if name == "transfer_to_agent":
            self.transfers.append({"queue": body["queue"]})
            return {"ok": True}
        if name == "close_call":
            if self.outcome is not None:
                return {"ok": False, "error": "already closed"}
            if "reason" in body and body.get("outcome") in ("promise", "paid"):
                return {"ok": False, "error": "reason must be omitted"}
            self.outcome = (body.get("outcome"), body.get("reason"))
            return {"ok": True}
        return {"ok": False, "error": "unknown tool"}


def subst(s, vars_):
    if not isinstance(s, str):
        return s
    out, i = "", 0
    while True:
        a = s.find("{{", i)
        if a < 0:
            return out + s[i:]
        b = s.find("}}", a)
        name = s[a + 2:b]
        val = vars_.get(name)
        if val is None and s.strip() == "{{" + name + "}}":
            return None  # whole field dropped
        out += s[i:a] + ("{{" + name + "}}" if val is None else str(val))
        i = b + 2


class Driver:
    def __init__(self, wf, bank: MockBank, call_vars: dict, script: list, verbose=False):
        self.wf, self.bank, self.script, self.verbose = wf, bank, list(script), verbose
        self.vars = dict(call_vars)
        self.spoken = []
        self.trace = []

    def set_mapped(self, mapping, data):
        code = data.pop("__http", 200) if isinstance(data, dict) else 200
        env = {"status": "success" if code == 200 else "error", "data": data, "status_code": code}
        for m in mapping or []:
            cur = env
            for part in m["path"].split("."):
                cur = cur.get(part) if isinstance(cur, dict) else None
                if cur is None:
                    break
            if cur is not None:
                self.vars[m["variable"]] = str(cur).lower() if isinstance(cur, bool) else cur

    def route(self, node):
        for tr in node.get("transitions", []):
            c = tr["condition"]
            if c.get("operator") == "always":
                return tr["target_node"]
            conds = c.get("conditions", [])
            for cc in conds:
                if cc.get("operator") == "equals" and str(self.vars.get(cc["variable"], "")) == str(cc["operand"]):
                    return tr["target_node"]
        return None

    def run(self, max_steps=400):
        name = self.wf["initial_node"]
        nodes = self.wf["nodes"]
        for _ in range(max_steps):
            n = nodes[name]
            t = n["node_type"]
            oe = n.get("on_enter", {})
            if oe.get("type") == "tts":
                said = subst(oe["text"], self.vars)
                if not (n.get("on_enter_first_entry_only") and any(x[0] == name for x in self.trace)):
                    self.spoken.append((name, said))
            self.trace.append((name, t))
            if t == "code":
                code = n["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"]
                g = {"vars": self.vars}
                exec(code, g)
                if self.vars.get("runtime_error"):
                    raise RuntimeError(self.vars["runtime_error"])
                nxt = self.route(n)
            elif t == "api_request":
                fn = n["pre_actions"][0]["function"]
                body = {}
                for k, prop in fn["parameters"]["properties"]["body"]["properties"].items():
                    v = subst(prop["default"], self.vars)
                    if v is not None:
                        body[k] = v
                pre = n["pre_actions"][0].get("pre_process_code")
                if pre:
                    cfg = {"body": body}
                    exec(pre, {"vars": self.vars, "config": cfg})
                    body = cfg["body"]
                data = self.bank.call(fn["name"], body)
                self.set_mapped(n.get("response_mapping"), data)
                nxt = self.route(n)
            elif t == "conversation":
                if not self.script:
                    raise RuntimeError(f"script exhausted in node {name}; spoken so far: {self.spoken[-2:]}")
                turn = self.script.pop(0)
                if self.verbose:
                    print(f"   [{name}] agent: {self.spoken[-1][1] if self.spoken and self.spoken[-1][0]==name else self.vars.get('neg_instruction') or self.vars.get('id_say')}")
                    print(f"   [{name}] customer -> {turn}")
                expected_node = turn.pop("_node", None)
                if expected_node and expected_node != name:
                    raise AssertionError(f"expected to be in {expected_node}, was in {name}")
                self.vars.update(turn)
                nxt = self.route(n)
                if nxt == name:   # nothing matched: stay
                    continue
            elif t == "end_call":
                return
            else:
                raise RuntimeError(t)
            if not nxt:
                raise RuntimeError(f"no route from {name}")
            name = nxt
        raise RuntimeError("step limit")


# ---------------------------------------------------------------------------------------------
# scripts for the public cases, expressed as extraction results per conversation turn
# ---------------------------------------------------------------------------------------------
def dob(d, m, y):
    return {"_node": "ask_0", "id_intent": "answers", "id_day": d, "id_month": m, "id_year": y}


def phone(x):
    return {"_node": "ask_1", "id_intent": "answers", "id_digits": x}


CONFIRM = {"_node": "opening", "holder": "confirmed"}
YES_RB = {"_node": "readback", "rb_intent": "confirms"}


def verified(case):
    y, m, d = case["identity"]["date_of_birth"].split("-")
    return [CONFIRM, dob(int(d), int(m), int(y)), phone(case["identity"]["phone_last4"])]


SCRIPTS = {
    "PUB-01": lambda c: verified(c) + [{"_node": "state_debt", "cust_intent": "pays_today"}, YES_RB],
    "PUB-02": lambda c: [{"_node": "opening", "holder": "third_party"},
                         {"_node": "third_party", "tp_intent": "asks_purpose"},
                         {"_node": "third_party", "tp_intent": "gives_time", "cb_kind": "tomorrow", "cb_time": "11:00"}],
    "PUB-03": lambda c: [CONFIRM, dob(12, 7, 1991), dob(21, 8, 1992), dob(21, 7, 1990)],
    "PUB-04": lambda c: verified(c) + [{"_node": "state_debt", "cust_intent": "proposes", "prop_kind": "date", "prop_day": 6, "prop_month": 11},
                                       {"_node": "negotiate", "cust_intent": "accepts"}, YES_RB],
    "PUB-05": lambda c: verified(c) + [{"_node": "state_debt", "cust_intent": "hardship"},
                                       {"_node": "negotiate", "cust_intent": "refuses"}],
    "PUB-06": lambda c: verified(c) + [{"_node": "state_debt", "cust_intent": "too_much"},
                                       {"_node": "negotiate", "cust_intent": "proposes", "prop_kind": "weekday", "prop_weekday": "friday", "prop_relative": "this"}, YES_RB],
    "PUB-07": lambda c: verified(c) + [{"_node": "state_debt", "cust_intent": "proposes", "prop_kind": "vague"},
                                       {"_node": "negotiate", "cust_intent": "proposes", "prop_kind": "date", "prop_day": 26},
                                       # the customer accepts by restating the offer (seen in a live run)
                                       {"_node": "negotiate", "cust_intent": "accepts", "prop_kind": "weekday", "prop_weekday": "tuesday", "prop_relative": "this", "prop_day": 27}, YES_RB],
    "PUB-08": lambda c: verified(c) + [{"_node": "state_debt", "cust_intent": "already_paid"}],
    "PUB-09": lambda c: verified(c) + [{"_node": "state_debt", "cust_intent": "restructuring"}],
    "PUB-10": lambda c: verified(c) + [{"_node": "state_debt", "cust_intent": "refuses"},
                                       {"_node": "negotiate", "cust_intent": "accepts"}, YES_RB],
    "PUB-11": lambda c: verified(c) + [{"_node": "state_debt", "cust_intent": "proposes", "prop_kind": "weekday", "prop_weekday": "friday", "prop_relative": "this", "prop_product": "all"}, YES_RB],
    "PUB-12": lambda c: [CONFIRM, dob(*reversed([int(x) for x in c["identity"]["date_of_birth"].split("-")])), phone("4401"), phone("4410"),
                         {"_node": "state_debt", "cust_intent": "proposes", "prop_kind": "tomorrow", "prop_product": "1"},
                         {"_node": "negotiate", "cust_intent": "refuses"},   # loan attempt 1
                         {"_node": "negotiate", "cust_intent": "refuses"},   # loan attempt 2
                         {"_node": "negotiate", "cust_intent": "refuses"},   # car loan attempt 1
                         YES_RB],
    "PUB-13": lambda c: verified(c) + [{"_node": "state_debt", "cust_intent": "proposes", "prop_kind": "date", "prop_day": 30, "prop_month": 10, "prop_product": "all"}, YES_RB],
}


# identity answers in pieces (speech style "pieces"): day+month first, year in the next turn; digits in two halves
def dob_pieces(d, m, y):
    return [{"_node": "ask_0", "id_intent": "answers", "id_day": d, "id_month": m}, {"_node": "ask_0", "id_intent": "answers", "id_year": y}]


def phone_pieces(x):
    return [{"_node": "ask_1", "id_intent": "answers", "id_digits": x[:2]}, {"_node": "ask_1", "id_intent": "answers", "id_digits": x[2:]}]


def _pieces_01(c):
    y, m, d = c["identity"]["date_of_birth"].split("-")
    return [CONFIRM] + dob_pieces(int(d), int(m), int(y)) + phone_pieces(c["identity"]["phone_last4"]) + [{"_node": "state_debt", "cust_intent": "pays_today"}, YES_RB]


SCRIPTS["PUB-01-pieces"] = _pieces_01


def run_case(wf, case, verbose=False):
    bank = MockBank(case, fail_promise_first=(case["id"] == "PUB-10"))
    cv = dict(case["variables"], customer_id="c_test")
    d = Driver(wf, bank, cv, SCRIPTS[case["id"]](case), verbose)
    d.run()
    exp = case["expected"]
    bad = []
    if bank.outcome != (exp["outcome"], exp.get("reason")):
        bad.append(f"outcome {bank.outcome} expected {(exp['outcome'], exp.get('reason'))}")
    key = lambda p: (p["product_id"], round(float(p["amount"]), 2), p["date"])
    if sorted(map(key, bank.promises)) != sorted(map(key, exp["promises"])):
        bad.append(f"promises {sorted(map(key, bank.promises))} expected {sorted(map(key, exp['promises']))}")
    nk = lambda n: (n["product_id"], n["reason"])
    if sorted(map(nk, bank.notes)) != sorted(map(nk, exp["notes"])):
        bad.append(f"notes {bank.notes} expected {exp['notes']}")
    if [(c["date"], c["time"]) for c in bank.callbacks] != [(c["date"], c["time"]) for c in exp["callbacks"]]:
        bad.append(f"callbacks {bank.callbacks} expected {exp['callbacks']}")
    if sorted(t["queue"] for t in bank.transfers) != sorted(t["queue"] for t in exp["transfers"]):
        bad.append(f"transfers {bank.transfers} expected {exp['transfers']}")
    if not bank.calls or bank.calls[-1][0] != "close_call":
        bad.append("last call is not close_call")
    if sum(1 for c in bank.calls if c[0] == "close_call") != 1:
        bad.append("close_call count != 1")
    return bad, bank, d


if __name__ == "__main__":
    wfs = {"A": json.load(open(sys.argv[1]))}
    wfs["B"] = json.load(open(sys.argv[2])) if len(sys.argv) > 2 and sys.argv[2].endswith(".json") else wfs["A"]
    only = sys.argv[-1].split(",") if not sys.argv[-1].endswith(".json") else None
    cases = [c for c in json.load(open(ROOT / "public-test-set.json")) if not only or c["id"] in only]
    if not only or "PUB-01-pieces" in only:
        base = next(c for c in json.load(open(ROOT / "public-test-set.json")) if c["id"] == "PUB-01")
        cases.append(dict(base, id="PUB-01-pieces", title=base["title"] + " [pieces]"))
    ok = 0
    for case in cases:
        try:
            bad, bank, d = run_case(wfs[case["brief"]], case, verbose=bool(only))
        except Exception as e:
            bad, bank, d = [f"driver error: {e}"], None, None
        print(("PASS" if not bad else "FAIL"), case["id"], case["title"], "|", " > ".join(c[0] for c in bank.calls) if bank else "")
        for b in bad:
            print("     -", b)
        if only and d:
            for s in d.spoken:
                print("     said", s)
        ok += not bad
    print(f"{ok} / {len(cases)} offline")
