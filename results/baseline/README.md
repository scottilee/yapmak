# Baseline and runtime verification

## Latest completed baseline

On 10 October at 12:03:44 UTC, platform and bank access both worked. The unchanged
sample agent completed Brief A: **0/10 passed**, 194 seconds of simulation time,
221.37 seconds for the full measurement including setup, scoring and exports.
Median slowest agent turn per call was approximately 4 seconds, with one failed
call ending through customer hangup. This is one run, not a repeatability estimate.

Artifacts: `20261010T120344Z/measurement.json`, `scores.json`, `simulation.log`,
`calls.json`, and `base.workflow.json`.

Transcript review confirms the happy path omitted the mandatory text-message
confirmation sentence. The service-error case did not retry create_promise and
sent a freeform close reason, which the bank rejected despite HTTP 200 and outer
status=success. Runtime checks must inspect data.ok, not transport success alone.
Call snapshots also contain simulated now=2026-10-14 alongside system clock
2026-10-10: these clocks demonstrably differ. This does not yet establish which
clock the date extractor uses. Flattened verification booleans are strings.

Other failures cover callback scheduling, identity retry termination, holiday and
deadline calculation, hardship, minimum-payment wording, already-paid outcomes,
and restructuring transfers. Missing tools/policies in the deliberately incomplete
sample explain much of this result; it does not measure the supplied builder.

## Earlier access diagnostics

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

The matrix below distinguishes verified chat observations from checks still pending. See the targeted-chat results below for evidence and limits. Use an isolated,
reused runtime-check workflow slot and synthetic practice sessions. Functional
checks must stay within the event's rules; no load tests or additional services.

| Contract | Minimal experiment | Required evidence |
|---|---|---|
| State persistence | Scalar strings verified in non-initial chat code node; lists/objects and pre-hooks pending | See runtime-date artifacts |
| Result envelopes | Verify two identity answers and read mapped plus flattened result fields | Correct data.* paths and boolean representation |
| Guarded writes | Verified for seeded validity/consent and repeat turn in chat; consent extraction still pending | Zero negative-path writes; one valid confirmed write, data.ok success route |
| Revision-bound consent | Amount correction and reconfirmation verified in chat; date/product/batch changes pending | See extraction-consent evidence and missing-data guard tests |
| Simulated calendar | Built-in chat date extraction followed real clock for tomorrow; code correctly read simulated now | Resolve structured expressions in code; vague speech extraction still pending |
| Tool-result freshness | Successful write for one product followed by failed write for another | No reuse of prior product success; truthful acknowledgement |
| Retry allowance | PUB-10 made two requests, one promise; persistent rejection made two requests, no promises | See bank-chat-retry evidence; stale-success-seeded retest blocked by 502 |
| Transfer/no notes | Dispute first product, then request transfer | No notes anywhere in ledger, including before transfer |
| Terminal order | Exercise normal and failure exits | One close_call, last bank action, goodbye before close |
| Publication/export | Update same slot, publish, export, simulate | Simulation version matches publication; exported content matches intended candidate |

Chat is suitable for fast feedback but may skip initial code nodes according to the
kit. Confirm consequential findings with a simulation. Hook exceptions are not a
supported cancellation mechanism; use explicit guard routing. Unknown transport
outcomes are not proof a write failed.

## Targeted chat runtime checks — 10 October, 12:29–12:31 UTC

No simulation was started. The example builder's `a.log` had no exit line when
checks began. All workflows reused the **runtime-check** slot; baseline and builder
slots were untouched. These are synthetic functional checks, not compliant final
phone agents and not a substitute for simulation evidence.

### Date extraction and non-initial code node

Artifacts: `runtime-date-20261010T122935Z/` (candidate, published export, IDs,
per-call turns/full snapshots, summary). Three nodes: conversation → code →
observation conversation. Built-in `type: date`, ordinary description, no custom
extraction prompt; call variable `now=2026-10-14T11:00`.

| Expression | Extracted variable | Expected under Brief A with simulated now |
|---|---|---|
| next Friday | 2026-10-16 | 2026-10-23 |
| tomorrow | 2026-10-11 | 2026-10-15 |

Snapshots show `system.iso_utc_now` on October 10. In both calls, the non-initial
code node ran and persisted `observed_now=2026-10-14T11:00`, `code_date=2026-10-14`,
and `code_ran=yes`. The tomorrow check disambiguates the clocks. These observations
support a real-clock anchor for default extraction in this chat configuration;
they do not prove every custom extractor or simulation uses the same anchor.

