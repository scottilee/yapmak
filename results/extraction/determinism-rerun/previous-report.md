# Extraction determinism — three audited runs per input

All nine runs exited 0, using `claude-opus-5-5`, with an extraction pass and a fresh audit pass each; none needed validation repair or hit the pass timeout. Total reported model cost: **$11.2676**. Elapsed wall-clock: **730.7 seconds (12.2 minutes)**, running one process per input concurrently and its three repeats sequentially. No simulations, compilation, publication, prompt edits, or production-source edits were performed.

| Input | Effective differing paths | Additional raw-only paths |
|---|---:|---:|
| Brief A | 19 | 18 |
| Brief A + Brief B | 54 | 0 |
| clean-eom | 15 | 13 |

Counts are leaf paths, including wording and order: a missing/renamed special case contributes multiple paths, so these are not counts of independent bugs. Full exact values follow below. Three samples establish observed variance, not its long-run frequency or determinism of fields that happened to agree.

## Prompt fixes to prioritize

1. **A+B overlay precedence:** `already_paid` and `dispute` both flip from `action.type=note`, `ends_call=false` in runs 1/3 to `action.type=close`, `ends_call=true` in run 2. The close outcomes/reasons differ correspondingly. Brief B rule 9 explicitly requires note-and-continue for both. The independent audit did not fix run 2. Suggested instruction: “For each later-document replacement, explicitly check all affected action, reason, and termination fields; a correct source quotation is not sufficient. Product-local paid/dispute handling must not retain a replaced whole-call close action.” These are incorrect IR values, not a measured end-to-end failure; the compiler also contains multi-product safeguards.
2. **Required meaning versus exact wording:** eight `phrases` fields are populated in A+B run 1 but empty in runs 2/3: `opening`, `debt_intro`, `all_today_question`, `already_paid_sentence`, `cannot_answer_sentence`, `recorded_promise_change_reply`, `robot_reply`, and `scam_reply`. Their corresponding `special_cases[*].say` values also vary. These rules often prescribe content without prescribing a literal sentence. Suggested instruction: “Populate every required spoken-content field. Copy explicitly mandated wording exactly; otherwise write a concise faithful sentence, and set `opening_verbatim=false` where wording is free. Do not omit required content merely because no verbatim sentence is supplied.” This matters: the frozen compiler's empty-opening fallback does not name Freya Bank. In Brief A all three runs consistently leave these nonverbatim phrase fields empty, so required spoken content is also stably omitted there, outside the differing-field counts (the all-products question is not required for A alone).
3. **Canonical special-case names and coverage:** A emits `refuse_to_talk_before_verification` in runs 1/2 but omits it in run 3. Rule A45 requires the pre-verification `not_verified / declined` behavior; decide one consistent representation (separate case or an explicit identity rule) and audit it. A+B calls the recorded-promise-change case `change_promise` in run 1 and `change_recorded_promise` in runs 2/3. Extend the canonical-name instruction beyond its current seven examples and prescribe ordering.
4. **Flag semantics:** A+B `before_persuasion` for `already_paid`, `dispute`, `human`, and `restructuring` is `false,false,true`; `refuse_to_talk.ask_once_first` is `true,false,false`. Define whether priority follows explicit “before” wording or also follows immediate-action semantics. Clarify how a two-refusal rule is represented when the trigger itself already says “twice”; do not leave the auditor to choose between trigger wording and a boolean. These are genuine IR flips; current compiler routing may mask some (for example, refusal counting is handled explicitly).
5. **Text and ordering normalization:** clean-eom's operational values agree in all three runs, including four identity checks and `end_of_month/business/preceding`. Its differences are the band name (`1-45` vs `days_1_45`), outcome `when` text (empty vs populated), special-case trigger wording, and ordering. A/A+B also alternate spoken questions with imperative instructions in `ask_text`, `hint_reply`, and `failed_instruction`. Specify one convention for these fields and require consistent presence of optional descriptive fields. Do not spend the first prompt fix on cosmetic wording while the overlay and required-content issues remain.

## Evidence and reproducibility

