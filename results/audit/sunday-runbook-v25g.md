# Sunday operator runbook — 11 October 2026 (UTC)

Based on `eb329ea`, `scripts/preflight.sh` and `scripts/submit.sh`. Briefs open **17:00**; submission closes **20:00**. Keep builds sequential. Never write hidden-brief rules, names or values into code or prompts, hand-edit extracted policy or exports, or use `--fast` for the submission. A builder rerun is allowed; general bug fixes must be independent of hidden content and separately committed.

**16:00 — platform timeline (already scheduled)**

The detached `results/audit/platform_watch.py` logs every minute from 16:00 to 20:05 UTC in `results/platform-watch-20261011.jsonl`. An initial precheck returned HTTP 200 for both services. It probes Freya workspaces and creates a bank practice session (no simulation); records UTC time, status, latency and errors; and never logs response bodies or credentials. The process requires this machine/sandbox to remain running. Check it at 16:30 and again just before building:

```bash
ps -p "$(cat results/platform-watch-20261011.pid)" -o pid,etime,command
tail -n 3 results/platform-watch-20261011.jsonl
```

After 16:00, require a recent `sample` (not just `watch_scheduled`) with both checks healthy. A stale log is unknown health. To restart if the process is dead: `set -a; source .env; set +a; nohup .venv/bin/python -u results/audit/platform_watch.py >> results/platform-watch-20261011.stderr.log 2>&1 < /dev/null &`. A file lock prevents duplicate loops. Compare sample timestamps with build `platform_retry` timestamps. See [unsupported-rule inventory](unsupported-rules-inventory.md) for known unresolved families; familiar findings still need review.

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
from pathlib import Path
fields = {
    'policy_compiled': ('api_mapping_notes', 'unresolved', 'audit_unresolved',
                        'unknown_special_cases', 'defaulted_without_source'),
    'workflow_compiled': ('api_mapping_notes', 'unresolved', 'unknown_special_cases',
                          'defaulted_without_source', 'compiler_notes', 'static_errors'),
    'api_mapping_incomplete': ('unmapped',),
    'offline_invariants': ('failing', 'error'),
    'platform_retry': ('step', 'attempt', 'error'),
    'run_end': ('success', 'checks_passed', 'degraded', 'error'),
}
for slot in ('hidden-1', 'hidden-2'):
    path = Path(f'traces/{slot}.jsonl')
    print(f'\n{path}')
    if not path.exists():
        print('MISSING TRACE'); continue
    seen = set()
    for number, line in enumerate(path.read_text().splitlines(), 1):
        try:
            e = json.loads(line)
        except ValueError:
            print(f'line {number}: incomplete/invalid JSON'); continue
        event = e.get('event')
        if event in fields:
            seen.add(event)
            print(number, event, json.dumps(
                {k: e.get(k, '<not emitted>') for k in fields[event]},
                ensure_ascii=False))
    print('Events not emitted:', ', '.join(sorted(set(fields) - seen)) or 'none')
PYCODE
```

Read both compilation events: `policy_compiled` carries extraction/audit diagnostics; current `workflow_compiled` also carries final compiler mapping notes and unresolved topics. The older eb329ea rehearsal lacks those extra workflow fields, shown as `<not emitted>` rather than an empty list. This snippet was executed against both real rehearsal traces: it prints mapping notes, unresolved entries, unknown special cases and `run_end.degraded`. Empty degraded does **not** certify audit or invariant coverage. Missing retry/incomplete events means none emitted, not an explicit clean check. Failed `run_end` may omit degraded. Verification evidence: `results/audit/runbook-trace-verification.txt`.

**Failure or degradation**

Build 1 failure does not stop build 2. Read the failing build log and trace; preserve their evidence. A form or old export can exist despite failure: require both successful fresh traces and exports from this invocation. For transient platform/credential issues, resolve the cause and rerun the same `submit.sh` command above (no `--branch` on the rerun). This rebuilds both agents and refreshes commits/form; allow up to another hour. Do not launch concurrent builds. If rerunning only one builder for diagnosis, copy that exact command from its build log, then rerun submit to regenerate the complete submission. Never substitute a hand-edited policy. For pending creation, reconcile via rerun; verify remote state before any registry intervention. If artifact scanning fails, identify the flagged file without exposing credentials; do not bypass the scan.

**Before submitting**

Verify both new exports, both traces and `submission/form.json`; use the form’s actual `run_command` (two commands joined by `&&`, each with `--deadline 1800`), not the schematic documentation example. `form.commit` is the artifacts commit, followed by the form commit. Review that commit and scan result. Push the reviewed branch to the intended GitHub remote and submit through the organizer channel before 20:00; the script only prints the push command unless `--push` is supplied. No push is performed by this audit.
