# Unsupported and unresolved rules inventory — 11 October 2026

Use this before the hidden builds: match an unresolved topic to the families below, then inspect the exact audit entry in the appendix. A familiar topic is **not safe to ignore**. An unfamiliar topic needs fresh review. “Unresolved” includes unsupported behavior, ambiguous/missing source rules and harmless wording choices; it is not a list of proven runtime failures.

Scope: the repository currently has **25 distinct external packages and 28 audit files**, rather than 20. All are included; gv, harwick and no-today have repeat runs. Earlier findings are preserved and marked superseded, not counted as separate packages. No extractor/build/simulation was run for this inventory. The companion JSON contains every verbatim unresolved entry, source-document paths and SHA-256 hashes so later changes can be distinguished. This is a historical audit inventory, not certification that the current builder still has every limitation.

## Reported limitations to recognize

| Rule family | Existing audit evidence | Interpretation for a new hidden brief |
|---|---|---|
| Callback weekday filters | clean-vesper, policy-callback-weekdays | Next business day only AND a named weekday; CallbackPolicy.days has no weekday filter. |
| Split/day-specific callback windows | harbor | Multiple intervals and different Friday hours cannot fit one start/end pair. |
| Per-question identity lockout | harbor | One wrong answer to a specific question fails immediately, independent of the global counter. |
| Campaign/effective-date applicability | aster, bracken, fenbrook, harwick | Activation windows and which revision applies before its effective date; separate source ambiguity from missing schema. |
| Full-first even during a floor attempt | aster, bracken; harwick2 | Attempt DSL cannot directly represent the reported ordering nuance; harwick2 also flags an unstated floor-if-full-refused choice. |
| Percentage rounding mode/precision | policy-whole-unit-floor, sable, selvi; gv/gv2 | Whole-unit ceiling, nearest-cent half-up or unspecified rounding. Current percent calculation rounds to two decimals; do not equate all rounding requirements. |
| Words prohibited throughout a call | policy-forbidden-all-call | Schema only exposes the pre-verification prohibited-word list. |
| Refusal behavior depends on verification or saved promises | clean-vesper, callback-weekdays, forbidden-all-call, no-today, orrery, palisade, selvi, sable, tamarisk, grunthal, harwick | Single special-case action may not express pre/post-verification routing and outcome precedence. Check exact trigger and saved-promise handling. |
| Third-party instructions and boundaries | bracken, clean-vesper, fenbrook, gv/gv2, kurilian, orrery, palisade | Dictated relative sentence, no disclosure, no security answers/payment for holder, and availability questions lack dedicated fields in these audits. Some behavior may live in the template. |
| Missing callback time | clean-vesper, palisade, no-today, reason-every-close | Ask for an explicit clock time instead of guessing; reported without a dedicated IR flag. |
| Early/vague date handling | clean-vesper, callback-weekdays, forbidden-all-call, reason-every-close, fenbrook | Offer earliest eligible date; fenbrook instead closes after the second vague answer. Distinguish an unsupported alternative from ordinary template behavior. |
| Below-floor/full-only proposals | clean-vesper, fenbrook, kurilian, orrery, palisade, forbidden-all-call | Dictated rejection sentence, counteroffer then refusal, or full-only explanation. A numeric floor alone may not encode dialogue rules. |
| Discount/waiver/new-plan prohibition and consent correction | clean-vesper, forbidden-all-call, reason-every-close, sable | Audits report no dedicated fields; template behavior is not proof of extracted source coverage. |
| Reasons on successful closes | reason-every-close | Audit says promise/paid reasons only live in outcomes.table, without dedicated fields. Check actual close arguments, not enum presence alone. |
| Missing/disabled routes versus strict defaults | fenbrook, gv/gv2, kurilian, orrery, selvi, tessel | Intentionally absent hardship/already-paid/restructuring/deceased/callback routes must stay absent. Orrery explicitly reports filling disabled callback outcomes merely to pass validation. |
| Unsupported/unknown named case | amber, gv2, harwick2 | Payment-plan conflict, or robot question represented by phrases.robot_reply instead of a special-case name. Robot phrasing alone is not necessarily a missing capability. |

