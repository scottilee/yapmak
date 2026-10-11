# Static validation performed

Validated with `.venv/bin/python` and bytecode writes disabled. This is fixture validation, not evidence of builder or phone-agent performance.

- 19 standalone packages; 2,279 source-linked expected IR paths resolve against current policy.py dataclass structure. Unsupported behaviors live separately in requirements.json rather than invented IR fields.
- Every JSON/YAML document parses. Native YAML equals the JSON control contract; independently resolved local $refs equal its contract. Seven collection operations exist in each package; the unrelated-endpoint variant has two explicit extras.
- Request/response schemas pass Draft4 schema checks. All oneOf positive/negative samples match their declared validity. Both callback samples fail the intentionally unsatisfiable required-property contract. This is expected and does not make that API usable.
- Outcome/reason enums, product types, per-type floor properties and array limits match the authored expectations. The expanded enum contains 20 types while the product count remains at most 3.
- Calendar oracle deadlines and callback weekday intersections match bankcal computations, including holidays on test clocks. Live promise amounts meet the fixed public floors and dates fall within per-product deadlines.
- The public loader accepts all 13 live cases, with original identities/products/faults/name variables preserved. Callback bounds and ledger uniqueness also pass.
- Process-audit helper was checked only with mocked in-memory inputs: empty/nonempty/missing/malformed degraded, and synthetic credential detection without printing a secret. No real traces were scanned.
- Final authoring review corrected the holder-question placeholder syntax in these new files to `{{title}} {{last_name}}`; document and expected phrase match.

No extractor, compiler workflow generation, builder, simulation, Freya API, commit, clone, or real trace scan was invoked. A passing structural check does not certify policy support, response-field discovery or transcript behavior. See PROCESS.md for the deferred process checks and requirements.json for intentional support gaps.
