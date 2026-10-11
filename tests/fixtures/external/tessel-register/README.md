# Tessel: table-only operating register

Read 01 then 02. All policy text, including precedence and exclusions, is in tables. No external rule is incorporated. `expected.json` uses the clean-eom mechanical check/source format. `openapi.json` defines seven POST paths; numeric-looking outcomes remain JSON strings. Dates in `date-oracle.json` come from bankcal.

Differences from Brief A: Saturday operations; a different holiday; three ordered security questions (text/year/five digits); two wrong answers; zero persuasion in every band; three deadline shapes including whichever-comes-first and twentieth of next month; a fixed capped floor; no already-paid or restructuring route; no voluntary hardship promise; table-only documents and numeric codes. Single product and notes-off match A and are not counted as differences.

Absent rules: restructuring, already-paid and active notes. No paid outcome or posting-delay sentence. Missing special cases are checked with `{"missing": true}` action values. Callback and hardship ARE present: callbacks next business day only; hardship ends the call even with a voluntary offer. Dispute also ends the call, rather than adding a note.

Representation caveat: the current validator requires a paid outcome despite the explicit exclusion. The oracle expects an empty paid_outcome so a made-up Paid code fails. Wildcard versus per-type fixed floor expansion and free prose triggers may need semantic review. This package has no policy conflicts. No extraction, build, simulation or live API checks were run.
