# Submission — Build the Builder (Freya Voice hackathon)

Hidden briefs open **Sunday 11 October 2026, 17:00 UTC**; submission closes **20:00 UTC**. One API key, one workspace, one
simulation at a time: run the two builds **sequentially**. Budget per build: 30 minutes (measured: ~5 min without a self-test
simulation, ~7 min with one).

## Run command (one per hidden brief, exactly as submitted)

```bash
cd <repo> && source .env && \
python3 build.py --briefs <hidden-1 brief file(s), comma-separated in reading order> --openapi <hidden-1 tool API file> --slot hidden-1

python3 build.py --briefs <hidden-2 brief file(s), comma-separated in reading order> --openapi <hidden-2 tool API file> --slot hidden-2
```

`python3` is the project virtualenv's interpreter (`.venv/bin/python`); setup is in README.md ("Our builder"). Requirements:
`FREYA_API_KEY`, `FREYA_BANK_TEAM_KEY` in `.env`, and a Claude login or `ANTHROPIC_API_KEY` for the extractor
(`claude-agent-sdk`). If the run is launched from inside a Claude Code session, prefix with
`env -u CLAUDECODE -u CLAUDE_CODE_CHILD_SESSION`.

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

1. Before 17:00: `git status` clean, `.venv` works from a fresh clone (`uv venv .venv && uv pip install --python .venv/bin/python claude-agent-sdk pytest`), `.env` filled, `.venv/bin/python -m pytest tests/ -q` green, no simulation running in the workspace.
2. Save the hidden brief files and tool API files into the repo (e.g. `hidden/hidden-1/`), **commit them unchanged**.
3. Run build 1, then build 2 (commands above). Do not edit the exported workflows. Do not add any value from a hidden brief to code or prompts; a parser crash fix is the only permitted code change — commit it separately with a message that says what crashed.
4. `git add out/hidden-1.workflow.json out/hidden-2.workflow.json traces/hidden-1.jsonl traces/hidden-2.jsonl out/hidden-*.policy.json out/hidden-*.audit.json && git commit -m "Hidden brief builds" && git push`.
5. Fill `submission/form.json` with the commit hash (`git rev-parse HEAD`) and submit it through the event form (confirm the channel: form vs. the address in the kit email).

## Submission form (template in `submission/form.json`)

```json
{
  "team": "<team name>",
  "repo": "<GitHub URL>",
  "commit": "<git rev-parse HEAD after step 4>",
  "run_command": "source .env && python3 build.py --briefs <brief files> --openapi <tool api file> --slot hidden-1   (same for hidden-2)",
  "workflows": {"hidden-1": "out/hidden-1.workflow.json", "hidden-2": "out/hidden-2.workflow.json"},
  "traces":    {"hidden-1": "traces/hidden-1.jsonl",       "hidden-2": "traces/hidden-2.jsonl"}
}
```

## Rules we rely on (README of the kit, hackathon page 10 Oct)

- Phone agent model fixed at `freya.AGENT_LLM`; the builder may use any model (we use `claude-opus-5-5` through the Claude Agent SDK).
- The agent calls only the seven bank tools, all as engine-fired `api_request` nodes; code nodes and hooks are allowed.
- `freya.save_workflow` reuses one workflow per slot (`.freya-agents.json`, not committed).
- Organizers re-run the builder at the submitted commit and compare with the trace: the build shape is fixed (no wall-clock-dependent iteration).
