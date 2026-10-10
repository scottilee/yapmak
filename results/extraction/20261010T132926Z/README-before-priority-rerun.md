# Freya intent extraction chat checks

Run: `20261010T132926Z`. **39/1368 scenarios completed**; 17 infrastructure-error attempts (not classification failures). 2 final-label disagreements, including 1 ambiguous/mixed-question probes. Clear-oracle agreement: 35/36. These are single observations, not three-run consistency scores.

**Coverage is incomplete: the requested approximately thirty live phrasings per intent have not been achieved.** The prepared corpus is not evidence of execution. Repeated HTTP 502/503/504 failures interrupted serial batches; each batch stops after three consecutive infrastructure errors.

**Concurrent source change:** `compile.py` changed while the frozen-schema run was in progress. The newer identity enum adds `question`, and read-back descriptions were expanded; those revisions were not tested. [Recorded diff](20261010T132926Z/concurrent-compiler-changes.diff). This task made no edits to `compile.py`.

## Method and limits

- Used only `POST /api/v2/chat/message` on `runtime-check`, with one isolated call per scenario, a greeting to establish the assistant question, and explicit chat end. No simulations or bank calls.
- Snapshot SHA-256: `050a8c620627c1a65b0e0d961fd81d2861b6ba8663e04e62d7cafb8474f5d246`. [Compiler snapshot](20261010T132926Z/compile.snapshot.txt); [exact schemas](20261010T132926Z/schemas.json); [cases](20261010T132926Z/cases.json); [raw results](20261010T132926Z/results.json). The compiler source was not edited.
- Copied complete extraction schemas, enum values, confidence thresholds, and enum transition conditions from the compiled Brief A fixture. Test conversations use fixed stage questions and inert destinations instead of production actions. This isolates extraction; it does not demonstrate production state handling, bank writes, or end-to-end routing.
- Thirty scenarios per semantic value: six base phrasings in each of `in_words`, `pieces`, `corrects`, `talkative`, and `asks_back`, plus boundary controls. These are style transformations of six base phrasings, not thirty independent paraphrases. `none` is a reset sentinel, not a customer intent.
- `pieces` uses separate chat turns. The bulk `corrects` style uses a reformulation cue; boundary probes include actual changed values/intents. `asks_back` adds a hearing question before the substantive answer and is reported separately because the existing descriptions do not define mixed-intent precedence.
- Expected labels were recorded before testing. Ambiguous bare “You tell me” is not counted as a clear error. A final label alone may reflect retained state; the disagreement table records whether the last turn actually extracted it.
- The fixed negotiation offer/read-back is 420 on Friday 16 October 2026; simulated `now` is 14 October at 11:00. Callback questions ask for both day and time. Missing hours must not become invented callback times.

## Observed boundaries

- Bare callback answer **“Morning.” → `other`**, while the expected availability label was `gives_time`. The clock time correctly stayed empty. The description currently specifies a day and/or time without explicitly including day parts; make that intent/completeness distinction explicit. A greeting interpretation is possible, so retain the preceding callback question when reproducing it.
- **“You tell me.” → `question`**; this is underspecified, not proof of a classifier defect. After that, **“What is the smallest amount I can pay?” → `too_much`**. **“You tell me what the deadline means.” → `question`** and **“Can you offer a smaller payment?” → `too_much`** also matched.
- **“Yes, I can pay on Friday the sixteenth.”** and **“Friday the sixteenth, yes, that works.”** both became `accepts` for the matching offer. **“Yes, actually no, I need the twentieth instead.” → `proposes`**.
- Read-back: **“Yes, correct, actually change it to three hundred and fifty.” → `changes`**; **“Do you mean this Friday or next Friday?” → `question`**. These are isolated intent observations, not consent/write-guard validation.
- Callback **“Tomorrow morning.” → “Around eleven.”**, **“Tomorrow.” → “In the morning.” → “Around eleven.”**, and **“Tomorrow around...” → “...eleven in the morning.”** ended at `gives_time`, `11:00`; no hour appeared before the final fragment. This harness retains extraction state; it does not exercise the production callback code’s clearing/reassembly behavior.
- Opening: **“Who is calling?”** and **“Go on, I am listening.”** both became `unclear`.

## Coverage and final intent labels

