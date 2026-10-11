# Cedar Reach Savings — deliberate schema-gap fixture

Shape: clean numbered specification. Feed only `01-specification.md`, in that order, and `openapi.json`. Everything else is evaluation material. The bank and API are fictional; `.example.invalid` prevents accidental live bank use. No public mock customer compatibility is claimed.

This package deliberately contains exactly TWO rules believed to be unexpressible in v23:

**CR-D1**: For every contract the deadline is the earlier of the sixth business day after now and the last business day of the current month. If it is earlier than today, take no promise and close cr-none/cr-r-refused. DeadlineRule supports one primitive, not min/composition or an expired-window action.

**CR-A1**: Effective floor = min(full overdue, max(type-specific base minimum, 25% of full overdue rounded UP to the next cent)). AmountPolicy.floors maps product type to one response property; no arithmetic, rounding or cap expression.

The remaining requirements use existing rule kinds: three security formats, local global error count, single product, no notes, immediate human transfer and hardship ending the call. OpenAPI retains all seven POST tool names with renamed fields, response array and hyphenated codes.

`expected.json` has 128 mechanical checks for supported values plus explicit `unsupported_rules`; `rule-probes.json` has 8 behavioral acceptance probes. `expected-api.json` covers the response/request field mapping outside PolicyIR. Matching supported checks is not a full pass. v23 should at least report both gaps unresolved; v24 must implement the semantics and pass the probes. A missing gap report or an invented approximation is an extraction defect. No approximate policy is supplied as gold truth.

All date values in probes were computed with bankcal; formula amounts use exact Decimal arithmetic. No extraction, build, publication or simulation was used to author the oracle. For future IR comparison use ../compare_expected.py for supported paths, then separately review every unsupported rule and its probes. A future schema may move fields; translate paths deliberately rather than marking changed structure correct automatically.

Uncertainty: the composite deadline and rounded percentage floor are intentionally outside the present schema; no claim is made about what a model will choose to omit. The legacy schema checker can validate only the supported skeleton, not the complete bank policy.