## Source gaps, contradictions and informational entries

| Family | Examples | Operator distinction |
|---|---|---|
| Missing dictated wording | Many; name-placeholders and notes-every-product contain only wording entries | Debt intro, today question, sympathy, protection explanation or write-failure wording. If only content is specified, a paraphrase is expected, not automatically unsupported. |
| Missing bands/deadlines or out-of-range products | amber, fenbrook, grunthal, gv, harwick, kurilian, palisade, tessel | Do not invent coverage. Kurilian has no bands/deadline; other packages omit only ranges outside their stated scope. |
| Missing close outcome or precedence | fenbrook, gv/gv2, kurilian, selvi, tamarisk | Relative/no-contact, account-read failure, or transfer after a saved promise; audit defaults are not documentary authority. |
| Contradictory calendar/date/attempt rules | gv/gv2, grunthal, harwick/harwick2 | Every-day week versus Sunday ban; missing roll direction; refusal consuming an attempt; ambiguous calendar branch. |
| Inconsistent codes/cross-references/source text | grunthal, harwick2, amber | Undefined code, nonexistent clause, contradictory paid/dispute instruction, garbled batch note handling, payment-plan conflict. |
| API required/property mismatch | gv/gv2, harwick/harwick2 | Amount property `sum` versus required `amt`; classify as API ambiguity, not a bank policy rule. |
| Identity budget disagreement | orrery | API tries_left versus memo limit; identify authority instead of silently importing a practice default. |
| Missing product metadata | harwick2 | No card suffix field; spoken naming cannot invent it. |

## Historical findings that must not be called currently unsupported without checking

- **Composite earliest deadline, expired-deadline no-promise, max-of floor:** cedar's older audit reports these as missing. Current policy.py exposes earliest/latest, dates.past_deadline and max_of; bankcal.py handles composite deadlines. This does not retroactively repair the archived extraction.
- **Ask for missing date parts:** aster/bracken say there is no explicit `ask` value; current policy.py documents `calendar.missing_date_parts="ask"`.
- **No promise today:** the first no-today audit reports a limitation; ext-policy-no-today2 has an empty unresolved list and current runtime checks dates.promise_today_allowed. Keep the first finding as history.
- **Sunday–Thursday business week:** ext-policy-sun-thu has no unresolved entries. Empty lists indicate no reported issue, not complete coverage proof.
- **Final compiler diagnostics:** current build.py emits mapping notes, unresolved topics and unknown special cases in workflow_compiled. Older eb329ea traces have these primarily in policy_compiled; use the updated runbook filter for both.

## Verbatim package evidence

Audit links below resolve to the original files. Array indices are zero-based. “No entries” means the audit's unresolved list is empty, not that its whole package was validated by this inventory.

### amber-valley — ext-amber.audit.json

Source: [out/ext-amber.audit.json](../../out/ext-amber.audit.json). 

- `unresolved[0]`: payment_plan row in §9 conflicts with §7 (never ask how much, never offer a new instalment plan); not compiled.
- `unresolved[1]`: No band for 0 days late or more than 60 days late.
- `unresolved[2]`: Month/day/year numeric date rule has no date identity question to apply to.
- `unresolved[3]`: Wording of the hardship sympathetic sentence is not dictated.

### codex-aster-quay — ext-aster.audit.json

Source: [out/ext-aster.audit.json](../../out/ext-aster.audit.json). 

- `unresolved[0]`: Campaign window (local now dates 14 Oct - 10 Nov 2026) has no IR field.
- `unresolved[1]`: Missing date components must be asked for; schema has no explicit 'ask' value for calendar.missing_date_parts (left at 'unresolved').
- `unresolved[2]`: 'Full-first still applies even to a later floor slot' cannot be expressed in the attempt DSL for band 1-6's floor slot.