The snapshot pins `extract.py`, `policy.py`, `compile.py`, `bankcal.py`, `trace.py`, all three input combinations, and their OpenAPI files; all hashes were rechecked unchanged after the runs. The synthetic input uses its matching mutated API. Outputs use nine distinct local extraction slots (`det-a-1..3`, `det-ab-1..3`, `det-clean-eom-1..3`); no Freya workflow slot was touched. Each SDK call starts a fresh context. Model choice and reported tool calls are recorded in the JSONL traces; no cross-run policy reads appear in the logged calls. Slot names differ by design, so prompts differ in output-path text.

[comparison.json](determinism-run/comparison.json) contains machine-readable differences and per-run timings/costs. [compare.py](determinism-run/compare.py) reproduces the tables; [run.py](determinism-run/run.py) records the orchestration used (archive the current results before rerunning, since the runner writes the same paths). Raw policies and audits are in [snapshot/out](determinism-run/snapshot/out), with traces in [snapshot/traces](determinism-run/snapshot/traces). Model-reported cost is not a billing reconciliation.


Nine fresh extraction runs with the same frozen source and inputs; no simulations or publication. Each run includes the extractor’s independent audit and any validation-triggered repair. Source hashes are in [manifest.json](determinism-run/manifest.json); raw policies, audits, and model traces are under [snapshot](determinism-run/snapshot/).

Comparison excludes every `source` span and unresolved free text/provenance. Diagnostic unresolved topic labels are reported separately below, outside the policy-difference counts. All other values, including wording, are compared. Effective comparisons apply the frozen `PolicyIR` defaults. Special cases are aligned by name, outcomes by outcome, and bands by range; their original order is compared separately. Other lists retain their order. `<missing>` is represented as `{"__missing__": true}`. Raw-only differences are also reported so omitted defaults are not hidden.

## a

19 effective field differences; 18 additional raw-only differences.

| Run | Exit | Seconds | Reported model cost | Passes |
|---|---:|---:|---:|---|
| [det-a-1](determinism-run/det-a-1.log) | 0 | 220.82 | $1.3133 | policy_extraction, policy_audit |
| [det-a-2](determinism-run/det-a-2.log) | 0 | 291.02 | $1.6327 | policy_extraction, policy_audit |
| [det-a-3](determinism-run/det-a-3.log) | 0 | 218.82 | $1.3374 | policy_extraction, policy_audit |

### Effective fields

| Field | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| `"identity.requirements[0].ask_text"` | `"Ask for the customer's date of birth."` | `"What is your date of birth?"` | `"Ask for the customer's date of birth."` |
| `"identity.requirements[0].hint_reply"` | `"Ask them to say the month as a word."` | `"Please say the month as a word."` | `"Ask them to say the month as a word."` |
| `"identity.requirements[1].ask_text"` | `"Ask for the last four digits of the phone number on file."` | `"What are the last four digits of the phone number on file?"` | `"Ask for the last four digits of the phone number on file."` |
| `"special_cases.__order__"` | `["already_paid", "dispute", "hardship", "restructuring", "human", "scam", "robot", "refuse_to_talk", "refuse_to_talk_before_verification", "cannot_answer", "change_recorded_promise"]` | `["already_paid", "dispute", "hardship", "restructuring", "human", "scam", "robot", "refuse_to_talk", "refuse_to_talk_before_verification", "cannot_answer", "change_recorded_promise"]` | `["already_paid", "dispute", "hardship", "restructuring", "human", "scam", "robot", "refuse_to_talk", "cannot_answer", "change_recorded_promise"]` |
| `"special_cases[human].trigger"` | `"The customer asks to speak to a human (before or after verification)."` | `"The customer asks to speak to a human."` | `"The customer asks to speak to a human."` |
| `"special_cases[refuse_to_talk].trigger"` | `"The customer says twice, after identity is verified, that they do not want to talk."` | `"After identity is verified, the customer says twice that they do not want to talk."` | `"The customer says twice that they do not want to talk (before identity is verified this closes as not_verified / declined)."` |
| `"special_cases[refuse_to_talk_before_verification].action.outcome"` | `"not_verified"` | `"not_verified"` | `{"__missing__": true}` |
| `"special_cases[refuse_to_talk_before_verification].action.reason"` | `"declined"` | `"declined"` | `{"__missing__": true}` |
| `"special_cases[refuse_to_talk_before_verification].action.type"` | `"close"` | `"close"` | `{"__missing__": true}` |
| `"special_cases[refuse_to_talk_before_verification].ask_once_first"` | `false` | `false` | `{"__missing__": true}` |
| `"special_cases[refuse_to_talk_before_verification].before_persuasion"` | `false` | `false` | `{"__missing__": true}` |
| `"special_cases[refuse_to_talk_before_verification].ends_call"` | `true` | `true` | `{"__missing__": true}` |
| `"special_cases[refuse_to_talk_before_verification].name"` | `"refuse_to_talk_before_verification"` | `"refuse_to_talk_before_verification"` | `{"__missing__": true}` |
| `"special_cases[refuse_to_talk_before_verification].offer_outcome"` | `["", ""]` | `["", ""]` | `{"__missing__": true}` |
| `"special_cases[refuse_to_talk_before_verification].offer_transfer_queue"` | `""` | `""` | `{"__missing__": true}` |
| `"special_cases[refuse_to_talk_before_verification].say"` | `""` | `""` | `{"__missing__": true}` |
| `"special_cases[refuse_to_talk_before_verification].takes_promise"` | `false` | `false` | `{"__missing__": true}` |
| `"special_cases[refuse_to_talk_before_verification].trigger"` | `"The customer says twice, before identity is verified, that they do not want to talk."` | `"Before identity is verified, the customer says twice that they do not want to talk."` | `{"__missing__": true}` |
| `"special_cases[robot].trigger"` | `"The customer asks whether they are talking to a robot or an AI."` | `"The customer asks whether they are speaking to a robot or an AI."` | `"The customer asks whether they are speaking to a robot or an AI."` |

