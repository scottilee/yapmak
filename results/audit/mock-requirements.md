# Mock bank on Cloudflare Workers — requirements from the builder (11 Oct 2026, final case)

The organisers' simulated customers call the phone agent; the agent's tools call **our** mock. The builder reads the tool API
from the mock itself. Implement the zip's service contract and test customers faithfully, and add what the builder needs.

## Must have
1. **`GET /openapi.json`** — OpenAPI 3 JSON. `servers[0].url` = the worker's own https URL. Seven POST operations whose
   paths end in exactly these names (any prefix is fine, e.g. `/v1/verify_identity`):
   `verify_identity`, `get_account`, `create_promise`, `add_note`, `schedule_callback`, `transfer_to_agent`, `close_call`.
   JSON request bodies with `properties` and `required`; one 200 JSON response schema per operation with `properties`.
   Field names may follow the contract (Turkish names are fine); the builder maps them by meaning, by description, and by
   type. **Give every property a one-line English `description`** — that is the strongest mapping signal.
2. **Response shape**: a boolean success flag in every response (`ok`/`success`/`basarili`…), an `error` string on failure.
   `verify_identity` → per-answer verified flag, all-verified flag, remaining-attempts integer when the contract has one.
   `get_account` → an array of products (objects with id, type (enum), past-due amount, days late, and any floor/minimum fields).
   `create_promise` → success flag (+ id). `close_call` → success flag.
3. **Enums** on: product type, note reason, transfer queue, close outcome, close reason, identity question field — exactly the
   codes the documents use. The builder validates the policy against these enums.
4. **Idempotent close**: `close_call` once per call; a second call with the same outcome must not error.
5. **Scorer side**: whatever the contract defines for the organisers (sessions / test-customer setup / records read-back) must
   work exactly as written; keep the worker up until results are out.
6. **No secrets in the worker source or logs.** Never print `CLOUDFLARE_API_TOKEN`.

## Nice to have
- `GET /health` returning 200 JSON.
- Deterministic test-customer data loaded from the zip's test-customers file (converted to JSON in the worker).
- Log each tool call (method, path, body) with `console.log` for debugging; no PII beyond what the contract has.

## Deploy
```
source .env                      # CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID
cd mock && npx wrangler deploy   # prints https://<name>.<subdomain>.workers.dev
curl -s https://<name>.<subdomain>.workers.dev/openapi.json | head -c 300
```
Then the builder runs as: `.venv/bin/python build.py <case_folder> https://<name>.<subdomain>.workers.dev`
(or `scripts/submit_final.sh <case_folder> <mock_url> --push`).
