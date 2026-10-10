# IR permutation sweep

`scripts/permute_policies.py --run --n 40 --seed 7` generates 40 policy IRs by permuting the public rule *kinds* of the
practice policy (never hidden content) together with a matching mutated OpenAPI, compiles each with the real compiler,
and runs `tests/invariants.py` on the result against a mock bank whose answers follow the generated policy.

Permuted per policy: identity sets (1–4 questions; date / digits 4-6-8 / year / text; numeric date order), wrong-answer
limit 2–5, calendars (incl. "today is a holiday", Saturday as a business day, Mon–Thu weeks), 1–3 bands with deadline
kinds nth_business_day / calendar_days (following or preceding) / end_of_month (business or calendar basis) / fixed_date,
one or two persuasion attempts, product sets with differently named floor properties, max_products 1–4, notes on/off,
three outcome/reason/queue vocabularies (incl. hyphenated codes), callback windows, create_promise retry 0/1/2,
human-case ask-once on/off.

Scenarios per policy (expected values computed from the IR via bankcal): happy path (pay today, or the next business day
when today is not one), refusal ladder, hardship then decline support, third party with callback, wrong identity until
exhausted, dispute on product 1 + promise on product 2, create_promise failing twice. Structural invariants on every
run: close_call exactly once and last, no get_account before all identity questions pass, no write without a
confirmation, bodies valid against the OpenAPI, promise dates not in the past, the reason omitted/required per the outcome table.

Result: **40 / 40 pass** (`summary.json`). The sweep found one runtime gap, now fixed in `workflow_runtime.py`:
"I can pay today" when today is a weekend/holiday discarded the roll-forward offer and fell through to the generic
attempt-1 date; it now offers the next business day as rule 20 says. Not reachable with the public `now` (a Wednesday).

Regenerate: `.venv/bin/python scripts/permute_policies.py --run` (about 2 minutes, offline). The generated
`perm-*.json` files are git-ignored; `summary.json` is kept.