### Raw-only fields (effective values agree)

| Field | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| `"special_cases[already_paid].offer_outcome"` | `["", ""]` | `{"__missing__": true}` | `["", ""]` |
| `"special_cases[already_paid].offer_transfer_queue"` | `""` | `{"__missing__": true}` | `""` |
| `"special_cases[cannot_answer].offer_outcome"` | `["", ""]` | `{"__missing__": true}` | `["", ""]` |
| `"special_cases[cannot_answer].offer_transfer_queue"` | `""` | `{"__missing__": true}` | `""` |
| `"special_cases[change_recorded_promise].offer_outcome"` | `["", ""]` | `{"__missing__": true}` | `["", ""]` |
| `"special_cases[change_recorded_promise].offer_transfer_queue"` | `""` | `{"__missing__": true}` | `""` |
| `"special_cases[dispute].offer_outcome"` | `["", ""]` | `{"__missing__": true}` | `["", ""]` |
| `"special_cases[dispute].offer_transfer_queue"` | `""` | `{"__missing__": true}` | `""` |
| `"special_cases[human].offer_outcome"` | `["", ""]` | `{"__missing__": true}` | `["", ""]` |
| `"special_cases[human].offer_transfer_queue"` | `""` | `{"__missing__": true}` | `""` |
| `"special_cases[refuse_to_talk].offer_outcome"` | `["", ""]` | `{"__missing__": true}` | `["", ""]` |
| `"special_cases[refuse_to_talk].offer_transfer_queue"` | `""` | `{"__missing__": true}` | `""` |
| `"special_cases[restructuring].offer_outcome"` | `["", ""]` | `{"__missing__": true}` | `["", ""]` |
| `"special_cases[restructuring].offer_transfer_queue"` | `""` | `{"__missing__": true}` | `""` |
| `"special_cases[robot].offer_outcome"` | `["", ""]` | `{"__missing__": true}` | `["", ""]` |
| `"special_cases[robot].offer_transfer_queue"` | `""` | `{"__missing__": true}` | `""` |
| `"special_cases[scam].offer_outcome"` | `["", ""]` | `{"__missing__": true}` | `["", ""]` |
| `"special_cases[scam].offer_transfer_queue"` | `""` | `{"__missing__": true}` | `""` |
## ab

54 effective field differences; 0 additional raw-only differences.

