"""Build the builder: one command, brief file(s) + tool API in, a published and exported Freya phone agent out.

    source .env   # FREYA_API_KEY, FREYA_BANK_TEAM_KEY; plus a Claude login or ANTHROPIC_API_KEY for the extractor
    python3 build.py --briefs briefs/brief-a.md[,briefs/brief-b.md] --openapi tools/openapi.json --slot hidden-1 [--cases public-test-set.json --brief A]

Fixed shape (plan §7): extract policy (3 bounded model passes) -> compile -> static check -> dry-run -> publish -> checkpoint export
-> chat smoke test -> one simulation (when a case file is given) -> final export. Every step is logged to traces/<slot>.jsonl.
The published agent never depends on the test outcome; the checkpoint is the deliverable from the moment it exists.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import freya  # noqa: E402
import compile as C  # noqa: E402
import extract as X  # noqa: E402
import policy as P  # noqa: E402
from trace import Trace, git_head  # noqa: E402


def retry(fn, what, tr, attempts=4, wait_s=20):
    """Platform calls get a few attempts: a 5xx from Freya is an outage, not a build problem (seen 10 Oct 13:41 UTC)."""
    last = None
    for i in range(1, attempts + 1):
        try:
            return fn()
        except Exception as e:
            last = e
            tr.event("platform_retry", step=what, attempt=i, error=repr(e)[:300])
            if i < attempts:
                time.sleep(wait_s)
    raise last


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--briefs", required=True, help="comma-separated brief files, in reading order")
    ap.add_argument("--openapi", required=True)
    ap.add_argument("--slot", required=True, help="workflow slot and output name, e.g. hidden-1")
    ap.add_argument("--cases", help="case file for the self-test simulation (public-test-set.json format); omit to skip the simulation")
    ap.add_argument("--brief", help="brief letter filter for --cases (A or B)")
    ap.add_argument("--policy", help="skip extraction and use this policy JSON (fixture path, '+'-joined overlays allowed)")
    ap.add_argument("--deadline", type=int, default=1800, help="seconds for the whole build")
    ap.add_argument("--no-smoke", action="store_true")
    a = ap.parse_args()

    t_start = time.monotonic()
    left = lambda: a.deadline - (time.monotonic() - t_start)
    briefs = a.briefs.split(",")
    out = ROOT / "out"
    out.mkdir(exist_ok=True)
    tr = Trace(ROOT / "traces" / f"{a.slot}.jsonl")
    tr.event("run_start", slot=a.slot, brief_paths=briefs, openapi_path=a.openapi, commit=git_head(ROOT), deadline_s=a.deadline,
             builder_model=X.MODEL, agent_model=freya.AGENT_LLM)
    export_path = out / f"{a.slot}.workflow.json"
    ids = None
    try:
        # 1. policy -----------------------------------------------------------------------------
        tools = C.parse_openapi(a.openapi)
        if a.policy:
            ir = P.PolicyIR.load_merged(a.policy.split("+"))
            tr.event("policy_loaded", path=a.policy)
        else:
            ir, audit = X.extract(briefs, a.openapi, a.slot, tr)
        problems = P.validate(ir, C.tool_enums(tools))
        if problems:
            raise SystemExit("policy invalid: " + "; ".join(problems))
        (out / f"{a.slot}.policy.json").write_text(ir.to_json())

        # 2. compile ----------------------------------------------------------------------------
        wf = C.compile_workflow(ir, tools)
        errs = C.static_check(wf, tools)
        tr.event("workflow_compiled", nodes=len(wf["nodes"]), size_kb=len(json.dumps(wf)) // 1024, static_errors=errs, compiler_notes=list(C.COMPILE_NOTES))
        if errs:
            raise SystemExit("static check failed: " + "; ".join(errs))
        (out / f"{a.slot}.candidate.json").write_text(json.dumps(wf, indent=1))

        # 3. publish + checkpoint ---------------------------------------------------------------
        retry(lambda: freya.validate_workflow(a.slot, wf), "validate", tr)
        ids = retry(lambda: freya.save_workflow(a.slot, wf), "publish", tr)
        if "version" not in ids:
            ids["version"] = retry(lambda: freya.update_workflow(ids["workflow_id"], wf), "publish_first", tr)   # first create: pin the agent model and publish
        tr.event("workflow_published", slot=a.slot, workflow_id=ids["workflow_id"], agent_id=ids["agent_id"], version=ids.get("version"))
        retry(lambda: freya.export_workflow(ids["workflow_id"], str(export_path)), "checkpoint_export", tr)
        tr.event("checkpoint_export", path=str(export_path.relative_to(ROOT)), version=ids.get("version"))

        # 4. smoke test -------------------------------------------------------------------------
        if not a.no_smoke:
            smoke(ids, ir, tr)

        # 5. one simulation (only with a case file and enough time) ------------------------------
        if a.cases and left() > 13 * 60:
            res = ROOT / "results" / f"{a.slot}.selftest.json"
            cmd = [sys.executable, "-u", str(ROOT / "tools" / "run_cases.py"), ids["agent_id"], "--cases", a.cases, "--out", str(res)]
            if a.brief:
                cmd += ["--brief", a.brief]
            t0 = time.time()
            budget = max(60, int(left() - 4 * 60))
            try:
                p = subprocess.run(cmd, capture_output=True, text=True, timeout=budget)
                tail = (p.stdout + p.stderr)[-3000:]
                summary = json.load(open(res)) if res.exists() else {}
                tr.event("simulation", agent_id=ids["agent_id"], version=ids.get("version"), cases=a.cases, brief=a.brief, duration_ms=int((time.time() - t0) * 1000),
                         passed=summary.get("passed"), total=summary.get("total"), simulation_id=summary.get("simulation_id"),
                         failed=[r["id"] for r in summary.get("rows", []) if not r["pass"]], output_tail=tail)
            except subprocess.TimeoutExpired:
                tr.event("simulation", agent_id=ids["agent_id"], status="timeout_after_s", seconds=budget)
        elif a.cases:
            tr.event("simulation_skipped", reason="not enough time left", left_s=int(left()))

        # 6. final export (the published version is unchanged by the test) ----------------------------
        retry(lambda: freya.export_workflow(ids["workflow_id"], str(export_path)), "final_export", tr)
        tr.event("export", path=str(export_path.relative_to(ROOT)), workflow_id=ids["workflow_id"], agent_id=ids["agent_id"], version=ids.get("version"))
        tr.event("run_end", success=True, elapsed_s=round(time.monotonic() - t_start, 1))
        print(json.dumps({"slot": a.slot, **ids, "workflow": str(export_path), "trace": str(tr.path), "elapsed_s": round(time.monotonic() - t_start)}))
    except BaseException as e:
        tr.event("run_end", success=False, error=repr(e)[:500], elapsed_s=round(time.monotonic() - t_start, 1), exported=export_path.exists())
        raise
    finally:
        tr.close()


def smoke(ids, ir: P.PolicyIR, tr: Trace):
    """One chat turn: does the workflow start and say the opening line? Never a simulation."""
    cv = {"customer_id": "c_smoke", "first_name": "Test", "last_name": "Customer", "title": "Ms", "now": "2026-10-14T11:00"}
    call_id, first = None, ""
    t0 = time.time()
    try:
        r = retry(lambda: freya.api("POST", "/api/v2/chat/message", {"workflowId": ids["workflow_id"], "message": "Hello?", "customerVariables": cv}),
                  "smoke_chat", tr, attempts=5, wait_s=30)
        call_id, first = r.get("callId"), r.get("response") or ""
    except Exception as e:
        tr.event("smoke_test", ok=False, error=repr(e)[:300], note="platform did not answer; the published workflow is unaffected")
        return
    finally:
        if call_id:
            try:
                freya.api("POST", "/api/v2/chat/end", {"callId": call_id})
            except Exception:
                pass
    opening = (ir.phrases.opening or "").split(".")[0].lower()
    tr.event("smoke_test", ok=bool(first) and (not opening or opening[:30] in first.lower()), first_line=first, duration_ms=int((time.time() - t0) * 1000), call_id=call_id)


if __name__ == "__main__":
    main()
