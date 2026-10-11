# Orrery: narrow mandate and signed override

Read numbered files 01 → 02 → 03; combine them in that order as the raw brief. `openapi.json` has the seven POST operations, renamed requests and `cartera` product responses. `expected.json` uses the clean-eom check/source format; `date-oracle.json` contains bankcal-computed examples.

Differences from Brief A: one security question; one wrong answer; seven-day week without holidays; the twentieth of next month; zero persuasion; full-only amounts; mixed-case/prefixed codes and renamed fields; scanned signed memo overriding four settings. One product and notes-off are explicit but are not counted as differences from A.

Absent rules: hardship, restructuring, already-paid, callbacks and reduced-payment floor. No active notes tool. Third parties receive only a call-back-yourself message, never a scheduled callback. No paid outcome or payment-posting sentence is expected. Missing special-case actions use `{"missing": true}`, which matches the existing diff helper's missing-path result. Disabled callback window values must not be treated as inferred operative rules.

Representation caveat: full-only has a 100% singleton amount interval in the supported floor DSL. The current validator insists on a paid outcome even when the source explicitly has none; the oracle intentionally expects an empty paid_outcome to expose that limitation. No fabricated Paid code should satisfy this fixture. Free prose and source-span equivalence still need semantic review. No unresolved document precedence: signed O-7 wins on precisely four settings.
