# Offline validation record

- Both live files pass `scripts.run_synthetic_cases.load_cases`: 13 + 2 cases, unique customer IDs within each file. Customer identities, names, products and faults match the public records exactly.
- Aster Quay: 130 oracle projection paths deserialize and validate against PolicyIR; 24 date/callback probes replay successfully.
- Bracken: 134 oracle projection paths deserialize and validate against PolicyIR; 20 date/callback probes replay successfully.
- Both APIs contain exactly seven POST operations. Request and response schemas pass JSON Schema Draft 4 schema checks (the compatible subset used here by OpenAPI 3.0). Required properties exist; all operation enum roles and product-field mappings agree with expected-api.json. Valid closing outcome/reason pairs validate; missing required reasons and reasons attached to reasonless outcomes are rejected.
- Effective policies reconstructed from authored oracle values pass policy.validate with exact enum roles. This checks fixture structure, not extraction accuracy. There is no model output or claimed simulation pass rate.

For a future extracted IR, run this read-only comparison from the repo root:

```bash
.venv/bin/python -B tests/fixtures/external/compare_expected.py tests/fixtures/external/codex-aster-quay path/to/extracted.policy.json
```

Use the Bracken package path for its IR. The comparator prints every differing checked value, unresolved entry and structural error. It uses the same projections as the existing synthetic checker. OpenAPI-specific mappings in expected-api.json need separate review because PolicyIR intentionally has no such fields. Suggested identity question phrasing, trigger wording, band labels and source spans are semantic-review items, not exact checks.

No pre-existing file was edited by this fixture-authoring task. Only new edge/external files were written. No extraction, build, simulation or Freya API was invoked.
