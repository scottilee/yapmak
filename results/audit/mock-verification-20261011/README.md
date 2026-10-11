# Independent deployed-mock verification — 11 October 2026

**Status: blocked; no deployed endpoint behavior verified.** Target: https://yapmak-bank-mock.winter-mountain-4405.workers.dev . Scope requested: every endpoint for every supplied test customer, compared with the authoritative service contract.

## Evidence and blockers

GET `/`, `/health` and `/openapi.json` received HTTP 403 from the sandbox network gate. Reading the body confirmed `Approval required for yapmak-bank-mock.winter-mountain-4405.workers.dev:443.` Retrying health with a browser-style User-Agent produced the same approval response. These are **not Worker failures** and do not establish deployment health. No write, reset or customer request reached the Worker.

The current checkout contains `mock/src/contract.js`, explicitly labelled as a scaffold to fill from the final zip. Its `CUSTOMERS` array is empty, as are note-reason, queue, outcome and close-reason lists. No authoritative final service contract or test-customer workbook was found in the checkout. The earlier practice fixtures are not an independent oracle for the final mock. Local source cannot establish which version is deployed.

## Local source findings to check against the final contract

These are observations about the scaffold, **not confirmed deployed-contract discrepancies**:

1. **Records are held in per-isolate memory** (`mock/src/index.js:5–6`). Multiple Cloudflare isolates or an isolate restart can separate or lose identity progress and ledger entries. Returning a promise ID does not make its record durable. Review against the organizer's session and records-readback requirements.
2. **State is keyed by customer, not call/session** (`:28`, `:51`, `:86`). A second call can inherit verification, previous promises or a previous close. The only reset shown clears all customers in that isolate (`:107`); do not use it while another operator is testing.
3. **Correct identity answers are accepted with zero attempts remaining** (`:30–35`). Whether exhaustion should lock verification must come from the contract; it cannot be assumed from the practice policy.
4. **The read-account endpoint does not check verification** (`:40–43`), despite its local API summary saying “verified customer.” The bank API may intentionally leave policy enforcement to the agent, so this needs a contractual decision rather than an assumed defect.
5. **Validation is incomplete compared with the advertised shapes:** create_promise coerces a numeric string to a number and checks date shape only (`:48–50`); callback accepts date/time shapes without validating actual calendar/time values (`:67–68`); add_note does not check product existence (`:59–61`). None of these observations is a claim that the bank should enforce payment-policy limits.
6. **Closing again with a different valid outcome returns success without changing the original record** (`:83–88`). Same-outcome retry idempotence and conflicting-outcome behavior need separate checks against the contract.
7. **Diagnostic routes and global reset have no visible authentication/session scope** (`:103–107`). Scorer/reset access requirements need confirmation from the contract before exercising reset.

## Coverage remaining

| Endpoint in local scaffold | Per-customer checks required | Status |
|---|---|---|
| verify_identity | Exact answers/normalization; wrong answers; remaining budget; all-verified; exhausted-budget behavior; call isolation | Blocked |
| get_account | Every returned customer/product field against supplied data; unknown customer and verification behavior | Blocked |
| create_promise | Valid write/readback; product/customer isolation; malformed amount/date; duplicate and retry semantics | Blocked |
| add_note | Each allowed reason; valid/unknown product; missing fields; persisted note | Blocked |
| schedule_callback | Valid date/time and readback; malformed values; duplicates/session isolation | Blocked |
| transfer_to_agent | Every contract queue; unknown queue; persisted transfer | Blocked |
| close_call | Every allowed outcome/reason combination; persisted close; identical retry and conflicting repeat | Blocked |
| health/openapi/records/reset and any contract-specific routes | Live shapes, customer count, state readback, scoped reset and scorer integration | Blocked; no reset attempted |

Next: approve the host network request, provide the final contract/customer-data paths, read the live API and existing records, then run a contract-derived customer × endpoint matrix using isolated sessions. Preserve before/after records and report exact expected-versus-observed responses. No deployment or mock source change has been made by this review.
