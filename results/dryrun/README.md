# Sunday dry run — two new hidden-style inputs

**Both builds completed and passed their pre-bank checks, but the exported workflows have two material compiler defects.** Inputs and exports were left unchanged. This is a dry run, not an event submission.

- Pipeline checkpoint: `d5b14c4d60120faa08e8f95647e4ce724a6584c7`. Isolated branch: `dryrun-sunday-20261010`.
- Unchanged input commit: **`d783c888b0422bcc199e512fa5f8c3f83856bb2c`**.
- Generated-output commit / `submission/form.json.commit`: **`2520f623718f73d87864050618cdaa35652a5480`**.
- The output commit has exactly eight files: two exported workflows, two traces, two policies and two audits. Its parent is the input commit. No pipeline file changed. The later evidence/form commit does not change the commit named in the form.
- All seven authored input files retain their pre-build SHA-256 hashes. Expected values were recorded outside the builder checkout before extraction and copied into this report only after both builds.

## New inputs

- [dry-1](../../hidden/dry-1/brief.md): Juniper Cooperative Bank, a single clean specification. Three security questions; five wrong answers; two product types; nine-calendar-day/four-business-day bands; same-day callbacks; two extra write attempts.
- [dry-2 mail](../../hidden/dry-2/01-mail.txt), [policy](../../hidden/dry-2/02-policy.md), [signed memo](../../hidden/dry-2/03-memo.txt), [code list](../../hidden/dry-2/04-codes.txt): Marlow Trade Bank. Four security questions and three product types. Historical email quotes conflict with a signed memo that changes question order, wrong-answer limit, the late-band deadline, retries, human transfers, and callback days.
- Each directory has its own mutated `openapi.json`: `/bank/` endpoints with operation IDs, `operation_success`, `check_passed`, `all_checks_complete`, `remaining_tries`, an `obligations` array, renamed product fields/types/floors, and bank-specific outcome/reason/queue enums. Hosts are deliberately `.example.invalid`. No bank-action end-to-end test was attempted against these synthetic hosts.

## Timings and checklist execution

| Step | Result | Elapsed |
|---|---|---:|
| venv | exit 0 | 0.017 s |
| dependencies | exit 0 | 0.153 s |
| claude-preflight | exit 0 | 2.692 s |
| offline-tests | exit 0 — 20 tests passed | 1.047 s |
| fixture-rehearsal | exit 0 | 17.437 s |
| Clean-spec hidden-1 build | exit 0; published, smoke and both pre-bank checks passed | **196.463 s** |
| Raw-pack hidden-2 build | exit 0; published, smoke and both pre-bank checks passed | **176.076 s** |
| Sequential build pair | 6 min 12.5 s | **372.539 s** |
| Input commit through output commit and form population | Includes failed push attempt | **372.566 s** |
| Full checklist interval: fresh-clone preflight start through populated form | Includes authoring/preparation and waiting for another simulation | **786.240 s (13 min 6.2 s)** |
| Preflight start through completed export audit | Includes post-build investigation | **943.182 s** |

The clone and virtualenv were fresh; the host already had uv, Claude CLI/authentication and package caches. The initial fixture rehearsal outputs were archived and the disposable clone restored before the input commit. One other simulation was running; the read-only workspace check then returned no active simulations before the builds started. This dry run started no simulations. Both hidden traces report the input commit and `tree_dirty=false`.

Builder model reported cost for the two extraction/audit pairs: **$2.1946** (excludes the CLI credential preflight and Freya-internal chat inference). No validation repair pass or timeout occurred. Both identity-start and third-party checks passed on their first attempts.

## Every observed export discrepancy

