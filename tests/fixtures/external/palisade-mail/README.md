# Palisade: mail reversal, five products, six-day calendar

Read 01 → 02 → 03. The mail is newest first; 10 October restores two save retries, reversing 8 October's zero. The long policy remains authoritative everywhere else; C-8 owns code vocabulary. `expected.json` is the clean-eom mechanical check/source format. No extraction was run.

Differences from Brief A: up to five products; Saturdays open; different holidays; whichever-comes-first deadline; twentieth of next month; floor = max(minimum, 15% rounded up to cents); zero attempts in the first band; no hardship or restructuring rules; immediate human transfer; abbreviated prose; Spanish/abbreviated schema fields and mixed-case codes. Notes are enabled.

Absent: hardship and restructuring special cases and their queues. Their absence is checked with `{"missing": true}` action expectations, not default Brief A behavior. Already-paid and dispute are product notes that continue the call. Transfers suppress all notes. S-1 is note-only and cannot be a close reason.

`date-oracle.json` supplies bankcal-derived deadlines and calendar anchors. Uncertainty is limited to equivalent IR representations: expanding the wildcard max_of rule per product is semantically equivalent and needs review. Freeform trigger wording/source spans need semantic review. Request and response schemas are complete synthetic contracts; `.example.invalid` endpoints are not live services.
