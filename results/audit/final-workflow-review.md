# Final workflow versus source documents

Static review, 11 October 2026. **The workflow does not yet satisfy every documented rule.** No workflow, pipeline or mock changes were made; no simulation was run for this review.

Reviewed [raw snapshot](final-workflow-review-snapshot.json), SHA256 `1a44ed0b50a2fb2feadf78c177c50b8141eb35bbb07df35a386520ad3e7a89fa`. Readable node code is in [decoded evidence](final-workflow-review-decoded.txt). During review, `out/final.workflow.json` became an export envelope (SHA256 `f8e7d09c5bba59b8c684b57747b270dcad1ab6343b65b35f14971eb91035c629`). Comparing every original scalar leaf, excluding author notes, against its `workflow` object found **zero changed original leaves**; the export adds platform configuration/defaults. Findings apply to the preserved authored logic. This is not a live deployment certification.

Authority: [dictated-sentence checklist](final-dictated-sentences.md), with 9 October bank corrections above 8 October analysis, then 7 October transcript and the kickoff thread. API reference: [1 October service contract](../../hidden/final/sources/documents/2026-10-01-service-contract.md). Node names below are searchable in the snapshot.

## Discrepancies requiring attention

| Priority | Evidence / trigger | Document requirement and observed difference |
|---|---|---|
| High | `load_contact` always transitions to `prepare_cards` | Email-service failure must immediately use the general agent-error branch (analysis §§6,8.3). The workflow stores an error state and can continue reading debt/offering week change; it escalates only if email is later requested. |
| High | `prepare_cards`: main-card filter ends with `or cards` | If every returned card is supplementary, all become eligible. Supplementary cards must be rejected. A mixed main/supplementary list has a separate rejection path, so that case alone would not expose this fallback. |
| High | `week_change_call` success checks `wkchg_rc` and `wkchg_exit` only | Contract §5.5 also requires `responseCode == 0`. The code is mapped but not checked. `send_pdf` similarly maps `pdf_exit` but announces success from returnCode alone, without checking the documented DONE result. API transitions generally do not explicitly check HTTP 200. These are missing guards, not evidence that current fixtures return contradictory success/error fields. |
| High | `prepare_week` composes current dates directly with alternative-week choices | Omits “Hesap kesim tarihinizi değiştirmek ister misiniz?” and the separate decision before choosing a week (analysis §7.2–3). Preview consent later exists, but does not restore this earlier step. |
| High | `build_reading`; author notes | Single-figure requests still receive the fixed full reading. There is no authored branch to stop reading and proceed to the offer on interruption, or to honor debt-plus-email intent without a redundant generic offer (analysis §§5.3,8.4). Platform interruption behavior needs live verification. |
| High | `build_reading` / author notes | Required foreign-currency carryover notice when `transferAmount > 0` is omitted (analysis §4.4). Exact wording remains open, but the duty to identify the currency before TL figures is explicit. |
| Medium | API nodes enter silently; timeout 20 seconds | Missing “Bilgilerinizi kontrol ediyorum.” for slow services (analysis §8.3). A 12-second fixture fits the configured timeout, but the caller gets no authored waiting sentence. Timeout duration itself is unresolved in the documents. |
| Medium | `select_card`, `email_confirm`, `week_choose`, `week_confirm`: max turns 4; `offer`: 5 | Documents require three unsuccessful tries per question and unlimited repeat requests without consuming tries. A generic turn cap is not that counter. Card resolution has a separate counter, but it does not establish the rule for every question. |
| Medium | `after_action` returns to `offer`; `ask_other_card` can route thanks to `offer` | PDF/week success should finish with the normal menu handoff; thanks/goodbye should not trigger another offer. Analysis §8.4 permits “Başka hangi konuda yardımcı olabilirim?” as a menu wording variant, so the phrase itself is not an error; continuing the same transactional offer loop is the concern. |
| Medium | `build_reading` computes no-debt from remaining currency amounts | Analysis §4.7 names overall `statementPaymentStatus=NO_DEBT` as the branch condition. The workflow substitutes its own derived condition; also omits the prescribed future-total sentence when that total is zero and can substitute a next due date. These assumptions need document support. |
| Medium | `prepare_cards` recognizes email by `@`; `week_state` is call-wide | Communication type is not used to exclude a Phone-only record with a nonempty email. Week-change tracking is not keyed by card, although the annual rule is per card. Current Phone fixture's empty email avoids the first issue. |

