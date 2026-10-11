# Kurilian Co-operative Bank — package (bullet fragments + supervisor-mail override)

Synthetic bank invented for this round. The full builder input is `01-call-sheet.md` + `02-codes.txt` + `03-supervisor-mail.txt` + `openapi.json`, read newest-first (the mail is the latest and overrides the sheet on the points it names). `expected.json` and this README are oracle material.

## Why this package exists (round goal: policies UNLIKE brief A)

Divergences from brief A — the diff treats each as the expected state of the extracted IR, not as a default:

1. **Rules ABSENT.** No hardship rule. No `already_paid` rule. No `restructuring` rule. No `refuse_to_talk` rule (refusals close `No-PTP/R07` immediately with no second ask). No callback booking (`third_party.callback.enabled = false`). No `add_note` tool used (`notes.enabled = false`). Zero persuasion attempts in any band (`bands[*].attempts = []`). A single security question (`identity.requirements` has one entry, the 4-digit `sec_code`).
2. **Shape.** One product only (`multi_product.max_products = 1`). A seven-day business week with no shutdown days and no holidays (`calendar.business_days = [0..6]`, `calendar.holidays = []`). There is no k-date / no upper limit on a promise; the deadline is set far in the future (`fixed_date: 2099-12-31`) so the band never governs.
3. **Document style.** Bullet fragments and abbreviations throughout (call sheet, codes file, supervisor mail). The override mail is a single short message that supersedes the full policy sheet.
4. **Vocabulary.** Mixed-case codes with hyphens and abbreviations: outcomes `PTP`, `No-PTP`, `DEC`, `VOID`, `transferred`; reasons `R07`, `F01`, `F02`, `RNG`, `JCB-unclear`, `kcb_person`; queue `kcb_desk`. Field names are abbreviated: `cust_ref` for customer id, `sec_code` for the security answer field, `amt_due` for the past-due amount, `dl_days` for days late, `prod_kind` for product class.

## Notes to schema (matches brief A's IR)

- `outcomes.all_paid_closes_as_paid` is **false** (the brief defines no `paid_outcome`; if it stayed `true`, an empty ledger could close with `paid_outcome=''`). The relevant outcome for any close is either `PTP` (a promise was recorded) or `No-PTP` / `DEC` / `VOID` / `transferred`.
- `outcomes.no_promise_reason_from_first_non_paid_note` is **false** because there are no notes; the no-promise reason is supplied directly by the `No-PTP/R07` path.
- `dates.weekend_or_holiday_roll_forward` is **false** because there are no weekends or holidays; rolling forward would never fire.
- `dates.after_deadline_offer_deadline` is **false** because the brief has no k-date / no upper limit.
- The `third_party.callback.*` fields stay defaulted (`enabled=false`); the outcomes they would have produced fall back to the unclear-holder path.

## How a missing rule is encoded in the IR

| Brief statement | IR expression |
|---|---|
| "no hardship rule" | `special_cases` has no `hardship` entry |
| "no callback" | `third_party.callback.enabled = false` |
| "no notes" | `notes.enabled = false`, `notes.reasons = []` |
| "only the full amount is ever acceptable" | `amounts.floors = {"loan": "amt_due"}` (floor equals full) |
| "zero persuasion attempts" | `bands[*].attempts = []` |
| "single security question" | one entry in `identity.requirements` |
| "no already_paid / restructuring / refuse_to_talk rule" | `special_cases` has none of those entries |
| "seven-day business week" | `calendar.business_days = [0..6]`, `calendar.holidays = []` |

## Comparing

```
.venv/bin/python tests/fixtures/external/compare_expected.py tests/fixtures/external/kurilian-sat-bullets path/to/extracted.policy.json
```

## Anything I was unsure about

- The package uses a single bullet-style brief (`01-call-sheet.md`) and a code list (`02-codes.txt`); the supervisor mail (`03-supervisor-mail.txt`) is short and is meant to be read as the newest authoritative voice. The extractor should treat the mail as overriding only the points it explicitly contradicts; in this case it reinforces the bullet sheet's "one question, no callback, no notes, no transfer except the human-request queue" wording. The mail is also the only document that names the queue `kcb_desk`.
- `add_note`, `schedule_callback` and the second non-transfer queue are still in the OpenAPI with minimal valid responses. This lets `parse_openapi` accept the doc and lets the static check pass without inventing absent paths.
- The IR keeps `all_paid_closes_as_paid = false` even though the default is `true`. With no `paid_outcome`, leaving the default on would let `_finalize` write an empty outcome when a synthetic case slipped a paid note in. Marking it false makes the policy unambiguous.
- The brief says "no hardship rule" but does not say "no dispute rule". Dispute is kept (`action: close, outcome: No-PTP, reason: R07`).
- The `auth: false` in expected.json paths is a path that still appears for slot-mapping completeness; the brief never uses it. Same for `kcb_desk` as the only `transfer_to_agent` queue.
- "Next <weekday>" is interpreted as the following calendar week; bare weekday resolves to the next occurrence on or after today. This matches the brief's wording and the existing `resolve_date_expr` behaviour.