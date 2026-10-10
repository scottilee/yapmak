"""Auditor probes for paths the 13 public scripts don't cover (offline only; no Freya, no sim slot).
Reuses tests/offline_sim.py Driver + MockBank. Usage: .venv/bin/python /tmp/opencode/audit/probes.py
"""
import json, pathlib, sys
ROOT = pathlib.Path("/Users/sl/sbx/hackathon")
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
import offline_sim as O  # noqa

WFA = json.load(open(ROOT / "out/gen-a.workflow.json"))
WFB = json.load(open(ROOT / "out/gen-ab.workflow.json"))
CASES = {c["id"]: c for c in json.load(open(ROOT / "public-test-set.json"))}


class FailBank(O.MockBank):
    """create_promise fails always (fail_pid=None: every product; else only that product)."""
    def __init__(self, case, fail_pid=None, n_fail=10**9):
        super().__init__(case)
        self.fail_pid, self.left = fail_pid, n_fail

    def call(self, name, body):
        if name == "create_promise" and self.left > 0 and (self.fail_pid is None or body.get("product_id") == self.fail_pid):
            self.left -= 1
            self.calls.append((name, dict(body)))
            return {"ok": False, "error": "service unavailable"}
        return super().call(name, body)


def run(wf, case, script, bank=None):
    bank = bank or O.MockBank(case)
    cv = dict(case["variables"], customer_id="c_test")
    d = O.Driver(wf, bank, cv, list(script))
    try:
        d.run()
    except Exception as e:
        return f"DRIVER-ERROR: {e}", bank, d
    return "ran", bank, d


def rep(label, status, bank, want_outcome=None, want_promises=None, want_notes=None,
        want_calls=None, want_no_calls=(), want_close_last=True):
    problems = []
    if status != "ran":
        problems.append(status)
    else:
        got = (bank.outcome)
        if want_outcome is not None and tuple(got) != tuple(want_outcome):
            problems.append(f"outcome {got} != {want_outcome}")
        key = lambda p: (p["product_id"], round(float(p["amount"]), 2), p["date"])
        if want_promises is not None and sorted(map(key, bank.promises)) != sorted(map(key, want_promises)):
            problems.append(f"promises {[key(p) for p in bank.promises]} != {want_promises}")
        nk = lambda n: (n["product_id"], n["reason"])
        if want_notes is not None and sorted(map(nk, bank.notes)) != sorted(map(nk, want_notes)):
            problems.append(f"notes {[nk(n) for n in bank.notes]} != {want_notes}")
        if want_calls is not None and [c[0] for c in bank.calls] != want_calls:
            problems.append(f"calls {[c[0] for c in bank.calls]} != {want_calls}")
        for t in want_no_calls:
            if any(c[0] == t for c in bank.calls):
                problems.append(f"unexpected {t} call")
        if want_close_last and (not bank.calls or bank.calls[-1][0] != "close_call"):
            problems.append("last call not close_call")
    print(("PASS" if not problems else "FAIL"), label)
    for p in problems:
        print("   -", p)
    return problems


CONFIRM = {"_node": "opening", "holder": "confirmed"}
YES_RB = {"_node": "readback", "rb_intent": "confirms"}
UNCL = {"_node": "opening", "holder": "unclear"}


def dob(d, m, y):
    return {"_node": "ask_0", "id_intent": "answers", "id_day": d, "id_month": m, "id_year": y}


def phone(x):
    return {"_node": "ask_1", "id_intent": "answers", "id_digits": x}


def verified(case):
    y, m, d = case["identity"]["date_of_birth"].split("-")
    return [CONFIRM, dob(int(d), int(m), int(y)), phone(case["identity"]["phone_last4"])]


results = []

# P1. day/month swapped hint is not a wrong answer (PUB-13, B; dob 1991-01-08 -> swapped 1991-08-01)
c = CASES["PUB-13"]
s = [CONFIRM, {"_node": "ask_0", "id_intent": "answers", "id_day": 1, "id_month": 8, "id_year": 1991},
     dob(8, 1, 1991), phone("6604"),
     {"_node": "state_debt", "cust_intent": "pays_today", "prop_product": "all"}, YES_RB]
st, bank, d = run(WFB, c, s)
results.append(rep("P1 swapped-hint retry not counted wrong", st, bank,
                   want_outcome=("promise", None),
                   want_promises=[{"product_id": "p1", "amount": 300.0, "date": "2026-10-14"},
                                  {"product_id": "p2", "amount": 900.0, "date": "2026-10-14"}]))

# P2. decline explanation then answer (rule 15 first decline is not terminal)
c = CASES["PUB-01"]
s = [CONFIRM, dob(14, 3, 1988), {"_node": "ask_1", "id_intent": "declines"}, phone("4471"),
                        {"_node": "state_debt", "cust_intent": "pays_today"}, YES_RB]
