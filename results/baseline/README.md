# Baseline and runtime verification

## Current status

The initial request was blocked at Freya validation. After platform access was
enabled, the retry at 2026-10-10T11:59:48Z validated, created and exported the sample
workflow successfully. See `20261010T115948Z/measurement.json` for IDs and timings.

The official harness then failed during bank session creation, before starting a
simulation. A direct diagnostic confirmed HTTP 403: approval is still required for
`freya-bank-mock.freyavoice.workers.dev:443`. The harness masks this plain-text
access error with a JSONDecodeError. This is not a policy or agent-score failure.

The Claude Agent SDK 0.2.165 is installed in `.venv`, and its sample-builder options
are compatible. Claude authentication still reports loggedIn=false. The restored
project skill is present and unchanged.

## Repeatable sample-agent measurement

From the kit root:

```bash
source .env
.venv/bin/python scripts/measure_baseline.py --brief A
.venv/bin/python scripts/measure_baseline.py --brief B
```

Run sequentially. Each invocation writes a timestamped directory containing phase
timings, exported workflow, official scores, simulation log, and full call records
with known credentials redacted. A failed setup still leaves measurement.json.
The sample agent is intentionally incomplete; its score is not the builder score.

Then measure the supplied builder separately, without changing its skill:

```bash
source .env
.venv/bin/python -u examples/agent_builder.py briefs/brief-a.md
.venv/bin/python -u examples/agent_builder.py briefs/brief-a.md briefs/brief-b.md
```

Capture full elapsed time and SDK traces, export each resulting workflow, and run
independent scoring of the generated agent. Preserve the original baseline before
any skill or builder changes. Do not run either builder while another simulation
is active. The example's SDK turn limit is not a 30-minute wall-clock deadline.

## Critical runtime acceptance matrix

All live checks below are **pending**, not verified by this review. Use an isolated,
reused runtime-check workflow slot and synthetic practice sessions. Functional
checks must stay within the event's rules; no load tests or additional services.

| Contract | Minimal experiment | Required evidence |
|---|---|---|
| State persistence | Write scalar/list/object state in code, read in a later node and pre-hook | Observed types/values, stored workflow, call ID |
| Result envelopes | Verify two identity answers and read mapped plus flattened result fields | Correct data.* paths and boolean representation |
| Guarded writes | Route invalid/unconfirmed proposals away from the write node, then confirm a valid one | Ledger has zero writes before valid consent and exactly one afterward |
| Revision-bound consent | Confirm a proposal, correct its amount/date before recording | Old consent invalidated; revised read-back required |
| Simulated calendar | Use now distinct from wall clock; ask for next Friday and next week | Exact date follows call date; vague phrase triggers clarification |
| Tool-result freshness | Successful write for one product followed by failed write for another | No reuse of prior product success; truthful acknowledgement |
| Retry allowance | Exercise supplied service-error case with maxRetries=0 | Only policy-authorized application attempts; inspect ledger |
| Transfer/no notes | Dispute first product, then request transfer | No notes anywhere in ledger, including before transfer |
| Terminal order | Exercise normal and failure exits | One close_call, last bank action, goodbye before close |
| Publication/export | Update same slot, publish, export, simulate | Simulation version matches publication; exported content matches intended candidate |

Chat is suitable for fast feedback but may skip initial code nodes according to the
kit. Confirm consequential findings with a simulation. Hook exceptions are not a
supported cancellation mechanism; use explicit guard routing. Unknown transport
outcomes are not proof a write failed.