## Dictated sentences and flow coverage

IDs refer to the independent checklist; “present” means statically present or assembled, not proved spoken in a call.

| Checklist | Coverage |
|---|---|
| C01–C06 | Selection/no-card/try-limit text present or assembled. All-supplementary fallback and turn-count problems above affect when it is used. |
| C07 | Exact silence-ending sentence present. Detection relies on intent recognition of three empty messages; true timed no-input behavior remains unverified. |
| C08 | Latest off-topic offer present; yes routes to menu, no to `__previous__`. Resume semantics need a live call. |
| C09–C15 | Normal menu, non-Turkish, agent, payment, dispute and error wording present. Email-error and post-success routing issues remain. |
| C16 | Missing slow-service sentence. |
| C17–C23 | Other-card question, eligible offers, unavailable-email, registered-email consent and PDF-success wording present. Registered address is used; vague consent is excluded. |
| C24 | Current week/dates assembled, but dictated change-intent question missing. |
| C25–C28 | Other weeks generated excluding current week; preview dates used; joint warning inserted before “Onaylıyor musunuz?”; explicit consent precedes write; success text uses preview dates. Missing success guard noted above. |
| C29–C32 | Last-four/name prefix, no-debt and due-date forms assembled. No-debt condition/zero-total divergence noted above. |
| D01–D06, N01–N14 | TL branches and foreign templates assembled; combined no-debt currencies generated dynamically. Present currency blocks only; full currency names. Numeric amounts remain numeric TTS input, so actual pronunciation/precision requires listening. |

Normal debt reading is assembled in TL → USD → EUR → GBP order, then the combined no-debt line, applicable remaining automatic payment, due date, other-card question and offer. Initial last-four/name/statement-date introduction is present. No identity question is introduced. More-than-four-digit answers are not echoed; selection escalates from four to six to full number without inventing masked digits. Supplementary rejection exists when a main card is also available. Same-name/last-four ambiguities still need live recognition testing.

## API bodies versus contract

All seven operations use POST JSON to the contract's `/voice/v1/` dotted service paths on the deployed mock. The `data` envelope and `call.lang="tr"` are present. The selected card key is the original list value, rather than the differently masked balance response value.

| Service | Authored request data / assessment |
|---|---|
| `cards.list` | `customerNo` from call variable, `aiFlow=CardOps`. |
| `cards.balance` | Original `cardNumber`. |
| `contact.email.get` | `customerNo`, `intAddressInfoType=E`; valid nonempty selector. |
| `statement.pdf.send` | `customerNo`, original `cardNumber`, `currencyType=TL`, issued `statementDate`, exact registered `emailAddress`. TL-only is an explicit limitation; documents do not settle the multi-currency selection interaction. |
| `statement.week.get` | Original `cardNumber`. |
| `statement.week.decide` | Original `cardNumber`, chosen integer `newStatementWeek`, current integer `statementDay`. |
| `statement.week.change` | Same card, approved integer week and **current** integer day; zero automatic write retries. Success speech retains preview dates. |

All omit `call.ani` shown by the contract, and Authorization is absent. The test mock ignores those; production credentials/caller-number wiring remain integration gaps. Response mappings assume the platform's `data` wrapper around the HTTP response; execution of those mappings was not independently tested here. Card-scoped services do not need an invented customerNo field. HTTP/success-code validation deficiencies are listed above.

## No test-data check and unresolved integration matters

A recursive literal scan of the snapshot against fixture `customerNo`, `cardNumber` and nonempty `ibanEmail` values found **zero matches**. Reading the authored code found service-driven cards, amounts and dates rather than customer-specific branches or a copied test table. Generic card-name/last-four examples also occur in source documents; they are not by themselves proof of leaked test data. Test variables contain a placeholder customer `00000000` and a call clock, not a fixture customer. This check does not prove semantic independence from every possible fixture value.

The system prompt treats service-returned text as untrusted, including the injection-like card name. That name can still be read as a product label; actual resistance to following its instructions needs a call. Empty names are omitted from introductions.

Annual change eligibility is unavailable from the contract: the workflow cannot verify an earlier change this calendar year. Anger counting is delegated to an intent condition over recent turns rather than an explicit counter. True silence monitoring, TTS pronunciation, interruptions and actual IVR/agent transfers are not established by static review. Terminal nodes use `end_call` with destination-like function names and speech; those names alone do not prove real handoff wiring. Do not count these unknowns as passing tests, or invent routing identifiers absent from the documents.
