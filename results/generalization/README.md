# Synthetic brief generalization checks — 10 October 2026

Both new briefs completed extraction and audit, passed compiler static checks and Freya dry-run, and were published/exported on the reused **`generalization-check`** scratch slot. The initial default `publish_check.py` runs exited **1** on HTTP **503 at chat startup**. **Retries at 14:07–14:08 UTC passed for both fixtures (exit 0, two chat turns each)**; see the retry evidence below. No simulations or bank operations were run. This is IR/compilation/publication evidence, not an end-to-end policy score.

After semantic review, **no incorrect operative policy values remain in the final audited IRs among the rules checked**. First-pass mistakes, audit corrections, strict-oracle differences, and all unresolved items are enumerated below. The oracles were authored before extraction; their overconstraints are disclosed rather than silently changed to match output.

## Successful retry after cooldown — 14:07 UTC

Used the same saved candidates and scratch slot, without rerunning extraction or compilation. Original failure logs remain intact. Both retry exports retain every supplied workflow field; differences are only platform additions under the checker’s existing exclusions.

| Fixture | Publish-check elapsed | Exit | Chat turns | Call ID | Artifacts |
|---|---:|---:|---:|---|---|
| clean-eom | 18.60 s | 0 | 2/2 | `a40637e6-030c-478b-b529-4e0dc4ac5584` | [Evidence](clean-eom/consistent-input-run/smoke-retry-20261010T140742Z/summary.json), [log](clean-eom/consistent-input-run/smoke-retry-20261010T140742Z/publish-check.log) |
| reversal-thread | 23.09 s | 0 | 2/2 | `6d44beb8-9c3e-4f1c-b602-06891a06e5a7` | [Evidence](reversal-thread/consistent-input-run/smoke-retry-20261010T140742Z/summary.json), [log](reversal-thread/consistent-input-run/smoke-retry-20261010T140742Z/publish-check.log) |

- Clean: gave the Larkspur opening, accepted “Yes, speaking,” announced **four** security questions, then asked for the registered business **postcode**.
- Thread: gave the Harbour opening, accepted “Yes, speaking,” announced **three** security questions, then asked for the eight-digit **company registration number**.
- Both reached `ask_0` with simulated date **2026-10-14**. Full call snapshots and chat API responses are preserved in the retry directories. These smoke checks did not verify identity answers or invoke bank tools, and do not establish full policy behavior.

## Inputs and mutations

| Fixture | Shape and stress points | Inputs |
|---|---|---|
| `clean-eom` | Clean numbered spec; four identity questions; 1–45 days-late band; `end_of_month`, business basis, preceding adjustment; two products | [Brief](../../tests/fixtures/synthetic/clean-eom-brief.md), [OpenAPI](../../tests/fixtures/synthetic/clean-eom-openapi.json), [120-check oracle](../../tests/fixtures/synthetic/clean-eom-expected.json) |
| `reversal-thread` | Email pack: signed memo appears **before** the older policy and superseded forwarded quotation. Memo forbids retries, removes the human-transfer barrier, changes only the late-band deadline, and forbids same-day callbacks | [Brief](../../tests/fixtures/synthetic/reversal-thread-brief.md), [OpenAPI](../../tests/fixtures/synthetic/reversal-thread-openapi.json), [117-check oracle](../../tests/fixtures/synthetic/reversal-thread-expected.json) |

Both APIs retain the seven operation names but mutate identity/product/outcome/reason/queue enums and floor fields. Response mutations: `ok → success`, `verified → answer_verified`, `attempts_remaining → checks_left`, `facilities → accounts`, product `product_id → account_id`, `type → kind`, `arrears → overdue_balance`, and `days_in_arrears → late_days`. The identity hint is removed. Request `product_id` is retained and explicitly mapped from response `account_id`. Non-live `.example.invalid` hosts prevent accidental mock-bank writes.

## Pipeline results

