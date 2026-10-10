# Fresh-clone rehearsal — checkpoint 23a4582

**Both requested builds succeeded from the clone without source edits or copying missing source files.** Checkpoint: `23a4582129f9bbd6fbeb00ec81dbace58af8a021`. Clone: `/tmp/freya-fresh-clone-dntc3a08/repo`. No simulations were requested or run.

| Step | Exit | External elapsed |
|---|---:|---:|
| Local `git clone --no-hardlinks` | 0 | 0.168 s |
| `uv venv .venv` | 0 | 0.066 s |
| Install pinned requirements | 0 | 2.555 s |
| `claude -p "say OK"` preflight | 0 | 2.510 s |
| Offline pytest | 0 | 1.028 s; **20 passed** |
| Fixture `rehearsal-a` build | 0 | **21.823 s** |
| Full extracted `rehearsal-ab` build | 0 | **248.822 s (4 min 8.8 s)** |

Both builds published/exported workflows, passed the opening smoke check, and passed `identity_start` and `third_party_no_disclosure` on their first attempts. A+B extraction took 79.506 s and audit 139.238 s; neither timed out. The fixture build made no builder extraction-model calls, but its default chat tests still use Freya's models.

## Missing files

- **Missing committed files: none. Missing required runtime/setup source files: none.** `build.py`, `extract.py`, `compile.py`, `policy.py`, `bankcal.py`, `freya.py`, `trace.py`, `scripts/chat_selftest.py`, pinned requirements, both briefs, the policy fixture and OpenAPI were all in the checkpoint. No original-worktree absolute path was needed; source, inputs, and fixtures remain byte-for-byte unchanged in the clone.
- **README-linked file absent:** `freya-agent-builder-implementation-plan.md` is ignored and not in the clone. The README's “How it works” link is therefore unavailable to the reviewer. It did not block execution.
- **Intentionally local files absent initially:** `.env` (copied as requested, mode 0600), `.freya-agents.json` (not copied; recreated by these builds), `.personas.json` (not needed because no simulations). `.venv/` was recreated, not copied. Caches were not required.
- Other ignored local workspace files absent and unused: `.sbx/README.md`, `.sbx/kit/spec.yaml`, `.sbx/project.json`. [File audit](file-audit.json) lists these explicitly. Generated results created in the original workspace after the checkpoint are not dependencies of this rehearsal.

## README omissions / corrections

1. **The shell Claude CLI is an undeclared setup dependency.** Requirements install `claude-agent-sdk` and its bundled CLI, but do not put a `claude` executable on the virtualenv's PATH. The README's bare `claude -p` worked because this host already has `/usr/local/share/npm-global/bin/claude`. With PATH restricted to the new venv and system binaries, `command -v claude` finds nothing. Document installing Claude Code separately, or provide a preflight that invokes the SDK's bundled executable. Claude login/API-key requirements are already mentioned; the missing step is making the actual preflight command available.
2. **Explain reused slot artifacts.** The checkpoint already tracks `out/rehearsal-a.candidate.json`, `out/rehearsal-a.workflow.json`, `results/rehearsal-a.selftest.json`, and `traces/rehearsal-a.jsonl`. The trace is append-only: this rehearsal's A run is appended after a prior run. Overwriting the other tracked artifacts makes the following A+B run log `tree_dirty=true`, even though all source/input files are unchanged. Document unique run/slot names or explicit trace archival before reuse. The saved `*.current-run.jsonl` files below isolate the new runs without deleting the original evidence. A started with `tree_dirty=false`; A+B's dirty state is accounted for by those four generated files.
3. **Update the “no LLM, ~10 s” fixture description.** It skips the extraction model, but default smoke and two pre-bank chat checks use Freya's models. It took 21.8 seconds here. The README does not describe the added default pre-bank self-test; `--no-smoke` skips both smoke and self-test, although this rehearsal left both enabled.
4. **Make the planning-document link available or remove it.** The ignored plan is not required at runtime, but its README link is broken from a fresh clone.
5. **Qualify the output list by build mode.** `out/<slot>.audit.json` comes from extraction/audit; the fixture-only run does not create a fresh audit file.

No undocumented package installation, source patch, hardcoded-path substitution, state-file copy, or extra runtime directory creation was needed. `uv` is already identified as a prerequisite with a Python-venv fallback in the README; that fallback was not exercised here.

## Exact commands exercised

From the repository root, create the checkpoint and clone it, then from the clone:

```bash
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
# Copy the existing .env into this directory, as requested; do not commit it.
source .env
claude -p "say OK"
.venv/bin/python -m pytest -q
.venv/bin/python -u build.py --policy tests/fixtures/brief_a.policy.json --openapi tools/openapi.json --slot rehearsal-a
.venv/bin/python -u build.py --briefs briefs/brief-a.md,briefs/brief-b.md --openapi tools/openapi.json --slot rehearsal-ab
```

The first command includes `--openapi`, which is required and documented even though the user's shorthand omitted it. Both runs source the copied `.env`; neither uses `--cases` or skips smoke.

## Evidence and limits

[Steps and timings](steps.json), [build summaries](build-summary.json), [fixture log](policy-build.log), [full-build log](full-build.log), [offline tests](offline-tests.log), [fixture current-run trace](traces/rehearsal-a.current-run.jsonl), [A+B current-run trace](traces/rehearsal-ab.current-run.jsonl). Full original traces, policies, candidates, exports and self-test results are retained alongside them. Secret values and the `.env` file are not part of this evidence.

This was a fresh repository and virtualenv **on the same host/user**, using CPython 3.14.4, existing `uv`, global Claude Code, existing Claude authentication, and package caches. It does not prove a bare machine has those prerequisites. The clone was local, not a network clone; the dependency-install time benefits from the host cache. Existing Claude user-level configuration/authentication was not cleared. A+B's trace records the exact checkpoint and source hashes, and the post-run source diff is empty.

Creating the checkpoint initially failed because this shell lacked `user.name`; the commit succeeded with per-command name/email matching the repository's previous author. No global Git configuration was changed. Already-staged evidence was included in the checkpoint; unrelated live output changes were not needed by the builds. README/source fixes are recommendations here, not changes applied to the tested checkpoint.