| Run | Exit | Seconds | Reported model cost | Passes |
|---|---:|---:|---:|---|
| [det-ab-1](determinism-run/det-ab-1.log) | 0 | 229.44 | $1.3565 | policy_extraction, policy_audit |
| [det-ab-2](determinism-run/det-ab-2.log) | 0 | 232.51 | $1.3516 | policy_extraction, policy_audit |
| [det-ab-3](determinism-run/det-ab-3.log) | 0 | 223.45 | $1.2931 | policy_extraction, policy_audit |

### Effective fields

| Field | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| `"identity.failed_instruction"` | `"Please use the mobile app or a branch."` | `"Tell the customer to use the mobile app or a branch."` | `"Tell the customer to use the mobile app or a branch."` |
| `"identity.requirements[0].ask_text"` | `"Could you tell me your date of birth?"` | `"Could you tell me your date of birth?"` | `"Could you please tell me your date of birth?"` |
| `"identity.requirements[0].hint_reply"` | `"Could you say the month as a word?"` | `"Ask them to say the month as a word."` | `"Could you please say the month as a word?"` |
| `"identity.requirements[1].ask_text"` | `"Could you tell me the last four digits of the phone number on file?"` | `"Could you tell me the last four digits of the phone number on file?"` | `"Could you please tell me the last four digits of the phone number we have on file for you?"` |
| `"outcomes.table[paid].when"` | `"rule 39; Brief B: every product noted paid"` | `"rule 39"` | `"rule 39; Brief B: no promise recorded and every product noted paid"` |
| `"phrases.all_today_question"` | `"Can you pay all of them today?"` | `""` | `""` |
| `"phrases.already_paid_sentence"` | `"Payments can take one business day to appear."` | `""` | `""` |
| `"phrases.cannot_answer_sentence"` | `"I do not have that information."` | `""` | `""` |
| `"phrases.debt_intro"` | `"I am calling from the collections team about a late payment."` | `""` | `""` |
| `"phrases.opening"` | `"I am a digital assistant calling from Freya Bank, and this call is recorded."` | `""` | `""` |
| `"phrases.recorded_promise_change_reply"` | `"You can change it in the mobile app."` | `""` | `""` |
| `"phrases.robot_reply"` | `"I am Freya Bank's digital assistant."` | `""` | `""` |
| `"phrases.scam_reply"` | `"You can verify this call by phoning Freya Bank's customer service number."` | `""` | `""` |
| `"special_cases.__order__"` | `["already_paid", "dispute", "hardship", "restructuring", "human", "scam", "robot", "refuse_to_talk", "change_promise", "cannot_answer"]` | `["already_paid", "dispute", "hardship", "restructuring", "human", "scam", "robot", "refuse_to_talk", "cannot_answer", "change_recorded_promise"]` | `["already_paid", "dispute", "hardship", "restructuring", "human", "scam", "robot", "refuse_to_talk", "cannot_answer", "change_recorded_promise"]` |
| `"special_cases[already_paid].action.outcome"` | `{"__missing__": true}` | `"paid"` | `{"__missing__": true}` |
| `"special_cases[already_paid].action.reason"` | `"paid"` | `""` | `"paid"` |
| `"special_cases[already_paid].action.type"` | `"note"` | `"close"` | `"note"` |
| `"special_cases[already_paid].before_persuasion"` | `false` | `false` | `true` |
| `"special_cases[already_paid].ends_call"` | `false` | `true` | `false` |
| `"special_cases[already_paid].say"` | `"Payments can take one business day to appear."` | `""` | `""` |
| `"special_cases[cannot_answer].say"` | `"I do not have that information."` | `""` | `""` |
| `"special_cases[change_promise].action.type"` | `"continue"` | `{"__missing__": true}` | `{"__missing__": true}` |
| `"special_cases[change_promise].ask_once_first"` | `false` | `{"__missing__": true}` | `{"__missing__": true}` |
| `"special_cases[change_promise].before_persuasion"` | `false` | `{"__missing__": true}` | `{"__missing__": true}` |
| `"special_cases[change_promise].ends_call"` | `false` | `{"__missing__": true}` | `{"__missing__": true}` |
| `"special_cases[change_promise].name"` | `"change_promise"` | `{"__missing__": true}` | `{"__missing__": true}` |
| `"special_cases[change_promise].offer_outcome"` | `["", ""]` | `{"__missing__": true}` | `{"__missing__": true}` |
| `"special_cases[change_promise].offer_transfer_queue"` | `""` | `{"__missing__": true}` | `{"__missing__": true}` |
| `"special_cases[change_promise].say"` | `"You can change it in the mobile app."` | `{"__missing__": true}` | `{"__missing__": true}` |
| `"special_cases[change_promise].takes_promise"` | `false` | `{"__missing__": true}` | `{"__missing__": true}` |
| `"special_cases[change_promise].trigger"` | `"The customer asks to change or cancel a promise that was already recorded."` | `{"__missing__": true}` | `{"__missing__": true}` |
| `"special_cases[change_recorded_promise].action.type"` | `{"__missing__": true}` | `"continue"` | `"continue"` |
| `"special_cases[change_recorded_promise].ask_once_first"` | `{"__missing__": true}` | `false` | `false` |
| `"special_cases[change_recorded_promise].before_persuasion"` | `{"__missing__": true}` | `false` | `false` |
| `"special_cases[change_recorded_promise].ends_call"` | `{"__missing__": true}` | `false` | `false` |
| `"special_cases[change_recorded_promise].name"` | `{"__missing__": true}` | `"change_recorded_promise"` | `"change_recorded_promise"` |
| `"special_cases[change_recorded_promise].offer_outcome"` | `{"__missing__": true}` | `["", ""]` | `["", ""]` |
| `"special_cases[change_recorded_promise].offer_transfer_queue"` | `{"__missing__": true}` | `""` | `""` |
| `"special_cases[change_recorded_promise].say"` | `{"__missing__": true}` | `""` | `""` |
| `"special_cases[change_recorded_promise].takes_promise"` | `{"__missing__": true}` | `false` | `false` |
| `"special_cases[change_recorded_promise].trigger"` | `{"__missing__": true}` | `"The customer asks to change or cancel a promise that was already recorded in this call."` | `"The customer asks to change or cancel a promise already recorded in this call."` |
| `"special_cases[dispute].action.outcome"` | `{"__missing__": true}` | `"no_promise"` | `{"__missing__": true}` |
| `"special_cases[dispute].action.type"` | `"note"` | `"close"` | `"note"` |
| `"special_cases[dispute].before_persuasion"` | `false` | `false` | `true` |
| `"special_cases[dispute].ends_call"` | `false` | `true` | `false` |
| `"special_cases[dispute].trigger"` | `"The customer says the debt is not theirs, they never had this product, or the product was closed or paid off in the past."` | `"The customer says the debt is not theirs, they never had this product, or the product was closed or paid off in the past."` | `"The customer says the debt is not theirs, that they never had this product, or that the product was closed or paid off in the past."` |
| `"special_cases[human].before_persuasion"` | `false` | `false` | `true` |
| `"special_cases[human].trigger"` | `"The customer asks to speak with a human."` | `"The customer asks to speak to a human."` | `"The customer asks to speak to a human. Applies before and after verification."` |
| `"special_cases[refuse_to_talk].ask_once_first"` | `true` | `false` | `false` |
| `"special_cases[refuse_to_talk].trigger"` | `"The customer says twice that they do not want to talk."` | `"The customer says twice that they do not want to talk (before verification this closes as not_verified / declined)."` | `"The customer says twice that they do not want to talk. Before identity is verified this closes as not_verified / declined instead."` |
| `"special_cases[restructuring].before_persuasion"` | `false` | `false` | `true` |
| `"special_cases[robot].say"` | `"I am Freya Bank's digital assistant."` | `""` | `""` |
| `"special_cases[robot].trigger"` | `"The customer asks whether they are speaking with a robot or an AI."` | `"The customer asks whether they are speaking to a robot or an AI."` | `"The customer asks whether they are talking to a robot or an AI."` |
| `"special_cases[scam].say"` | `"You can verify this call by phoning Freya Bank's customer service number."` | `""` | `""` |

