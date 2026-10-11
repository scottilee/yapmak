# Sunday operator runbook — 11 October 2026 (UTC)

Based on `eb329ea`, `scripts/preflight.sh` and `scripts/submit.sh`. Briefs open **17:00**; submission closes **20:00**. Keep builds sequential. Never write hidden-brief rules, names or values into code or prompts, hand-edit extracted policy or exports, or use `--fast` for the submission. A builder rerun is allowed; general bug fixes must be independent of hidden content and separately committed.

**16:30 — preflight in the intended submission checkout**

```bash
cd /Users/sl/sbx/hackathon
git status --short
git rev-parse HEAD
bash scripts/preflight.sh
```

Resolve every FAIL; review WARNs, Git identity/remote and `submission/config.json`. Preserve unrelated work; ensure the intended code is committed. Preflight checks credentials, Claude, pytest, platform health and registry, and creates a practice mock session. It does not run a full extracted build. If dependencies need rebuilding: `uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt`. Keep `.env` private. Missing registry means new workflows; do not delete an existing registry to resolve an error. Leave enough time to rehearse any code change before 17:00.

**17:00 — save the supplied inputs unchanged, then build**

Each of `hidden/hidden-1/` and `hidden/hidden-2/` must contain exactly the supplied single Markdown brief and its API file (JSON/YAML). Do not put README, expected values or other files there: the script treats every non-API file as brief content.

```bash
bash scripts/submit.sh hidden/hidden-1 hidden/hidden-2
```

This commits inputs, extracts/builds sequentially (30-minute deadline each), scans and commits fresh artifacts, then writes and commits `submission/form.json`. It does not push. Watch each final JSON for `elapsed_s`, `degraded`, workflow/agent IDs and export paths, and the final `build 1: ok   build 2: ok`. Logs: `traces/hidden-N.build.log`; events: `traces/hidden-N.jsonl`. Inspect diagnostics without opening giant model-response lines:

```bash
.venv/bin/python - <<'PYCODE'
import json
for slot in ('hidden-1', 'hidden-2'):
    print(slot)
    for line in open(f'traces/{slot}.jsonl'):
        e = json.loads(line)
        if e.get('event') in ('policy_compiled', 'api_mapping_incomplete',
                              'offline_invariants', 'platform_retry', 'run_end'):
            print(json.dumps(e, ensure_ascii=False))
PYCODE
```

Check `policy_compiled.api_mapping_notes`, `unknown_special_cases`, `defaulted_without_source`, `unresolved` and `audit_unresolved`; `offline_invariants.failing`; any `api_mapping_incomplete` or `platform_retry`; and `run_end.success`, `checks_passed`, `degraded`. Empty degraded does **not** certify the audit or invariants. Missing retry/incomplete events means none emitted, not an explicit clean check. Failed `run_end` may omit degraded entirely. Compiler-stage mapping notes are not fully surfaced in the trace.

**Failure or degradation**

Build 1 failure does not stop build 2. Read the failing build log and trace; preserve their evidence. A form or old export can exist despite failure: require both successful fresh traces and exports from this invocation. For transient platform/credential issues, resolve the cause and rerun the same `submit.sh` command above (no `--branch` on the rerun). This rebuilds both agents and refreshes commits/form; allow up to another hour. Do not launch concurrent builds. If rerunning only one builder for diagnosis, copy that exact command from its build log, then rerun submit to regenerate the complete submission. Never substitute a hand-edited policy. For pending creation, reconcile via rerun; verify remote state before any registry intervention. If artifact scanning fails, identify the flagged file without exposing credentials; do not bypass the scan.

**Before submitting**

Verify both new exports, both traces and `submission/form.json`; use the form’s actual `run_command` (two commands joined by `&&`, each with `--deadline 1800`), not the schematic documentation example. `form.commit` is the artifacts commit, followed by the form commit. Review that commit and scan result. Push the reviewed branch to the intended GitHub remote and submit through the organizer channel before 20:00; the script only prints the push command unless `--push` is supplied. No push is performed by this audit.
