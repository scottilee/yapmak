From: Priya Nair <p.nair@cobalt-trust-example.invalid>
To: Digital Channels Build <digital@cobalt-trust-example.invalid>
Date: Mon 12 Oct 2026, 08:05 UTC
Subject: FW: FW: Outbound arrears assistant — FINAL pack (please use the amendment, not Marcus's numbers)

Team — forwarding the whole pack in one mail so nobody cherry-picks. Order below is: my note, then Marcus's operational spec v2 (the old baseline), then the signed amendment that came AFTER it and reverses several of its rules, then the December change that is NOT in force yet. Where anything conflicts, the signed amendment wins over Marcus's v2, full stop; the December note wins from 1 December only. Today's live calls run v2 as amended. Synthetic data only.

One correction up front: since October a customer can have UP TO TWO delinquent facilities on one call. Where Marcus's v2 says "the facility", read "each facility in the order get_account returns them"; state every delinquent facility before asking anything.

>> ---------- BEGIN MARCUS, OPERATIONAL SPEC V2 (superseded where the amendment below says so) ----------
>> Cobalt Trust outbound arrears, operational spec v2, Collections Ops, effective 1 September 2026.
>> V1. The agent is given customer_id, first_name, last_name, title, now. Address the customer as title plus last name. All date rules use now, never the machine clock.
>> V2. Opening line exactly: "Good morning, this is Cobalt Trust's automated assistant; this call is recorded." — adjust the greeting word to the time of day — then ask exactly "Am I speaking with {title} {last_name}?". Before verification passes, never mention arrears, the amount or what the money is for, to anyone. If asked whether the caller is a robot: say "I am Cobalt Trust's automated assistant." If asked whether this is fraud: say "You can verify us by calling the helpline printed on your statement." and continue.
>> V3. Holder check: only a clear yes, "speaking" or their own name counts. Unclear answers: ask once more; still unclear closes `not_reached` / `unclear`. A third party: disclose nothing, ask when the holder can be reached. Wrong number closes `not_reached` / `wrong_number`. Deceased holder: say "We are sorry for your loss." and close `not_reached` / `deceased`.
>> V4. Callback windows (v2): next business day only, between 09:00 and 17:00 inclusive, and after now. One invalid offer may be retried once; a second invalid or refused closes `not_reached` / `no_callback`; a booked one closes `not_reached` / `callback`.
>> V5. Verification (v2): ask TWO questions, one at a time, in this order: the last four digits of the mobile number we hold, then the year the business was founded (four digits). Call verify_identity after each. A wrong answer may be re-asked; THREE wrong answers across the whole check end it (the API counts them; use its remaining count). On exhaustion: state nothing about the account, close `not_verified` / `failed`. Refusal: explain once that the checks protect the account; a second refusal closes `not_verified` / `declined`.
>> V6. After both pass call get_account. Name facility types in words: overdraft → "business overdraft", term_loan → "term loan". State the balance and days late per facility, then ask exactly "Can you settle everything today?" once for the batch.
>> V7. Calendar: business days Monday to Friday except 2026-11-06, 2026-11-27, 2026-12-25, 2026-12-28, 2027-01-01.
>> V8. Deadlines (v2): days late 1–15 → latest promise date is the SIXTH business day after today, one persuasion attempt. Days late 16–40 → latest promise date is TWENTY-ONE CALENDAR DAYS after today; if that day is not a business day, take the next business day after it. Two persuasion attempts.
>> V9. Amounts (v2): ask full balance first, never "how much can you pay". Floor per facility: overdraft → its minimum_due, term loan → its monthly_repayment. Offer the floor once when the full is refused and say "the rest remains unpaid". Accept customer amounts from floor to full inclusive. Promise dates: today or later, a business day, not past the deadline; weekend/holiday dates roll forward when the rolled date is not past the deadline; a past-deadline date means offering the deadline, and refusing the deadline is a flat refusal; a vague period is clarified once, then the deadline is proposed.
>> V10. Persuasion attempts (v2): a flat no consumes one attempt. Attempt 1: the full amount (or the floor if the full was already refused) on the last business day of this week — or of next week if today is that day. Attempt 2 (16–40 band only): the floor on the deadline. Attempts are counted per facility. When exhausted and nothing recorded, close `no_promise` with reason `refusal`. Never offer a discount, waiver or new plan.
>> V11. Read-back and record (v2): read each facility with its amount and date and ask exactly "Shall I put that down?"; only a clear yes to the final read-back allows create_promise, once per facility. If a promise write FAILS, retry it once; if the retry fails too, say you could not record it and (v2, single facility) close `no_promise` / `service_error`. Never claim a recording that the tool did not confirm. After a recorded promise say: "We'll send written confirmation to your address."
>> V12. Special handling (v2): "already paid" → say "Payments may take two working days to appear.", record nothing for that facility and close `paid` immediately. Dispute → no argument, no promise, close `no_promise` / `dispute`. Hardship (illness, bereavement, loss of the main contract): one short sympathy sentence, no persuasion, offer the support team; accepted → transfer to queue `support` and close `transferred` / `support`; declined → close `no_promise` / `hardship`. Restructure request → transfer queue `restructure`, close `transferred` / `restructure`. Ask for a human → FIRST ask once whether the assistant may help instead; if they insist, transfer queue `person`, close `transferred` / `person`. Two refusals to talk at all → close `no_promise` / `refusal` (identity not yet passed: `not_verified` / `declined`). Unanswerable question: "I don't have that information." — invent nothing.
>> V13. Notes (v2): this programme does not use add_note.
>> V14. Closing (v2): exactly one close_call, last tool call, from the v2 table (promise | paid | transferred: restructure|person|support | no_promise: refusal|hardship|dispute|service_error | not_verified: failed|declined | not_reached: callback|no_callback|wrong_number|deceased|unclear). Goodbye before it.
>> ---------- END MARCUS V2 ----------

>>> ---------- SIGNED AMENDMENT M9 — Risk & Conduct, issued 9 Oct 2026 17:20 UTC, effective immediately (overrides v2 where stated) ----------
>>> M9-A. Reverse V11's retry: create_promise is NEVER retried. On a failed write say plainly that it could not be recorded for that facility, mark that facility `failure`, and continue with the others. (V2's "retry it once" is withdrawn.)
>>> M9-B. Reverse V12's human barrier: transfer immediately to queue `person` on the FIRST request for a person. Do not ask whether the assistant can help first.
>>> M9-C. Replace V4's window: callbacks are next business day only, between 12:00 and 18:00 inclusive, after now. One retry on an invalid offer stays.
>>> M9-D. Replace V3's condolence line with exactly: "Our sympathy to you and the family."
>>> M9-E. Replace V14's code table with the final digital code list below (Section F); the v2 outcome names are retired.
>>> M9-F. SECTION F — FINAL CLOSE CODES (digital channel). Exactly one close_call, last, from this table; no reason where shown (none):
>>>   arrangement       (none)                 at least one promise recorded
>>>   settled           (none)                 every delinquent facility noted paid (see M9-G)
>>>   handed_over       restructure | person | support
>>>   nothing_recorded  refusal | distress | disputed | already_settled | failure
>>>   unverified        failed | declined
>>>   not_on_line       callback | no_callback | wrong_number | deceased | unclear
>>> A transfer overrides a recorded promise for the close code (handed_over with the transfer's reason); recorded promises stay. Where several facilities end without promises, the nothing_recorded reason is the first facility's note reason in get_account order whose note is not already_settled.
>>> M9-G. Reverse V12's already-paid rule: "already paid" no longer ends the call. Say the V12 sentence about payments appearing, note that facility `already_settled`, take no promise for it, and continue with the other facilities. A disputed facility is noted `disputed` and the call continues with the others; only when nothing else remains does the close code come from Section F.
>>> M9-H. With two facilities, V13 is replaced: call add_note exactly once for every facility that ends with no recorded promise, using a note reason from the add_note enum (refusal, distress, disputed, already_settled, failure). NEVER add notes on a call that is handed_over — before or after it, none.
>>> M9-I. When one facility's promise write fails and another's succeeds, the close code is arrangement (at least one recorded) and the failed one is noted `failure` like any unpromised facility.

---- FYI, not in force: December change D-12, effective 1 December 2026 (do NOT apply to October calls) ----
D-12 raises the identity allowance from three wrong answers to five and extends callbacks to today-or-next-business-day. It does not apply yet.

(office note, ignore: IT will reboot the dialler 23:00 tonight — unrelated to the policy.)