### Raw-only fields (effective values agree)

| Field | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| None | — | — | — |
## clean-eom

15 effective field differences; 13 additional raw-only differences.

| Run | Exit | Seconds | Reported model cost | Passes |
|---|---:|---:|---:|---|
| [det-clean-eom-1](determinism-run/det-clean-eom-1.log) | 0 | 114.4 | $0.8581 | policy_extraction, policy_audit |
| [det-clean-eom-2](determinism-run/det-clean-eom-2.log) | 0 | 188.94 | $1.2232 | policy_extraction, policy_audit |
| [det-clean-eom-3](determinism-run/det-clean-eom-3.log) | 0 | 132.03 | $0.9018 | policy_extraction, policy_audit |

### Effective fields

| Field | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| `"bands[1..45].name"` | `"1-45"` | `"days_1_45"` | `"1-45"` |
| `"outcomes.table[lark_arranged].when"` | `""` | `"at least one recorded promise and no transfer"` | `"at least one recorded promise and no transfer"` |
| `"outcomes.table[lark_no_deal].when"` | `""` | `"no promise; reason is first non-settled product's note reason in get_account order"` | `"no promise; reason is the first non-settled product's note reason in get_account order"` |
| `"outcomes.table[lark_settled].when"` | `""` | `"all products settled"` | `"no promise and all products settled"` |
| `"outcomes.table[lark_transferred].when"` | `""` | `"call transferred"` | `"call transferred"` |
| `"outcomes.table[lark_unreached].when"` | `""` | `"holder not reached"` | `"holder not reached"` |
| `"outcomes.table[lark_unverified].when"` | `""` | `"identity check failed or declined"` | `"identity check failed or declined"` |
| `"special_cases.__order__"` | `["already_paid", "dispute", "hardship", "restructuring", "human", "refuse_to_talk", "robot", "scam", "cannot_answer", "change_recorded_promise"]` | `["already_paid", "dispute", "hardship", "restructuring", "human", "refuse_to_talk", "robot", "scam", "change_recorded_promise", "cannot_answer"]` | `["already_paid", "dispute", "hardship", "restructuring", "human", "refuse_to_talk", "robot", "scam", "change_recorded_promise", "cannot_answer"]` |
| `"special_cases[cannot_answer].trigger"` | `"The customer asks another question the assistant cannot answer."` | `"The customer asks another question the assistant is unable to answer."` | `"The customer asks another question the assistant cannot answer."` |
| `"special_cases[change_recorded_promise].trigger"` | `"The customer asks to change an already recorded promise."` | `"The customer asks to change an already recorded promise."` | `"The customer asks to change a promise that has already been recorded."` |
| `"special_cases[dispute].trigger"` | `"The customer says it is not their debt, they never held the product, or it was closed or paid off earlier."` | `"The customer says it is not their debt, they never held the product, or it was closed or paid off earlier."` | `"The customer says the debt is not theirs, they never held the product, or it was closed or paid off earlier."` |
| `"special_cases[human].trigger"` | `"The customer asks to speak to a human / a person."` | `"The customer asks to speak to a human."` | `"The customer asks to speak to a human or a person."` |
| `"special_cases[refuse_to_talk].trigger"` | `"The customer refuses to talk / does not want to continue the call."` | `"The customer refuses to talk or continue the call."` | `"The customer refuses to talk or continue the call."` |
| `"special_cases[restructuring].trigger"` | `"The customer asks to restructure or reduce instalments."` | `"The customer asks to restructure or reduce instalments."` | `"The customer asks to restructure the debt or reduce instalments."` |
| `"special_cases[scam].trigger"` | `"The customer asks whether this call is a scam."` | `"The customer asks whether the call is a scam."` | `"The customer asks whether this call is a scam."` |

