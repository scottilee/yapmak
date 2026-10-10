# v22 fresh-clone rehearsal

**All requested stages passed.** Cloned `/Users/sl/sbx/hackathon` into `/tmp/v22-clone` at clean commit `df51f26c0c9fa364a02bd83026a4e6bb22e5952f`. Ran 10 October 2026, 22:08–22:13 UTC. Total measured sequence: **299.0 seconds (4m 59s)**. No pipeline code was edited and no missing repository files required recovery.

| Stage | Exit | Wall time | Result |
|---|---:|---:|---|
| Local clone | 0 | 0.46 s | Clean committed source |
| `uv venv` + dependency installation | 0 | 0.20 s | Python 3.14.4; 35 packages installed from the available cache |
| `scripts/preflight.sh --with-build` | 0 | 35.49 s | 88 tests passed; Claude/API/bank health passed; fixture build passed; 2 warnings, 0 failures |
| Full A+B `build.py` | 0 | 207.44 s | Extraction + audit, no repair; published and exported; chat self-tests passed |
| `scripts/submit.sh hidden/dry-1 hidden/dry-2 --fast` | 0 | 55.46 s | Both builds passed sequentially, artifacts scanned, local artifact/form commits created |

Build-internal times: rehearsal-a **25.3 s**, rehearsal-ab **207.3 s**, hidden-1 **24.7 s**, hidden-2 **30.6 s**. Full A+B extraction/audit reported **$1.1158324**; this excludes the separate Claude preflight invocation.

## Findings and setup gaps

1. **The supplied command sequence needs an explicit environment load before the standalone full build.** Neither Freya key was set in the parent environment. Copying `.env` only creates the file; preflight sources it inside its own process. I therefore added `set -a; source .env; set +a` before the full A+B command. The README already says to source `.env`, but the requested sequence omitted that step; using `set -a` also supports assignments without `export`. This was the only operational addition to the requested sequence, apart from timing/log capture and ensuring `.env` mode `0600`.
2. **Fast mode retains stale audit artifacts.** Both new `out/hidden-*.policy.json` files describe Freya Bank because `--fast` deliberately uses the practice fixture. Yet `out/hidden-1.audit.json` remains the old Juniper Cooperative Bank audit and `out/hidden-2.audit.json` remains the old Marlow Trade Bank audit, byte-for-byte unchanged. `submit.sh` includes these existing files in its artifact scan/list; they remain in the submitted tree even though no extraction audit occurred in these builds. This does not invalidate the mechanics rehearsal, but is misleading provenance. Recommended fix: archive/remove an old slot audit when building with `--policy`, and select submission artifacts from the current run's manifest rather than file existence. No fix was applied during this reproduction.
3. **Preflight warnings were expected and handled:** Git user name/email were absent, so submit used its team-name / `submission@localhost` fallback; `.freya-agents.json` was absent, so four new workflows were created in the clone's local registry. No registry was copied from the original workspace.
4. **No required tracked file was missing.** Both submission scripts, submission configuration, dry-run input packs, API files, fixtures and compiler/runtime modules were in the clone. The intentionally ignored `.env` was copied as requested. The registry was regenerated.
5. **Scope of “from scratch”:** this was a fresh checkout and virtualenv on the existing host. `uv`, `claude`, GNU `timeout`, and working Claude credentials were already available. Dependency downloads benefited from the host cache. README documents the CLI/login requirement; `preflight.sh` also requires `timeout`, which is not named in README setup and is not standard on macOS. This host had `/usr/bin/timeout`, so no failure occurred.

`--fast` checks submission mechanics with the practice policy/API; it **does not** test extraction or correctness against the two mutated dry-run briefs. The separate A+B run did use fresh extraction. No simulations or submission delivery were performed.

## Trace and output checks

- All four builds ended successfully, each with a successful chat self-test and zero suspect export read-back differences.
- Each trace has **15 HTTP starts and 15 matching completions**; no unmatched request IDs.
- Every recorded source hash matches the source at the cloned commit. Later traces mark the tree dirty because earlier rehearsal outputs changed tracked files, not because builder source was edited.
- The two input directories remained byte-for-byte unchanged.
- Form commit `d14b78fdd2f7252aafa440ef54ca38354ebe7660` contains exactly the workflow and trace bytes named in the generated form. The following form commit is `03a07851901fdb69b2318426c4401a3bcfdd8540`.
- These two commits exist **only in the disposable clone**. Nothing was pushed, and the original repository HEAD remains `df51f26c0c9fa364a02bd83026a4e6bb22e5952f`. The form is rehearsal evidence, not an actual submission.

## Commands executed

```bash
git clone /Users/sl/sbx/hackathon /tmp/v22-clone
cd /tmp/v22-clone
uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt
cp /Users/sl/sbx/hackathon/.env .env
chmod 600 .env
scripts/preflight.sh --with-build
set -a; source .env; set +a
.venv/bin/python -u build.py --briefs briefs/brief-a.md,briefs/brief-b.md --openapi tools/openapi.json --slot rehearsal-ab
scripts/submit.sh hidden/dry-1 hidden/dry-2 --fast
```

The credential copy used Python `shutil.copy2` with the same source/destination, followed by mode `0600`. Timed commands ran in subprocesses, so the full-build subprocess explicitly sourced `.env`. `submit.sh` sources it itself. The exact orchestrator is [rehearsal-run.py](rehearsal-run.py); it refuses an existing clone via ordinary `git clone` behavior.

Evidence: [timings.json](timings.json), [preflight.log](preflight.log), [full-ab.log](full-ab.log), [submit-fast.log](submit-fast.log), [build-summary.json](build-summary.json), [submission-checks.json](submission-checks.json). Exported workflows, policies, audits, traces, chat evidence and form are preserved under [artifacts/](artifacts/). The disposable clone remains at `/tmp/v22-clone` for inspection; it intentionally retains uncommitted rehearsal outputs and archived traces outside the submission script's artifact list.
