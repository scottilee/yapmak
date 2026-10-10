"""Build the builder: one command, brief file(s) + tool API in, a published and exported Freya phone agent out.

    source .env   # FREYA_API_KEY, FREYA_BANK_TEAM_KEY; plus a Claude login or ANTHROPIC_API_KEY for the extractor
    .venv/bin/python build.py --briefs briefs/brief-a.md[,briefs/brief-b.md] --openapi tools/openapi.json --slot hidden-1 [--cases public-test-set.json --brief A]
    .venv/bin/python build.py --policy <policy.json[+overlay.json]> --openapi tools/openapi.json --slot <name>   # no LLM; rehearsal path

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


def instrument_freya(tr: Trace):
    """Every Freya HTTP call that writes (POST/PUT/DELETE) becomes a trace event, so the trace accounts for each create,
    update, publish, simulation and chat turn — not only the summaries."""
    real = freya.api

    def api(method, path, body=None, **params):
        t0 = time.time()
        try:
            out = real(method, path, body, **params)
            if method != "GET":
                tr.event("freya_call", method=method, path=path, ok=True, duration_ms=int((time.time() - t0) * 1000))
            return out
        except Exception as e:
            tr.event("freya_call", method=method, path=path, ok=False, error=repr(e)[:200], duration_ms=int((time.time() - t0) * 1000))
            raise
    freya.api = api


def file_sha(path):
    import hashlib
    try:
        return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()[:16]
    except Exception:
        return ""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--briefs", help="comma-separated brief files, in reading order; required unless --policy is given")
    ap.add_argument("--openapi", required=True)
    ap.add_argument("--slot", required=True, help="workflow slot and output name, e.g. hidden-1")
    ap.add_argument("--cases", help="case file for the self-test simulation (public-test-set.json format); omit to skip the simulation")
    ap.add_argument("--brief", help="brief letter filter for --cases (A or B)")
    ap.add_argument("--policy", help="skip extraction and use this policy JSON (fixture path, '+'-joined overlays allowed)")
    ap.add_argument("--deadline", type=int, default=1800, help="seconds for the whole build")
    ap.add_argument("--no-smoke", action="store_true")
    a = ap.parse_args()
    if not a.briefs and not a.policy:
        ap.error("--briefs is required unless --policy is given")

    t_start = time.monotonic()
    left = lambda: a.deadline - (time.monotonic() - t_start)
    briefs = a.briefs.split(",") if a.briefs else []
    out = ROOT / "out"
    out.mkdir(exist_ok=True)
    tr = Trace(ROOT / "traces" / f"{a.slot}.jsonl")
    dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    tr.event("run_start", slot=a.slot, brief_paths=briefs, openapi_path=a.openapi, commit=git_head(ROOT), tree_dirty=bool(dirty),
             argv=sys.argv, input_sha256_16={p: file_sha(p) for p in briefs + [a.openapi]},
             code_sha256_16={f: file_sha(ROOT / f) for f in ("build.py", "extract.py", "compile.py", "policy.py", "bankcal.py", "freya.py")},
             deadline_s=a.deadline, builder_model=X.MODEL, agent_model=freya.AGENT_LLM)
    instrument_freya(tr)
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

        # 4. pre-bank chat self-test (identity start + third party); never a simulation, never fatal ------------
        if not a.no_smoke:
            smoke(ids, ir, tr)
            selftest(ids, ir, tr, a.slot)

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
        if ids is not None:
            print("published workflow exists; the failing step was after it:", str(e)[:160], file=sys.stderr)
        if "API key" in str(e) or "Not logged in" in str(e):
            print("HINT: the extractor's Claude credentials are dead. Check with:  claude -p \"say OK\"  "
                  "— if that fails, re-login (claude /login) or export a real ANTHROPIC_API_KEY (sk-ant-…) into .env, then re-run.", file=sys.stderr)
        raise
    finally:
        tr.close()


def selftest(ids, ir: P.PolicyIR, tr: Trace, slot: str):
    """scripts/chat_selftest.py (chat route only, never a simulation): the first security question matches the IR, and a
    third party hears nothing about the account and is asked when the holder can be reached. `pass` is the strict first
    attempt; one retry tells flaky (the Freya extractor is stochastic) from broken. Informational: the checkpoint is
    already exported and the published workflow does not depend on it."""
    res = ROOT / "results" / f"{slot}.selftest.json"
    cmd = [sys.executable, str(ROOT / "scripts" / "chat_selftest.py"), "--workflow-id", ids["workflow_id"],
           "--policy", str(ROOT / "out" / f"{slot}.policy.json"), "--retry-on-fail", "1", "--deadline", "300", "--out", str(res)]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=360)
        out = json.load(open(res)) if res.exists() else {"ok": None, "stdout": p.stdout[-1500:], "stderr": p.stderr[-800:]}
        tr.event("selftest", ok=out.get("ok"), result=out, exit_code=p.returncode, duration_ms=int((time.time() - t0) * 1000))
    except Exception as e:
        tr.event("selftest", ok=None, error=repr(e)[:300], duration_ms=int((time.time() - t0) * 1000))


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