### Raw-only fields (effective values agree)

| Field | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| `"special_cases[already_paid].ask_once_first"` | `{"__missing__": true}` | `false` | `false` |
| `"special_cases[cannot_answer].ask_once_first"` | `{"__missing__": true}` | `false` | `{"__missing__": true}` |
| `"special_cases[cannot_answer].takes_promise"` | `{"__missing__": true}` | `false` | `{"__missing__": true}` |
| `"special_cases[change_recorded_promise].ask_once_first"` | `{"__missing__": true}` | `false` | `{"__missing__": true}` |
| `"special_cases[change_recorded_promise].before_persuasion"` | `{"__missing__": true}` | `false` | `{"__missing__": true}` |
| `"special_cases[change_recorded_promise].takes_promise"` | `{"__missing__": true}` | `false` | `{"__missing__": true}` |
| `"special_cases[dispute].ask_once_first"` | `{"__missing__": true}` | `false` | `false` |
| `"special_cases[hardship].ask_once_first"` | `{"__missing__": true}` | `false` | `false` |
| `"special_cases[restructuring].ask_once_first"` | `{"__missing__": true}` | `false` | `false` |
| `"special_cases[robot].ask_once_first"` | `{"__missing__": true}` | `false` | `{"__missing__": true}` |
| `"special_cases[robot].takes_promise"` | `{"__missing__": true}` | `false` | `{"__missing__": true}` |
| `"special_cases[scam].ask_once_first"` | `{"__missing__": true}` | `false` | `{"__missing__": true}` |
| `"special_cases[scam].takes_promise"` | `{"__missing__": true}` | `false` | `{"__missing__": true}` |

