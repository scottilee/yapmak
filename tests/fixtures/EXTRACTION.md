# Chat-tested extraction inputs for the template

`extraction_schemas.json` contains conversation-node `extraction_schema` arrays,
per-field confidence thresholds, routing examples, evidence links and limitations.
`extraction_adapters.json` supplies the corresponding code snippets; prepend
`bankcal.py` on the build machine. These are tested components, not a complete
production conversation state machine. Adapt routing node names to the template.

- Date values are components, not Freya `type: date`. Consume fields according to
  date_kind, ignoring irrelevant stale values. A vague period goes to clarification.
- Never route on is_set(day), is_set(amount), or extracted digits alone. Require
  the current answer's completeness state and deterministic validation.
- A partial answer can contain a numeric fragment, or leave the previous numeric
  value in vars. Partial-answer tests confirm no processing transition fires.
- Reset numeric fields with numeric sentinels; empty-string resets were ineffective
  for typed amounts. Reset status to absent/pending after consumption.
- Confidence 0.7 worked for the sampled fields except corrected_amount: the correct
  350 was discarded at confidence 0.562. The verified fixture uses 0.5 for that field,
  with code validation and read-back. These are empirical choices, not guarantees.
- Any correction increments the proposal revision, clears confirmed_revision, and
  leaves proposal_complete false until changed values are captured and validated.
  A clear yes only confirms a complete revision. Questions are pending, not yes.
- Four-digit phone validation and day-month-year DOB parsing are practice settings;
  derive them from each brief. The date adapters likewise contain explicit practice
  flags that must be replaced by the extracted calendar policy.
- The retry check shows HTTP 500 may leave bank_ok unset, while API-level rejection
  maps it to false. Clear it to pending before every request so an old success cannot
  be reused. The updated stale-success-seeded chat retest hit a platform HTTP 502;
  the ordinary retry and persistent-rejection paths were observed successfully.

Evidence is in `results/baseline/README.md`. Reproduce checks using
`scripts/extraction_checks.py` and `scripts/bank_chat_checks.py`, which reuse
runtime-check and never start a simulation. Run them serially: each publication
changes the same workflow slot. The separate A+B example-builder baseline uses an
isolated starter-kit directory so its coding agent cannot overwrite template source.