Decision: extract structured date expressions and resolve them deterministically
against `now`. Keep vague expressions unresolved. Code-node state persistence for
these scalar strings is verified; lists/objects and pre-hook persistence remain
pending. Call IDs: `2e304382-9276-4bb5-b74b-9782c3cf5d10` (Friday),
`2ef4fbd2-8d09-400b-beab-bf3c265e637e` (tomorrow).

### Guarded engine-fired promise write

Artifacts: `runtime-guard-20261010T123002Z/`. Four nodes were needed to include a
separate bank-success observation node: conversation → code → guarded api_request
→ recorded conversation. The failure/blocked branch returns to the first node.
Each case used a fresh PUB-01 practice session; test setup verified identity with
the public fixture answers and fetched exact product IDs before starting chat.
Proposal validity and confirmation were supplied as test variables to isolate
code/routing enforcement; this does **not** test consent extraction from speech.

| Case | Write-node entries | create_promise ledger requests | Persisted promises |
|---|---:|---:|---:|
| Below-floor amount, confirmed | 0 | 0 | 0 |
| Valid amount, unconfirmed | 0 | 0 | 0 |
| Valid amount, confirmed, followed by check again | 1 | 1 | 1 |

The confirmed trace routes `check → write` on `verdict == 'ok'`, then
`write → recorded` on mapped `bank_ok == 'true'`. Node-level mapping path was
`data.ok`. After the additional check, the persisted attempted flag blocks a
second write. Both request counts and persisted records agree; negative results
were not caused by a bank rejection. These checks establish the tested chat paths,
not a universal exactly-once guarantee across timeouts, interruption or retries.
The API-failure branch and amount-revision consent extraction were subsequently checked; see the speech-to-structure section below.

### Calendar implementation validation

`bankcal.py` preserves the handoff compatibility functions and adds structured
`resolve_date_expr`, `callback_ok`, and `nth_business_day_after` (alias
`add_business_days`). `parse_now` returns the existing `(date, time)` tuple.
Non-business deadlines require explicit adjustment; end-of-month requires an
explicit calendar/business basis. The compiler must read the module source on the
build machine rather than embedding file access or a future import.

`.venv/bin/python -m pytest tests/ -q`: **9 passed**, including public anchors,
legacy normalization/verdict acceptance, malformed inputs, callback boundaries,
450 comparisons against an independent simple business-day reference loop, and
execution of the complete source after preceding setup statements. Source uses
only datetime/json/re and has no double-brace delimiters.

## Speech-to-structure inputs and remaining chat checks — 10 October

Deliverables: `tests/fixtures/extraction_schemas.json`,
`tests/fixtures/extraction_adapters.json`, and `tests/fixtures/EXTRACTION.md`.
No edits to policy.py, compile.py or build.py were made for this workstream.
All checks below reused runtime-check and used chat, not simulation.

| Component | Observed result | Evidence directory under results/baseline |
|---|---|---|
| Structured date components | 7/7 scenario checks: PUB-04 6 November, PUB-07 vague then Monday 26th, PUB-13 30 October, spoken ordinal, same-turn correction, split ordinal, next Friday | extraction-date-20261010T123734Z |
| Amount floats | 3/3: words=420, split four hundred and / twenty=420, correction=350 | extraction-amount-20261010T123941Z |
| DOB extraction + code normalization | 3/3: word date, numeric day/month/year, split DOB | extraction-identity_date-20261010T124007Z |
| Four-digit identity regex | 2/2: leading-zero 0358 and split forty-four / seventy-one=4471; partial turn did not route | extraction-identity_digits-20261010T124028Z |
| Consent | 5/5 after threshold calibration: confirm, yes-but-correct, confirm/correct/reconfirm, refusal, question | extraction-consent-20261010T124154Z |
| Revision-bound confirmation with numeric reset | Revision 1 confirmed, correction to 350 clears consent, revision 2 needs fresh yes | extraction-consent-20261010T124552Z |
| Date correction after a complete date | November 6, partial twenty..., then October 23; partial did not enter processing | extraction-date-20261010T124317Z |
| Amount correction after a complete amount | 300, partial four hundred and..., then 420; numeric -1 sentinel persisted; partial did not route | extraction-amount-20261010T124534Z |
| Day/month-swapped hint | 1987-03-06 returns day_month_swapped with 3 wrong answers left; 1987-06-03 passes with allowance still 3 | bank-chat-hint-20261010T124346Z |
| PUB-10 engine-fired retry | Two ledger requests: service-unavailable then ok:true; exactly one persisted promise | bank-chat-retry-20261010T124403Z |
| Retry exhaustion | Deliberate unknown-product rejection twice, zero promises, service_error branch, no recording claim | bank-chat-retry-20261010T124403Z |