### codex-bracken-thread — ext-bracken.audit.json

Source: [out/ext-bracken.audit.json](../../out/ext-bracken.audit.json). 

- `unresolved[0]`: Missing date components must be asked for; the IR has no explicit 'ask' value (missing_date_parts left at default 'unresolved').
- `unresolved[1]`: The final release is 'effective 14 October' (today is 2026-10-11); the documents do not say which values govern calls before that date. The final-release values are applied.
- `unresolved[2]`: How 'Full-first still applies even to a later floor slot' interacts with the 1–14 'floor by deadline' slot is not fully expressible in the attempt DSL.
- `unresolved[3]`: Third-party brevity / never accept third-party answers or promises / ask holder availability before callback have no dedicated IR field.

### codex-cedar-limits — ext-cedar.audit.json

Source: [out/ext-cedar.audit.json](../../out/ext-cedar.audit.json). 

- `unresolved[0]`: CR-D1 deadline is the earlier of two rules (6th business day vs last business day of current month); the DSL has no min-of-two, encoded with extra 'cap'/'combine' keys the compiler must honour.
- `unresolved[1]`: Deadline-before-today case (no promise, close cr-none/cr-r-refused) has no IR field.
- `unresolved[2]`: Effective floor combines a base field, a 25% rule rounded up to the cent, and a cap at full; the floor_rules DSL cannot express it natively, encoded with extra keys.

### codex-harbor-exceptions — ext-harbor.audit.json

Source: [out/ext-harbor.audit.json](../../out/ext-harbor.audit.json). 

- `unresolved[0]`: Memo B split callback window (Mon–Thu 09:00–12:00 and 14:00–18:00; Fri 09:00–11:30) cannot be expressed as a single start/end; stored 09:00–11:30, compiler must add the Mon–Thu slots.
- `unresolved[1]`: Memo A per-field rule (single wrong phone_suffix fails verification immediately, never re-asked) has no IR field; the compiler must enforce it alongside the global limit of four.

### fenbrook-table-sheet — ext-fenbrook.audit.json

Source: [out/ext-fenbrook.audit.json](../../out/ext-fenbrook.audit.json). 

- `unresolved[0]`: No dictated wording for the first ask, and no statement that the first ask is for payment today.
- `unresolved[1]`: A vague date after one re-ask closes CCC-NO / F-no instead of offering the k-date.
- `unresolved[2]`: The third-party sentence has no IR field; the close outcome for a third party who is not a wrong number is not stated.
- `unresolved[3]`: The below-floor sentence 'That is below what we can take.' has no IR field.
- `unresolved[4]`: No already_paid, restructuring, refuse_to_talk or deceased rule.
- `unresolved[5]`: Promise followed by transfer: precedence not stated (default kept).
- `unresolved[6]`: Effective date 14 October 2026 is not representable.

### grunthal-legal-register — ext-grunthal.audit.json

Source: [out/ext-grunthal.audit.json](../../out/ext-grunthal.audit.json). 

- `unresolved[0]`: 10.2 names note `ghb-disputed`, absent from 11.1, the codes list and the add_note enum; mapped to `ghb-dispute`.
- `unresolved[1]`: 7.1 'adjusted to a business day' gives no direction; 'preceding' assumed for the 20th-of-next-month candidate.
- `unresolved[2]`: No days-late bands defined; single band 1..90 from the API's dl_days range.
- `unresolved[3]`: Pay-today question wording not dictated.
- `unresolved[4]`: Hardship sympathy sentence wording not dictated.
- `unresolved[5]`: Clause 13 / 13.1 referenced by 3.4 and 7.5 does not exist.
- `unresolved[6]`: Interaction of 7.3 (today refusal consumes an attempt) with 7.2's single attempt.
- `unresolved[7]`: refuse_to_talk final outcome depends on 11.3 rank when a promise is already recorded.

### gv-finance-sheet — ext-gv.audit.json

