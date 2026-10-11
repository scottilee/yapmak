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

18. **OpenAPI schema composition crashed the build** — found by the external packages (`tests/fixtures/external/`): both realistic APIs use
    base properties plus `oneOf` refinements (per-product-type floor fields; reason omitted for reasonless outcomes) and `parse_openapi`
    raised "schema composition is unsupported". (fix: compositions are flattened — properties united with enum unions, `allOf` adds every
    variant's required, `oneOf`/`anyOf` keep only the fields required by every variant, `not` dropped; response/request needles widened for
    `facility_ref`/`account_ref`, `category`, `callback_on`/`callback_at`, `route_key`, `closing_code`/`closing_reason`. Practice exports
    byte-identical; `tests/test_openapi_composition.py`.)

19. **`ok:false` without a remaining counter looped on "I could not read that"** (review item, confirmed by the external package aster: no
    counter, policy counts in code). Fixed: a bank refusal counts as a wrong answer; the agent formats every answer itself so "unreadable"
    is not a real state.
20. **A common date for several products stopped at the first product needing an answer** (other agent's live case codex-1 PUB-13: "the
    26th for both" → p1 rolled to the 27th, but p2's clamp to its 23 Oct deadline was lost and it got a fresh attempt-1 proposal for the 16th).
    Fixed: the common date is applied to every product first; the first open question becomes the current product.
21. Known limitation, not fixed: two special cases in one sentence ("the card is paid and the loan is not mine") extract as one intent, so one
    product gets the other's note (codex-2 PUB-13). Needs a multi-intent extraction schema.

## v24 additions (11 Oct 02:40–03:20 UTC)
- OpenAPI compositions flattened; mapper vocabularies widened (items 18); `ok:false` without a counter counts as wrong (19); common date
  applied to every product (20); "stay on this product" sentence in multi-product attempt instructions (LLM skipped the loan's second
  attempt three times live).
- **Floor rules** (`amounts.floor_rules`: percent of the past-due amount with a minimum, fixed amount, or a field) and **deadline kinds**
  `day_of_month` ("the 15th of next month") and `month_offset` on `end_of_month` ("end of next month"); extraction guide, validation,
  runtime, invariants and the permutation generator extended; 7 new tests. Practice exports unchanged in behaviour (the embedded runtime
  changed, so the bytes did).
- Another agent edited `workflow_runtime.py` and the regression tests concurrently (≈03:00 UTC): it removed the past-deadline guard and the
  support-offer acceptance (both live-verified) and rewrote a test to match. Restored. Its two other changes were kept: an explicit full date
  with a year wins over a weekday mismatch, and an idle-labelled turn that carries a date or amount is treated as a proposal.

- **`aside` extraction variable** (negotiate + read-back): a robot/scam question asked in the same message as an answer ("Yes, that works.
  Are you a robot?") is answered in the next sentence — prefixed to the fixed read-back or goodbye speech, or to the LLM's next instruction.
  The read-back is fixed TTS, so before this the question was silently dropped; it was the single most frequent judge failure tonight
  (PUB-04 ×3, PUB-07 ×1, codex PUB-07).
- Composite deadlines (`earliest`/`latest` of simple rules), `dates.past_deadline = no_promise`, and `max_of` floors (greater of a base field
  and a percentage, rounded up to the cent) — the three cheap kinds among the four the cedar/harbor packages flagged as unexpressible. Still
  unsupported: per-weekday split callback windows and a per-field "one wrong answer locks" rule (both logged as unresolved by the extractor).

- **Code-node retry**: live B PUB-13 (03:26 UTC): the write-step code node hit the platform's "unparseable result" fault once (the previous
  node in the same call ran fine), its default transition went to close_call with empty outcome variables, and the bank rejected the close
  three times — a confirmed read-back with no promise. Code nodes now carry `maxRetries: 1` (they are deterministic over `vars`, so a re-run is
  safe; api_request nodes keep 0). `build.py` additionally records an offline run of the invariant scenarios on the compiled workflow in the
  trace before publishing (informational, never blocking).

- **Bare weekday vs the offer / the past** — live A PUB-07 (03:51 UTC): the agent offered Tuesday 27 Oct, the customer said "I can do that
  on Tuesday" (weekday tuesday, relative this), and bankcal's "this Tuesday" from a Wednesday is LAST Tuesday (13 Oct) → a past proposal,
  an LLM claim of a recording, then a goodbye that closed without a promise. Fixed: a weekday that names the offer on the table restates the
  offer; a bare weekday never resolves to the past (the coming one is used). Also: a goodbye at the read-back now finalizes at once (unsaved
  proposals abandoned, notes written, one close) instead of asking what to change (the second reviewer's R5).

- **First floor offer dated like attempt 1** — live A asks_back PUB-06: "too much" at the first question → the floor was offered for today;
  the public PUB-06 ledger expects the accepted floor on Friday 16 Oct, i.e. the floor rides on attempt 1's date. Refusing it is the flat
  refusal that uses attempt 1 (rule 30) and repeating the same offer is forbidden (rule 31), so attempt 2 (floor on the deadline) follows at
  once; probe P5 and the ladder test now encode that reading. Weekday + day + this/next precedence refined ("Monday the 26th" when "this
  Monday" has passed is the 26th; "this Friday" with a stray "30th" from another sentence stays the coming Friday).

- 05:00–05:40 UTC: fresh-v24 review items fixed — floor offer / direct acceptance honour `no_window`; an explicit "next <weekday>" is not
  folded into the offer; an aside that arrives with the final confirmation is spoken before the "recorded" sentence or the goodbye
  (`aside_carry`); composite deadline children fully validated. `submit.sh` now fails loudly when `git push` fails (the rehearsal showed a
  silent exit 0). Verify success flag `accepted` (sable/tamarisk APIs) added to the mapper — another crash-class vocabulary gap. "This product
  already has a promise" from the bank now counts as recorded (stale practice session / duplicate-write race). The other agent's two edits were
  re-adopted in guarded form: the brief's special-case trigger text is appended to the tuned intent descriptions only when it adds vocabulary
  (practice export unchanged), and the neutral hint fallback sentence.

## Generalisation gaps noted (not changed in v23)
Text identity answers sent verbatim (spaces kept); bare weekday earlier in the week resolves to the past; `refuse_to_talk.ask_once_first`
ignored; `prop_product` enum stops at 3; out-of-range days_late falls back to the nearest band; `ok:false` without a remaining counter
loops on "could not read that" until the stuck guard.

## Code quality / docs
POLICY duplicated in every code node (size); dead branches in `_apply_proposal` and `st_neg_route`; `check_provenance` lacks ordinal
number words (false `value-absent n` positives); invariants used a fixed `now` (v23: clock sweep over four dates + deadline and
business-day checks on every promise); `--fast` committed stale audits (fixed in submit.sh); `preflight.sh` needed GNU timeout (fixed);
README should name the Claude credential requirement for reviewers who rebuild top-10 entries.

## v25 (11 Oct 06:00–07:00 UTC) — triage of the whole-codebase review + two adversarial packages

Review points (another agent's 8-point codebase review) and what was done:

1. **"already" false success** — valid. `st_write_step` treated any `ok:false` whose error mentioned "already" as recorded. Narrowed to "already has a promise" / "promise already" / "already recorded" / "duplicate promise".
2. **transfer / note / close failure handling** — partly valid. A failed transfer or note is logged and the call still closes with the policy's outcome (one retry on `close_call` without reason is deliberate: a transient rejection must not strand the call). No change; the public bank never fails these, and a stranded call scores zero whereas a missing note loses at most the case.
3. **unresolved rules are only traced, never block** — valid observation, deliberate: an unpublished agent scores 0. Unresolved items stay in `unresolved` + trace; v24 already stopped injecting them into prompts.
4. **ignored IR fields** — valid and fixed. The runtime now honours `dates.weekend_or_holiday_roll_forward=false` (names the non-business day, asks for another day, proposes nothing), `dates.after_deadline_offer_deadline=false` (names the latest date, asks for a day on or before it), `outcomes.transfer_overrides_promise=false` (a recorded promise closes as the promise outcome even after a transfer), `calendar.missing_date_parts="ask"` (a bare day without a month is handled like a vague date: asked once). Default behaviour unchanged. The GVF call sheet ("no nudging to the next business day", "date past the k-date -> not recordable") had both date flags extracted as false already — until now the runtime ignored them.
5. **unfamiliar special-case names are not executable** — valid limitation. `policy.unknown_special_cases()` is now written to the trace, and the extractor guide tells the model to map document cases onto the seven routable names.
6. **API mapping ambiguity / allOf enum union** — valid and fixed: `allOf` enums intersect (oneOf/anyOf still unite); `_pick` records every needle that matched several properties in `MAPPING_NOTES` (trace `api_mapping_notes`).
7. **multi-product language** — valid limitation (per-field lock, split-sentence intents); not a schema change for today. The "floor once" sentence is consistent with the runtime (one floor offer per product).
8. **build success semantics / --fast** — design choice (checks are informational, publish never blocked); `--fast` is a rehearsal path and publishes to the hidden slots only when invoked by the operator.

Two adversarial hidden-style packages (`tests/fixtures/external/gv-finance-sheet`, `harwick-lowe-register`, written by another model) exposed real gaps, all fixed:
- `create_promise` lists the amount property as `sum` but `required: [amt]` (both packages). `compiler_openapi.request_aliases()` now sends a required name that has no property of its own as an alias of the argument it means (`sum` and `amt` both carry the amount); the static check and the invariants' mock bank accept such names. `amt` and `money` added to the amount needles.
- `ref_no` as the customer field (Harwick) matched no needle → `customer_id` was silently omitted from every request. `ref` and `debtor` added (excluding product/facility/item/loan/queue/promise/note names).
- `cat` / `outst` as product type / outstanding amount (Harwick) matched no needle → build stopped. Added `cat`, `outst`, `owed`, `owing`, `bal`, `dpd`, `delinq` needles **and** a general mechanism: `PolicyIR.api_fields` ({"<tool>.<slot>": property}) lets the extractor state field names the documents define (Harwick 6.1 spells them out); the compiler honours a stated name only when the schema has it, else falls back to needles. Guide text added for `api_fields` and for `floor_offered_once=false` ("zero persuasion", missed on GVF).
- Expected-vs-actual differences that are NOT builder faults: GVF `bands` day range (the sheet gives none; extractor used all), `paid_outcome` S8 (sheet has no already-paid rule), placeholder spelling in `holder_question` (ours is `{{title}}`), Harwick band (c) `floor_if_full_refused` (7.2(b) does not say it; the expected file assumed it).

Gates on the v25 tree: 144 unit tests, probes 14/14 (A+B), invariants brief A / A+B / GVF / Harwick all pass (GVF: after_deadline & weekend_named n/a under its no-offer flags), permutations 40/40. Live: `scripts/batch_v25a.sh` (A reps 3, B reps 3) — results in `results/gen/r25a-*.json`.

## v25 b–d (11 Oct 07:00–07:40 UTC) — unfamiliar tool APIs, absent outcomes, compound sentences

Another agent's packages Orrery/Palisade/Tessel/Kurilian/Grunthal/Fenbrook and 24 live edge cases (`tests/fixtures/edge/unlike-round`, `edge-a4`, `edge-b3`). Live on v25c: brief A 10/10 ×3 and B 3/3 ×3 unchanged; old edge set A 9/10 (from 7/10), B 0/3; new sets A 4/8, B 0/3 before the fixes below.

- **Spanish property names stopped the build before extraction** (Orrery, Palisade: `pregunta`, `respuesta`, `contrato`, `importe`, `fecha`, `cola`, `resultado`). `compiler_openapi._pick` rewritten: exact name → English word-start match (names normalised: camelCase, accents) → multilingual synonym table → property descriptions → type/position fallback (`_request_fallback`, `_response_fallback`); the customer field is anchored on `get_account`'s single argument. `tool_enums(strict=False)` + `unmapped_request_slots()` let the extractor run anyway and tell the model which arguments to state in `api_fields`. A stated name (`api_fields`) replaces only weak or missing mappings (`_slot`): Palisade's model-stated names were wrong on 2 of 32. All 14 APIs on disk map correctly; YAML tool API files are accepted (PyYAML added).
- **A brief with no already-paid rule or no transfer** (Orrery, Kurilian, Fenbrook) was forced to invent `paid_outcome` / `transfer_outcome` by `policy.validate`; now required only when a path needs them and supplies none; the runtime closes a fully paid call without a paid outcome using the claim's reason. A hardship case of type `continue` without a reason no longer closes with the literal reason "hardship" (Palisade): the policy's refused reason is used.
- **Dictated read-back sentence with placeholders** (Kurilian, Fenbrook: "Amount {{payment_amount}}, on {{date}}. Save this arrangement?"): `_confirm_phrase` fills them for one proposal and keeps the placeholder-free sentences for several. The remainder sentence (floor wording) is read back whenever a partial amount is confirmed (live PUB-06-unlike: the agent said it had no information about the rest).
- **Compound sentences** ("the card gets 220 on Friday; the loan is not mine; the car loan I cannot pay, I lost my job"): extraction variables `cust_intent_2/3` + `prop_product_2/3` (multi-product only), `prop_amount_2` (two amounts for two products), `prop_date_like` (move one product onto another's date), `prop_minimum` ("the minimum" as the amount), `prop_product` gains `none`. Runtime `_secondary()` marks paid/dispute claims on their product, applies a proposal for another product, promotes a hardship statement to the main intent and keeps the original proposal; paid/dispute claims without a named product now apply to one product, never to all. Read-back: a change that changes nothing twice gets one clarifying question, four times abandons (the loop of 30 identical read-backs is gone).
- **Hardship stated together with a proposal** ("I lost my job, but I can pay the minimum on Friday"): the support offer is made first; when declined, the proposal is applied instead of closing with no promise. A request for a person after the support team was offered goes to the support queue.
- **Dates**: "next Friday" said while Friday is still ahead this week is the coming Friday (three independent case authors read it so; said on a Friday it stays the one after). A too-low amount after the floor was offered gets the floor once more on the customer's own date before it counts as a refusal. A third party who cannot name a time gets two more asks, not one.
- Gates after each step: unit tests (now 163), probes 14/14, invariants on brief A, A+B and all eight extracted packages, permutations 40/40. `build.py` prints and traces `degraded` (extractor fallbacks, failed checks).

## v25 e–f (11 Oct 07:40–08:10 UTC) — second round of packages (19 + Turkish) and live edge sets

- **Live edge sets on v25d**: unlike-round A 10/10, B 3/3 (both from 0/3 and 7/10 at the start of the day); edge-a4 5/8, edge-b3 1/3; practice A 9/10 ×3 (PUB-04: the persona's "I will pay on the twenty-third" was cut after "twenty" by the platform, the agent took the 20th), B 2/3 ×3 (PUB-12: the dialogue model twice invented a third personal-loan offer "110 on 30 October" after the runtime told it to move to the car loan — reproduced offline as correct runtime output). `_enter_product` now names the finished product ("The personal loan is finished: do not propose anything more for it. Now the car loan.").
- **19 round-2 packages + `selvi-turkish-fields`**: all 35 OpenAPI files on disk now map (nested product list inside an envelope: `payload.products`; Turkish names without descriptions: type/position fallback anchored on names shared across tools — `create_promise`'s product/date, `add_note`'s reason, the boolean every tool returns is the success flag; the extractor's stated names then correct the remaining boolean permutation). 11 of them extracted: all pass invariants after two fixes — (1) `close_call` with `reason` **required**: `finalize` always sends the outcome's table reason when the API requires one or the table allows exactly one, and the no-reason close nodes carry the reason field; (2) `dates.promise_today_allowed=false` was rejected by the validator and ignored by the runtime: now the earliest date is the next business day and "I can pay today" is answered with that offer. `calendar.next_weekday` ("coming" default, "following_week" when the documents define it so — one spec does). Mismatches left are expected-file representations (business-day order, band keys, note-vs-close reading of refusals).
- Floor re-offer after a too-low counter no longer repeats the number ("the amount already proposed"); `pays_today` accepted as a secondary statement; read-back amount extraction given worded-number examples (live: "make it three hundred dollars tomorrow" extracted no amount).
- Gates: 167 unit tests, probes 14/14, invariants brief A / A+B / 15 extracted packages, permutations 40/40. Live v25e batch `results/gen/r25e-*`; final candidate v25f `scripts/batch_v25f.sh`.

## v25 g (11 Oct 08:20–09:20 UTC) — the PUB-12 hand-over regression and its fix

- **Symptom**: PUB-12 (brief B) 0/3 on v25e, 2/3 on v25c/d, after 3/3 ×2 on v25a/b. Every failure is the dialogue model inventing a third offer for the finished personal loan ("110.00 on Friday 30 October", "150.00 on 23 October", "220.00 on 30 October") after the runtime had told it to move to the car loan. The engine's variable snapshots (`variable_extracted.variable_table`) show the correct car-loan instruction in `neg_instruction` and none of the invented numbers anywhere; offline replays of the same turns produce the correct instruction. Code-node latency was 0.2 s. The model ignores a correct instruction at the hand-over point.
- **Experiment** (`scripts/batch_exp1-4.sh`, PUB-12 only on the B slot, `results/gen/exp*`): A = v25e as published 1/2 (plus 0/3 earlier); B = no new extraction entries 2/2; C = no new entries and no hand-over prefix 1/2; D = compact entries 2/2; E = entries off 2/2. The large extraction schema correlates with the failures but is not the sole cause (C failed once without it).
- **Fix**: a `handover` conversation node whose `on_enter` is fixed TTS (`{{handover_text}}` from `_enter_product`: "I understand. For your car loan, can you make a payment of 140.00 on Friday 16 October 2026?"; "Thank you. For your personal loan, …" after a proposal; "I understand, and I will not ask about that one. …" after a paid/dispute/hardship note) and then the `negotiate` prompt, schema and routing. Every code node that could route to `negotiate` can route to `handover`. The offline driver treats `handover` as `negotiate` for scripted turns. `compile.COMPOUND_SCHEMA` = "compact" (second statement + product, second amount, the minimum; no third statement, no move-onto-another-date; short descriptions); "full" remains for the tests, "off" is available.
- Live gate for the commit: variant F (= v25g gen-ab) PUB-12 ×3, then `scripts/batch_v25g.sh` (four edge sets, A ×3, B ×3).

## v25 g, live gate and platform outage (11 Oct 09:20–11:30 UTC)

- Variant F (= v25g gen-ab: fixed-text hand-over + compact schema) PUB-12 **3/3**. Full v25g batch: unlike-round A 9/10 (PUB-02: the relative gave a time before retracting), unlike-round B 1/3 (the compact schema loses the third statement of a three-statement sentence; those two cases need the full schema), then the platform degraded (503/504 streaks from ~09:30, API unreachable from ~10:45): edge-a4, edge-b3, A ×3 and B ×3 could not run. Variant G (hand-over + full schema) could not be published or tested for the same reason.
- Robustness for the hidden builds taken from the outage: `freya.run_simulation` start deadline 90 s → 240 s; `build.py` `persist()` keeps retrying validate / publish / checkpoint export / final export every 30 s for as long as the build budget allows (minus the final-export reserve) instead of 4 × 20 s.
- Commit recommendation given at 10:50 UTC: v25g as a checkpoint (brief A evidence from v25e 10/10 ×3 carries over: A never enters the hand-over node; B evidence = PUB-12 3/3), with a second commit if the platform returns and G or the A/B repetitions change the picture.

## v25 h (11 Oct 13:15–13:30 UTC) — transport failures on bank tools are not customer answers

- Commit `eb329ea` = v25g. Gate on it: brief A ×3 → 10/10, 10/10, 9/10 (the miss: a 60 s platform turn, the persona hung up); brief B ×3 → 3/3, 0/3, 3/3 (run 2: two calls dropped by the platform after the account lookup; PUB-12 asked the date of birth twice).
- **That PUB-12 miss was ours to fix**: the bank mock answered `verify_identity` with a Cloudflare HTML error page; the engine logged `function_call_error`, left `v_ok`/`v_verified` empty, and `st_verify_after` counted it as a wrong answer ("That does not match our records"). Now: no parseable result → the check is fired again with the same answer (up to two retries, `verify_after_i → verify_i`), then a technical-problem close (`no_promise` / service_error). Same for `get_account` → `init_products → get_account` when no product list came back. Offline mock bank gained `bank.drop = {"verify_identity": 1}`; three new tests (172 total). Live gate: `scripts/batch_v25h.sh` → `results/gen/r25h-*`.
- **v25h live gate (13:30–13:47 UTC)**: brief B 3/3, 3/3, 3/3. Brief A 7/10, 10/10, 10/10: the three run-1 misses (PUB-01, PUB-04, PUB-09) ended `customer-ended-call` 1–2 s after the customer's first reply with no extraction or routing event at all — the platform did not process the turn (first calls after a publish), the agent never spoke again, the persona hung up. Nothing in the build ran. Recommendation: commit v25h.