| Fixture | Extract + audit | Model cost | Compile | Publish / export | Chat smoke | Raw oracle matches |
|---|---:|---:|---|---|---|---:|
| clean-eom | 187.85 s; exit 0 | $1.21 | 40 nodes; exit 0 | Passed; 744 platform-added defaults, **0 removals/changes** | Initial HTTP 503; retry **passed, exit 0** | 119/120 |
| reversal-thread | 176.69 s; exit 0 | $1.14 | 36 nodes; exit 0 | Passed; 668 platform-added defaults, **0 removals/changes** | Initial HTTP 503; retry **passed, exit 0** | 115/117 |

Timings are recorded stage durations, not a continuous builder benchmark. Extraction used `claude-opus-5-5` with the existing extraction/audit passes. No generated policy/workflow was manually corrected. `extract.py`, `compile.py`, `policy.py`, and `publish_check.py` were not edited for this task; per-stage hashes are recorded and matched across both runs.

Workflow ID: `feb14436-3471-4f9b-9be6-570407b7d71f`; agent ID: `5a55e67e-b5f4-48c9-bca7-7ece2590041f`. The original second publication reused these IDs and reported version 2; the successful smoke retries published versions 3 (clean) and 4 (thread). The active scratch slot contains the email-thread workflow; both individual exports are retained.

| Fixture | Final IR | Full comparison | Publication evidence |
|---|---|---|
| Clean | [IR](clean-eom/consistent-input-run/probe-clean-eom-v2.policy.json), [audit](clean-eom/consistent-input-run/probe-clean-eom-v2.audit.json) | [Every check](clean-eom/consistent-input-run/ir-diff.json), [audit-applied diff](clean-eom/consistent-input-run/audit-applied-diff.json) | [Pipeline](clean-eom/consistent-input-run/pipeline.json), [log](clean-eom/consistent-input-run/publish-check.log), [export](clean-eom/consistent-input-run/published.export.json), [stored diff](clean-eom/consistent-input-run/stored-diff.json) |
| Thread | [IR](reversal-thread/consistent-input-run/probe-reversal-thread-v2.policy.json), [audit](reversal-thread/consistent-input-run/probe-reversal-thread-v2.audit.json) | [Every check](reversal-thread/consistent-input-run/ir-diff.json), [audit-applied diff](reversal-thread/consistent-input-run/audit-applied-diff.json) | [Pipeline](reversal-thread/consistent-input-run/pipeline.json), [log](reversal-thread/consistent-input-run/publish-check.log), [export](reversal-thread/consistent-input-run/published.export.json), [stored diff](reversal-thread/consistent-input-run/stored-diff.json) |

## Important extracted values

| Rule | Required and observed final value |
|---|---|
| Clean identity order | `postcode`, `birth_year`, `company_number`, `founded_year`; formats text/year/digits/year; company number exactly 8 digits |
| Clean security allowance | Four wrong answers globally, using `checks_left`; questions about security do not count as refusal |
| Clean deadline | `{"kind":"end_of_month","basis":"business","adjustment":"preceding"}` |
| Clean calendar anchor | With now=2026-10-14, deadline **2026-10-29**: October 30 is a holiday and October 31 is Saturday |
| Thread identity | `company_number`, `postcode`, `founded_year`; two wrong answers globally |
| R7-A retry reversal | `promise_write.retry_on_failure = 0`, overriding P3 retry once |
| R7-B human-request reversal | `human.ask_once_first = false`; immediate `harbour_desk` transfer |
| R7-C scoped deadline amendment | 1–15 band remains 9 business days; 16–60 band becomes 4 business days; attempt counts remain 1 and 2 |
| Thread calendar anchors | With now=2026-10-14, early **2026-10-28**, late **2026-10-21**, skipping the October 19 holiday |
| R7-D callback reversal | `next_business_day`, hours unchanged at `09:15`–`17:45` |
| Superseded quotation | Did not restore retry=1, ask-once=true, same-day callback, or late deadline=6 |

Calendar anchors were evaluated offline using the final extracted rules and `bankcal.deadline`; see each run’s `deadline-checks.json`. No new simulator/customer data was fabricated.

## Every observed incorrect or incomplete value, and disposition

