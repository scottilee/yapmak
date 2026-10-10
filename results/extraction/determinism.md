# Extraction determinism — three audited runs per input

**Result: all nine runs succeeded, but extraction is not byte-for-byte deterministic.** Three repetitions each of A, A+B and clean-eom, all using the same frozen source/input snapshot at `2064600d6ff207fa43df8ea27c1e643bc282bbe3`. Total wall-clock **533.4 seconds (8m 53s)** with three input groups in parallel and repetitions sequential within each group; reported model cost **$9.2575**. Every run used extraction + audit, with **no repair**, no publication and no simulation. Individual extraction durations: 143.0–179.7 seconds.

| Input | Differing effective leaf paths | Prior sweep | Additional raw-only differences |
|---|---:|---:|---:|
| A | 7 | 19 | 0 |
| A+B | 15 | 54 | 0 |
| clean-eom | 20 | 15 | 0 |

The tables below enumerate every differing field and all three exact values. “Effective” means dataclass defaults have been applied, **not** that every field is consumed by the runtime. The previous report is preserved in `determinism-rerun/previous-report.md`.

### What matters for behavior

- **The previous A+B already-paid/dispute close-vs-note flip did not recur:** all three use note actions and `ends_call: false`. Identity question order, band ranges/deadline rules, holidays, floor-field mappings, outcome/reason enums and write-retry counts agree within each input group. Three repetitions are evidence of improved consistency, not proof of future determinism.
- **Spoken wording still changes:** A's failed-identity instruction and sympathy sentence; A+B's phone-digits question, pay-all-today question, cannot-answer reply, floor wording and sympathy sentence. No missing required phrase flip recurred. These alternatives are mostly semantically similar, but they change generated prompts and can change a stochastic judge's result.
- **Non-wording flips remain, without a demonstrated routing difference in this compiler:** late-band attempt 2 `floor_if_full_refused` flips, but its amount is explicitly `floor` in every run, making that flag redundant at `_start_attempt`. `refuse_to_talk.ask_once_first` and `before_persuasion` flags vary; the runtime uses fixed handling for those cases rather than those flags. `ask_once_first` is read for the human-transfer case, which did not flip.
- **Synthetic refusal action changes:** clean-eom runs 1/2 emit `{type: note, reason: lark_refused}`; run 3 emits `{type: close, outcome: lark_no_deal, reason: lark_refused}`. The independently authored oracle expects the latter. Runs 1/2 match **119/120** oracle fields; run 3 **120/120**. The current refusal handler ignores this action object, marks remaining products refused and finalizes after the second refusal, so this is an IR representation discrepancy, not proof of a wrong close outcome. It still deserves canonical extraction wording.
- Clean-eom additionally varies a band label, special-case order, trigger text, outcome explanatory text and whether `openapi.json` appears in `source_docs`. These are not deadline/outcome enum changes.

### Excluded text can still affect the generated agent

As requested, source spans and unresolved text are excluded from the field-difference count. **That exclusion does not make the workflows equivalent:** the compiler appends unresolved text to the dialogue system prompt. A+B run 1 adds `Rule 33 (never offer a discount, a waiver, an instalment plan or any term not in the brief) has no structural IR field; it must be carried by the prompt text.` Runs 2/3 do not. This reintroduces the exact negative-offer vocabulary removed from the hand-written prompts. Keep diagnostics separate from dialogue rules; generate the positive rule “Only discuss terms supplied in your current instruction” instead. This is the highest-value finding from the rerun.

### Proposed extraction-description changes

1. Define one canonical representation for refusal-to-talk: a close action naming the final outcome/reason, `ask_once_first: true` for a two-refusal policy, and explicit `ends_call`; defer product notes to the notes/outcome policy. Do not encode the same rule sometimes as a note and sometimes as a close.
2. Define `floor_if_full_refused` only for a `full` attempt; use false for an explicit floor attempt. Define `before_persuasion` consistently for priority special cases. These changes reduce representational variance without changing supported behavior.
3. Copy dictated phrases exactly. For content-only phrases, specify one canonical sentence/normalization rather than asking for a fresh paraphrase on each pass; do not normalize mandated verbatim text. Keep the current requirement that mandatory content cannot be left empty.
4. Fix `source_docs` to the caller's ordered brief paths; use a stable special-case ordering and band naming convention. Keep explanatory `when`/trigger wording out of comparisons used to decide whether routing changed.

These are recommendations only; the extractor prompt was not edited during measurement.

