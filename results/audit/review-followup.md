# Follow-up review: validity and fixes

The findings mostly describe an older revision. The remaining gaps were fixed without committing or pushing.

| Finding | Current assessment and action |
|---|---|
| S1: extractor access / artifact leakage | Repository-wide extractor access was already removed: scratch copies and an enforced Read/Write allowlist are in place. This pass centralizes credential scanning in `artifact_security.py`, adds gates before workflow validation/publication/export, and adds `scripts/check_artifacts.py` for submission files. `SUBMISSION.md` now consistently describes policy/audit JSON as supporting evidence committed with the submission. |
| S2: import-time redaction | Already changed to read current environment secrets at logging time. This pass also redacts recognizable API-key and Bearer-token formats and sanitizes HTTP error bodies before constructing exceptions. |
| S3: unchecked tool URLs | HTTPS and authority checks already existed. Hostname/port validation and a consistent HTTPS origin for the seven bank tools are now enforced. This is syntax/origin validation, not a claim that an arbitrary supplied host is trusted. |
| E1: inflated policy / entire legacy calendar embedded | Outdated. `embed_policy()` already uses compact JSON, and AST dependency slicing includes only reachable runtime/calendar helpers. Added a regression test proving `parse_amount`, `resolve_date_expression`, and `callback_slot` are absent from every emitted code node. No extra core/legacy split is needed to remove those functions from emitted workflows. |
| E2: duplicate opening smoke | Already removed. The builder's chat self-test covers the opening. |
| E3: deadline-unaware retries | Already bounded by a shared monotonic deadline and POSIX timer. This pass moves actual request retries into `retrying.py`; chat evidence GETs use the same helper. |
| D1: duplicated chat lifecycle / event parsing | Fixed with `scripts/chatlib.py`, used by chat self-test, publish check, runtime checks, extraction checks, intent checks, and bank-check event parsing. It merges wrapped/plain variable snapshots, preserves all event names, and closes known calls after failed turns. A live test exposed events with existing `node` metadata; the merge now handles those correctly. |
| D2: three retry helpers | Partly inaccurate: `bank_chat_checks.retry()` is a promise-retry test scenario, not a request retry helper. Actual request retries now share one implementation. Chat POSTs are not automatically replayed after ambiguous failures. |
| Q1: string-matched annotation names | Already replaced with `typing.get_type_hints/get_origin/get_args`, recursive typed loading and explicit type errors. |
| Q2: ignored runtime_error | Fixed. Chat self-test and publish check inspect every observed snapshot, including errors later cleared. Missing variable evidence is labeled unavailable, not clean. These checks cover the exercised paths, not every possible conversation. |
| Q3: compile monolith | Already split into OpenAPI, nodes, static checks, and ordinary runtime source modules; `compile.py` is approximately 450 lines. Dependency slicing is retained. |
| Q4: magic budgets | Simulation/reserve/outer-chat budgets already had names. Added `CHAT_SCENARIO_BUDGET_S` for the child chat-check budget. |
| Q5: unbounded calendar wait | Already replaced by the shared batch runner with bounded predecessor, health, and job waits. |
| Positives / Q6 | Preserved: no shell-based subprocess execution, credential-free workflow requests, extraction without Bash, validation gates, checkpoint-before-tests, archived traces, synthetic-case tamper checks. |

## Verification

- `.venv/bin/python -m pytest tests/ -q`: **81 passed**.
- Python syntax checks passed for the changed modules and all migrated chat clients.
- Credential scan passed on all eight existing hidden policy/audit/workflow/trace submission artifacts.
- Fresh compilation of A and A+B: zero static errors, 33 nodes each. Serialized sizes were 363,950 and 365,711 bytes respectively; no claimed percentage improvement against an unmeasured old baseline.
- Live pre-bank chat check on the existing `rehearsal-a` slot: **both scenarios passed on the first attempt**, including `no_runtime_error` with actual variable evidence. Elapsed time: **20.6 s**. [Result](chat-selftest-review.json).
- The earlier live parser failure is retained as [diagnostic evidence](chat-selftest-review.before-parser-fix.json); a regression test covers its duplicate metadata keys.
- No simulations started or workflows republished in this follow-up.

Credential scans cover current configured secret values and recognizable token formats; they are not a general data-loss-prevention guarantee. The extractor's enforced file-access restrictions remain the primary protection against reading credentials from an injected brief.