| Fixture / pass | Path | Extracted value | Required interpretation / final disposition |
|---|---|---|---|
| Both consistent-input first passes | `special_cases.refuse_to_talk.action.type` and `.outcome` | `close` with fixed `lark_no_deal` or `harbour_no_deal` | A second refusal marks remaining products refused and ends processing; final outcome must still respect existing promises and the first non-settled note. Audit changed action to `note`, removed fixed outcome, retained refused reason and `ends_call=true`. Corrected in both final files. |
| Clean consistent-input first pass | `special_cases.cannot_answer.before_persuasion` | Omitted, loading as **false** | Rule 8 says these cases precede persuasion. Audit wrote **true**. Corrected. |
| Thread first pass | 26 `source.doc` fields | File name with appended rule/memo commentary rather than a source-file path | Audit normalized all 26 to `tests/fixtures/synthetic/reversal-thread-brief.md` and put rule references in `source.text`. Every old/new path is listed below and in the full diff. |
| Thread first pass | `outcomes.table[1].when` | `all products settled` | Audit clarified `no promise and all products settled`; the separate precedence flags were already correct. |
| Thread first pass | `outcomes.table[2].when` | `call transferred` | Audit clarified `call transferred (overrides any promise)`; the transfer precedence flag was already correct. |
| Thread first pass | `outcomes.table[3].when` | First non-settled note, with order not stated in this summary | Audit added `in get_account order`; the operational precedence field was already correct. |

The audit also made default `takes_promise=false` values explicit for thread restructuring, human transfer, and refusal to talk, and expanded source quotations. Those defaults already loaded as false; these were not changed policy values. No raw JSON keys were silently discarded by `PolicyIR` loading in either final run. Identity question wording, extra robot/cannot-answer/change-recorded-promise cases and their required phrases were manually reviewed in addition to the numeric/enum/boolean oracle.

### Strict-oracle differences that are not final extractor errors

| Fixture | Raw difference | Semantic review |
|---|---|---|
| Both | Oracle expected `refuse_to_talk.action={close, no_deal, refused}`; final IR uses `{note, refused}` | **Oracle overconstraint.** The audit’s note-and-finalize representation respects the brief’s outcome precedence better. Original expected files are retained unchanged so this is visible. |
| Thread | Late-band attempt 2 has `floor_if_full_refused=false`; oracle used true | **Inactive-field difference.** That attempt already has `amount=floor`, so it always selects the floor regardless of this flag (`compile.py` selects floor when amount is floor OR the conditional flag applies). Neither the brief nor behavior requires true here. |

### Every normalized thread source path

All rows below now contain `tests/fixtures/synthetic/reversal-thread-brief.md`; references were moved into the associated source text.

| Path | Original value |
|---|---|
| `amounts.source.doc` | reversal-thread-brief.md (P3 rule 6) |
| `bands.0.source.doc` | reversal-thread-brief.md (P3 rule 5; unchanged by R7-C) |
| `bands.1.source.doc` | reversal-thread-brief.md (Risk memo R7-C, amending P3 rule 5) |
| `calendar.source.doc` | reversal-thread-brief.md (P3 rule 4) |
| `dates.source.doc` | reversal-thread-brief.md (P3 rule 6) |
| `identity.requirements.0.source.doc` | reversal-thread-brief.md (P3 rule 3) |
| `identity.requirements.1.source.doc` | reversal-thread-brief.md (P3 rule 3) |
| `identity.requirements.2.source.doc` | reversal-thread-brief.md (P3 rule 3) |
| `identity.source.doc` | reversal-thread-brief.md (P3 rules 1, 3) |
| `multi_product.source.doc` | reversal-thread-brief.md (P3 rules 4, 5, 7, 9) |
| `notes.source.doc` | reversal-thread-brief.md (P3 rule 9) |
| `outcomes.source.doc` | reversal-thread-brief.md (P3 rules 9, 10) |
| `phrases.source.doc` | reversal-thread-brief.md (P3 rules 1, 4, 5, 7, 8, 9) |
| `promise_write.source.doc` | reversal-thread-brief.md (Risk memo R7-A, amending P3 rule 7) |
| `special_cases.0.source.doc` | reversal-thread-brief.md (P3 rule 8) |
| `special_cases.1.source.doc` | reversal-thread-brief.md (P3 rule 8) |
| `special_cases.2.source.doc` | reversal-thread-brief.md (P3 rule 8) |
| `special_cases.3.source.doc` | reversal-thread-brief.md (P3 rule 8) |
| `special_cases.4.source.doc` | reversal-thread-brief.md (Risk memo R7-B, amending P3 rule 8) |
| `special_cases.5.source.doc` | reversal-thread-brief.md (P3 rule 8) |
| `special_cases.6.source.doc` | reversal-thread-brief.md (P3 rule 8) |
| `special_cases.7.source.doc` | reversal-thread-brief.md (P3 rule 8) |
| `special_cases.8.source.doc` | reversal-thread-brief.md (P3 rule 8) |
| `special_cases.9.source.doc` | reversal-thread-brief.md (P3 rule 7) |
| `third_party.callback.source.doc` | reversal-thread-brief.md (Risk memo R7-D, amending P3 rule 2) |
| `third_party.source.doc` | reversal-thread-brief.md (P3 rule 2) |