Source: [out/ext-gv.audit.json](../../out/ext-gv.audit.json). Earlier run; superseded by `out/ext-gv2.audit.json`. 

- `unresolved[0]`: No days-late bands are defined; one catch-all band with the k-date is used.
- `unresolved[1]`: Rounding of 15% of amt_due in bottom_line is not stated.
- `unresolved[2]`: No paid outcome code exists; 'paid off and closed' closes No-PTP / No-PTP, so paid_outcome is No-PTP and no already-paid sentence is dictated.
- `unresolved[3]`: The sentence telling third parties to have the customer call the bank, and the third-party restrictions, have no schema field.
- `unresolved[4]`: Callback scheduled_outcome is undefined because callbacks are disabled.
- `unresolved[5]`: Conflict: every day is a business day vs 'sun day named -> not recordable'.
- `unresolved[6]`: No words are dictated for 'say it failed' after the second write failure.
- `unresolved[7]`: create_promise API mismatch: property 'sum' vs required 'amt'.
- `unresolved[8]`: Whether a transfer overrides a recorded promise is not stated.

### gv-finance-sheet — ext-gv2.audit.json

Source: [out/ext-gv2.audit.json](../../out/ext-gv2.audit.json). 

- `unresolved[0]`: Hardship/bereavement handling is not in the documents.
- `unresolved[1]`: No already-paid sentence or paid outcome; 'paid off and closed' is folded into dispute; paid_outcome set to No-PTP.
- `unresolved[2]`: Rounding of 15% of amt_due is not specified.
- `unresolved[3]`: Sunday vs. 'business day = every day of the week' conflict.
- `unresolved[4]`: Third-party sentence and non-disclosure rules have no IR slot.
- `unresolved[5]`: Transfer after a recorded promise: outcome precedence not stated.
- `unresolved[6]`: create_promise amount property: schema defines `sum` but requires `amt`.
- `unresolved[7]`: Robot question has no known special-case name; kept as phrases.robot_reply.

### harwick-lowe-register — ext-harwick.audit.json

Source: [out/ext-harwick.audit.json](../../out/ext-harwick.audit.json). Earlier run; superseded by `out/ext-harwick2.audit.json`. 

- `unresolved[0]`: Facilities with 0 or more than 60 days past have no band.
- `unresolved[1]`: Wording of the first pay-today question is not dictated (written from content).
- `unresolved[2]`: Wording of the 10.3 sympathy sentence is not dictated (written from content).
- `unresolved[3]`: 10.5 'treatment 10.6 otherwise' for a non-insisting request for a person is not spelled out.
- `unresolved[4]`: 10.6 refusal after a written payment closes per 11.3 (HL-PAY), not HL-FULL/hl-refuse.
- `unresolved[5]`: No Sunday shift for the 9th-calendar-day branch of band (a).
- `unresolved[6]`: M-77 is in force from 13 Oct 2026 00:00 UTC; rules for an earlier `now` are not stated; S-72 is dated 'Wed 13 Oct' though that date is a Tuesday.
- `unresolved[7]`: create_promise schema: property `sum` vs required `amt`.

### harwick-lowe-register — ext-harwick2.audit.json

Source: [out/ext-harwick2.audit.json](../../out/ext-harwick2.audit.json). 

- `unresolved[0]`: Whether the 9th-calendar-day branch of band (a) is shifted when it falls on a Sunday (7.1(a)).
- `unresolved[1]`: No wording for the today question (7.3) or the hardship sympathy sentence (10.3); minimal sentences written.
- `unresolved[2]`: create_promise amount property: API defines `sum` but requires `amt`; documents silent.
- `unresolved[3]`: Facilities at 0 or over 60 days past are not covered by any band.
- `unresolved[4]`: Robot question has no known special-case name; handled via phrases.robot_reply.
- `unresolved[5]`: No card last-digits field; card named 'store card'.
- `unresolved[6]`: 10.2 'A payment of this very overdue amount is NOT what 10.1 covers' conflicts with 10.1.
- `unresolved[7]`: 10.5 'treatment 10.6 otherwise' is unclear about when refusal treatment applies.
- `unresolved[8]`: 9.4 whole-batch refusal note handling is garbled; no note code named for it.
- `unresolved[9]`: 11.5 'the failure is stated' has no wording.
- `unresolved[10]`: Band (c) first attempt: floor-if-full-refused not stated.
- `unresolved[11]`: Mail S-72 is headed 'Wed 13 Oct 2026', but that date is a Tuesday (no value depends on it).

