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
import re
import runcontrol

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import freya  # noqa: E402
import compile as C  # noqa: E402
import extract as X  # noqa: E402
import policy as P  # noqa: E402
from trace import Trace, git_head  # noqa: E402

SIM_MIN_BUDGET_S = 13 * 60
FINAL_EXPORT_RESERVE_S = 4 * 60
CHAT_CHECK_BUDGET_S = 360
CHAT_SCENARIO_BUDGET_S = 300


from retrying import retry


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

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", a.slot):
        ap.error("--slot must be a simple name containing letters, digits, '_' or '-'")
    if a.deadline <= 0:
        ap.error("--deadline must be positive")
    with runcontrol.deadline(a.deadline):
        build(a)


def build(a):
    t_start = time.monotonic()
    left = runcontrol.remaining

    def persist(fn, what):
        """Publish-path calls keep retrying through a platform outage for as long as the build budget allows (30 s apart),
        keeping the final-export reserve; an unpublished agent scores zero, so these never give up early."""
        attempts = max(4, int((left() - FINAL_EXPORT_RESERVE_S) / 30))
        return retry(fn, what, tr, attempts=attempts, wait_s=30)
    briefs = a.briefs.split(",") if a.briefs else []
    out = ROOT / "out"
    out.mkdir(exist_ok=True)
    tr = Trace(ROOT / "traces" / f"{a.slot}.jsonl")
    export_path = out / f"{a.slot}.workflow.json"
    ids = None
    checkpoint_exported = False
    try:
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, capture_output=True, text=True, timeout=runcontrol.timeout(5)).stdout.strip()
        tr.event("run_start", slot=a.slot, brief_paths=briefs, openapi_path=a.openapi, commit=git_head(ROOT), tree_dirty=bool(dirty),
                 argv=sys.argv, input_sha256_16={p: file_sha(p) for p in briefs + [a.openapi] + (a.policy.split("+") if a.policy else [])},
                 code_sha256_16={f: file_sha(ROOT / f) for f in ("build.py", "extract.py", "compile.py", "compiler_nodes.py", "compiler_openapi.py", "compiler_checks.py", "workflow_runtime.py", "policy.py", "bankcal.py", "freya.py", "trace.py", "runcontrol.py", "artifact_security.py", "retrying.py", "scripts/chatlib.py", "scripts/chat_selftest.py")},
                 deadline_s=a.deadline, builder_model=X.MODEL, agent_model=freya.AGENT_LLM)
        # 1. policy -----------------------------------------------------------------------------
        tools = C.parse_openapi(a.openapi)
        if a.policy:
            ir = P.PolicyIR.load_merged(a.policy.split("+"))
            tr.event("policy_loaded", path=a.policy)
        else:
            ir, audit = X.extract(briefs, a.openapi, a.slot, tr)
        problems = P.validate(ir, C.tool_enums(tools, ir.api_fields))
        if problems:
            raise SystemExit("policy invalid: " + "; ".join(problems))
        X.check_artifact(ir.to_json())
        (out / f"{a.slot}.policy.json").write_text(ir.to_json())

        # 2. compile ----------------------------------------------------------------------------
        wf = C.compile_workflow(ir, tools)
        errs = C.static_check(wf, tools)
        tr.event("workflow_compiled", nodes=len(wf["nodes"]), size_kb=len(json.dumps(wf)) // 1024, static_errors=errs, compiler_notes=list(C.COMPILE_NOTES))
        if errs:
            raise SystemExit("static check failed: " + "; ".join(errs))
        (out / f"{a.slot}.candidate.json").write_text(json.dumps(wf, indent=1))
        # offline behaviour check before publishing: the IR-parameterized scenarios against a mock bank (seconds). Informational —
        # a failing scenario is recorded for the operator, never blocks the publish (an unpublished agent scores zero).
        try:
            sys.path.insert(0, str(ROOT / "tests"))
            import invariants as INV
            t0 = time.time()
            fails = {}
            for sc in INV.SCENARIOS:
                for now in INV.NOWS[:2]:
                    problems, _bank = INV.run_scenario(ir, wf, sc, tools, now)
                    if problems and not problems[0].startswith("n/a"):
                        fails[f"{sc}@{now[:10]}"] = problems[:3]
            tr.event("offline_invariants", scenarios=len(INV.SCENARIOS) * 2, failing=fails, duration_ms=int((time.time() - t0) * 1000))
        except Exception as e:  # noqa: BLE001 - never fatal
            tr.event("offline_invariants", error=repr(e)[:300])

        # 3. publish + checkpoint ---------------------------------------------------------------
        persist(lambda: freya.validate_workflow(a.slot, wf), "validate")
        ids = persist(lambda: freya.save_workflow(a.slot, wf), "publish")
        if "version" not in ids:
            ids["version"] = persist(lambda: freya.update_workflow(ids["workflow_id"], wf), "publish_first")   # first create: pin the agent model and publish
        tr.event("workflow_published", steps=len(wf["nodes"]), tools=sorted({pa["function"]["name"] for n in wf["nodes"].values() for pa in n.get("pre_actions", []) if pa["function"].get("handler") == "__function__:api_call"}), slot=a.slot, workflow_id=ids["workflow_id"], agent_id=ids["agent_id"], version=ids.get("version"))
        persist(lambda: freya.export_workflow(ids["workflow_id"], str(export_path)), "checkpoint_export")
        checkpoint_exported = True
        tr.event("checkpoint_export", path=str(export_path.relative_to(ROOT)), version=ids.get("version"))

        # read-back: the exported file is what we submit; log what the platform changed or stripped (plan §5)
        try:
            stored = json.loads(export_path.read_text()).get("workflow") or {}
            from compiler_checks import workflow_diff
            diffs = workflow_diff(wf, stored)
            stripped = [d for d in diffs if "missing in stored" in d or (" -> " in d and "added by platform" not in d)]
            tr.event("workflow_readback", differences=len(diffs), platform_additions=len(diffs) - len(stripped),
                     suspect=stripped[:8], suspect_count=len(stripped))
        except BaseException as e:      # noqa: BLE001 - checkpoint exists; a diff hiccup must not kill the build
            tr.event("workflow_readback", error=repr(e)[:200])

        # 4. pre-bank chat self-test (identity start + third party); never a simulation, never fatal ------------
        checks = {}
        if not a.no_smoke:
            checks["selftest"] = selftest(ids, ir, tr, a.slot)

        # 5. one simulation (only with a case file and enough time) ------------------------------
        if a.cases and left() > SIM_MIN_BUDGET_S:
            res = ROOT / "results" / f"{a.slot}.{tr.run_id}.simulation.json"
            res.parent.mkdir(parents=True, exist_ok=True)
            cmd = [sys.executable, "-u", str(ROOT / "tools" / "run_cases.py"), ids["agent_id"], "--cases", a.cases, "--out", str(res)]
            if a.brief:
                cmd += ["--brief", a.brief]
            t0 = time.time()
            budget = max(60, int(left() - FINAL_EXPORT_RESERVE_S))
            try:
                p = runcontrol.run(cmd, seconds=budget, cwd=ROOT)
                tail = (p.stdout + p.stderr)[-3000:]
                summary = json.loads(res.read_text()) if p.returncode == 0 and res.exists() else {}
                tr.event("simulation", exit_code=p.returncode, result_path=str(res.relative_to(ROOT)), result_valid=bool(summary), agent_id=ids["agent_id"], version=ids.get("version"), cases=a.cases, brief=a.brief, duration_ms=int((time.time() - t0) * 1000),
                         passed=summary.get("passed"), total=summary.get("total"), simulation_id=summary.get("simulation_id"),
                         failed=[r["id"] for r in summary.get("rows", []) if not r["pass"]], output_tail=tail)
            except subprocess.TimeoutExpired:
                tr.event("simulation", agent_id=ids["agent_id"], status="timeout_after_s", seconds=budget)
        elif a.cases:
            tr.event("simulation_skipped", reason="not enough time left", left_s=int(left()))

        # 6. final export (the published version is unchanged by the test) ----------------------------
        persist(lambda: freya.export_workflow(ids["workflow_id"], str(export_path)), "final_export")
        tr.event("export", path=str(export_path.relative_to(ROOT)), workflow_id=ids["workflow_id"], agent_id=ids["agent_id"], version=ids.get("version"))
        degraded = list(X.DEGRADED) + ([] if all(v is True for v in checks.values()) else [f"check failed: {k}" for k, v in checks.items() if v is not True])
        tr.event("run_end", success=True, checks=checks, checks_passed=all(v is True for v in checks.values()), degraded=degraded, elapsed_s=round(time.monotonic() - t_start, 1))
        print(json.dumps({"slot": a.slot, **ids, "workflow": str(export_path), "trace": str(tr.path), "degraded": degraded, "elapsed_s": round(time.monotonic() - t_start)}))
    except BaseException as e:
        tr.event("run_end", success=False, error=repr(e)[:500], elapsed_s=round(time.monotonic() - t_start, 1), exported=checkpoint_exported)
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
    res = ROOT / "results" / f"{slot}.{tr.run_id}.chat-selftest.json"
    res.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(ROOT / "scripts" / "chat_selftest.py"), "--workflow-id", ids["workflow_id"],
           "--policy", str(ROOT / "out" / f"{slot}.policy.json"), "--retry-on-fail", "1", "--deadline", str(CHAT_SCENARIO_BUDGET_S), "--out", str(res)]
    t0 = time.time()
    try:
        p = runcontrol.run(cmd, seconds=CHAT_CHECK_BUDGET_S, cwd=ROOT)
        out = json.loads(res.read_text()) if p.returncode in (0, 1) and res.exists() else {"ok": None, "stdout": p.stdout[-1500:], "stderr": p.stderr[-800:]}
        ok = bool(out.get("ok")) and p.returncode == 0
        tr.event("selftest", ok=ok, result_path=str(res.relative_to(ROOT)), result=out, exit_code=p.returncode, duration_ms=int((time.time() - t0) * 1000))
        return ok
    except Exception as e:
        tr.event("selftest", ok=None, error=repr(e)[:300], duration_ms=int((time.time() - t0) * 1000))
        return None


if __name__ == "__main__":
    main()
