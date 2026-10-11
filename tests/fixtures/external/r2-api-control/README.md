# r2-api-control

Target: control. Standalone clean specification in `01-specification.md`; API is `openapi.json`. `expected.json` retains the clean-eom check/source format. `api-expected.json` states transport expectations; `requirements.json` states additional semantic/behavioral expectations. `date-oracle.json` contains bankcal-derived values, not live personas.

Policy control: no intentionally unsupported policy rule.

Absent rules: none of the seven named special cases are omitted. This campaign retains paid, dispute, hardship, restructuring, human, scam and refusal-to-talk rules. Differences from Brief A include three security questions, an API format-hint exception, four bands with mixed deadlines, Saturday operations (or Sunday–Thursday in that isolated variant), different holidays/limits/codes, per-type products/floors, two write retries, immediate human transfer and no voluntary hardship promises. The flagship also imposes named callback weekdays and a reason for every close. Shared identity and write-safety behaviors intentionally remain; “values changed” does not mean negating privacy or consent rules.

API-only variants share r2-api-control's policy semantics; only the named transport axis changes. For whole-unit floors, historical minimum fields in the API are informational and cannot replace the formula. For missing-property input, even an invented routing_token fails the closed request schema. No source conflict or implied fallback exists.

Review limits: literal phrase placeholders and freeform trigger/source-span equivalence need semantic review. Expected unsupported behavior must remain visible rather than being counted as a passing agent. No extraction, build, simulation or Freya API call was performed.
