# Trace review

Audit target: source snapshot at HEAD `2064600d6ff207fa43df8ea27c1e643bc282bbe3`. Historical evidence is evaluated against its own recorded source, not attributed to today's instrumentation. Machine-readable counts, source-hash reconciliation, and mutation lists: `trace-reconciliation.json`.

| Trace | Observed model evidence | Freya HTTP evidence | Build seconds |
|---|---|---|---:|
| `traces/e2e-ab.jsonl` | 2 aggregate SDK sessions only | No individual HTTP events | 292.7 |
| `traces/review-ab.jsonl` | 2 aggregate SDK sessions only | 5 mutation completions; no request IDs/start events; child chat requests omitted | 224.5 |
| `traces/hidden-1.jsonl` | 2 aggregate SDK sessions only | Same older coverage | 196.3 |
| `traces/hidden-2.jsonl` | 2 aggregate SDK sessions only | Same older coverage | 176.0 |
| `rehearsal-a`, run `2e2cc43d` (archived during this audit) | None: explicit `policy_loaded` fixture mode | 18 starts and 18 matching completions, including child process requests; no unmatched IDs | 84.2 |

- **Every model call? Not provable for the historical end-to-end runs.** Current extraction records session start/end, every SDK-visible assistant message (message ID and usage), tool request and permission decision. The fresh determinism sweep exercises this instrumentation. Provider-internal HTTP retries, failed requests before an assistant message, and Freya's internal dialogue/extractor model calls are not individually visible. A message ID is not an HTTP request ID; do not label these complete provider request accounting.
- **Every Freya write? New client coverage is substantially stronger, but the older traces cannot be repaired retrospectively.** Current `freya.api` logs starts/completions around all client HTTP calls and propagates trace context to chat subprocesses. Engine-fired bank tool calls inside Freya are not local HTTP calls and require platform ledger/event evidence. Request logs omit bodies, query strings and payload hashes: a dry-run POST and a create POST have the same method/path. A completion proves a locally observed response, not uniquely the content or resulting remote write. No fresh full publication run was performed here.
- **Provenance:** `e2e-ab`'s recorded commit lacks its entry point (see the original `../e2e-ab-trace-review.md`). The six recorded source hashes in `review-ab` and the hidden dry runs match those files at their recorded commits, but their manifests cover fewer dependencies than today's code. `review-ab` is explicitly dirty. `rehearsal-a` is dirty, six recorded files differ from its commit and five did not exist there. It cannot be reproduced from that commit alone. Today's builder records all refactored core modules plus chat code, but hashes are truncated to 16 hex characters and outputs are not hashed in the trace.
- **Hand-built / brief-values concern:** automatic extraction followed by generic compilation is supported by the artifacts; embedding extracted policy in emitted code is normal compilation. There is no evidence of manually constructing a submitted hidden agent in these traces. However, a blanket “no brief values in source” claim remains too strong: `policy.py` still defaults to 3 identity failures, 2 holder asks, 10:00–19:00 callbacks, 3 products and one write retry. These defaults can affect omitted fields. Intent vocabulary and fallback dialogue are also template-authored. The old tracked `out/gen_brief_a.py` is no longer present. Clean committed source plus unchanged input files and policy/audit artifacts are the strongest reviewer evidence; dirty runs do not supply that guarantee.
- **Timing:** every reviewed build has a successful `run_end.elapsed_s`, so instrumented build duration is directly derivable. It excludes setup and prior development. Current start/end timestamps and monotonic elapsed timing provide the same measure, including failed builds when the final handler runs; abrupt process termination can leave no final event.
- **Remaining trace improvements:** include sanitized request query/dry-run mode and payload SHA-256; record policy/candidate/export hashes and extraction prompt hashes; retain the exact committed source revision. These are recommendations, not changes made in this audit.

## Reproduction command

From a clean checkout of `2064600d6ff207fa43df8ea27c1e643bc282bbe3`, after README setup and working Claude credentials, this reproduces the current A+B build mode with explicit model settings and no simulation:

```bash
set -a
source .env
set +a
BUILDER_MODEL=claude-opus-5-5 FREYA_AGENT_PROVIDER=experimental-5 FREYA_AGENT_MODEL=experimental-5 \
  .venv/bin/python -u build.py \
  --briefs briefs/brief-a.md,briefs/brief-b.md \
  --openapi tools/openapi.json --slot auditor-ab --deadline 1800
```

This is a prospective current-code run, **not an exact replay of the historical `e2e-ab` trace**, and it was not executed during this audit. Publication updates/reuses the named slot. The nine extraction-only rerun commands and frozen source hashes are under `../../extraction/determinism-rerun/`.

## Fresh extraction trace reconciliation

The completed sweep has 18 paired SDK sessions, 160 assistant-message events with IDs/usage (61 distinct message IDs), and 96 tool requests with matching permission decisions. No missing IDs, unmatched sessions/decisions or Freya HTTP calls were observed. Repeated message IDs reflect multiple SDK message events, so event counts are not provider HTTP request counts and usage must not be blindly summed across them. Cost is taken from session-end totals. See `../../extraction/determinism-rerun/output-checks.json`.

## Concurrently completed rehearsal

Another process replaced `traces/rehearsal-a.jsonl` during this audit. Both reviewed versions are preserved under `reviewed-traces/` (run IDs in filenames). The new run `767e7045` completed in **51.8 s**, with **17 starts / 17 matching completions**, no unmatched HTTP IDs, successful chat self-test and `workflow_readback.suspect_count=0` (629 platform additions). It still loads the policy fixture and is dirty; recorded source differs from its commit for build.py, compile.py, compiler_checks.py, workflow_runtime.py, policy.py. This is useful publication/chat evidence for the concurrent tree, but is neither a clean-commit reproduction nor a full extraction-to-publication run. Machine reconciliation: `latest-rehearsal-reconciliation.json`.
