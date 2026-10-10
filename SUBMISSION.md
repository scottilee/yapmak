# Submission — Build the Builder (Freya Voice hackathon)

Hidden briefs open **Sunday 11 October 2026, 17:00 UTC**; submission closes **20:00 UTC**. One API key, one workspace, one
simulation at a time: run the two builds **sequentially**. Budget per build: 30 minutes (measured: ~5 min without a self-test
simulation, ~7 min with one).

## Run command (one per hidden brief, exactly as submitted)

```bash
cd <repo> && source .env && \
.venv/bin/python build.py --briefs <hidden-1 brief file(s), comma-separated in reading order> --openapi <hidden-1 tool API file> --slot hidden-1

.venv/bin/python build.py --briefs <hidden-2 brief file(s), comma-separated in reading order> --openapi <hidden-2 tool API file> --slot hidden-2
```

Setup is in README.md ("Our builder": venv + `pip install -r requirements.txt` + `.env` + credential pre-flight).
Requirements: `FREYA_API_KEY`, `FREYA_BANK_TEAM_KEY` in `.env`, and working Claude Code credentials for the extractor —
verify with `claude -p "say OK"` **before** 17:00; if that fails the `--briefs` path cannot run at all.
`build.py` strips `CLAUDECODE`/`CLAUDE_CODE_CHILD_SESSION` itself (extract.py `_prepare_env`).

Optional self-test (practice briefs only — public expectations do not apply to hidden rules):
`--cases public-test-set.json --brief A|B`. For hidden briefs the builder runs the extraction audit, the static checklist and a
chat smoke test, and records that in the trace.

## What each run produces

| Artifact | Path |
|---|---|
| Exported phone agent (from Freya, after publication) | `out/<slot>.workflow.json` |
| Builder trace (every model call, Freya write, test) | `traces/<slot>.jsonl` |
| Extracted policy + audit (evidence, not submitted) | `out/<slot>.policy.json`, `out/<slot>.audit.json` |

## Sunday checklist

1. Before 17:00: `git status` clean (HEAD == working tree — re-run the clone rehearsal after every compiler change),
   fresh clone installs with `uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt` (or `python3 -m venv` + pip where python3-venv exists), `.env` filled, `claude -p "say OK"` green,
   `.venv/bin/python -m pytest tests/ -q` green,
   `.venv/bin/python build.py --policy tests/fixtures/brief_a.policy.json --openapi tools/openapi.json --slot rehearsal-a` green (~10 s),
   no simulation running in the workspace.
2. Save the hidden brief files and tool API files into the repo (e.g. `hidden/hidden-1/`), **commit them unchanged**.
3. Run build 1, then build 2 (commands above). Do not edit the exported workflows. Do not add any value from a hidden brief to code or prompts; a parser crash fix is the only permitted code change — commit it separately with a message that says what crashed.
4. `git add out/hidden-1.workflow.json out/hidden-2.workflow.json traces/hidden-1.jsonl traces/hidden-2.jsonl out/hidden-*.policy.json out/hidden-*.audit.json && git commit -m "Hidden brief builds" && git push`.
5. Fill `submission/form.json` with the commit hash (`git rev-parse HEAD`) and submit it through the event form (confirm the channel: form vs. the address in the kit email).
   Note for the reviewer: `run_start` in each trace records the HEAD *at run time* (step 3), which is necessarily one commit behind the
   submitted commit (step 4 adds only generated artifacts — `out/hidden-*`, `traces/hidden-*` — and touches no pipeline file).

## Submission form (template in `submission/form.json`)

```json
{
  "team": "<team name>",
  "repo": "<GitHub URL>",
  "commit": "<git rev-parse HEAD after step 4>",
  "run_command": "source .env && .venv/bin/python build.py --briefs <brief files> --openapi <tool api file> --slot hidden-1   (same for hidden-2)",
  "workflows": {"hidden-1": "out/hidden-1.workflow.json", "hidden-2": "out/hidden-2.workflow.json"},
  "traces":    {"hidden-1": "traces/hidden-1.jsonl",       "hidden-2": "traces/hidden-2.jsonl"}
}
```

## Rules we rely on (README of the kit, hackathon page 10 Oct)

- Phone agent model fixed at `freya.AGENT_LLM`; the builder may use any model (we use `claude-opus-5-5` through the Claude Agent SDK).
- The agent calls only the seven bank tools, all as engine-fired `api_request` nodes; code nodes and hooks are allowed.
- `freya.save_workflow` reuses one workflow per slot (`.freya-agents.json`, not committed).
- Organizers re-run the builder at the submitted commit and compare with the trace: the build shape is fixed (no wall-clock-dependent iteration).
