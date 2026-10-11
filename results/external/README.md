# External hidden-style packages (authored by another agent, 11 Oct 02:00 UTC)

`tests/fixtures/external/codex-aster-quay` (table-heavy spec: Tue–Sat business week, MDY dates, 6-digit PIN, three deadline kinds, notes off,
zero retries, hyphenated codes) and `codex-bracken-thread` (newest-first signed mail thread with reversals, four security questions, business
month-end, notes on, every API field renamed). Both OpenAPI files use base properties + `oneOf` refinements.

| package | extraction | oracle mismatches (`compare_expected.py`) | compiled + 14 invariant scenarios × 4 clocks | cost |
|---|---|---|---|---|
| aster | 1 pass + audit, no repair | 1 (`notes.note_each_unpromised_product`: notes are disabled, so inert) | all pass after the fixes below | $1.12 |
| bracken | 1 pass + audit, no repair | 0 | all pass | ~$1.1 |

Round 2 (03:10 UTC): `amber-valley` (mail + policy + two memos + codes) 0 mismatches, 0 unresolved; `codex-cedar-limits` and
`codex-harbor-exceptions` were written with two deliberately unexpressible rules each — the extractor matched everything expressible (cedar 1
inert mismatch, harbor 0) and logged each unsupported rule as `unresolved` with the exact text, instead of guessing. All five compiled
policies pass the 14 invariant scenarios × 4 clocks. Three of the four flagged kinds were then added to the schema (composite deadlines,
no-promise-when-expired, max-of floors); split callback windows and per-field lock remain unsupported by design.

What the packages found (all fixed the same night, after the v23 commit):
1. `parse_openapi` rejected any `allOf/oneOf/anyOf` — a hidden API written like these would have crashed the build before extraction.
   Compositions are now flattened (enum unions; `allOf` adds required, `oneOf` keeps the common required; `not` dropped).
2. Response/request field vocabularies: `facility_ref`/`account_ref` (id), `category` (type), `callback_on`/`callback_at`, `route_key`,
   `closing_code`/`closing_reason` were not recognised by the mappers.
3. Runtime: a bank "not verified" answer without a remaining-attempts field was treated as unreadable and re-asked for ever (aster counts in code).
4. Test harness: the mock bank in `tests/invariants.py` now speaks each API's own field names, so renamed APIs can be checked offline.

Re-run: `.venv/bin/python extract.py <docs> <openapi> ext-<name>` then
`.venv/bin/python -B tests/fixtures/external/compare_expected.py tests/fixtures/external/<pkg> out/ext-<name>.policy.json` and
`.venv/bin/python tests/invariants.py out/ext-<name>.policy.json tests/fixtures/external/<pkg>/openapi.json`.

Round 3 (05:25 UTC): `v24-sable-percent` (clean spec with percent floor + minimum, "15th of next month", earliest-of, end of next month,
no-promise-when-expired) and `v24-tamarisk-thread` (mail thread with a rejected draft, max-of floors): sable 1 inert mismatch (adjustment on a
business-basis month end), tamarisk 0; both extracted policies compile and pass the invariant scenarios; the extractor used every new rule kind
correctly on its first exposure to those phrasings. Both APIs named the verify success flag `accepted`, which the mapper did not know — fixed.
