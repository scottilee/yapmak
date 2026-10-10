# Fresh-clone rehearsal — the Sunday simulation the repo has not had

Auditor pass, 10 Oct 07:2x UTC. Cloned **HEAD `b8bd586ef41df24002e1edba3f89e657f451ef4d`** to `/tmp/opencode/rehearsal`, followed README "Our builder" verbatim, copied `.env` from the workspace, ran the two builds. No simulation was started (neither build passed `--cases`); Freya writes were two new scratch slots `rehearsal-a`/`rehearsal-ab`.

## 1. Files missing from the clone: NONE

Every file the pipeline imports at runtime is tracked at HEAD: `build.py, compile.py, extract.py, policy.py, bankcal.py, freya.py, trace.py, tools/openapi.json, tools/run_cases.py, tools/score.py, docs/*, briefs/*, public-test-set.json, examples/*, scripts/publish_check.py, tests/* (incl. all fixtures, synthetic dirs), env.example, VERSION, SUBMISSION.md, submission/form.json, .claude/skills/…`. No hardcoded absolute paths: `grep -E "/Users/sl|/tmp/opencode|sbx/hackathon"` across all pipeline `.py` → 0 hits. `extract.py._prepare_env()` correctly strips the proxy-placeholder key and the sandbox session vars.

## 2. Setup steps the README omits or gets wrong

1. **`--policy` cannot be used alone.** `--briefs` and `--openapi` are `required=True` in build.py argparse. `build.py --policy X --slot Y` (the fast offline rehearsal everyone would try) dies in <1 s with argparse exit 2: `the following arguments are required: --briefs, --openapi`. Fix: make them optional when `--policy` is given, or document `--briefs <anything>` requirement.
2. **The venv recipe hides in the last prose line and assumes `uv`.** The "Our builder" code block starts with `.venv/bin/python` but never says how the venv comes to exist; the one-liner at the bottom (`uv venv .venv && uv pip install …`) presumes `uv` is preinstalled (it happens to be here: uv 0.9.26) and there is **no requirements.txt / pyproject**, so an organizer re-running the top-10 from a plain machine needs pip + the prose. Add a `requirements.txt` (`claude-agent-sdk`, `pytest`).
3. **`python3` vs `.venv/bin/python` inconsistency.** SUBMISSION.md's run commands say `python3 build.py …` ("python3 is the project virtualenv's interpreter" — true only if activated), while README examples use `.venv/bin/python`. The submitted `run_command` must be one exact non-interactive string; pick `.venv/bin/python`.
4. **Claude-credential pre-flight is a comment, not a step.** README line: `# plus a Claude login or ANTHROPIC_API_KEY`. With the sandbox proxy key dead, the first real symptom is a raw `ResultError: Invalid API key` traceback **1.2 s into the build**, after extraction pass 1 (the failure trace itself is handled: `run_start` + `run_end success:false` are written). README should add: `claude -p "say OK"` before Sunday, and build.py should convert that error into a one-line actionable message.
5. **Undocumented optional env vars** the code reads with defaults: `BUILDER_MODEL` (default `claude-opus-5-5`) and `EXTRACT_PASS_TIMEOUT_S` (default 420). env.example doesn't list them; on event day the model choice/timeout is a budget decision people can't see.
6. **form.json commit chicken-and-egg**: the `commit` field asks for "the commit that contains out/hidden-*.workflow.json and traces/hidden-*.jsonl" — those artifacts cannot exist in the commit used *at* run start, and `run_start` records the pre-artifact HEAD. Unavoidable (artifacts get added afterwards), but state it in SUBMISSION.md so the reviewer agent's commit-vs-trace reconciliation doesn't read the mismatch as tampering.

## 3. Elapsed times (fresh clone)

| Step | Time |
|---|---|
| `uv venv .venv` | 0.05 s |
| `uv pip install claude-agent-sdk pytest` | 5.2 s |
| copy `.env` (from workspace, not from env.example — see §2.4) | — |
| build `rehearsal-a` with `--policy` (first run creates the slot): compile 0.1 s (33 nodes, static ok), publish 6.1 s, export 6.6 s, chat smoke 9.6 s | **10.5 s** |
| build `rehearsal-a` again (slot reuse): same workflow_id/agent_id | 9.7 s |
| full build `rehearsal-ab` (`--briefs A,B --openapi …`) | **died at 1.2 s** — `Invalid API key` (extraction never ran; trace has clean run_end success:false) |
| `pytest -q` | 20 passed, 0.8 s |
| `offline_sim` on committed gen-a/gen-ab | 14/14 |
| `compile.py` fixtures → committed `out/gen-a.workflow.json` | byte-identical |