| Context | Expected intent | Completed / target | Exact matches | In words | Pieces | Corrects | Talkative | Asks back |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| negotiate | accepts | 4 / 30 | 4 | 1/1 | 1/1 | 1/1 | 0/0 | 1/1 |
| negotiate | pays_today | 0 / 30 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| negotiate | proposes | 0 / 30 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| negotiate | refuses | 0 / 30 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| negotiate | too_much | 1 / 30 | 1 | 1/1 | 0/0 | 0/0 | 0/0 | 0/0 |
| negotiate | already_paid | 0 / 30 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| negotiate | dispute | 0 / 30 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| negotiate | hardship | 0 / 30 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| negotiate | restructuring | 0 / 30 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| negotiate | human | 0 / 30 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| negotiate | scam | 0 / 30 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| negotiate | refuses_to_talk | 0 / 30 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| negotiate | question | 0 / 30 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| negotiate | other | 0 / 30 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| opening | confirmed | 5 / 30 | 5 | 2/2 | 0/0 | 1/1 | 1/1 | 1/1 |
| opening | third_party | 1 / 30 | 1 | 1/1 | 0/0 | 0/0 | 0/0 | 0/0 |
| opening | wrong_number | 1 / 30 | 1 | 1/1 | 0/0 | 0/0 | 0/0 | 0/0 |
| opening | deceased | 1 / 30 | 1 | 1/1 | 0/0 | 0/0 | 0/0 | 0/0 |
| opening | wants_human | 1 / 30 | 1 | 1/1 | 0/0 | 0/0 | 0/0 | 0/0 |
| opening | refuses | 1 / 30 | 1 | 1/1 | 0/0 | 0/0 | 0/0 | 0/0 |
| opening | unclear | 1 / 30 | 1 | 1/1 | 0/0 | 0/0 | 0/0 | 0/0 |
| third_party | gives_time | 2 / 30 | 2 | 1/1 | 1/1 | 0/0 | 0/0 | 0/0 |
| third_party | wrong_number | 1 / 30 | 1 | 1/1 | 0/0 | 0/0 | 0/0 | 0/0 |
| third_party | deceased | 1 / 30 | 1 | 1/1 | 0/0 | 0/0 | 0/0 | 0/0 |
| third_party | cannot_say | 0 / 30 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| third_party | refuses | 0 / 30 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| third_party | asks_purpose | 0 / 30 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| third_party | other | 0 / 30 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| identity | answers | 0 / 30 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| identity | declines | 0 / 30 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| identity | asks_purpose | 0 / 30 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| identity | wants_human | 0 / 30 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| identity | refuses_to_talk | 0 / 30 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| identity | other | 0 / 30 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| readback | confirms | 1 / 30 | 1 | 1/1 | 0/0 | 0/0 | 0/0 | 0/0 |
| readback | changes | 0 / 30 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| readback | declines | 0 / 30 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| readback | already_paid | 0 / 30 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| readback | dispute | 0 / 30 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| readback | hardship | 0 / 30 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| readback | restructuring | 0 / 30 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| readback | human | 0 / 30 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| readback | refuses_to_talk | 0 / 30 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| readback | question | 0 / 30 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| readback | other | 0 / 30 | 0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |

## Exact final-label disagreements

Turns are separated with **→**. Expected means the predeclared desired interpretation; mixed/underspecified rows require a precedence decision before being called defects.

| Case / evidence | Style | Exact utterance(s) | Expected | Observed | Last-turn extraction | Assessment |
|---|---|---|---|---|---|---|
| [boundary-09](20261010T132926Z/calls/boundary-09.turns.json) | boundary | “You tell me.” | other | question | question @ 1.0 | mixed/underspecified |
| [boundary-17](20261010T132926Z/calls/boundary-17.turns.json) | boundary | “Morning.” | gives_time | other | other @ 1.0 | label mismatch |

## Boundary controls

