# Trace review re-run — `traces/review-ab.jsonl` (full A+B build with extraction, 15:20–15:24 UTC, 224.5 s)

Produced by the instrumented `build.py` (HEAD `d5b14c4` + uncommitted compiler changes; `tree_dirty: true` is recorded in `run_start`).

| Reviewer question | Answer from the trace |
|---|---|
| Does the trace account for every model call? | Two `model_call` events, one per Agent-SDK session: `policy_extraction` (claude-opus-5-5, 6 turns, 75 s, $0.50) and `policy_audit` (7 turns, 130 s, $0.77), each with model and purpose as the kit asks. The SDK does not expose the individual requests inside a session; the session's turn count, duration and cost are recorded. |
| Every Freya write? | Five `freya_call` events in order: dry-run `POST /api/v2/workflow`, create `POST /api/v2/workflow`, `PUT /api/v2/workflow/<id>` (model pin + publish path), `POST /api/v2/chat/message`, `POST /api/v2/chat/end`; plus `workflow_published` (ids, version) and two exports. The pre-bank self-test's own chat turns run in a subprocess and are recorded inside the `selftest` event (both scenarios passed on the first attempt) rather than as per-call events. |
| Could a reviewer think the agent was hand-built or that brief values are in code? | `run_start` records argv, the commit, the dirty flag, SHA-256 prefixes of the two briefs and the API file and of the six builder files; `policy_compiled` lists the special cases, 5 unresolved items and 7 audit fixes; `workflow_compiled` records the one compiler decision (`opening_reworded`: "this call is recorded" → "we record this call", because `opening_verbatim` is false for Brief A). The policy and audit artifacts are written next to the export. |
| Build time derivable? | `run_end.elapsed_s = 224.5`; publication at 215.6 s, checkpoint export immediately after, self-test 9 s. |

Remaining gap: the recorded commit must contain the builder — commit before the Sunday runs (the dirty flag makes a stale commit visible).
The exported workflow from this run passes the offline state machine 14/14 (`tests/offline_sim.py out/gen-a.workflow.json out/review-ab.candidate.json`).