## Every remaining unresolved item

Only **one item per fixture** is in final `IR.unresolved`: out-of-range lateness. The audits also list the constraints below as missing dedicated IR fields or unspecified wording. “No dedicated field” does **not** establish missing runtime enforcement: several are implemented by the existing template. Do not interpret audit-only entries as genuine policy contradictions, or treat `IR.unresolved` alone as the complete coverage report.

| Applies to | Location | Item marked unresolved | Assessment |
|---|---|---|---|
| Clean | IR + audit | Product has 0 or more than 45 days late | No band/handling specified. Genuine out-of-scope input gap; in-range EOM rule is unambiguous. |
| Thread | IR + audit | Product has 0 or more than 60 days late | No band/handling specified. Genuine out-of-scope input gap; memo precedence is resolved. |
| Both | Audit only | Holder confirmation: yes/speaking/own name count; hello/questions do not | Explicit source rule; template/extraction coverage, not an unresolved policy value. |
| Both | Audit only | Missing callback hour must be clarified, never guessed | Explicit source rule; extraction/completeness guard requirement. |
| Clean | Audit only | Third parties must learn nothing about purpose/accounts | Explicit privacy rule; prompt/template coverage. |
| Both | Audit only | One short sympathy sentence; no dictated exact wording | Intentional language freedom; not a conflicting policy value. |
| Both | Audit only | Honest failed-write message; no dictated exact sentence | Required behavior is clear; exact wording is free. Thread expressly requires saying no promise was recorded for that product. |
| Both | Audit only | Never offer discount, waiver or a new instalment plan | Explicit prohibition; existing default system prompt includes it. |
| Clean | Audit only | Do not call get_account before all security questions pass | Explicit ordering/authorization rule; must remain enforced by workflow guards. |
| Clean | Audit only | Use call variable now, never the real clock | Explicit calendar rule; template/code coverage. |
| Thread | Audit only | A flat refusal consumes one persuasion attempt | Explicit attempt-count rule; template coverage. |
| Thread | Audit only | Any correction cancels consent | Explicit authorization rule; needs state/guard enforcement, not merely prompt wording. |
| Thread | Audit only | Never claim a failed write was recorded | Explicit truthfulness rule; bank-result gating plus dialogue. |

The complete original audit strings are preserved below, without dropping subclauses:

### clean-eom

**IR entries:**

- `bands`: The brief defines a deadline only for days late 1–45 inclusive; no rule is given for products more than 45 days late (or 0 days late).

**Audit entries:**

- No deadline or attempt rule exists for products 0 days late or more than 45 days late (only band 1-45 is defined). This is already listed in policy.unresolved.
- Constraints with no IR field, kept only as prompt-level rules: what counts as holder confirmation (yes, speaking, own name; not hello or a question); a missing callback hour must be clarified, never guessed; third parties are told nothing; the hardship sympathy sentence is not dictated verbatim; the wording of the service-error message ('says it failed') is not dictated; never offer a discount, waiver or new instalment plan; never call get_account before all questions pass; use call variable now, never the machine clock.

