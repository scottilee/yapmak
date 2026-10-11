# Fenbrook Community Credit Union — package (table-only sheet with abbreviated field names)

Synthetic bank invented for this round. The full builder input is `01-call-sheet.md` + `02-codes.md` + `openapi.json`. `expected.json` and this README are oracle material.

## Why this package exists (round goal: policies UNLIKE brief A)

Divergences from brief A — the diff treats each as the expected state of the extracted IR, not as a default:

1. **Shape.** One product only (`multi_product.max_products = 1`), `kind = share_loan`. The deadline pattern is the LATER of (a) the fifth (5th) business day after the call, and (b) the last business day of the current calendar month; encoded as the IR's `latest` kind. For the supplied clock `2026-10-14T11:00`, the k-date resolves to `2026-10-30`.
2. **Calendar.** A seven-day business week (`calendar.business_days = [0..6]`), no shutdown days and no holidays (`calendar.holidays = []`). Roll-forward is irrelevant: every day is already a business day (`weekend_or_holiday_roll_forward = false`).
3. **Document style.** Table-only sheet: the call sheet is a single 49-row table with columns `#` / `Section` / `Rule`. The codes list is a small list of `OUTCOMES` / `QUEUES` / `NOTES` blocks.
4. **Vocabulary.** Mixed-case hyphenated codes: outcomes `CCC-OK`, `CCC-NO`, `CCC-FAIL`, `CCC-TR`; reasons `F-no`, `F-wrong`, `F-unclear`, `F-pin`, `F-dec`, `F-person`; queue `fcc-desk`. Field names are abbreviated: `cust_ref` (customer id), `pi_code` (security answer field), `payment` (create_promise amount), `amt_due` (response past due), `dl_days` (response days late), `minimum` (floor field).
5. **Rules ABSENT.** No callback booking (`third_party.callback.enabled = false`). No `add_note` tool (`notes.enabled = false`). No restructure rule. No "already paid" rule. One persuasion attempt only.
6. **Single security question.** `identity.requirements` has one entry (the 4-digit `pi_code`).

## Notes to schema (matches brief A's IR)

- `dates.weekend_or_holiday_roll_forward = false` because every day is a business day.
- `dates.after_deadline_offer_deadline = false` because the k-date IS the deadline.
- `outcomes.all_paid_closes_as_paid = false` because no `paid_outcome` is defined (the brief has no already-paid path).
- `outcomes.no_promise_reason_from_first_non_paid_note = false` because notes are disabled.
- The `hardship` special case carries an empty `offer_transfer_queue`. The brief says "one short sentence of sympathy, no persuasion, no promise, close `CCC-NO/F-no`"; the IR encodes this as `action = {type: "close", outcome: "CCC-NO", reason: "F-no"}`. The runtime's `_special(hardship)` enters the support-awaiting state when the intent fires; with no transfer queue configured, the next turn's `accepts` or `pays_today` response runs `_transfer('hardship')` which uses the action's outcome (CCC-NO) because the close action is what the brief asks for. The expected outcome is CCC-NO/F-no either way.
- The `refuse_to_talk` special case is absent: the brief treats plain refusals and the second-refusal path identically as `CCC-NO/F-no`, with no separate close-with-refuse outcome. The runtime's standard intent=refuses branch produces the same ledger.

## How a "rules" difference is encoded in the IR

| Brief statement | Package expression |
|---|---|
| One product only | `multi_product.max_products = 1` |
| Seven-day business week | `calendar.business_days = [0..6]`, `calendar.holidays = []` |
| Later of two deadline candidates | `bands[*].deadline.kind = "latest"` with two child rules |
| Single security question | one entry in `identity.requirements` |
| Floor per category | `amounts.floors = {"share_loan": "minimum"}` |
| No callback | `third_party.callback.enabled = false` |
| No notes | `notes.enabled = false`, `notes.reasons = []` |
| Hardship closes without a transfer | `special_cases.hardship.action.type = "close"`, `offer_transfer_queue = ""` |

## Comparing

```
.venv/bin/python tests/fixtures/external/compare_expected.py tests/fixtures/external/fenbrook-table-sheet path/to/extracted.policy.json
```

## Anything I was unsure about

- The `payment` field name for create_promise matches the `"payment"` needle in the amount slot picker. The OpenAPI description says "the amount in create_promise" so an extractor would name it consistently; the compiler maps it onto the IR's `amount` slot.
- The `kind` field in get_account maps to the IR's `account.type` slot via the existing needle (`"kind"` is one of the `account.type` needles in `compiler_openapi._pick`). `share_loan` is the only enum value.
- The `minimum` field in get_account is a floor field; the IR's `amounts.floors` dict references it by name and the runtime looks up `p.get(rule.get("field"))`. There is no automatic `floors.*` → response-slot mapping in the IR; the dict's value is just the API's field name.
- The k-date `latest` rule resolves to the LATER candidate (per `bankcal.deadline` for `kind: latest`). For the supplied clock 2026-10-14, both 5 business days (2026-10-21) and the last business day of October (2026-10-30) are valid business days, so the k-date is 2026-10-30.
- The call sheet row 44 hardship rule is the only "no transfer on hardship" pattern in the kit. The runtime's support-awaiting state still fires when the intent fires; this is documented above and in `comparison_notes` inside `expected.json`. A clean runtime implementation would treat `offer_transfer_queue == ""` as "no support, just close"; the fixture documents the intended behaviour either way.
- The call sheet row 22 debt intro reads "I am calling about the overdue share loan of Fenbrook Community Credit Union."; the compiler's `default_prompts` uses this verbatim when `phrases.debt_intro` is set in the IR.
- The call sheet's `pi_code` security field name is a placeholder for the 4-digit security code; the OpenAPI's `field` enum lists it verbatim and the verify_identity path uses it directly (no name translation is required because the `field` semantic name itself is `field` and the enum value is just an identifier).