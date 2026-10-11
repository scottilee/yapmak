# Harbor Glass Cooperative — deliberate schema-gap fixture

Shape: policy plus cover mail, dated signed memo and code list. Feed only `01-mail.txt`, `02-policy.md`, `03-signed-memo.md`, `04-code-list.txt`, in that order, and `openapi.json`. Everything else is evaluation material. The bank and API are fictional; `.example.invalid` prevents accidental live bank use. No public mock customer compatibility is claimed.

This package deliberately contains exactly TWO rules believed to be unexpressible in v23:

**HG-I1**: Keep the global four-wrong-answer ceiling, but a single wrong phone_suffix locks the identity check immediately; a successfully verified field is never requested again. IdentityPolicy has only a global wrong limit; IdentityRequirement has no local limit or stop-after-first-wrong override.

**HG-C1**: Callback today or next business day: Monday through Thursday 09:00–12:00 or 14:00–18:00; Friday 09:00–11:30 only; all endpoints inclusive and strictly after now. CallbackPolicy has a single contiguous start/end interval, no weekday windows or lunch closure.

The remaining requirements use existing rule kinds: four security formats, API global error count, up to three products, notes, ask-once human transfer and product-specific hardship. OpenAPI retains all seven POST tool names with renamed fields, response array and hyphenated codes.

`expected.json` has 132 mechanical checks for supported values plus explicit `unsupported_rules`; `rule-probes.json` has 9 behavioral acceptance probes. `expected-api.json` covers the response/request field mapping outside PolicyIR. Matching supported checks is not a full pass. v23 should at least report both gaps unresolved; v24 must implement the semantics and pass the probes. A missing gap report or an invented approximation is an extraction defect. No approximate policy is supplied as gold truth.

All date values in probes were computed with bankcal; formula amounts use exact Decimal arithmetic. No extraction, build, publication or simulation was used to author the oracle. For future IR comparison use ../compare_expected.py for supported paths, then separately review every unsupported rule and its probes. A future schema may move fields; translate paths deliberately rather than marking changed structure correct automatically.

Uncertainty: the callback rule's per-weekday open intervals and the per-field error ceiling are intentionally outside the present schema and require new deterministic behavior; no claim is made about what a model will choose to omit. The legacy schema checker can validate only the supported skeleton, not the complete bank policy.