### reversal-thread

**IR entries:**

- `days_late_outside_bands`: The documents define bands only for 1–15 and 16–60 days late inclusive; handling of a product with 0 or more than 60 days late is not stated.

**Audit entries:**

- Products 0 or more than 60 days late: there is no band and no handling rule.
- Not expressible in the schema, so the prompt must carry them: 'Hello or a question does not' confirm the holder; a missing callback hour must be clarified, never guessed; a flat refusal uses up one persuasion attempt; any correction cancels consent; never claim a failed write was recorded; on write failure tell the customer no promise was recorded (no exact sentence is given); one short sentence of sympathy for hardship (no exact sentence is given); never offer a discount, waiver or new instalment plan.

## Audit tool behavior and publication limits

The clean audit first attempted disallowed `Edit` calls (and its trace lists a `Bash` attempt), then recovered with the allowed full-file `Write`. Its intermediate audit temporarily said the fixes were not applied; the **final policy and final audit confirm they were applied**. This was not a final pipeline failure and no manual correction was made. A useful extraction-prompt improvement is to reinforce “rewrite the complete JSON with Write; do not use Edit or Bash.”

Publication stored 744 added defaults for clean and 668 for thread, with zero differences to supplied values after the existing checker’s documented top-level exclusions. Full difference lists are retained, not just the first 40 printed by `publish_check.py`. Both original exports exist. Initial chat startup failed; the later retries passed without changes to either candidate. Neither the synthetic bank endpoints nor public mock customers can validate these renamed identities/products without an appropriate mock adapter.

## Initial fixture-authoring attempt (preserved, not counted as extractor failures)

The first versions inherited stale prose from `memo-openapi.json`: “three wrong answers,” “both questions,” `ok` in response descriptions after renaming it to `success`, and generic permission to repeat a failed call. The extractor correctly highlighted conflicts with the new briefs. Those descriptions were corrected in the synthetic APIs, then both complete extraction/audit runs were repeated. Core builder files and extracted policies were not patched. Original inputs, output policies, audits and traces remain in each `initial-fixture-attempt/` directory.

The initial clean extraction additionally set `already_paid.ends_call`, `dispute.ends_call`, and `hardship.ends_call` to **true** despite continuing other products; its own audit corrected all three to **false**. The initial thread extraction’s floor-attempt boolean and refusal-action representation differences are documented in its raw comparison; the floor boolean is semantically inactive as explained above.

Every final `unresolved` entry from that initial attempt is retained here for completeness; repeated concerns below do not imply additional errors in the corrected-input run:

