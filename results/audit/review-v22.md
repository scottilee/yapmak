# Independent code review of v22 (fresh agent, no prior context) — 10 Oct 2026, ~22:30 UTC

Reviewer brief: read the hackathon rules page, then the code; find anything that costs leaderboard points; verify offline only.
Items marked **confirmed** were reproduced by the reviewer with a throwaway offline driver and re-reproduced by us before v23.

## Score-relevant issues (v23 fixes in parentheses)

1. **Persuasion attempt proposes a date after the deadline** — confirmed. `_start_attempt` took `attempt_date(...)` unclamped; with a
   3-business-day deadline on a Friday the agent proposed and recorded a date after the deadline. Practice bands (7/12 days) never hit
   it. (v23: attempt date clamped to the deadline; an attempt identical to the refused offer is skipped.)
2. **Deadline already in the past records a past-dated promise** — confirmed. Month-end business deadline with `now` on a month-end
   holiday. (v23: a past deadline becomes the first business day from today.)
3. **Hardship on a multi-product brief marks every product and closes** — confirmed. `SpecialCase.ends_call` was never read by the
   runtime; both dry-run briefs say "mark only this product and continue". (v23: with `ends_call: false` only the products under
   discussion are noted and the call continues; default behaviour unchanged.)
4. **Callback retry wording hardcodes "today … or the next business day"** — confirmed. (v23: sentence built from `callback.days`.)
5. **Day-then-time callback answer burned the single retry** — confirmed in the driver. (v23: the day is kept and combined with the
   time from the next turn; "outside the window" is said only when a time was actually given.)
6. **Audit/repair pass failure kills a build with a valid pass-1 policy** — suspected. (v23: pass-1 snapshot; a failed audit or repair
   falls back to it, traced as `policy_audit_fallback` / `policy_repair_fallback`.)
7. **`policy.validate` had no callback checks** — confirmed: `days='same_day'` or `start='8:00'` validated and then every slot was
   rejected at runtime. (v23: days literal, HH:MM, start<=end, numeric_date_order validated.)
8. Repetition flakiness in the dialogue layer (sympathy for a parking complaint; robot question at read-back; sandbox errors) —
   measured, not fixed: prompt wording stays frozen by decision.
9. "Can you hear me?" counted as unclear in 6/32 sweep phrasings — not changed (extraction schema frozen).

10. **Floor offer dated on a non-business day** — found by the new offline scenarios (`too_much` with `now` on a Saturday): the floor
    was offered "today" and recorded for the Saturday. (v23: offers default to the first business day from today, clamped to the deadline.)

11. **Accepting the support transfer closed as no_promise/hardship** — found by the live edge cases (`tests/fixtures/edge/edge-a1.json`,
    PUB-05 "accepts the transfer"): `_transfer` took the outcome from the hardship case's *decline* action instead of its offer outcome,
    and "yes, please connect me to the support team" extracted as `human`, which the support state did not treat as acceptance.
    No public case accepts the offer, so it never showed. (v23: offered transfers use the offer queue/outcome; `human`/`restructuring`
    in the support state accept the offer; new invariant scenario `hardship_accept` on all 40 policies.)

12. **A security answer accompanied by a question was not verified** — live A `--reps 3` run 3, PUB-03: "twenty one July nineteen ninety.
    This is getting annoying, how much do I owe?" extracted as `question`; the wrong date never reached the bank, a fourth attempt verified.
    (v23: a message that carries a complete answer in the question's format is an answer; the next sentence also covers the question.)
13. From `results/audit/independent-current-review.md` (second independent reviewer): (1) `unresolved` extraction notes were injected into the
    system prompt as "further rules" — removed, they stay trace evidence (test: a planted note never reaches the workflow); (2) `run_end`
    now carries `checks` / `checks_passed` so success is qualified by the readiness checks; (3) a repair fallback now rewrites the audit
    file, keeping the rejected audit under `rejected_audit` and stating that its `fixed` claims were not applied; (4) operative fields
    that equal the schema default while their section cites no source are listed in the trace (`defaulted_without_source`).

14. **Idle turns never routed: a call could run until the customer hung up without close_call** — live B `--reps 3` run 1, PUB-12: after
    the LLM skipped an instruction and improvised a goodbye, 80 "Thank you, goodbye" turns were extracted as `other`, which had no transition.
    Also A `talkative`: two calls "not closed with close_call". First fix (wrap up after three idle turns) **regressed talkative customers**
    (B talkative 0/3, A talkative 6/10, PUB-12 attempts cut short: chatter was treated as refusal, and re-asking the proposal was judged as an
    extra persuasion attempt). Final rule: `other`/`scam` route into the router but are harmless — a few words, no re-ask, nothing marked —
    and a new extraction value `goodbye` (customer says goodbye / is hanging up) or eight idle turns in a row wraps the call up (open proposal
    declined, read-back or finalize). At the read-back: chatter re-speaks the confirmation; goodbye or six idle turns count as a decline.
    This is the one extraction-schema change of v23 (a new enum value with a one-line description).
15. **Transfer after a proposal that was never confirmed**: tried recording the pending proposal (read-back first, then transfer) — reverted,
    because the auditors' probes P11/P12 read brief A as "agreed but unconfirmed is not written"; the edge-case expectation was corrected instead.

16. **A stray day number overrode an explicit weekday** — live B talkative PUB-11: "my cousin's wedding is on the thirtieth. I can pay all
    three this Friday" → prop_day=30 + weekday friday/this; the day won and 30 October was recorded (clamped to deadlines) instead of
    16 October. (v23: with a weekday and a day, the reading that restates the agent's current offer wins; otherwise an explicit
    this/next weekday wins over a number that does not name it; "Tuesday the 27th" still works.)
17. Tried: "too much" at the first question = persuasion attempt 1 with the floor — reverted after re-reading rule 26 (the floor offer is
    not an attempt; refusing it is the flat refusal that starts the ladder), which the auditors' probe P5 encodes.

## Generalisation gaps noted (not changed in v23)
Text identity answers sent verbatim (spaces kept); bare weekday earlier in the week resolves to the past; `refuse_to_talk.ask_once_first`
ignored; `prop_product` enum stops at 3; out-of-range days_late falls back to the nearest band; `ok:false` without a remaining counter
loops on "could not read that" until the stuck guard.

## Code quality / docs
POLICY duplicated in every code node (size); dead branches in `_apply_proposal` and `st_neg_route`; `check_provenance` lacks ordinal
number words (false `value-absent n` positives); invariants used a fixed `now` (v23: clock sweep over four dates + deadline and
business-day checks on every promise); `--fast` committed stale audits (fixed in submit.sh); `preflight.sh` needed GNU timeout (fixed);
README should name the Claude credential requirement for reviewers who rebuild top-10 entries.
