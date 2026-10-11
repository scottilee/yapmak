# Aster Quay Mutual hidden-style fixture

Shape: table-heavy single operating specification. Fictional bank and non-routable `.example.invalid` API; intended for offline extraction/compilation evaluation, not the fixed public-customer mock.

Feed **only** `01-tables.md` in that order, with `openapi.json`. Never feed `expected.json`, `expected-api.json`, `date-probes.json` or this README as bank instructions.

Targets: MDY date plus six-digit PIN plus text identity; local two-error counter; Tuesday–Saturday calendar; fixed holiday deadline and preceding calendar-day adjustment; one product, no notes, no retries, no human ask-once and hardship ends the call.

`expected.json` contains 130 effective-rule checks using the existing synthetic projection format. `expected-api.json` covers field mappings outside PolicyIR. `date-probes.json` contains 24 calls and results computed directly with bankcal (no manually calculated expected dates). Outcome reason sets are compared without order; identity and offer order matter. The oracle was authored without running extraction. Exact quoted mandatory sentences are checked; suggested identity question paraphrases and trigger prose need semantic review.

The fixed-deadline campaign is deliberately limited to 14 October–10 November 2026; do not evaluate it after that validity window. add_note remains in the seven-operation API but is explicitly unauthorized for this campaign.

Validation: hand-authored effective values deserialize and pass policy.validate against the exact API enum roles; all date probes are replayable offline. No extractor, builder, simulation or Freya API has been run. Uncertainties: equivalent special-case encodings may need semantic adjudication; this fixture does not assert how a particular model will paraphrase non-mandatory prose.