The trace's `workflow_compiled` event now carries `compiler_notes: opening_reworded` — the verbatim-sentence rewrite (synthetic-report S2) at least self-documents in the trace.

## 4. Risks this rehearsal exposed for Sunday

1. **HEAD is not the working tree.** The workspace has uncommitted modifications to `compile.py`, `extract.py`, `policy.py` (clone hash `6316a64c…` vs workspace `beb381fd…`). The clone rehearsal tested the *older* committed compiler. **Re-commit and re-run this exact rehearsal against the new HEAD before freezing.**
2. **The extraction leg cannot currently be rehearsed by anyone outside the builders' own session** — Claude credentials are dead in the general environment (works in the builders' session per their modified `results/extract/s1-extractor-diff.log`, fails in a fresh shell/machine: `~/.claude/.credentials.json` absent here, placeholder key rejected). On event day the key must exist for the *submitted* machine, and `--no-…` fallback: with creds gone the entire `--briefs` path is dead — recommend build.py accept a pre-drafted `--policy` produced *by the extractor* only (i.e., no manual policy authored after 17:00), plus the §2.4 pre-flight.
3. Slot-reuse registry (`.freya-agents.json`) is gitignored and machine-local — correct behavior (fresh clone creates new workflows, second run updates), and the printed `"version": 1` after the update is inaccurate (registry stores no version counter) — cosmetic for the trace reviewer.
4. My earlier audit slots (`out/audit-rev.policy.json`) were overwritten by builders' own extraction runs on those slot names — harmless, but keep Sunday slots (`hidden-1/2`) reserved.

Repro: `git clone <repo> /tmp/opencode/rehearsal && cd /tmp/opencode/rehearsal && uv venv .venv && uv pip install --python .venv/bin/python claude-agent-sdk pytest && source .env && time .venv/bin/python build.py --briefs briefs/brief-a.md --openapi tools/openapi.json --policy tests/fixtures/brief_a.policy.json --slot rehearsal-a`

## §5 Fix status (applied in the working tree, awaiting a builder commit)

| # | Finding | Status |
|---|---|---|
| 1 | `--policy` needed `--briefs` | **Fixed** in build.py (`--briefs` optional, ap.error when neither given). Verified in the clone: `--policy … --openapi … --slot rehearsal-a` → success, 7.3 s, slot reused. `--openapi` deliberately stays required (needed for enum validation + tool URLs). |
| 2 | uv-only setup, no requirements.txt | **Fixed**: `requirements.txt` (claude-agent-sdk==0.2.165, pytest==9.1.1 — versions proven in the clone). README now leads with the **uv path (verified)** and notes the fallback. Discovery while testing the fallback: `python3 -m venv` **fails on this machine** (no `ensurepip`/python3-venv) — documented as fallback-only rather than the primary path. |
| 3 | `python3` vs `.venv/bin/python` | **Fixed** everywhere: README, SUBMISSION.md run commands, docstring, `submission/form.json` run_command string. |
| 4 | credential pre-flight undocumented + raw traceback | **Fixed**: README + SUBMISSION checklist step 1 add `claude -p "say OK"`; build.py prints a one-line `HINT:` on "Invalid API key"/"Not logged in" before the traceback (verified firing in the clone); also prints a "published workflow exists" marker when the step after publish fails. |
| 5 | `BUILDER_MODEL` / `EXTRACT_PASS_TIMEOUT_S` undocumented | **Fixed** in env.example (commented defaults) + README tail. |
| 6 | commit chicken-and-egg | **Fixed** as a note in SUBMISSION.md step 5 (trace records pre-artifact HEAD; submitted commit adds generated files only). |

Re-verified from the clone after the patches: argparse messages ×3, `--policy` build 7.3 s, credential HINT, 20/20 pytest, form.json string. Not fixed here (not mine to touch): builders must **commit the working tree** (compile/extract/policy are still ahead of HEAD) and re-run this rehearsal against the new HEAD; Claude credentials still dead outside the builders' session.
