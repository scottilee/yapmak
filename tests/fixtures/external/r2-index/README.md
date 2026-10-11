# Round 2 fixture inventory

The manifest lists 19 standalone packages: one clean hidden-style specification, one API control, nine API variations, and eight policy variations. Each contains its own numbered policy, OpenAPI, expected.json, API expectations, semantic requirements, bankcal examples and README.

The flagship, `../r2-clean-vesper/`, has three ordered identity checks with a format hint, four mixed-deadline bands, holidays overlapping test clocks, Tuesday/Thursday morning callbacks, up to three products with per-type floors, notes on every unpromised product, and reasons on every outcome. Named callback weekdays and successful-close reasons are source-linked support gaps, not silently omitted expectations.

API axes: camelCase; native YAML; nested products; alternate envelope; local $ref components; disjoint oneOf close branches; unrelated endpoints; twenty product types; and a required-but-undefined callback property. That last schema is deliberately unsatisfiable and must be rejected or have callback writes blocked with a diagnostic. All other API variants retain the control policy's semantics.

Policy axes: Sunday–Thursday; no promises today; notes for promised and unpromised products; name placeholders; words forbidden throughout the call; reasons on every close; two morning callback weekdays; and whole-unit percentage rounding. requirements.json describes unsupported/behavioral obligations. Passing the existing IR comparison alone does not certify these packages; degradation is not a runnable-policy pass.

Expected values cite numbered source clauses and are not derived from extraction outputs. Decimal independently checks whole-unit floors; bankcal computes every expected date. Source conflicts are absent. No named special-case rule is absent in this round.

Live cases: `../../edge/r2-personas/`. Deferred process checks: PROCESS.md and process_checks.py. No existing files were edited. No extraction, builds, simulations, or Freya API calls were run.
