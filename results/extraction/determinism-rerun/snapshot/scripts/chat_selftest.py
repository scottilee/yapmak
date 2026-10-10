"""Pre-bank chat self-test for a published workflow — two scenarios via POST /api/v2/chat/message only.

(a) identity-start:  opening -> "Yes, speaking."          must land on the FIRST security question, whose text
                                                        must contain the first requirement's ask_text from the policy IR.
(b) third-party:     opening -> "This is her husband, ..." must NOT speak any pre-verification prohibited word
                                                        (IR phrases + generic account words + product names) and
                                                        must ask when the holder can be reached.

No bank answers are required, so this works for hidden briefs whose mock rejects unknown identity values.
Never starts a simulation; each scenario is one chat call, ended in a finally. Prints pass/fail JSON (exit 0/1).
`pass` is the FIRST attempt (strict gate for build.py); `--retry-on-fail N` re-runs failing scenarios and reports
`attempts/flaky/recovered` — Freya's extractor is stochastic and misclassified "Yes, speaking." / the husband line
once in five sampled runs (see results/audit/chat-selftest-examples/).

    source .env; .venv/bin/python scripts/chat_selftest.py --slot rehearsal-a \
        [--policy out/<slot>.policy.json] [--workflow-id <id>] [--vars '{...}'] [--out results/x.json] \
        [--retry-on-fail 1] [--verbose] [--deadline 420]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import freya  # noqa: E402
import policy as P  # noqa: E402
import runcontrol
from scripts.chatlib import Chat, variables_from, runtime_errors

GENERIC_BANNED = ["debt", "payment", "pay ", "amount", "due", "overdue", "arrears", "balance", "promise",
                  "collections", "instalment", "installment", "facilit", "product"]  # "facilit"/"product" are stems


def evidence_checks(session, target):
    call = session.evidence()
    values, events = variables_from(call)
    routes = [e for e in events if e.get("event") == "route_evaluated"]
    errors = runtime_errors(call)
    observed = any(isinstance(m.get("workflowSnapshot", {}).get("variableTable"), dict) for m in call.get("messages", []) if isinstance(m.get("workflowSnapshot"), dict)) or any(isinstance(e.get("variable_table"), dict) for e in events)
    return [
        {"name": "no_runtime_error", "pass": not errors if observed else None,
         "detail": "; ".join(errors) if errors else ("no runtime error observed" if observed else "variable evidence unavailable"), "soft": not observed},
        {"name": "routed_to_" + target,
         "pass": any(e.get("target") == target and e.get("matched") is not False for e in routes) if routes else None,
         "detail": f"holder={values.get('holder')!r} routes={[str(e.get('from_node')) + '->' + str(e.get('target')) for e in routes[-4:]]}",
         "soft": not routes},
    ]


def banned_words(ir):
    words = set(GENERIC_BANNED)
    ph = ir.phrases
    for w in ph.prohibited_before_verification or []:
        words.add(str(w).lower())
    for v in (ph.product_naming or {}).values():
        words.add(str(v).lower())
    return words


def scenario_identity(workflow_id, ir, cv, verbose=False):
    checks, turns = [], []
    with Chat(workflow_id, cv) as session:
        r1 = session.send("Hello?").get("response") or ""
        turns.append({"user": "Hello?", "agent": r1})
        opening = (ir.phrases.opening or "").split(".")[0].lower().strip()
        checks.append({"name": "opening_spoken", "pass": bool(r1) and (not opening or opening[:30] in r1.lower()), "detail": r1[:200]})
        checks.append({"name": "holder_asked", "pass": "?" in r1, "detail": r1[:200]})
        reqs = ir.identity.requirements or []
        ask = str(getattr(reqs[0], "ask_text", "") or "").lower().strip() if reqs else ""
        r2 = session.send("Yes, speaking.").get("response") or ""
        turns.append({"user": "Yes, speaking.", "agent": r2})
        ok = bool(ask) and (re.sub(r"\s+", " ", ask) in re.sub(r"\s+", " ", r2.lower()))
        checks.append({"name": "first_question_matches_ir", "pass": ok, "detail": f"want ask_text={ask!r} in {r2[:220]!r}"})
        checks.append({"name": "first_question_marked", "pass": "?" in r2, "detail": r2[:200]})
        checks.extend(evidence_checks(session, "ask_0"))
    return checks, turns


def scenario_third_party(workflow_id, ir, cv, verbose=False):
    checks, turns = [], []
    with Chat(workflow_id, cv) as session:
        r1 = session.send("Hello?").get("response") or ""
        turns.append({"user": "Hello?", "agent": r1})
        r2 = session.send("This is her husband, she's not here.").get("response") or ""
        turns.append({"user": "This is her husband, she's not here.", "agent": r2})
        low = re.sub(r"\s+", " ", r2.lower())
        hits = sorted(w for w in banned_words(ir) if w in low)
        checks.append({"name": "no_account_words", "pass": not hits, "detail": f"banned hits={hits} in {r2[:220]!r}"})
        asked = "?" in r2 and re.search(r"\b(when|what time|reach|available|call back|connect)\b", low)
        checks.append({"name": "asks_when_reachable", "pass": bool(asked), "detail": r2[:220]})
        checks.extend(evidence_checks(session, "third_party"))
    return checks, turns


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--slot", help="workflow slot (resolved via .freya-agents.json unless --workflow-id given)")
    ap.add_argument("--workflow-id")
    ap.add_argument("--policy", help="policy IR JSON written by build.py (default out/<slot>.policy.json)")
    ap.add_argument("--vars", help="JSON object or path overriding customer variables (now, title, names...)")
    ap.add_argument("--out", help="write the result JSON here too")
    ap.add_argument("--deadline", type=int, default=420, help="seconds for the whole self-test")
    ap.add_argument("--retry-on-fail", type=int, default=0, metavar="N",
                    help="re-run a failing scenario up to N times (Freya extraction is stochastic; a scenario that fails then passes is reported flaky=true, pass=true)")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    if a.deadline <= 0:
        ap.error("--deadline must be positive")
    with runcontrol.deadline(a.deadline):
        run(a)


def run(a):
    wf = a.workflow_id
    if not wf:
        if not a.slot:
            sys.exit("give --slot or --workflow-id")
        reg = json.load(open(ROOT / ".freya-agents.json"))
        wf = reg[a.slot]["workflow_id"]
    ppath = a.policy or (ROOT / "out" / f"{a.slot}.policy.json")
    ir = P.PolicyIR.load(str(ppath))

    cv = {"customer_id": "c_smoke", "first_name": "Test", "last_name": "Customer", "title": "Ms", "now": "2026-10-14T11:00"}
    if a.vars:
        extra = json.loads(a.vars) if a.vars.strip().startswith("{") else json.load(open(a.vars))
        cv.update(extra)

    t0 = time.monotonic()
    left = lambda: a.deadline - (time.monotonic() - t0)
    result = {"workflow_id": wf, "policy": str(ppath), "ok": None, "elapsed_s": None, "scenarios": [],
              "banned_words": sorted(banned_words(ir))}

    for name, fn in (("identity_start", scenario_identity), ("third_party_no_disclosure", scenario_third_party)):
        if left() < 30:
            result["scenarios"].append({"name": name, "pass": False, "skipped": "deadline"}); break
        attempts = []
        for k in range(1 + (a.retry_on_fail or 0)):
            try:
                checks, turns = fn(wf, ir, cv, a.verbose)
            except Exception as e:
                checks, turns = [{"name": "chat_call", "pass": False, "detail": repr(e)[:200]}], []
            passed = all(c["pass"] is not False for c in checks)
            attempts.append({"pass": passed, "checks": checks, "turns": turns})
            if passed or k >= a.retry_on_fail:
                break
        # pass = FIRST attempt (strict gate for build.py); flaky/recovered report what retries showed
        first = attempts[0]
        result["scenarios"].append({"name": name, "pass": first["pass"], "checks": first["checks"], "turns": first["turns"],
                                    "attempts": len(attempts), "flaky": len(attempts) > 1 and not first["pass"] and attempts[-1]["pass"],
                                    "recovered": any(x["pass"] for x in attempts[1:]) if len(attempts) > 1 else False})
        if a.verbose:
            for c in first["checks"]:
                print(f"[{name}] {'PASS' if c['pass'] else ('n/a' if c['pass'] is None else 'FAIL')} {c['name']}: {str(c.get('detail'))[:120]}", file=sys.stderr)

    result["ok"] = all(s["pass"] for s in result["scenarios"]) and len(result["scenarios"]) == 2
    result["elapsed_s"] = round(time.monotonic() - t0, 1)
    txt = json.dumps(result, indent=1)
    if a.out:
        pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(a.out).write_text(txt)
    print(txt)
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
