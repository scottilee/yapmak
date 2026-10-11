# Unlike round: live conversation fixtures

`edge-1.json` contains 13 cases, one per fixed public customer. Identity, products, names and inherited faults are copied unchanged; PUB-07 alone changes now. Brief A applies to PUB-01–10; B to PUB-11–13. `dates.json` is a calendar audit, not a runnable case file.

Targets: successive corrections; callback retraction into wrong number; incomplete phone digits; self-corrected amount/deadline; hardship proposal withdrawn for support; withheld hedged consent; this/next Friday self-correction; already-paid claim plus a question; unlisted product question; corrected amount across a write retry; three product dispositions in one sentence; reverse speech order versus ledger precedence; and a revised common earlier date.

These are not the generator's basic happy/refusal/date-change cases. Each script fixes the final customer choice and each check cites the governing A/B rules. A question is not blanket consent: the hedged case explicitly says not to record until the later clear yes. The mortgage is never added to the immutable product list. No contradictory hardship/dispute claims are made about the same product.

Uncertainty: transcript phrasing and turn splitting are model-dependent; no claim of live pass rate is made. Checks constrain bank actions and rule meaning rather than demanding an exact number of clarification turns. The customer repeats complete digits if asked, so either retaining or re-asking the unsolicited fragment can reach the same ledger. No bank rule is absent in these live cases: they retain A/B.

Validation: use only `.venv/bin/python` with `run_synthetic_cases.load_cases` on `edge-1.json`. No simulations, extraction, builds or Freya calls were run. Scoring reference: https://www.freyavoice.ai/hackathon — Outcome is ledger-based; Policy/Honesty use the judge; all three repetitions must pass.