### kurilian-sat-bullets — ext-kurilian.audit.json

Source: [out/ext-kurilian.audit.json](../../out/ext-kurilian.audit.json). 

- `unresolved[0]`: The documents define no days-late bands and no deadline, so bands is empty. The validator needs at least one band, and making one up would invent a threshold.
- `unresolved[1]`: No question about paying today is dictated, so today_question is empty.
- `unresolved[2]`: The third-party sentence and the below-full-proposal sentence have no phrase field. The documents give no close outcome for a third party who is not a wrong number.
- `unresolved[3]`: The documents do not say what to say when the write fails; they only say to say that it failed.
- `unresolved[4]`: Deceased account holder is not covered.
- `unresolved[5]`: Promise recorded and then a transfer: the documents do not say which outcome wins; the default is kept.
- `unresolved[6]`: Hardship and already-paid have no rule; statements of that kind have no defined route other than the dispute wording ('it was paid off and closed').
- `unresolved[7]`: The callback and deceased outcome pairs stay empty because callbacks are not used and deceased is not covered. A strict check of these pairs may flag them as empty.

### orrery-seven — ext-orrery.audit.json

Source: [out/ext-orrery.audit.json](../../out/ext-orrery.audit.json). 

- `unresolved[0]`: Hardship, restructuring and already-paid: the documents explicitly have no rule for them (continue the ordinary full-only discussion), so they are not routed as special cases.
- `unresolved[1]`: Callback outcomes: the documents say callbacks are disabled and there is no callback outcome. The slots are filled with NR0/N0 (relative/no contact) only so the file passes validation.
- `unresolved[2]`: The relative's sentence "Please ask the customer to call our published number." has no IR field.
- `unresolved[3]`: Below-full proposals: explain full-only, then treat rejection as a flat no. This is not expressible beyond floor=100%.
- `unresolved[4]`: Refusal to talk before verification closes ID0/D1, not No-PTP/R01.
- `unresolved[5]`: The wording for a failed promise save is not dictated.
- `unresolved[6]`: The API's tries_left may disagree with the memo's one-wrong-answer limit.

### palisade-mail — ext-palisade.audit.json

Source: [out/ext-palisade.audit.json](../../out/ext-palisade.audit.json). 

- `unresolved[0]`: No band/deadline for products more than 90 days late.
- `unresolved[1]`: Below-floor counteroffer and rejected-counteroffer-as-refusal have no dedicated IR field.
- `unresolved[2]`: Refusal-to-talk second refusal marks all remaining products R-1 (multi-product nuance) and IDStop/I-2 before verification.
- `unresolved[3]`: Relatives may not verify or pay for the holder; not expressible in IR.
- `unresolved[4]`: Callback: ask for missing clock time; not expressible in IR.

### r2-clean-vesper — ext-clean-vesper.audit.json

Source: [out/ext-clean-vesper.audit.json](../../out/ext-clean-vesper.audit.json). 

- `unresolved[0]`: Callback must be on the next business day AND that day must be Tuesday or Thursday; the IR cannot express the weekday restriction (no eligible slot otherwise).
- `unresolved[1]`: No dictated debt-intro sentence; only content (every product, amount, days late) is required.
- `unresolved[2]`: Wording of the hardship sympathetic sentence is not dictated.
- `unresolved[3]`: refuse_to_talk second refusal before verification closes ID-STOP/NO-CHECK, while after verification it marks remaining products DECLINE; the IR has one action per case.
- `unresolved[4]`: Third-party non-disclosure, missing callback time must be asked, below-earliest-date proposals offered the earliest eligible date, and 'never offer discount/waiver/new plan' are behavioural rules without dedicated IR fields.