| Affected exports | Expected by brief/API | Exported behavior | Evidence / impact |
|---|---|---|---|
| hidden-1 and hidden-2 | Full amount comes from `outstanding_amount`; lateness comes from `days_past_due` | `SLOTS.account.past_due = "days_past_due"` | The substring mapper prioritizes `past_due` over `outstanding`. Executing each exported `init_products` with an offline API-shaped row containing amount **987.65**, days late **13**, and floor **5** produces full amount **13.0**. This can corrupt the spoken balance and every full-amount proposal. The IR correctly extracts floors and deadlines; this is a compiler response-mapping defect. |
| hidden-2 opening | Signed memo D: transfer a human request immediately, without first offering help | Exported `opening_route` receives `holder=wants_human` but sets `next=opening` | IR has `human.ask_once_first=false`, but this pre-verification branch ignores it and asks whether the assistant can help. Offline execution of the actual exported Python confirms the route. |
| hidden-2 identity | Same immediate-transfer rule during security | Exported `id_route_0` receives `id_intent=wants_human` but sets `next=ask_0` | Same ignored flag in the identity route. It should route to transfer. No model classification uncertainty is involved in this check. |

**255 checks: 249 matched, 6 failed assertions representing the two root causes above.** The amount mapping and its runtime consequence are counted separately for each export. The other two failed assertions are Marlow’s opening and identity transfer routes. Full expected/actual values are in [workflow-audit.json](workflow-audit.json). No defect was repaired during this run: the checklist permits only parser-crash fixes, and neither issue caused a crash.

## Requested checks that passed

- **Identity order and formats:** Juniper `membership_year → date_of_birth → access_suffix` (year, month/day/year date normalized to ISO, six digits); Marlow `postcode → registration_code → founding_year → contact_birthdate` (text, seven digits, year, month/day/year date normalized to ISO). All seven exact question sentences are retained. The exported nodes speak `{{id_say}}`; executing exported `_ask_text(i)` renders the expected question. Exported verification-success routes advance in order and reach get_account after the last question. The live pre-bank checks verify the first question for each bank.
- **Memo precedence in the IR:** Marlow retains eight business days for the early band, changes the late band to end-of-month/business/preceding, allows four total wrong answers, zero extra write attempts, next-business-day callbacks only, and sets immediate human transfer. The last of these is not honored by the two runtime branches noted above.
- **Close-node enums:** all close_call nodes carry the correct mutated outcome enums, reason enums when applicable, `/bank/close_call` URL, and `data.operation_success` response mapping. Reason-free close nodes omit the reason property. The embedded outcome/reason table and special-case close/transfer combinations match the code lists. This is a structural/offline check, not a claim that every end-to-end outcome path was exercised.
- **Mandatory sentences:** all eleven required phrase fields per bank match, including verbatim opening, holder question, debt introduction, today questions, robot/scam/unanswerable replies, saved-promise confirmation, already-paid explanation, and saved-promise-change reply. Identity-failure, deceased, floor, read-back-consent and exact identity-question sentences also match. The actual opening TTS contains the mandatory opening. Later spoken sentences were checked in exported configuration/code rather than through a completed bank conversation.
- **Deadline math:** `bankcal.deadline` was called using the rules and calendars recovered from each export. Expected values were calculated separately with datetime arithmetic. All 16 cases match; the exported deadline function AST also matches the pinned bankcal implementation.

| now date | Juniper 1–18: +9 calendar, following | Juniper 19–75: +4 business | Marlow 1–24: +8 business | Marlow 25–90: business month-end |
|---|---|---|---|---|
| 2026-10-14 | 2026-10-23 | 2026-10-21 | 2026-10-26 | 2026-10-29 |
| 2026-10-23 | 2026-11-02 | 2026-10-30 | 2026-11-06 | 2026-10-29 |
| 2026-11-25 | 2026-12-04 | 2026-12-01 | 2026-12-07 | 2026-11-30 |
| 2026-12-24 | 2027-01-04 | 2026-12-30 | 2027-01-07 | 2026-12-31 |

## Extractor unresolved reports

