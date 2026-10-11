# Independent v23 regression review

Scope: committed diff `e870198..70ce3b4` (v22 → v23), primarily build.py, extract.py, policy.py, compile.py, workflow_runtime.py and changed offline gates. Neither revision has a literal v22/v23 tag; commit subjects identify them. No commit was made for this review. Pipeline files and out/ were not edited. No Freya API, models or live simulations were used. Review is independent of the schema's author, but performed in this existing reviewer session, not by a newly spawned context-free agent.

**Disposition: changes need follow-up; passing offline gates are not a clean sign-off.** Existing gates: `.venv/bin/python -B -m pytest tests/ -q -p no:cacheprovider` with PYTHONDONTWRITEBYTECODE=1 → **113 passed in 13.15 s**. Targeted pure-function probes expose the following problems. `reproduce.py` loads the two committed runtime sources into separate in-memory namespaces; it does not publish, run the workflow driver, or write a ledger. Full exact results are in runtime-probes.json.

## R1 — high: an expired hard deadline is extended without authority

New workflow_runtime.py:581–582 replaces any past deadline with next_business_day(today). At now=2026-10-30T11:00, holiday=2026-10-30, the business-month-end rule yields **2026-10-29** via bankcal, but v23 changes the product deadline to **2026-11-02**. v22 retained the policy date. Avoiding a past payment is correct; manufacturing a later permitted payment is not. The dry-2 memo explicitly forbids rolling into the next month.

The new test test_past_deadline_never_records_a_past_date asserts the invented November date, and tests/invariants.py skips upper-bound enforcement when `dl < now` (line 309) and normalizes some expected deadlines forward. Thus the gate now blesses the breach. Keep the original cap and handle an empty feasible interval using an explicit supported policy action/unresolved outcome. Do not merely adjust the test to another future date. v22 also needed a safe empty-window path; the regression is the newly authorized out-of-policy future deadline.

## R2 — high: weekday plus explicit day/month loses the explicit year

New `_resolve_date` weekday branch at workflow_runtime.py:118–145 constructs d_expr from day/month but never reads prop_year. With fields kind=weekday, weekday=saturday, day=16, month=10, year=2027 (e.g. “Saturday the sixteenth of October twenty twenty-seven”), v22 returns **2027-10-16**, whereas v23 returns **2026-10-17**. The gold date is computed through bankcal, not manual arithmetic. This can turn an after-deadline proposal into a much earlier apparently valid one; read-back may catch it conversationally but routing already lost the requested date.

Preserve and validate explicit complete dates before contextual weekday disambiguation. A current offer must never override an explicit year. Add tests with explicit future/past years and conflicting weekday/date combinations; distinguish a real explicit date from an unrelated extracted number rather than dropping the year.

## R3 — medium/high: support offer hijacks a distinct human request

New workflow_runtime.py:919–920 interprets any `human` or `restructuring` intent, with no payment fields while awaiting support, as support acceptance. A distinct utterance such as “No, not support; I want a general customer-service person” can correctly extract `human` and is now immediately transferred to support. The probe shows v22 asks once whether the assistant can help (A42), while v23 selects transferred/support without such consent. A32 has priority over persuasion/restructuring in a simultaneous hardship statement, but does not authorize silently treating every later human request as consent to care.

The new parametrized regression test asserts all three enum values are equivalent, so it cannot distinguish the good fix (“connect me to support”) from this regression. Add explicit offered-transfer acceptance/refusal/destination information, or clarify a genuinely ambiguous response before selecting a queue. Preserve the separate human-request rule.

## R4 — medium: new idle branch discards otherwise usable payment fields

At workflow_runtime.py:869–887, `other`, `scam`, empty and `goodbye` return before payment fields are examined. With `cust_intent=other`, prop_amount=200 and prop_kind=tomorrow on PUB-01, v22 retains a valid **200 / 2026-10-15** proposal and enters read-back; v23 says to return to payment later and drops both fields. The fields are cleared at entry. This makes independent intent classification more fragile just where customers mix chatter with amounts and dates. The identity branch was improved to prioritize complete structured answers, but the payment branch regressed in the opposite direction.

Treat “idle” as no usable proposal evidence, not merely a broad intent label. Define precedence for explicit stop/dispute/hardship/refusal rather than trusting arbitrary extracted numbers. An offline test should cover mixed content with valid fields and ensure no consent is inferred.

## R5 — medium: goodbye handling still does not finish the read-back path

This is an incomplete new feature rather than a previously correct v22 flow. `goodbye` is newly extracted/routed, but readback_route maps its first occurrence to declines, keeps the pending proposal, and instructs “Ask what they would like to change: the amount or the date” (1128–1134 → 1180–1192). The existing new test deliberately expects script exhaustion in negotiate, not a closing outcome. In multi-product negotiation the new goodbye branch calls `_advance`, which may start another product or return to read-back rather than end the call.

Give explicit termination its own finalization behavior: abandon unsaved proposals, preserve saved ones, write only authorized notes, and close once. The gate should assert that end state instead of accepting a stalled dialogue. Do not confuse a courtesy “thanks” with an explicit goodbye/hangup.

## Other review observations

- Good changes: configured callback retry wording, preserving split callback day/time, amount/date cap on ordinary attempts, offered hardship-transfer outcome selection, typed format validation, separately reported self-test status, and logging audit fallback/default provenance.
- Audit fallback is explicitly logged and preserves a structurally valid first pass. That is availability, not correctness assurance: `policy.validate` does not prove that an audited omission or unresolved rule was honored. The final run may succeed using an unaudited policy; the trace now tells the reviewer this, which is useful.
- Removing unresolved text from prompts avoids treating diagnostics as dialogue instructions, but unresolved rules are neither enforced nor compile-blocked. This behavior change is material for hidden briefs; see the census and gap fixtures.
- No new key-exposure/shell-execution issue was established in this diff. No live reliability or judge pass-rate claim follows from these unit probes.

Reproduce: `.venv/bin/python -B results/audit/v23-independent-70ce3b4/reproduce.py`. The JSON compares both revisions for all five cases. Tests exercise exact extracted values, not claims about the probability that Freya emits those values.