| Initial fixture | Topic | Exact unresolved text |
|---|---|---|
| clean-eom | days_late_outside_band | The brief defines only the 1–45 days-late band; it does not say how to handle a product with 0 or more than 45 days late. |
| clean-eom | wrong_answer_limit_conflict | The verify_identity summary says "Three wrong answers in total end the check" and get_account says "Refused until both questions are passed", but the brief sets 4 wrong answers across 4 questions and says to use the API's checks_left. The brief value (4, via checks_left) was used. |
| clean-eom | hardship_sympathy_sentence | Hardship requires "one short sentence of sympathy" but the brief gives no verbatim wording. |
| clean-eom | no_discount_rule_unrepresented | Rule 6 "Never offer a discount, waiver or a new instalment plan." has no dedicated IR field; it is recorded only in amounts.source and must be carried by prompt text. |
| clean-eom | refuse_to_talk_close_outcome | Rule 8 says a second refusal to talk ends the call and marks remaining products `lark_refused` but names no close outcome; the close follows rule 9 precedence, so `lark_no_deal` / `lark_refused` applies only when no promise was already recorded (a recorded promise still gives `lark_arranged`). |
| reversal-thread | identity.wrong_answer_limit | The brief says maximum wrong answers across the entire check is 2 and to use the API's checks_left; the API summary says three wrong answers in total end the check. Brief value 2 used, counting delegated to checks_left. |
| reversal-thread | get_account precondition | The get_account summary says it is refused until both questions are passed, while the brief has three security questions; the brief's three-question order is used. |
| reversal-thread | hardship sympathy sentence | The brief requires one short sentence of sympathy for hardship but does not dictate its wording. |
| reversal-thread | create_promise retry vs API 500 text | The API's 500 response says 'The call may be repeated.' Signed memo R7-A says NEVER retry a failed create_promise (exactly one request per product); R7-A governs, so retry_on_failure is 0. The forwarded 2 October checklist ('Retry every failed promise once') is historical and superseded. |
| reversal-thread | failed write wording | R7-A: on the first create_promise failure 'tell the customer no promise was recorded for it'; P3 7: 'Never claim a failed write was recorded.' No exact sentence is dictated and the schema has no phrase field for it. |
| reversal-thread | flat refusal consumes an attempt | P3 5: 'A flat refusal consumes one persuasion attempt.' The schema has no field for this; it is implied by the attempt lists in bands. |
| reversal-thread | no discount/waiver/instalment plan | P3 6: 'Never offer a discount, waiver or a new instalment plan.' No schema field expresses this prohibition. |
| reversal-thread | callback missing hour | P3 2: 'A missing hour must be clarified, never guessed.' No schema field expresses this; third parties must be told nothing about purpose or accounts. |
| reversal-thread | clamped date explanation | P3 5: a common date after a product's deadline is clamped to that product's deadline 'and explained in the read-back'; the explanation wording is not dictated. |

Initial audit-only entries (exact):

- **clean-eom**: Days late outside 1-45 (0 or >45): the brief defines no band.
- **clean-eom**: The API conflicts with the brief: the verify_identity summary says three wrong answers end the check, and get_account says 'both questions'. The brief sets 4 wrong answers over 4 questions via checks_left, and the brief's value is used.
- **clean-eom**: Hardship 'one short sentence of sympathy' has no verbatim wording.
- **clean-eom**: 'Never offer a discount, waiver or a new instalment plan' has no IR field.
- **clean-eom**: Refusal to talk names no close outcome. lark_no_deal/lark_refused only applies when no promise is recorded; otherwise rule 9 precedence gives lark_arranged.
- **reversal-thread**: Identity wrong-answer limit: the API summary says three wrong answers end the check, the brief says 2 and to rely on checks_left. The brief's 2 is used.
- **reversal-thread**: The get_account summary says 'both questions' but the brief has three. The brief's three-question order is used.
- **reversal-thread**: The wording of the hardship sympathy sentence is not dictated.
- **reversal-thread**: The API's 500 response says the call may be repeated, but R7-A forbids retrying create_promise. R7-A governs.
- **reversal-thread**: There is no dictated sentence for telling the customer that no promise was recorded after a failed write (R7-A).
- **reversal-thread**: 'A flat refusal consumes one persuasion attempt' has no schema field.
- **reversal-thread**: 'Never offer a discount, waiver or a new instalment plan' has no schema field.
- **reversal-thread**: 'A missing hour must be clarified, never guessed' (callbacks) has no schema field.
- **reversal-thread**: The wording for explaining a clamped common date in the read-back is not dictated.

## Reproduction

Expected values and source fixtures are generated by `scripts/make_generalization_briefs.py`; the comparison helper is `scripts/check_synthetic_ir.py`. The runner invokes the existing three CLIs and records their commands, durations, exit codes, source hashes, logs, final policy, audit and workflow exports. Publication must remain sequential because the slot is reused.

```bash
source .env
.venv/bin/python scripts/run_synthetic_pipeline.py clean-eom
.venv/bin/python scripts/run_synthetic_pipeline.py reversal-thread
```

For the exact recorded commands and input hashes, use each `consistent-input-run/pipeline.json`. Each directory also contains its input snapshots, so subsequent fixture or compiler edits can be distinguished from the tested versions.