## Diagnostic unresolved topic labels

These labels are model-authored diagnostic identifiers, not operative rules. Text and provenance are excluded; sorting removes incidental order. They are not included in the policy-field totals.

| Input | Run 1 topics | Run 2 topics | Run 3 topics |
|---|---|---|---|
| a | `["calendar.missing_date_parts", "no_ir_field.change_at_confirmation", "no_ir_field.hardship_before_restructuring", "no_ir_field.holder_question_after_customer_question", "no_ir_field.no_invention", "no_ir_field.no_other_terms", "no_ir_field.no_repeat_refused_offer", "no_ir_field.proposal_not_refusal", "no_ir_field.relative", "phrases.all_today_question", "phrases.already_paid_sentence", "phrases.cannot_answer_sentence", "phrases.debt_intro", "phrases.opening", "phrases.recorded_promise_change_reply", "phrases.robot_reply", "phrases.scam_reply", "special_cases.hardship.say"]` | `["calendar.missing_date_parts", "phrases.all_today_question", "phrases.already_paid_sentence", "phrases.cannot_answer_sentence", "phrases.debt_intro", "phrases.opening", "phrases.recorded_promise_change_reply", "phrases.robot_reply", "phrases.scam_reply", "prohibited_offers", "special_cases.hardship.precedence_over_restructuring", "special_cases.hardship.say"]` | `["calendar.missing_date_parts", "phrases.already_paid_sentence", "phrases.cannot_answer_sentence", "phrases.debt_intro", "phrases.opening", "phrases.recorded_promise_change_reply", "phrases.robot_reply", "phrases.scam_reply", "special_cases priority", "special_cases.hardship.say"]` |
| ab | `["calendar.missing_date_parts", "identity.ask_text", "identity.failed_instruction", "identity.requirements.hint_reply", "negotiation rules without IR fields", "phrases.all_today_question", "phrases.debt_intro", "phrases.opening", "phrases.robot_reply/scam_reply/already_paid_sentence/cannot_answer_sentence/recorded_promise_change_reply", "prohibited offers", "special_cases.hardship precedence over restructuring", "special_cases.hardship/refuse_to_talk in multi-product calls", "special_cases.refuse_to_talk two-strike", "third_party relative restrictions"]` | `["calendar.missing_date_parts", "outcomes.transfer_overrides_promise", "phrases.all_today_question", "phrases.already_paid_sentence", "phrases.cannot_answer_sentence", "phrases.debt_intro", "phrases.opening", "phrases.recorded_promise_change_reply", "phrases.robot_reply", "phrases.scam_reply", "special_cases.hardship (multi-product)"]` | `["calendar.missing_date_parts", "outcomes.transfer_overrides_promise", "phrases.all_today_question", "phrases.already_paid_sentence", "phrases.cannot_answer_sentence", "phrases.debt_intro", "phrases.opening", "phrases.recorded_promise_change_reply", "phrases.robot_reply", "phrases.scam_reply", "special_cases.hardship.ends_call", "special_cases.hardship.say"]` |
| clean-eom | `["bands beyond 45 days late"]` | `["bands"]` | `["bands", "hardship sympathy sentence"]` |