### r2-policy-callback-weekdays — ext-policy-callback-weekdays.audit.json

Source: [out/ext-policy-callback-weekdays.audit.json](../../out/ext-policy-callback-weekdays.audit.json). 

- `unresolved[0]`: Callback must be on the next business day AND that day must be Tuesday or Thursday; otherwise no callback date (IR cannot express the weekday filter).
- `unresolved[1]`: Hardship sympathetic sentence wording is not dictated.
- `unresolved[2]`: Refuse-to-talk close after verification follows §10 precedence; before verification ID-STOP/NO-CHECK.
- `unresolved[3]`: debt_intro wording is not dictated.
- `unresolved[4]`: Customer date before the earliest eligible date -> offer the earliest eligible date (no IR field).

### r2-policy-forbidden-all-call — ext-policy-forbidden-all-call.audit.json

Source: [out/ext-policy-forbidden-all-call.audit.json](../../out/ext-policy-forbidden-all-call.audit.json). 

- `unresolved[0]`: guaranteed/penalty/lawsuit are forbidden for the whole call, but the IR only has a list of words forbidden before verification.
- `unresolved[1]`: The hardship sympathetic sentence and the debt introduction wording are not dictated.
- `unresolved[2]`: After verification, a second refusal to talk marks the remaining products DECLINE and closes under §10 precedence; the close action NO-AGREEMENT/DECLINE only applies when no promise was saved.
- `unresolved[3]`: Below-floor counteroffer, the ban on discounts/waivers/plans, and offering the earliest eligible date for an early date have no IR fields.

### r2-policy-name-placeholders — ext-policy-name-placeholders.audit.json

Source: [out/ext-policy-name-placeholders.audit.json](../../out/ext-policy-name-placeholders.audit.json). 

- `unresolved[0]`: Hardship sympathetic sentence wording is not dictated (§9); a generic sentence was used.
- `unresolved[1]`: Debt introduction wording is not dictated (§1 dictates only the content).

### r2-policy-no-today — ext-policy-no-today.audit.json

Source: [out/ext-policy-no-today.audit.json](../../out/ext-policy-no-today.audit.json). Earlier run; superseded by `out/ext-policy-no-today2.audit.json`. 

- `unresolved[0]`: Today is never an eligible promise date (§5/§6); dates.promise_today_allowed must stay true for the template, so the compiler must block today.
- `unresolved[1]`: debt_intro words are not dictated, only its content (§1).
- `unresolved[2]`: Hardship sympathetic sentence words are not dictated (§9).
- `unresolved[3]`: Refusal to talk before verification closes ID-STOP/NO-CHECK, after verification marks remaining products DECLINE (§9): two-branch behaviour not expressible in one special case.
- `unresolved[4]`: Callback with missing clock time must be asked, never guessed (§4): no IR field.

### r2-policy-no-today — ext-policy-no-today2.audit.json

Source: [out/ext-policy-no-today2.audit.json](../../out/ext-policy-no-today2.audit.json). 

No unresolved entries.

### r2-policy-notes-every-product — ext-policy-notes-every-product.audit.json

Source: [out/ext-policy-notes-every-product.audit.json](../../out/ext-policy-notes-every-product.audit.json). 

- `unresolved[0]`: debt_intro: the documents dictate the content (every product, amount, days late) but not the sentence; a paraphrase is used.
- `unresolved[1]`: Hardship sympathetic sentence wording is not dictated; a short paraphrase is used.

### r2-policy-reason-every-close — ext-policy-reason-every-close.audit.json

Source: [out/ext-policy-reason-every-close.audit.json](../../out/ext-policy-reason-every-close.audit.json). 