st, bank, d = run(WFA, c, s)
results.append(rep("P2 decline-then-answer recovers", st, bank, want_outcome=("promise", None),
                   want_promises=[{"product_id": "p1", "amount": 420.0, "date": "2026-10-14"}]))

# P3a. "who is this?" (unclear) then confirm -> must NOT close yet (rule 3: ask that follows is the second ask)
c = CASES["PUB-01"]
s = [UNCL, CONFIRM] + verified(c)[1:] + [{"_node": "state_debt", "cust_intent": "pays_today"}, YES_RB]
st, bank, d = run(WFA, c, s)
results.append(rep("P3a question-then-confirm survives", st, bank, want_outcome=("promise", None),
                   want_promises=[{"product_id": "p1", "amount": 420.0, "date": "2026-10-14"}]))

# P3b. hello (unclear) then question (unclear) then yes -> rule 3 says the re-ask after the question IS the second ask;
# counter here closes after two unclear turns. Expect FAIL vs brief if outcome is not_reached/unclear.
s = [UNCL, UNCL, CONFIRM] + verified(c)[1:] + [{"_node": "state_debt", "cust_intent": "pays_today"}, YES_RB]
st, bank, d = run(WFA, c, s)
print("P3b unclear+question+yes -> outcome:", bank.outcome, "| close calls:", [x[0] for x in bank.calls])

# P4. third party offers time outside the window twice -> no schedule, not_reached/no_callback (rule 7)
c = CASES["PUB-02"]
s = [{"_node": "opening", "holder": "third_party"},
     {"_node": "third_party", "tp_intent": "gives_time", "cb_kind": "today", "cb_time": "09:00"},
     {"_node": "third_party", "tp_intent": "gives_time", "cb_kind": "tomorrow", "cb_time": "20:30"}]
st, bank, d = run(WFA, c, s)
results.append(rep("P4 outside-window twice -> no_callback", st, bank,
                   want_outcome=("not_reached", "no_callback"), want_no_calls=("schedule_callback",)))

# P5. floor refused then attempts consumed (rule 26+30; PUB-06 late band, floor 637.50, deadline 2026-10-23)
c = CASES["PUB-06"]
s = verified(c) + [{"_node": "state_debt", "cust_intent": "too_much"},
                   {"_node": "negotiate", "cust_intent": "refuses"},     # refuse floor -> flat refusal uses attempt 1
                   {"_node": "negotiate", "cust_intent": "refuses"},     # refuse attempt 1 -> attempt 2 floor on deadline
                   {"_node": "negotiate", "cust_intent": "accepts"}, YES_RB]
st, bank, d = run(WFA, c, s)
results.append(rep("P5 floor-refused attempt ladder", st, bank, want_outcome=("promise", None),
                   want_promises=[{"product_id": "p1", "amount": 637.50, "date": "2026-10-23"}]))

# P6. vague date twice -> agent proposes deadline (rule 21)
c = CASES["PUB-06"]
s = verified(c) + [{"_node": "state_debt", "cust_intent": "refuses"},
                   {"_node": "negotiate", "cust_intent": "proposes", "prop_kind": "vague"},
                   {"_node": "negotiate", "cust_intent": "proposes", "prop_kind": "vague"},
                   {"_node": "negotiate", "cust_intent": "accepts"}, YES_RB]
st, bank, d = run(WFA, c, s)
results.append(rep("P6 vague twice -> deadline offered", st, bank, want_outcome=("promise", None),
                   want_promises=[{"product_id": "p1", "amount": 2125.10, "date": "2026-10-23"}]))

# P7. correction at read-back (rule 35): amount 300 in range -> re-read -> confirm
c = CASES["PUB-01"]
s = verified(c) + [{"_node": "state_debt", "cust_intent": "pays_today"},
                   {"_node": "readback", "rb_intent": "changes", "prop_amount": 300},
                   {"_node": "readback", "rb_intent": "confirms"}]
st, bank, d = run(WFA, c, s)
results.append(rep("P7 readback correction re-validated", st, bank, want_outcome=("promise", None),
                   want_promises=[{"product_id": "p1", "amount": 300.0, "date": "2026-10-14"}]))

# P8. create_promise fails twice (single product A) -> no_promise/service_error (rule 37)
c = CASES["PUB-01"]
s = verified(c) + [{"_node": "state_debt", "cust_intent": "pays_today"}, YES_RB]
st, bank, d = run(WFA, c, s, bank=FailBank(c, fail_pid=None))
results.append(rep("P8 write fails twice -> service_error", st, bank,
                   want_outcome=("no_promise", "service_error"), want_promises=[]))

