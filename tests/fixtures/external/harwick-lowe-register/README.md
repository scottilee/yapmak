# Harwick & Lowe Commercial Bank — un-brief-A package (legal register)

Evaluation package. **Builder input is ONLY** three documents read oldest-last, numbered newest-first: `01-amendment-mail.txt` (Wed 13 Oct 2026), `02-signed-memo.md` (Mon 12 Oct 2026), `03-policy.md` (Mon 5 Oct 2026), plus `openapi.json`. All other files (`README.md`, `expected.json`) are oracle material, never builder input. The bank is fictional; the API host is `.example.invalid`. No public mock customer compatibility is claimed.

## Precedence model (deliberate)

- The three documents conflict only where the memo names the clauses it replaces; the policy states in its header that newer documents win there. The mail S-72 reverses exactly one element — the day restriction of memo item M-3 (callbacks back to `today_or_next_business_day`) — while keeping M-3's `09:00–18:00` hours. All conflicts have stated resolution; nothing is left implicit.
- Memo replaces: identity order (M-1), wrong-answer ceiling 3 → 4 (M-2), callback clause 3.1 (M-3, now corrected by S-72), late-band deadline (M-4).

## Why this package exists (round goal: policies UNLIKE brief A)

Divergences from brief A (expected state of the extracted policy):

1. **Shape.** Up to FIVE facilities (`multi_product.max_products=5`); Monday–Saturday business week, Sunday closed, no holidays (`calendar.business_days=[0..5]`). Field names are deliberately non-English/abbreviated (`ref_no`, `konto_code`, `geburtsdatum`, `postleitzahl`, `facility_id`, `cat`, `outst`, `days_o`, floors `od_min`/`tl_min`/`eq_min`/`cl_min`/`inv_min`) while the agent still speaks English.
2. **Deadlines.** Three bands with three different deadline kinds: (a) `earliest` of nine calendar days and the business month-end (whichever comes first), (b) the 15th of the following month (`day_of_month`), (c) the 20th of the following month after memo M-4 replaced the month-end branch. Late band keeps two persuasion attempts (full on the week-end, floor on the k-date); the other two bands have one attempt.
3. **Document style.** Legal register: numbered clauses, cross-references, definitional preamble, a mod-but-old-school company voice. Plus a scanned-mail style cover and a signed memo.
4. **Vocabulary.** Mixed-case hyphenated codes: outcomes `HL-PAY`, `HL-CLR`, `HL-TR`, `HL-FULL`, `HL-ID`, `HL-MISS`; reasons `hl-refuse`, `hl-distress`, `hl-dispute`, `hl-R07`, `hl-rework`, `hl-person`, `hl-fail`, `hl-decline`, `hl-cb`, `hl-nocb`, `hl-wrong`, `hl-deceased`, `hl-unclear`; queues `hl-rework` and `hl-desk` only. Codes live inside policy clause 11.6, not in a separate sheet.
5. **Hardship different.** No support transfer exists: hardship sets the `hl-distress` note and continues; nothing is offered. (`special_cases.hardship.offer_transfer_queue` stays empty; the extractors that default a support queue here are wrong.)
6. **Notes ON** with one note per unresolved facility, none on transfers, `hl-R07` after a failed retry per facility only.

## expected.json

Same mechanical shape as the synthetic fixture (`checks` with dotted projectable paths + `source`, plus `comparison_notes`). Ordered identity requirements and the three `bands.$rules` assert composition exactly; the outcome table comparison is order-insensitive, as usual. Absent/different rules are stated in `comparison_notes` rather than defaulted.

## Comparing

```
.venv/bin/python tests/fixtures/external/compare_expected.py tests/fixtures/external/harwick-lowe-register <policy.json>
```

## Uncertainties / decisions

- `dates.past_deadline` stays at the template default (`next_business_day`): the M-4 k-date (20th of the next month) and both 7.1(a)/(b) branches can never be in the past relative to `now`, so the policy states no expired rule. Pointed out rather than hidden.
- Clause 7.2(b)'s first attempt date ("last business day of the current week, or of the following week where today is that day") maps to the template's `last_business_day_this_week_or_next` date source; any other mapping should be reviewed manually.
- The "hl-" prefix was chosen hyphenated (mixed case only in `R07`, mirroring the round's vocabulary examples) so case-sensitive extraction is exercised.
- The success "OTC" no other ambiguity: the mail's subject says "one correction" and its body says which one; if a builder applies more of M-3 than the hours, it fails the callback `days` check.
- No probes were pre-simulated; band k-dates for the fixed practice clock (2026-10-14) would be: band (a) `earliest(2026-10-23, 2026-10-31)` = 2026-10-23; band (b) 2026-11-16 is a Monday (business); band (c) 2026-11-20 (Friday, business). Computed with bankcal semantics for a Mon–Sat calendar.