### Validation and scope

All nine policies compile with **zero static errors** (A/A+B: 33 nodes; clean-eom: 41). Offline scripts pass **39/39** across the three A and three B policies; these inject structured extraction values and do not test Freya's natural-language classification. Detailed compile/oracle/transcript checks and generated system prompts: `determinism-rerun/output-checks.json`.

All **18 SDK sessions** have start/end records; **160 assistant-message events** have IDs/usage, corresponding to **61 distinct message IDs**, and **96 tool calls** have matching allow/deny decisions (all allowed, no unexplained tool calls). Multiple SDK events can share a message ID: do not count message events as separate HTTP requests or sum their usage naively. There are **zero Freya HTTP calls** in these extraction traces. Provider-internal requests/retries remain outside SDK visibility.

Concurrent edits occurred after the snapshot, including `policy.py`; see `../audit/current/concurrent-changes.patch`. The nine-run comparison measures the frozen revision, **not the later schema**. No commits or pushes were made.

Re-run into a new evidence directory after loading credentials:

```bash
set -a
source .env
set +a
.venv/bin/python results/extraction/determinism-rerun/run.py --out results/extraction/determinism-next
```

The original executed runner is retained as `run-executed.py`; the reusable runner additionally captures all test/helper dependencies and refuses to overwrite an existing evidence directory. Exact per-input CLI form inside the frozen snapshot: `.venv/bin/python -u extract.py <comma-separated briefs> <openapi> det-<a|ab|clean-eom>-<1|2|3>` (use the repository venv's absolute interpreter path from that directory).


Nine fresh extraction runs with the same frozen source and inputs; no simulations or publication. Each run includes the extractor’s independent audit and any validation-triggered repair. Source hashes are in [manifest.json](determinism-rerun/manifest.json); raw policies, audits, and model traces are under [snapshot](determinism-rerun/snapshot/).

Comparison excludes every `source` span and unresolved free text/provenance. Diagnostic unresolved topic labels are reported separately below, outside the policy-difference counts. All other values, including wording, are compared. Effective comparisons apply the frozen `PolicyIR` defaults. Special cases are aligned by name, outcomes by outcome, and bands by range; their original order is compared separately. Other lists retain their order. `<missing>` is represented as `{"__missing__": true}`. Raw-only differences are also reported so omitted defaults are not hidden.

## a

7 effective field differences; 0 additional raw-only differences.

| Run | Exit | Seconds | Reported model cost | Passes |
|---|---:|---:|---:|---|
| [det-a-1](determinism-rerun/det-a-1.log) | 0 | 168.42 | $1.0424 | policy_extraction, policy_audit |
| [det-a-2](determinism-rerun/det-a-2.log) | 0 | 171.12 | $1.0399 | policy_extraction, policy_audit |
| [det-a-3](determinism-rerun/det-a-3.log) | 0 | 175.34 | $1.0558 | policy_extraction, policy_audit |

### Effective fields

| Field | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| `"bands[8..45].attempts[1].floor_if_full_refused"` | `false` | `true` | `false` |
| `"identity.failed_instruction"` | `"Please use the mobile app or visit a branch."` | `"Please use the Freya Bank mobile app or visit a branch."` | `"Please use the mobile app or visit a branch."` |
| `"special_cases[hardship].say"` | `"I am sorry to hear that."` | `"I am very sorry to hear that."` | `"I am sorry to hear that."` |
| `"special_cases[hardship].trigger"` | `"The customer mentions illness, a death in the family or job loss (this takes precedence over persuasion attempts and over a restructuring request)."` | `"The customer mentions illness, a death in the family or job loss."` | `"The customer mentions illness, a death in the family or job loss."` |
| `"special_cases[human].trigger"` | `"The customer asks to speak to a human or a person (before or after verification)."` | `"The customer asks to speak to a human (before or after verification)."` | `"The customer asks to speak to a human (before or after verification)."` |
| `"special_cases[refuse_to_talk].ask_once_first"` | `false` | `true` | `true` |
| `"special_cases[refuse_to_talk].trigger"` | `"The customer says twice that they do not want to talk. Before identity is verified this closes as not_verified / declined instead."` | `"The customer says twice that they do not want to talk. After verification this closes as no_promise / refused; before identity is verified the same customer is closed as not_verified / declined."` | `"The customer says they do not want to talk; the call closes when they say it a second time. Before identity is verified this closes as not_verified / declined."` |

### Raw-only fields (effective values agree)

| Field | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| None | — | — | — |
## ab

15 effective field differences; 0 additional raw-only differences.

| Run | Exit | Seconds | Reported model cost | Passes |
|---|---:|---:|---:|---|
| [det-ab-1](determinism-rerun/det-ab-1.log) | 0 | 176.92 | $1.0604 | policy_extraction, policy_audit |
| [det-ab-2](determinism-rerun/det-ab-2.log) | 0 | 176.8 | $1.0559 | policy_extraction, policy_audit |
| [det-ab-3](determinism-rerun/det-ab-3.log) | 0 | 179.66 | $1.0856 | policy_extraction, policy_audit |

### Effective fields

| Field | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| `"amounts.floor_wording"` | `"The rest stays overdue."` | `"The rest stays overdue."` | `"the rest stays overdue"` |
| `"bands[8..45].attempts[1].floor_if_full_refused"` | `false` | `true` | `true` |
| `"identity.requirements[1].ask_text"` | `"Could you please tell me the last four digits of the phone number we have on file?"` | `"Could you please tell me the last four digits of the phone number on file?"` | `"Could you please tell me the last four digits of the phone number we have on file for you?"` |
| `"outcomes.table[paid].when"` | `"rule 39; with several products, every product noted paid"` | `"rule 39; multi-product: every product noted paid"` | `"rule 39; with several products, every product is noted paid"` |
| `"phrases.all_today_question"` | `"Can you pay all of them today?"` | `"Can you make all of these payments today?"` | `"Can you pay all of them today?"` |
| `"phrases.cannot_answer_sentence"` | `"I do not have that information."` | `"I do not have that information."` | `"I am sorry, I do not have that information."` |
| `"special_cases[already_paid].before_persuasion"` | `false` | `true` | `false` |
| `"special_cases[already_paid].trigger"` | `"The customer says they already paid this past-due amount (for a product)."` | `"The customer says they already paid this past-due amount."` | `"The customer says they already paid this past-due amount."` |
| `"special_cases[cannot_answer].say"` | `"I do not have that information."` | `"I do not have that information."` | `"I am sorry, I do not have that information."` |
| `"special_cases[dispute].before_persuasion"` | `false` | `true` | `false` |
| `"special_cases[hardship].say"` | `"I am sorry to hear that."` | `"I am sorry to hear that."` | `"I am very sorry to hear that."` |
| `"special_cases[human].trigger"` | `"The customer asks to speak to a human."` | `"The customer asks to speak to a human or a person."` | `"The customer asks to speak to a human / a person."` |
| `"special_cases[refuse_to_talk].ask_once_first"` | `true` | `false` | `true` |
| `"special_cases[refuse_to_talk].trigger"` | `"The customer says twice that they do not want to talk (before identity is verified this closes as not_verified / declined)."` | `"The customer says twice that they do not want to talk."` | `"The customer says twice that they do not want to talk."` |
| `"special_cases[robot].trigger"` | `"The customer asks whether they are talking to a robot or an AI."` | `"The customer asks whether they are talking to a robot or an AI."` | `"The customer asks whether they are speaking to a robot or an AI."` |

### Raw-only fields (effective values agree)

| Field | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| None | — | — | — |
## clean-eom

20 effective field differences; 0 additional raw-only differences.

| Run | Exit | Seconds | Reported model cost | Passes |
|---|---:|---:|---:|---|
| [det-clean-eom-1](determinism-rerun/det-clean-eom-1.log) | 0 | 143.02 | $0.9480 | policy_extraction, policy_audit |
| [det-clean-eom-2](determinism-rerun/det-clean-eom-2.log) | 0 | 160.62 | $1.0079 | policy_extraction, policy_audit |
| [det-clean-eom-3](determinism-rerun/det-clean-eom-3.log) | 0 | 146.94 | $0.9615 | policy_extraction, policy_audit |

### Effective fields

| Field | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| `"bands[1..45].name"` | `"1-45"` | `"late_1_45"` | `"late_1_45"` |
| `"outcomes.table[lark_arranged].when"` | `"at least one recorded promise and no transfer"` | `"At least one recorded promise and no transfer."` | `"at least one recorded promise and no transfer"` |
| `"outcomes.table[lark_no_deal].when"` | `"no promise; reason from first non-settled product's note in get_account order"` | `"Otherwise; reason is the first non-settled product's note reason in get_account order."` | `"no promise; reason from first non-settled product's note"` |
| `"outcomes.table[lark_settled].when"` | `"no promise and all products settled"` | `"No promise and all products settled."` | `"all products settled"` |
| `"outcomes.table[lark_transferred].when"` | `"call transferred"` | `"Call transferred; overrides any promise."` | `"call transferred"` |
| `"outcomes.table[lark_unreached].when"` | `"holder not reached"` | `"Holder not reached."` | `"holder not reached"` |
| `"outcomes.table[lark_unverified].when"` | `"identity check failed or declined"` | `"Security check failed or declined."` | `"identity check failed or declined"` |
| `"source_docs"` | `["tests/fixtures/synthetic/clean-eom-brief.md"]` | `["tests/fixtures/synthetic/clean-eom-brief.md", "openapi.json"]` | `["tests/fixtures/synthetic/clean-eom-brief.md"]` |
| `"special_cases.__order__"` | `["already_paid", "dispute", "hardship", "restructuring", "human", "refuse_to_talk", "robot", "scam", "cannot_answer", "change_recorded_promise"]` | `["already_paid", "dispute", "hardship", "restructuring", "human", "refuse_to_talk", "robot", "scam", "cannot_answer", "change_recorded_promise"]` | `["already_paid", "dispute", "hardship", "restructuring", "human", "refuse_to_talk", "robot", "scam", "change_recorded_promise", "cannot_answer"]` |
| `"special_cases[already_paid].trigger"` | `"The customer says they have already paid the overdue amount for a product."` | `"The customer says they have already paid the overdue amount for a product."` | `"The customer says they have already paid the product."` |
| `"special_cases[cannot_answer].before_persuasion"` | `true` | `true` | `false` |
| `"special_cases[cannot_answer].trigger"` | `"The customer asks another question the assistant is unable to answer."` | `"The customer asks another question the assistant is unable to answer."` | `"The customer asks another question the assistant cannot answer."` |
| `"special_cases[change_recorded_promise].trigger"` | `"The customer asks to change a promise that has already been recorded."` | `"The customer asks to change a promise that has already been recorded."` | `"The customer asks to change an already recorded promise."` |
| `"special_cases[dispute].trigger"` | `"The customer says the debt is not theirs, they never held the product, or it was closed or paid off earlier."` | `"The customer says the debt is not theirs, they never held the product, or it was closed or paid off earlier."` | `"The customer says it is not their debt, they never held the product, or it was closed/paid off earlier."` |
| `"special_cases[human].trigger"` | `"The customer asks to speak to a human or a person."` | `"The customer asks to speak to a human or a person."` | `"The customer asks to speak to a human / a person."` |
| `"special_cases[refuse_to_talk].action.outcome"` | `{"__missing__": true}` | `{"__missing__": true}` | `"lark_no_deal"` |
| `"special_cases[refuse_to_talk].action.type"` | `"note"` | `"note"` | `"close"` |
| `"special_cases[refuse_to_talk].trigger"` | `"The customer refuses to talk or continue the call."` | `"The customer refuses to talk or continue the call."` | `"The customer refuses to talk / does not want to continue the conversation."` |
| `"special_cases[restructuring].trigger"` | `"The customer asks to restructure the debt or reduce the instalments."` | `"The customer asks to restructure the debt or reduce instalments."` | `"The customer asks to restructure or reduce instalments."` |
| `"special_cases[robot].trigger"` | `"The customer asks whether this is a robot."` | `"The customer asks whether they are talking to a robot."` | `"The customer asks whether this is a robot."` |

### Raw-only fields (effective values agree)

| Field | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| None | — | — | — |

## Diagnostic unresolved topic labels

These labels are model-authored diagnostic identifiers, not operative rules. Text and provenance are excluded; sorting removes incidental order. They are not included in the policy-field totals.

| Input | Run 1 topics | Run 2 topics | Run 3 topics |
|---|---|---|---|
| a | `["all_today_question", "scam_reply customer service number"]` | `["all_today_question", "missing_date_parts", "scam_reply_phone_number"]` | `["all_today_question", "missing_date_parts"]` |
| ab | `["hardship_multi_product", "missing_date_parts", "no_extra_terms"]` | `["hardship_multi_product", "missing_date_parts"]` | `["calendar.missing_date_parts", "phrases.all_today_question", "special_cases.hardship (multi-product)"]` |
| clean-eom | `["days late outside 1-45"]` | `["bands", "hardship sympathy wording"]` | `["bands"]` |
