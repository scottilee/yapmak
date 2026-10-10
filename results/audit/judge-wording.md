# Judge-wording audit — transcripts vs. the literal checks in the public + synthetic cases

Corpus: 319 `checks` strings across `public-test-set.json`, `tests/fixtures/synthetic/*.json`, `tests/fixtures/calendar/*.json` (194 unique; the `-expected.json` files contribute ~150 IR-path assertions that no judge reads — **41 are natural-language judge checks**). Scanned surfaces of `out/gen-a.workflow.json` / `out/gen-ab.workflow.json` (identical template): `system_prompt`, every `task_message`, every baked `on_enter.tts`, the runtime instruction literals inside the code nodes, and extraction descriptions.

**Judge model reminder:** outcome checks read the ledger; policy/honesty checks read the *transcript*. Everything below is a risk only where the literal string can reach the transcript — either because it is a baked TTS line (deterministic, no risk unless wrong) or because a model-visible prompt/instruction names the banned thing in a way an echo could reproduce. The precedent: `"This call is recorded"` → rewritten to `"We record this call"` (the "does not say 'recorded' before a successful call" check), and the restated floor.

## Hits that should change (severity: likely → unlikely under a literal judge)

**H1 — negotiate/state_debt task quotes the exact banned question. [likely]**
Current: `Never ask the customer for an amount in any form (not "how much can you pay", not "what is the lowest you could pay"): you propose every amount, from your instruction.`
Check hit: *"agent never asks how much she can pay"* — a model that reasons aloud or mirrors the example produces the check's failure string verbatim.
Proposed: `Never ask the customer to choose or name an amount: you propose every amount, from your instruction.`

**H2 — the floor sentence never uses the noun the check uses. [likely, PUB-06 family]**
Checks: *"minimum payment offered once, with the note that the rest stays overdue"*. Engine instructions say `Offer the lowest amount you can record, 126.00, ...` — semantically right, lexically "minimum payment" is absent.
Proposed (three assembly points: `below_floor`, `_too_much`, attempt/floor note): when the IR `amounts.floors` field for the product type reads as human words, use them first:
`Offer the minimum payment for the credit card ending 1903: 637.50 on Friday 16 October — that is the lowest amount I can record. Say that the rest stays overdue.`
For loan floors: "the instalment amount of X" (note: "instalment" is NOT a pre-verification banned word; H5 handles its other use). Suggest carrying this as a per-type phrase in the IR (`floor_words`) so nothing is hardcoded and Cobalt/Meridian-style field names (`minimum_due` → "minimum due", `line_payment` → "line payment") degrade gracefully.

**H3 — below-floor rejection says "cannot be recorded" pre-write. [medium]**
Current: `Say that 100.00 cannot be recorded. Offer the lowest amount you can record, ...`
Check: *"agent does not say 'recorded' before a successful call"* — the token appears, negated, before any write. A literal matcher trips.
Proposed: `Say that 100.00 is below what this call can take. Offer the lowest amount you can record, 126.00, on ...` ("can take" avoids every stored/recorded token; the same-sentence "lowest amount you can record" also appears post-verification, where it matches check phrasing used elsewhere).

**H4 — readback task: "Do not say anything is recorded." [medium]**
Proposed: `You will be told in a later instruction when something has gone through; until then, do not confirm that anything is stored.` — removes the quoted token, keeps the rule.

**H5 — system prompt lines that name the banned offers. [medium]**
Current: `- Never offer a discount, a waiver, an instalment plan or any term that is not in your instructions.`
Checks hit: *"no discount, waiver or plan offered"*. Proposed: `- The only terms you may mention are the amounts and dates given in your current instruction; propose nothing else.`
Also the negotiate tail: `If they ask for a payment plan or lower instalments, say you will connect them with a colleague; do not describe any plan.` → `If they ask to spread the debt over time or change its terms: say a colleague will handle that part, then wait for the system's transfer.`
And the harness line `The system records promises, callbacks, notes and transfers itself and tells you in your current instruction what was done; never say that anything is recorded, booked, transferred or scheduled unless your current instruction says so.` → `The bank's system files promises, callbacks, notes and transfers itself and tells you in your current instruction what happened; only confirm an action once the current instruction says it happened.` (de-duplicates "recorded"; keeps one clear rule.)

**H6 — pre-verification tasks list the banned words verbatim. [medium]**
Current (opening + every `ask_i`): `Do NOT mention collections, debt, payment, credit card, loan or any account to anyone in this step; ...`
Checks hit: *"the word 'collections' is not said before identity is verified"*, *"no debt read before the identity check"*, *"no amount or product disclosed"*. Echo risk is exactly these five tokens.
Proposed (positive-only): `Until the account holder is confirmed, you may speak only about confirming who you are speaking with and the security check. If asked why you are calling, say you can only discuss it with {{title}} {{last_name}} personally.` (second sentence already exists; only the token list goes).

**H7 — third_party task: "even if they ask or offer to pay". [low]**
Proposed: `...and give no account information, even if they ask what the call is about or offer to settle it for {{last_name}}.` — removes the verb "pay" from the pre-verification surface.

## Verified-OK (do not change)

- Opening TTS: `"We record this call."` — rewritten form, consistent with H3/H4/H5; the "recorded"-check only bans past tense before a write.
- Post-write TTS: `"Your promise of ... is recorded."` + IR `after_promise_sentence` verbatim — this is the *intended place*; checks *"text-message sentence said after the promise"*, *"Recorded p1 promise survives transfer"* align.
- Failure goodbyes: `"I will not record a promise for it."`, `"I am sorry, I could not record the promise because of a technical problem."` — negated, post-attempt, match *"Never claim p2 was recorded"* / *"no promise recorded"*.
- Clamp/date-cap instruction `"the latest date I can record for the X is ..."` — literal match to check *"agent says the latest date it can record is 4 November"* ✓ intentional alignment; keep.
- `"That does not match our records."` — fine.
- Debt statement `"calling from the Freya Bank collections team about a late payment"` — spoken post-verification only; rule 17 mandates it; PUB-01's 'collections' check is scoped to *before* verification. Keep (but see plan F4: it should come from IR wording eventually).
- `hardship` instruction *"say one short sentence of sympathy"* and floor wording *"the rest stays overdue"* — both verbatim from brief A; match checks lexically as intended.
- Extraction descriptions (`cust_intent` names "payment plan", "instalments", example amounts): never rendered to the customer; no judge exposure. No action.
- gen-ab: same surfaces as gen-a plus the clamp sentence; no additional tokens found.

## How to apply without touching builders' files

All of the above live in `compile.py`'s `default_prompts()`/RUNTIME instruction strings and, for H2, ideally in a new IR phrase slot (`amounts.floor_words`) filled by `extract.py` from the documents' own floor nouns. Wording-only changes; no routing, enum or math touched.

Repro scan: the extraction walk used here is re-runnable via
`.venv/bin/python - <<'EOF' … walk wf, print surfaces containing any of ["recorded","record","records","discount","waiver","instalment"," plan","how much","minimum","collections","debt","payment"] EOF`
— or: `grep -o "'[^']\{25,240\}'" out/gen-a.workflow.json | grep -Ei "recorded|discount|waiver|instalment|plan|how much|minimum|collections"` against the JSON-escaped file.