| Case | Context | Exact utterance(s) | Expected → observed | Callback time expected → observed |
|---|---|---|---|---|
| boundary-01 | negotiate | You tell me. → What is the smallest amount I can pay? | too_much → too_much | — |
| boundary-02 | negotiate | You tell me what the deadline means. | question → question | — |
| boundary-03 | negotiate | Can you offer a smaller payment? | too_much → too_much | — |
| boundary-04 | negotiate | Yes, I can pay on Friday the sixteenth. | accepts → accepts | — |
| boundary-05 | negotiate | Friday the sixteenth, yes, that works. | accepts → accepts | — |
| boundary-06 | negotiate | Yes, actually no, I need the twentieth instead. | proposes → proposes | — |
| boundary-07 | negotiate | I agree, sorry, no, that is too much; suggest less. | too_much → too_much | — |
| boundary-08 | negotiate | How much did you just say? | question → question | — |
| boundary-09 | negotiate | You tell me. | other → question | — |
| boundary-10 | opening | Who is calling? | unclear → unclear | — |
| boundary-11 | opening | Go on, I am listening. | unclear → unclear | — |
| boundary-12 | readback | Yes, correct, actually change it to three hundred and fifty. | changes → changes | — |
| boundary-13 | readback | Do you mean this Friday or next Friday? | question → question | — |
| boundary-14 | third_party | Tomorrow morning. → Around eleven. | gives_time → gives_time | '11:00' → '11:00'; time check=True |
| boundary-15 | third_party | Tomorrow. → In the morning. → Around eleven. | gives_time → gives_time | '11:00' → '11:00'; time check=True |
| boundary-16 | third_party | Tomorrow around... → ...eleven in the morning. | gives_time → gives_time | '11:00' → '11:00'; time check=True |
| boundary-17 | third_party | Morning. | gives_time → other | '' → ''; time check=True |
| boundary-18 | third_party | Tomorrow at three, sorry, around eleven in the morning. | gives_time → gives_time | '11:00' → '11:00'; time check=True |

## Proposed description wording (not applied or validated)

These are candidate replacements/clarifications for review. Changing a description can shift other classes; repeat the same corpus after any change before treating it as an improvement.

| Field | Proposed wording | Purpose |
|---|---|---|
| `cust_intent` — questions and unclear speech | “`question` means a substantive information request that does not express a more specific payment/special-case intent. A request for a lower payment is `too_much`, even when phrased as a question. Greetings, noise, waiting, and an unfinished or uninterpretable fragment are `other`. Bare ‘you tell me’ needs context; do not infer inability to pay from those words alone.” | Separate generic questions, requests to reduce an amount, and insufficient evidence. |
| `cust_intent` — acceptance/proposal | “`accepts` means agreement to the current offer, including repeating its same amount and/or date. Repeating the offered date does not make it `proposes`. `proposes` means a different or newly volunteered amount/date. `pays_today` means an explicit commitment to pay today/now; merely asking about today is not commitment.” | Remove overlap between accepts and any mention of a date/amount. |
| All intent fields — corrections/mixed speech | “Classify the final intended meaning after explicit corrections; disregard a retracted yes/no or replaced value. A hearing/check-back question does not override an otherwise explicit substantive answer. A substantive question with no clear agreement must never become confirmation.” | Define correction and incidental-question precedence. Apply policy-specific special-case precedence separately. |
| `holder` / `id_intent` | “At the holder check, ‘hello’, ‘go ahead’, ‘I am listening’, and questions are `unclear`, not identity confirmation. For the newer identity enum observed during this run, ordinary questions about purpose/security/robots/scams are `question`; `asks_purpose` requires explicitly withholding an answer until told the purpose. A request to repeat or a hearing problem must not count as a refusal. The frozen older identity enum did not have `question`; do not apply this wording to it without the corresponding enum update. Giving only part of the requested security answer is `answers`, not completion.” | Respect context-specific enums; there is no universal question/unclear value. |
| `tp_intent` | “`gives_time` means any availability information: a day, a clock time, or a part of day such as ‘morning’. It does not imply a complete schedulable slot. ‘Tomorrow morning’ followed by ‘around eleven’ is a continuation of the same availability answer. `cannot_say` means explicit inability to provide availability; silence or an unfinished fragment is `other`.” | Keep intent distinct from callback completeness. |
| `cb_time` | “Extract only an explicitly stated clock time. ‘Morning’ or ‘afternoon’ alone leaves the time empty. ‘Around eleven in the morning’ is `11:00`. A continuation may use the immediately preceding part-of-day context, but never invent an hour from a day part. A correction replaces the earlier hour.” | Avoid guessed callback hours and clarify multi-turn pieces. |
| `rb_intent` | “`confirms` means explicit agreement to the unchanged read-back, including repeating the same amount/date. Any changed amount/date is `changes`, even after ‘yes’ or ‘correct’. A question without unqualified agreement is `question`. An incomplete correction is not confirmation; request completion.” | Prevent stale or premature consent. |

## Infrastructure and reproducibility

17 infrastructure-error attempts were excluded from classifier denominators. Raw error details remain in results.json; retries retain the original attempt. Completed calls and per-turn variables are under `20261010T132926Z/calls/`.

Resume the snapshot with:

```bash
source .env
.venv/bin/python -u scripts/intent_chat_checks.py --resume results/extraction/20261010T132926Z
.venv/bin/python scripts/report_intent_checks.py results/extraction/20261010T132926Z
```