# P9. create_promise fails twice for product 2 of 2 (B rule 11): p1 recorded, note service_error p2
c = CASES["PUB-13"]
s = verified(c) + [{"_node": "state_debt", "cust_intent": "pays_today", "prop_product": "all"}, YES_RB]
st, bank, d = run(WFB, c, s, bank=FailBank(c, fail_pid="p2"))
results.append(rep("P9 p2 fails twice, p1 kept", st, bank, want_outcome=("promise", None),
                   want_promises=[{"product_id": "p1", "amount": 300.0, "date": "2026-10-14"}],
                   want_notes=[{"product_id": "p2", "reason": "service_error"}]))

# P10. dispute on product 2 of 3 (B rule 9): p1 promised, p2 noted dispute, p3 refused noted
c = CASES["PUB-12"]
s = verified(c) + [{"_node": "state_debt", "cust_intent": "proposes", "prop_kind": "tomorrow", "prop_product": "1"},
                   {"_node": "negotiate", "cust_intent": "dispute", "prop_product": "2"},
                   {"_node": "negotiate", "cust_intent": "refuses"},   # p3 early band: 1 attempt -> refused
                   YES_RB]
st, bank, d = run(WFB, c, s)
results.append(rep("P10 dispute one product, continue", st, bank, want_outcome=("promise", None),
                   want_promises=[{"product_id": "p1", "amount": 510.0, "date": "2026-10-15"}],
                   want_notes=[{"product_id": "p2", "reason": "dispute"}, {"product_id": "p3", "reason": "refused"}]))

# P11. restructuring after one product agreed but not yet recorded (B rule 10): no writes, no notes, transferred
c = CASES["PUB-12"]
s = verified(c) + [{"_node": "state_debt", "cust_intent": "proposes", "prop_kind": "tomorrow", "prop_product": "1"},
                   {"_node": "negotiate", "cust_intent": "restructuring"}]
st, bank, d = run(WFB, c, s)
results.append(rep("P11 restructuring: agreed-unrecorded not written", st, bank,
                   want_outcome=("transferred", "restructuring"), want_promises=[], want_notes=[],
                   want_no_calls=("add_note", "create_promise")))

# P12. transfer AFTER a recorded promise within the same call: B closing/A rule 117 -> transferred wins,
# recorded promise stays. Reached only if a special case fires before the batch write; simulate via readback decline
# then refuses_to_talk? Engine writes immediately after confirm, so check instead: dispute on p2 after p1 confirmed
# in readback batch (rule: notes on transfer only) -> not applicable. Use human request during negotiate after
# p1 proposed: A-style rule 42 -> transfer general, p1 proposed-unrecorded not written (consistent with B10).
c = CASES["PUB-01"]
s = verified(c) + [{"_node": "state_debt", "cust_intent": "proposes", "prop_kind": "tomorrow"},
                   {"_node": "readback", "rb_intent": "human"},
                   {"_node": "negotiate", "cust_intent": "human"}]
st, bank, d = run(WFA, c, s)
results.append(rep("P12 human after proposal -> transfer, no write", st, bank,
                   want_outcome=("transferred", "human"), want_promises=[],
                   want_no_calls=("create_promise",)))

# P13. hardship then customer names a date anyway (rule 32 tail): record the promise
c = CASES["PUB-06"]
s = verified(c) + [{"_node": "state_debt", "cust_intent": "hardship"},
                   {"_node": "negotiate", "cust_intent": "proposes", "prop_kind": "tomorrow"}, YES_RB]
st, bank, d = run(WFA, c, s)
results.append(rep("P13 hardship then customer names date -> recorded", st, bank,
                   want_outcome=("promise", None),
                   want_promises=[{"product_id": "p1", "amount": 2125.10, "date": "2026-10-15"}]))

# P14. third party cannot say at all -> close no_callback without scheduling (rule 7)
c = CASES["PUB-02"]
s = [{"_node": "opening", "holder": "third_party"},
     {"_node": "third_party", "tp_intent": "cannot_say"},
     {"_node": "third_party", "tp_intent": "cannot_say"}]
st, bank, d = run(WFA, c, s)
print("P14 cannot-say twice -> outcome:", bank.outcome, "callbacks:", bank.callbacks)

# P15. wrong answer counts globally across the two questions (rule 12):
# 2 wrong DOBs, pass DOB, 1 wrong phone -> check ends on the phone question, get_account never reached.
c = CASES["PUB-01"]
s = [CONFIRM, dob(1, 1, 1901), dob(2, 2, 1902), dob(14, 3, 1988), phone("0000")]
st, bank, d = run(WFA, c, s)
results.append(rep("P15 three wrongs end check (global across questions)", st, bank,
                   want_outcome=("not_verified", "failed"),
                   want_calls=["verify_identity", "verify_identity", "verify_identity", "verify_identity", "close_call"],
                   want_no_calls=("get_account",)))

print(f"\n{sum(1 for r in results if not r)} / {len(results)} probes fully as expected by the brief")
