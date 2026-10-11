# v23 independent review and v24 inputs

Reviewed `e870198` (v22) → `70ce3b4` (v23), already committed before this task. No commit or push was made.

- [Rule-kind census](rule-kind-census.md): 15 ranked gaps, current behavior and recommended v24 scope.
- [Regression review](review.md): four reproducible behavioral changes plus incomplete goodbye handling. All 113 existing offline tests still pass.
- [Pure runtime probes](runtime-probes.json), rerunnable with `.venv/bin/python -B results/audit/v23-independent-70ce3b4/reproduce.py`.
- [Judge-wording check](judge-wording.md): exact risky strings, pre-existing versus newly added, and proposed replacements.
- New fixtures: `tests/fixtures/external/codex-cedar-limits/` and `tests/fixtures/external/codex-harbor-exceptions/`, with two deliberate schema gaps each. They have complete bank documents and seven-operation OpenAPIs, supported-value oracles and behavioral gap probes.

Scope restrictions honored: no pipeline-file edits, no writes under repository out/, no simulations, no model/extractor/build runs. No publication was attempted while clarification of the requested hidden-1/hidden-2 publication versus those restrictions remained pending. These deliberately unsupported fixtures are v24 evaluation inputs, not claimed correct generated phone agents.
