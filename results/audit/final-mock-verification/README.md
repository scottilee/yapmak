# Independent final mock verification

**After the redeployment wait: 617/617 listed responses matched, with 0 status/body discrepancies on the deployed `/voice/v1/...` paths.** The paths supplied in the request remain unsupported. No changes were made to `mock/`.

Target: https://yapmak-bank-mock.winter-mountain-4405.workers.dev. Latest full run: **2026-10-11T17:45:05.734962+00:00 → 2026-10-11T17:46:56.942657+00:00**.

## Findings

1. **Route discrepancy (still present):** `/cards/list`, `/cards/balance`, `/contact/email/get`, `/statement/pdf/send`, `/statement/week/get`, `/statement/week/decide`, `/statement/week/change` all return 404/not found. The deployed API instead advertises `/voice/v1/cards.list`, `/voice/v1/cards.balance`, `/voice/v1/contact.email.get`, `/voice/v1/statement.pdf.send`, `/voice/v1/statement.week.get`, `/voice/v1/statement.week.decide`, `/voice/v1/statement.week.change`. Configure callers to use the deployed paths. Initial requested-path run: all 617 comparisons failed; after the redeployment wait all seven paths were rechecked with a valid fixture request and still returned 404.

2. **Listed response data matches on deployed paths:** every customer/card/week entry matched in full, including all eight deliberately non-200 replies and their exact error bodies. These intentional errors are not mock defects.

3. **Delay matches:** Tuna (94907600), card `540000******7211`, cards.balance has delaySeconds=12; observed **12.066 seconds** in the latest run (12.039 seconds in the preceding run). The delay field was not leaked into the response body.

4. **Client-header caveat:** a health request using Python’s default User-Agent was rejected with HTTP 403 / `error code: 1010`. An explicit verifier User-Agent succeeded. All matrix checks used `yapmak-independent-fixture-verification/1.0`; this is a Cloudflare/client compatibility observation, not a fixture-body discrepancy.

## Complete fixture coverage

34 customers; 62 cards from successful card-list responses, plus three card keys under Alp’s failed card-list response. All downstream entries for Alp were tested too.

| Service | Responses checked | Matched |
|---|---:|---:|
| cards.list | 34 | 34 |
| cards.balance | 65 | 65 |
| statement.week.get | 65 | 65 |
| statement.week.decide | 195 | 195 |
| statement.week.change | 195 | 195 |
| contact.email.get | 34 | 34 |
| statement.pdf.send | 29 | 29 |

## Method and limits

The independent scripts read only the supplied fixture to construct expectations; they do not import mock implementation code. Each leaf is checked once per run using POST JSON with customerNo, exact masked cardNumber when applicable, and newStatementWeek for week operations. The sent fields are top-level as requested; envelope variants and numeric/string permutations were not exhaustively tested. Requests were sequential with a short pause and no hidden retries. Mock PDF/send and week/change are fixture replay requests; no reset, deployment or source edit was performed.

Every response field/value was compared, including GUIDs, result metadata, nulls, string types, array order, missing fields and extra fields. JSON whitespace/object-key ordering and equivalent number spellings (0 versus 0.0) are not differences. This does not establish behavior for unspecified customers/cards/weeks, missing PDF entries, authentication, persistence, full integration-contract compliance or the authored phone workflow.

Source SHA-256: `009d3609d33a3b001ce04861822cd2592cb5482a7a5b0a5cb69442592889aa65`. Fixture unchanged through completion: **yes**. Advertised OpenAPI JSON unchanged between latest-run start/end snapshots: **true**. This is a timestamped observation, not a guarantee against later redeployment.

## Evidence

- Latest full run: `post-redeploy/summary.json`, `post-redeploy/responses.jsonl`, `post-redeploy-run.log`. Each JSONL row retains the request and exact expected/actual status/body.
- Latest requested-path checks: `post-redeploy/requested-route-recheck.json`.
- Before/after health/API snapshots and default User-Agent 403: `post-redeploy/`.
- Earlier advertised-path pass: `advertised-paths/summary.json` and `responses.jsonl` (617/617).
- Initial requested-path failures: top-level `summary.json`, `responses.jsonl`, `run.log`.
- Independent scripts: `verify.py`, `verify_advertised.py`, `verify_post_redeploy.py`.
- Customer guide: [final-contract-summary.md](../final-contract-summary.md).