These are individual functional observations, not three-run consistency scores.
Each directory preserves candidate/export, IDs, call snapshots, user turns, and
summaries; bank checks also retain ledger records. The schema fixture links its
actual evidence and lists unverified cases.

### Important integration findings

1. Completeness must gate processing. A partial ordinal produced day=20, but no
   processing route fired until the continuation produced day=23. A previous amount
   may remain in vars during a partial correction; never route on is_set alone.
2. Consume only the date_kind's fields. The vague keyword persisted during the later
   numbered date, but code correctly ignored it and resolved the day number.
3. Numeric reset by empty string was ineffective in one typed amount snapshot.
   A numeric -1 sentinel persisted and blocked reuse of prior amount data. Use zero
   for unspecified date components and a separate current-turn completeness flag.
4. The first consent run invalidated consent but lost a correct amount correction:
   the extractor returned 350 with confidence 0.562, below min_confidence=0.7.
   `extraction-consent-20261010T124047Z/summary.json` records this failure. The
   corrected_amount field now uses 0.5, with code validation, read-back and fresh
   confirmation. Missing correction data leaves proposal_complete=false so another
   yes cannot authorize the stale amount. Other sampled fields retained 0.7.
5. A question maps to pending, not confirm. The fixture adds that fourth consent
   state deliberately. Correction wins over yes in "Yes, but make that 350."
6. The swapped-date hint did not consume an attempt. Successful DOB verification
   still returned all_verified=false because the phone check had not run.
7. On PUB-10's HTTP 500, the mapped bank_ok was unset, not false. Retry logic must
   treat missing/pending as failure and reset success state before every attempt
   and product. The script now seeds stale bank_ok=true and clears it to pending
   before each write; the live retest of that added safeguard was blocked by 502.
8. Engine pre_actions are logged as function api_call, with nodeId=write. Matching
   only the declared name create_promise missed the success event in the first
   analysis. The corrected analysis finds bank success at 7.694 s and the recording
   claim at 10.595 s. No claim preceded success.
9. PUB-10 is configured to fail once, then succeed. It cannot prove two service
   outages. The separate persistent-rejection check deliberately uses a nonexistent
   product ID and is labeled accordingly; this is not production product selection.

### Platform errors and remaining limits

A broader retest with a compound date-status AND proposal-intent gate passed
PUB-04, then hit HTTP 502 at chat startup. Subsequent date and stale-success retry
checks also hit 502 before their first response. Failed/incomplete runs are kept
in extraction-date-20261010T124610Z, extraction-date-20261010T124641Z and
bank-chat-retry-20261010T124736Z; they are not counted as policy failures or passes.
Standalone non-proposal intent scenarios (refusal, hardship, dispute, paid,
restructuring, human, question) are scripted but their run was not reached after
the startup errors. Proposal intent was observed in the successful date tests.
Production guards still require schema validation and policy-specific amount/date
checks. Consent date/product/batch corrections need the same revision protocol;
the live consent experiment covered amount corrections.

## A+B example-builder baseline attempt

The preceding A run had an exit line before this work began. Attempted the
unchanged `examples/agent_builder.py briefs/brief-a.md briefs/brief-b.md` in an
isolated starter-kit copy to avoid editing template source. It exited in 0.74 s
with **Not logged in**, before any workflow creation or simulation. No B score is
available. Evidence: `results/example-builder/ab/ab.log`, `measurement.json`, and
`traces/20261010-053537.jsonl`. Authentication setup used by the earlier A run is
not available in this shell; a user question is pending. The isolated run wrapper
is `scripts/run_ab_baseline.py`; it copies outputs and traces outside its ignored
kit directory and records elapsed time and exit status.

## Offline Phase 4 inputs and repository hygiene

Six script variants are in `tests/fixtures/synthetic/`, each retaining its original
public case ID, identity and products. Manifest labels distinguish direct --cases
support, a Friday-now adapter, an interruption-dependent transfer script, and the
offline-only double-write-failure fixture. The stock runner ignores case-file now
and faults when creating bank sessions; scripts/run_synthetic_cases.py explicitly
passes the desired now into simulation variables and rejects custom faults.
No synthetic simulation was launched. Four mutation inputs cover holiday/deadline
changes, identity order, callback hours, and a dated amendment's limited scope.

`.venv/bin/python -m pytest tests/ -q`: 14 passed. Added offline checks verify
extractor placeholders/types, missing-correction consent blocking, stale date-field
selection, synthetic-runner capability limits, and embedding of all adapters.
`.gitignore` excludes credentials, Python environments/caches, local Freya state,
and isolated starter-kit copies. Source, fixtures, selected results, submission
exports and builder traces remain trackable. Ignore rules do not remove files
already staged or tracked.
