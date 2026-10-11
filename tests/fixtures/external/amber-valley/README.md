# Amber Valley Savings hidden-style fixture

This package is a synthetic hidden-brief rehearsal for the builder's extractor.
It is **offline only**: the OpenAPI server URL uses `.example.invalid` and there
are no practice customers, so it cannot accidentally call a real bank.

## What it targets

- **Raw-material parsing**: a cover email, a table-heavy policy, two signed memos
  (one overriding policy settings, the second reversing one override), and a
  separate code list.
- **Conflict resolution**: M-AVS-001 changes identity order, wrong-answer limit,
  late-band deadline and human-transfer behaviour. M-AVS-002 restores the retry
  on `create_promise`. The expected IR must reflect the *effective* rules.
- **OpenAPI normalization flexibility**: paths are prefixed `/avs/`, the success
  flag is renamed `transaction_ok`, `get_account` returns `obligations` with
  `facility_id`/`product_type`/`balance_due`/`delinquency_days`, and the
  remaining-wrong-answers slot is `remaining_attempts`.
- **One unsupported special case**: `payment_plan` asks the agent to negotiate a
  3-month instalment plan. The fixed template cannot support this, so the
  extractor should surface it in `unresolved[]` rather than silently ignore it.

## Files

| File | Purpose |
|---|---|
| `01-mail.txt` | Cover email quoting obsolete historical settings that must not be restored. |
| `02-policy.md` | Main table-heavy policy with all base rules. |
| `03-memo.txt` | M-AVS-001 overrides + M-AVS-002 reversal. |
| `04-codes.txt` | Authoritative outcome/reason/queue/note vocabulary. |
| `openapi.json` | Seven `POST` paths with renamed response fields and prefixed paths. |
| `expected.json` | Expected extraction checks in the same shape as `tests/fixtures/synthetic/clean-eom-expected.json`. |

## Things I was unsure about

- The `other_question` special case is fully supported by the template; only
  `payment_plan` is intentionally unresolved. If the extractor treats any other
  case as unsupported, that is a false positive.
- M-AVS-001 section D removes the human ask-once; M-AVS-002 does not touch it,
  so `special_cases.human.ask_once_first` must be `false`.
- The historical forwarded paragraph in `01-mail.txt` contains values that
  conflict with both the policy and the memos; it should be ignored entirely.
