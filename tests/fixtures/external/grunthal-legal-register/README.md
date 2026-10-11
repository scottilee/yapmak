# Grunthal Handelsbank AG — package (legal register with foreign field names)

Synthetic bank invented for this round. The full builder input is `01-regulation.md` + `02-codes.md` + `openapi.json`. `expected.json` and this README are oracle material.

## Why this package exists (round goal: policies UNLIKE brief A)

Divergences from brief A — the diff treats each as the expected state of the extracted IR, not as a default:

1. **Shape.** Up to five obligations per debtor (`multi_product.max_products = 5`). Floor field per category is keyed off `categorie` (`darlehen`/`kontokorrent`/`leasing`/`kreditkarte`/`hypothek`), with `kontokorrent` and `kreditkarte` sharing `kk_min`.
2. **Deadline.** Whichever comes first of (a) ten business days after the call and (b) the twentieth (20th) day of the calendar month following the call. Encoded as the IR's `earliest` kind, with one `nth_business_day` and one `day_of_month` child. For the practice clock `2026-10-14T11:00`, the k-date resolves to `2026-10-28` (10 business days wins).
3. **Document style.** Legal register with numbered clauses, cross-references, definitional preamble, a mod-but-old-school company voice.
4. **Vocabulary.** Mixed-case hyphenated codes: outcomes `ghb-arranged`, `ghb-settled`, `ghb-transferred`, `ghb-no-deal`, `ghb-unverified`, `ghb-unreached`; reasons `ghb-rework`, `ghb-person`, `ghb-refuse`, `ghb-distress`, `ghb-dispute`, `ghb-R07`, `ghb-failed`, `ghb-declined`, `ghb-cb`, `ghb-no-cb`, `ghb-wrong`, `ghb-deceased`, `ghb-unclear`; queues `ghb-rework` and `ghb-desk` only. Field names are foreign or abbreviated: `cust_ref` for customer id, `item_id` for product id, `sum` for the promise amount, `amt_due` for the past-due amount, `dl_days` for days late, `tilgung_min`/`kk_min`/`l_min`/`h_min` for floors; the identity fields are German (`kontonummer`, `gruendungsdatum`, `plz`); the wrong-answer remaining-count field is `versuche_verbleibend`.

## Notes to schema (matches brief A's IR)

- `outcomes.no_promise_reason_from_first_non_paid_note = true` (the regulation explicitly states the precedence in clause 11.3: "with the note of the first non-cleared obligation, in account-facility order").
- `dates.weekend_or_holiday_roll_forward = true` because clause 8.3 requires a business day ("a date is recordable when today or later, a business day").
- `dates.after_deadline_offer_deadline = true` (clause 7.5).
- The "every obligation stated before any ask" clause maps to `state_all_before_asking = true`.
- `multi_product.ask_all_today_once` and `per_product_attempts` are kept `true` (the regulation's "counters are per obligation" wording in clause 7.3 is implicit but the multi-product defaults apply).
- The "second refusal closes with `ghb-refuse` on every remaining obligation" path uses `special_cases.refuse_to_talk` with `action.type = "close"` (single-product semantics) and `ends_call = true`. The compiler and runtime do not currently run a multi-product "set every remaining obligation's disposition to `ghb-refuse` and finalize" branch from a refuse-to-talk special case; that is a known limitation noted in the README. The expected `action.type` is `"close"` here because the regulation's clause is described as a call-level action, not as a per-product note.

## How a "rules" difference is encoded in the IR

| Brief A statement | Package 2 expression |
|---|---|
| 47 rules on a single brief A | 12 clauses, German identity field names, abbreviated outcomes |
| bands with two persuasion attempts | one attempt per obligation; full on k-date, floor if full already refused |
| close as `paid` after an already-paid claim | `ghb-cleared` note + close as `ghb-settled` if every obligation is cleared |
| hardship sympathy + support team | hardship sympathy (one short sentence) + `ghb-distress` note + no transfer (per clause 10.3) |
| restructure = lower instalments | clause 8.4 forbids it; the call transfers at once to `ghb-rework` |
| table for the practice mock | fields `cust_ref`, `item_id`, `sum`, `amt_due`, `dl_days` map via the existing needles |

## Comparing

```
.venv/bin/python tests/fixtures/external/compare_expected.py tests/fixtures/external/grunthal-legal-register path/to/extracted.policy.json
```

## Anything I was unsure about

- The "whichever comes first" deadline is encoded as the IR's `earliest` kind with two children; the runtime calls `bankcal.deadline(...)` which iterates the children and returns the minimum ISO date. For the supplied clock 2026-10-14, the result is 2026-10-28 (10 business days), strictly before 2026-11-20 (20th of next month). Other `now` values may flip the order; the IR does not encode the preference between the two children, only that both apply.
- Identity field names in German (`kontonummer`, `gruendungsdatum`, `plz`) are kept verbatim in the verify_identity `field` enum; the runtime does not translate them, the model just lists them in the right order.
- The `_floor_of` path picks the per-category floor from the response; the brief's clause 6.2 is unambiguous that `kontokorrent` and `kreditkarte` share `kk_min`. The compiler's slot mapping accepts both names because the IR `floors` dict is keyed by the brief's category names.
- The "second refusal closes with `ghb-refuse` on every remaining obligation" path is encoded as a `refuse_to_talk` special case with `action.type = "close"` (not `"note"`); the runtime's `_special` for refuse-to-talk closes the call. A real hidden-brief multi-product case that exercises this clause would need either (a) the runtime to extend refuse-to-talk to a per-obligation note or (b) the customer to invoke refuse-to-talk on the last undecided obligation. Either way, this fixture documents the intended behaviour, not a runtime guarantee.
- The `text` field on `add_note` is in the OpenAPI but the regulation does not use it; the request body would carry `text = ""` and the bank system would record nothing extra. Keeping it in the schema lets a future brief that wants notes-with-text plug in without an OpenAPI rewrite.
- `identity.asking_purpose_counts_as_decline` is `false`. The regulation does not address this directly; the schema default (`false`) keeps a "why do you need it?" question from counting as a decline. A reader of the regulation might infer the opposite; the README and the expected JSON call it out.