# GRIMSBY VALE FINANCE — un-brief-A package (call-sheet register)

Evaluation package. **Builder input is ONLY** `01-call-sheet.md`, `02-codes.txt`, in that order, plus `openapi.json`. Everything else (`README.md`, `expected.json`) is oracle material and is never sent to the builder. The bank is fictional; the API host is `.example.invalid`. No public mock customer compatibility is claimed.

## Why this package exists (round goal: policies UNLIKE brief A)

Divergences from brief A — read this list as the expected state of the extracted policy, not as gaps:

1. **Rules absent.** No hardship rule anywhere. No callback rule at all (`third_party.callback.enabled=false`): a relative is told to have the customer ring the bank and the call closes `NOANS`/`CNA`; `schedule_callback` is never called. No notes tool use (`notes.enabled=false`; `add_note` exists in the API but no path calls it). No already-paid rule (the `S8` outcome row is reserved and unreachable). No restructuring rule. No floor *counter-offer*: a below-`bottom_line` amount is simply not recordable (`amounts.floor_offered_once=false`). Zero persuasion: `bands` carry empty `attempts`; one plain refusal ends the call; the agent never proposes an amount or a date (`dates.vague_ask_once_then_deadline=false`, `dates.after_deadline_offer_deadline=false`, `dates.weekend_or_holiday_roll_forward=false`).
2. **Shape.** One product max (`multi_product.max_products=1`). Seven-day business week, no holidays. Deadline is a `day_of_month` rule: the 20th of the month after the call, adjustment `none`.
3. **Document style.** Bullet fragments with abbreviations (internal ops one-pager), not a numbered specification. Second document is a bare code sheet.
4. **Vocabulary.** Mixed-case and numeric codes (`PTP`, `No-PTP`, `ID-F`, `G01`, `G02`, `D60`, `NR`, `DECD`, `CNA`, `HUM`, `R07`, `S8`, queue `GVF-THREAD`). Abbreviated field names (`cust_ref`, `item_id`, `amt_due`, `dl_days`, `min_pmt`, request fields `amt`, renamed `items` array).
5. **Floor rule.** `max_of`: the greater of `min_pmt` and 15 percent of `amt_due`, capped implicitly by the never-above-full bound.
6. **Identity.** Exactly ONE security question (`sec_code`, digits, 4), purpose questions explicitly NOT refusals (`asking_purpose_counts_as_decline=false`).

## expected.json

Same mechanical shape as `tests/fixtures/synthetic/clean-eom-expected.json` (`checks` → dotted projectable paths, each with `source`). Absent rules are expressed inside values (false flags, empty lists) and again in `comparison_notes`, so a diff can treat "absent" as expected rather than as a schema default. `bands.$rules` and `outcomes.$table` follow the same `$`-projection conventions as the synthetic fixtures.

## Comparing

For an extracted policy JSON:
```
.venv/bin/python tests/fixtures/external/compare_expected.py tests/fixtures/external/gv-finance-sheet <policy.json>
```
Only projectable paths are compared; absent rules are asserted by the false/empty values named above and the `comparison_notes` block.

## Uncertainties / decisions

- `dates.past_deadline` is left at the template default (`next_business_day`) because the 20th-of-next-month k-date can never lie before `now`; the call sheet states no expired-rule handling deliberately, so a builder has nothing to read on the topic. Flagged rather than hidden.
- `outcomes.all_paid_closes_as_paid` is kept true as a structural default; with the already-paid rule absent it is unreachable, as recorded in the check's `source`.
- The debt-introduction sentence after verification is deliberately UNFIXED (the sheet says "state amt_due + dl_days flat, no dressing up"), so no `phrases.debt_intro` check is asserted; a builder's own wording is acceptable.
- The customer-facing sentence for "why do you check this" (decline explanation) is left unpinned; only the once-then-close behaviour is asserted.
- Below-`bottom_line` handling is deliberately worded so that an immediate refuse-and-close is expected; a builder that first offers the floor would violate the zero-persuasion line. Judge probes should check for the absence of a second amount offer.
- The `add_note` endpoint carries the two `No-PTP`-family codes purely so the enum lists are non-empty; using it fails the sheet.
