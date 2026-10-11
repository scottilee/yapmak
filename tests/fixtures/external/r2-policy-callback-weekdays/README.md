# r2-policy-callback-weekdays

Target: weekdays. Read `01-specification.md` with `openapi.json`. This is a standalone package. `expected.json` uses the clean-eom check/source format; `api-expected.json` adds transport assertions/examples. `requirements.json` records semantic obligations that the existing scalar diff cannot certify. `date-oracle.json` uses bankcal; the whole-unit-floor package also has an independent Decimal amount oracle.

Read requirements.json for source-linked semantic/unsupported requirements.

API variants retain r2-api-control policy semantics; the twenty-type variant only expands type/name/floor mappings. Policy variants each change one requested axis. No practice-bank defaults are incorporated. No named special-case rule is absent: already-paid, dispute, hardship, restructuring, human, scam and refusal-to-talk are all present. No active requirement should be inferred from an unused/default schema member.

Differences from Brief A include three identity questions with a format hint, four mixed-deadline bands, different calendar/holidays, products/floors, codes and limits, two retries, immediate human transfer, and no voluntary hardship promise. Privacy and confirmation safeguards are intentionally retained. No policy conflicts exist.

Review caveats: equivalent floor DSL forms and freeform trigger/source spans require semantic review. Passing expected.json alone does not satisfy requirements.json. An explicit unsupported diagnostic is not a passing phone agent. No extraction, build, simulation or Freya API call was run.