Juniper’s final IR marks two wording topics unresolved: the sympathetic hardship sentence and the wording of the first human/refusal-to-talk clarification. Neither has mandated wording in the brief. Its audit also lists constraints without dedicated IR fields (relative privacy, incomplete callback time, below-floor handling, prohibited offers and honest write-failure claims). Marlow’s final IR has no unresolved entries, while its audit still lists unspecified sympathy wording and similar non-IR constraints, including text-space normalization and consent invalidation. These are diagnostic coverage caveats, not additional demonstrated deadline/identity/enum discrepancies. Exact audit text is preserved in workflow-audit.json and the committed audit files.

## Checklist ambiguities and incomplete external steps

1. **Push cannot complete:** the repository has no configured remote. Step 4’s `git push` was attempted and exited 128, “No configured push destination.” The local commits are real and reachable on the dry-run branch; no remote publication is claimed.
2. **Form remains a local dry-run artifact:** the real output hash, both actual commands and artifact paths are filled. Team name and repository URL remain the existing placeholders because neither is configured. The checklist still says to confirm form versus kit-email delivery. No real event form or email was submitted.
3. **Commit-hash self-reference:** the form must name the step-4 artifact commit, not the later commit that saves the filled form/report. Otherwise updating the form to HEAD changes HEAD again. This report and the form retain the artifact hash above; both traces correctly reference its parent input commit.
4. **Rehearsal output cleanup is unspecified:** step 1’s fixture build generates or overwrites tracked artifacts and can archive an old trace to an untracked filename. To restore the required clean starting tree, this disposable clone’s rehearsal artifacts were preserved externally and its prior tracked outputs restored before committing inputs. No source files were reset or changed.
5. **Step 4 omits some generated files:** `.candidate.json`, pre-bank `results/hidden-*.selftest.json`, and a filled form are not among its listed commit paths. The eight requested build artifacts were committed exactly; self-test evidence is included later under results/dryrun. The traces also contain the self-test results.
6. **Prerequisites and test names:** the README assumes a shell Claude CLI (Python requirements alone do not expose `claude` on PATH). “No LLM, ~10 s” describes extraction bypass only: default smoke/pre-bank tests use Freya models and took 17.4 s in this rehearsal. SUBMISSION describes a smoke check but not the two additional pre-bank scenarios.
7. **Green build is not a semantic acceptance gate:** both traces say success despite the exported amount-mapping and human-routing errors. Pre-bank checks cannot detect post-verification account mapping. Also, step 3 explicitly permits only parser-crash fixes; the checklist gives no permitted recovery path for a semantic defect discovered during the hidden window.
8. **Shared-workspace availability:** step 1 requires no simulation running but specifies neither a lock nor a wait policy. This run waited and recorded an idle observation; it cannot reserve the workspace against other processes afterward.

## Exact run commands

Run from the checkout containing the committed input files. These are the commands actually executed, sequentially, with no --cases or --policy shortcut:

```bash
source .env && .venv/bin/python build.py --briefs hidden/dry-1/brief.md --openapi hidden/dry-1/openapi.json --slot hidden-1
source .env && .venv/bin/python build.py --briefs hidden/dry-2/01-mail.txt,hidden/dry-2/02-policy.md,hidden/dry-2/03-memo.txt,hidden/dry-2/04-codes.txt --openapi hidden/dry-2/openapi.json --slot hidden-2
```

`submission/form.json.run_command` joins those two commands with `&&` so the second starts only after the first succeeds. The pipeline source remained fixed throughout.

## Evidence and repeatability

[Preflight timings](preflight.json), [build/commit/push timings](sunday-steps.json), [run summary](run-summary.json), [input hashes](input-manifest.json), [artifact integrity](integrity.json), [predeclared expectations](expected-before-build.json), [workflow audit](workflow-audit.json), [push error](push.log). Exported agents and builder traces are the normal `out/hidden-*.workflow.json` and `traces/hidden-*.jsonl` files in the artifact commit.

To repeat the offline export audit from the dry-run branch: `.venv/bin/python results/dryrun/audit_exports.py`. It reads the saved exports, compares their embedded policies and close nodes, and executes only exported pure Python runtime functions against local sample variables; it makes no platform or bank request. The temporary clone path is recorded in the command logs. Credentials were copied only as ignored `.env`, never committed.