- `unresolved[0]`: No IR field for the close reasons of AGREED (SAVED) and SETTLED (PAYMENT-REPORTED); carried only in outcomes.table.
- `unresolved[1]`: Hardship sympathetic sentence and debt introduction wording are not dictated; written sentences are used.
- `unresolved[2]`: Callback 'Missing clock time: ask, never guess' has no IR field.
- `unresolved[3]`: 'If it precedes the earliest eligible date, offer the earliest eligible date' has no IR flag.
- `unresolved[4]`: 'Never offer a discount, waiver or a new payment plan' and 'A correction invalidates consent' have no IR fields.

### r2-policy-sun-thu — ext-policy-sun-thu.audit.json

Source: [out/ext-policy-sun-thu.audit.json](../../out/ext-policy-sun-thu.audit.json). 

No unresolved entries.

### r2-policy-whole-unit-floor — ext-policy-whole-unit-floor.audit.json

Source: [out/ext-policy-whole-unit-floor.audit.json](../../out/ext-policy-whole-unit-floor.audit.json). 

- `unresolved[0]`: The floor-rule DSL cannot express rounding UP to a whole currency unit (ceil(0.23*past_due), never cents); recorded as a percent rule plus an unresolved entry.
- `unresolved[1]`: Hardship sympathetic sentence is not dictated; a short sentence was written.
- `unresolved[2]`: Refuse-to-talk: ID-STOP/NO-CHECK before verification; after verification remaining products are marked DECLINE and the close follows §10 precedence.

### selvi-turkish-fields — ext-selvi.audit.json

Source: [out/ext-selvi.audit.json](../../out/ext-selvi.audit.json). 

- `unresolved[0]`: No already_paid special case: the documents say there is no already-paid rule or paid outcome, and a continue-only already_paid case would require a paid_outcome. The sentence is kept in phrases.already_paid_sentence.
- `unresolved[1]`: Floor rounding is half-up to the nearest cent, but the percent floor rule has no rounding field.
- `unresolved[2]`: The hardship sympathy sentence is not dictated; a short sentence was written.
- `unresolved[3]`: Refuse_to_talk before verification closes dogrulanmadi/istemedi; the special-case action only covers the reddetti note after verification.
- `unresolved[4]`: No close outcome is given for a failed get_account.

### tessel-register — ext-tessel.audit.json

Source: [out/ext-tessel.audit.json](../../out/ext-tessel.audit.json). 

- `unresolved[0]`: No paid outcome exists (codes: 'Paid route absent'), so outcomes.paid_outcome stays empty; a validator that requires it will flag this.
- `unresolved[1]`: No already-paid rule and no restructuring rule; these remarks only get acknowledged honestly within the ordinary discussion.
- `unresolved[2]`: Bands cover days late 1-75 only; nothing is said for more than 75 days late.
- `unresolved[3]`: The hardship sympathetic sentence is required, but its wording is not dictated.

### v24-sable-percent — ext-sable.audit.json

Source: [out/ext-sable.audit.json](../../out/ext-sable.audit.json). 

- `unresolved[0]`: Floor rounding is 'nearest whole cent'; the percent floor rule has no rounding-mode field.
- `unresolved[1]`: Hardship sympathy sentence wording is not dictated; 'I am sorry to hear that.' is a written-to-content sentence.
- `unresolved[2]`: Refusal to talk has no dedicated close pair; outcome follows the general precedence.
- `unresolved[3]`: Prohibition on offering discounts, waivers or new instalment plans has no IR field.

### v24-tamarisk-thread — ext-tamarisk.audit.json

Source: [out/ext-tamarisk.audit.json](../../out/ext-tamarisk.audit.json). 

- `unresolved[0]`: Hardship sympathy sentence wording is not dictated (wrote 'I am sorry to hear that.').
- `unresolved[1]`: The final close after a refuse_to_talk second refusal is not stated explicitly; it follows outcome precedence.
- `unresolved[2]`: No wording is given for the account-protection explanation after a security refusal.
- `unresolved[3]`: No wording is given for telling the customer that a promise write failed.
