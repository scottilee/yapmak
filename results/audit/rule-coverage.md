# Audit 1 — Rule coverage: IR fixtures + compiler vs. briefs/brief-a.md, brief-b.md

Audited against source docs (not the plan/IR). Line refs are to `compile.py` sha256 `008ef977…` (see `snapshot-sha256.txt`; the file changed during the audit — 05:48 vs 06:03 builds — re-check refs against `git diff` before trusting numbers). Fixtures: `tests/fixtures/brief_a.policy.json`, `brief_ab.policy.json`. No Freya calls.

Verdicts: **code** = enforced deterministically in code nodes/routing; **bake** = fixed text baked into `on_enter`; **prompt** = prompt-only guard; **missing** = no enforcement path.

## Brief A (rules 1–47)

| # | Rule (short) | Enforcement | Verdict |
|---|---|---|---|
| 1 | Opening line; nothing debt-related pre-verification | opening TTS baked `compile.py:1482,1491`; prohibited list → prompt `:1414`; structurally, debt text only exists after `get_account` | code+bake+prompt |
| 2 | "Am I speaking with …" | `phrases.holder_question` baked `:1482` | code |
| 3 | Ask again on unclear; **the ask that follows an answered question is the second ask**; then `not_reached/unclear` | **compile.py:441–443** increments `holder_unclear` on *any* unclear, including a question, and closes at 2 | **blocks score** — see F1 |
| 4 | Robot/AI question | prompt `:1420` (robot_reply from IR) | prompt |
| 5 | Say nothing to a third party; ask when reachable | prompt `:1440` + routing | prompt |
| 6 | Callback window today/next-bd 10:00–19:00 >now; `schedule_callback`; `not_reached/callback` | `st_cb_route` `:477–511` + `bankcal.py:269–298` | code |
| 7 | Outside window: ask once, then `no_callback` | `:503–511` (IR `retry_once`) — probe P4/P14 | code |
| 8/9 | Wrong number / deceased (+exact sentence, no more asks) | `:418–421`, `:469–476`; IR `deceased_sentence` | code |
| 10 | Relatives: no verification, no info | structural (third-party path never reaches `ask_i`) | code |
| 11 | Two questions in order; DOB as YYYY-MM-DD; numeric = day-month-year | `st_id_route` `:524–586`; dmy order driven by IR `numeric_date_order` in extraction desc `:1522` | code |
| 12 | Wrong answer re-asked; 3 wrong **in total**, whichever question | `:615–620` global `id_wrong` + API `left<=0` — probe P15 (2 wrong Q1 + 1 wrong Q2 → `not_verified/failed`, no `get_account`) | code |
| 13 | `day_month_swapped` hint: say month as word; not a wrong answer | `:607–610` uses IR `hint_field`/`hint_reply` — probe P1 | code (needs `hint_field` set in IR, see F6) |
| 14 | After 3 wrong: no debt talk; app/branch instruction; `not_verified/failed` | `:618–619`; `failed_instruction` from IR | code |
| 15 | Decline → explain once; second decline or purpose-question-as-decline closes `not_verified/declined` | `:530–537`; `asks_purpose` extracted `:1515–1517` | code (IR flag `asking_purpose_counts_as_decline` is inert, F5) |
| 16 | `get_account` only after both pass | `verify_after → get_account` routing | code |
| 17 | "collections team about a late payment", name product, amount, days late | baked `:666–672`; **the sentence itself is hardcoded, not IR** (F4) | code (rigid) |
| 18 | Bands 1–7→12bd, 8–45→7bd, attempts 1/2 | IR `bands[]` + `bankcal.py:132–176` | code |
| 19 | ≥today, business day, ≤deadline | `bankcal.py:510–540` | code |
| 20 | Weekend/holiday → next bd; after-deadline → rule 23 | `:760–763` roll_forward / after_deadline | code |
| 21 | Vague → ask once → propose deadline | `:782–790` — probe P6 | code |
| 22 | this/next weekday semantics | `bankcal.py:221–234` + IR `next_weekday_means_following_week` | code |
| 23 | After-deadline → offer deadline; refusal of deadline = flat refusal | `:752–756` + refuses path `:971–981` | code |
| 24 | Full first; never "how much can you pay?" | prompt `:1451`; all amounts from code | prompt(+code proposals) |
| 25 | Floor by product type | IR `amounts.floors`; `_floor_of` `:651` | code |
| 26 | Floor once w/ "rest stays overdue"; refusal = flat; attempt 2 may name floor on deadline | `_too_much` `:995–1021`, `floor_wording` IR — probe P5 | code |
| 27 | floor..full accepted (inclusive); below floor → floor once then flat | `bankcal.py:534` + `:766–772` | code |
| 28 | "Can you make this payment today?" baked | `:669` — hardcoded string (F4) | code (rigid) |
| 29 | Customer date/amount is never a refusal | `has_prop` checks `:907+`, extraction desc `:1548` | code |
| 30 | Flat refusal = 1 attempt; attempt 1 last-bd-this-week (next week if today); attempt 2 floor@deadline late-only | `_start_attempt` `:684–700` + `bankcal.py:179–197` — probe P5 | code |
| 31 | Attempts exhausted → `no_promise/refused` | `:702–724`, finalize | code |
| 32 | Hardship: sympathy, no persuasion, offer support; accept→`transferred/support`; decline→`no_promise/hardship`; before 30/41; self-dated proposal still recorded | `:843–848` + `aw=='support'` fallthrough — probe P13. IR `special_cases.hardship.say` unused; instruction text hardcoded `:844` (F4) | code (rigid) |
| 33 | Never offer discount/waiver/plan | prompt `:1423` | prompt |
| 34 | Read-back product+amount+date, "Do you confirm?", write only after clear yes | `_readback` `:726–738` (`confirm_phrase` IR), `rb_intent` gate `:1069–1080` | code |
| 35 | Change at read-back → re-validate, re-read | `st_readback_route` `:1083–1101` — probe P7 | code |
| 36 | One promise per product; recorded promise immutable; **"change it in the mobile app" reply** | No post-record turn exists at all (writes chain straight to close). IR `recorded_promise_change_reply` referenced **nowhere** in compile.py; `one_promise_per_product` inert | **missing** — F2 |
| 37 | Say recorded only after ok:true; retry once; second fail → `no_promise/service_error` | `write_step` `:1124–1149` (`retry_on_failure` IR) — probes P8/PUB-10 | code (timeout caveat F7) |
| 38 | Mandatory text-message sentence after recorded promise | baked goodbye `:1183` | code (dropped if a transfer follows a record — currently unreachable; nit) |
| 39 | Already paid: "one business day" sentence, no promise, `paid` (no reason) | `_special` `:849–872`; reason='' → `close_noreason` — PUB-08 | code |
| 40 | Dispute (incl. "closed/paid-off before") → `no_promise/dispute` | same; trigger in extraction desc `:1549` | code (prompt for trigger recognition) |
| 41 | New plan/lower instalments → transfer `restructuring`, no plan description | `:812–814` — PUB-09 | code |
| 42 | Human: ask once, insist → transfer `general`/`transferred/human` | `:816–825`, also opening `:424–430`, identity `:544–550` — probe P12. IR `ask_once_first` inert | code |
| 43 | Scam question: verify-by-customer-service line, continue | prompt `:1421`; `scam` intent is **not routed** (`ROUTED_INTENTS` `:1468`) | prompt |
| 44 | Unanswerable → "I do not have that information" | prompt `:1422` | prompt |
| 45 | Two "don't want to talk" → `no_promise/refused`; pre-verification → `not_verified/declined` | opening `:432–438`, identity `:530`, negotiate `:829–841` | code |
| 46 | Exactly one `close_call`, last, outcome+reason per table | finalize `:1154–1181`; single close node pair `:1586–1590`; offline asserts count==1 & last | code — but `st_close_after` `:1220–1222` **ignores `close_ok`** (F3) |
| 47 | Goodbye before close | goodbye baked on close node `on_enter` `:1586–1590` | bake |

## Brief B (1–11 + closing)

| # | Rule | Enforcement | Verdict |
|---|---|---|---|
| 1–5 | 1–3 products; per-product floor/band/deadline/attempts; pay-all-today once; per-product from attempt 1 | `st_init_products` `:625–672`, phase machine `:702–724` — PUB-11/12 | code |
| 6 | Common date after one product's deadline → clamp, say so in read-back | `:1023–1050` + `:731–733` (IR `common_date_clamped_per_product`) — PUB-13 | code — **amount dropped for multi-target proposals** `:1035` (F8) |
| 7 | Batch read-back, one confirm, write per product | `_readback` `:726–738` + `write_step` `:1124–1149` | code |
| 8 | `add_note` per unpromised product incl. when zero promises | finalize notes `:1196–1199` | code — **literal-vocabulary coupling** (F9, see schema-drift X3) |
| 9 | Dispute/paid on one product doesn't end the call | `_special` multi branch `:860–872` — probe P10 | code |
| 10 | Transfer: recorded stay, agreed-unrecorded NOT written, no notes anywhere on transfer | `:812`, finalize precedence `:1158`, notes gate `:1196` — probe P11. The "recorded promise survives a later transfer" leg is structurally unreachable (writes chain into close; see F2) | code (partial) |
| 11 | One product's double write failure → keep others, note `service_error` | `write_step` loop `:1124–1149` — probe P9 | code |
| Closing | transfer > promise > all-paid→paid > no_promise with first non-paid note reason in `get_account` order | `st_finalize` `:1154–1176` | code — reason passthrough only maps `service_error`, all other dispositions pass through as literals (F9) |

## Findings

- **F1 — Rule 3 second-ask counting is wrong when the customer's first unclear answer precedes a question. [blocks score]** `compile.py:441–443` closes after two unclear turns regardless of whether one was a question that the brief says must be answered first (answer→re-ask→*that* re-ask is the second ask). Repro: `results/audit/offline_probes.py` P3b — "hello" → "who is this?" → "yes" ends `not_reached/unclear`; brief expects the call to continue. Hidden benchmark talks back (page: "a question back"), so this pattern is likely. Fix: don't increment the counter when the turn is a question; answer first, and count only post-answer asks.
- **F2 — Rule 36 mobile-app reply has no path. [blocks score if a hidden "corrects" case asks post-record]** IR carries the phrase (`brief_a.policy.json:105`) but `compile.py` never reads `recorded_promise_change_reply`; the engine chains writes → finalize → close, so there is also no conversational slot after a record where the ask could occur. Same mechanism makes B10's "recorded promises stay (and the customer can be told)" unreachable.
- **F3 — `st_close_after` ignores `close_ok`. [blocks score]** `compile.py:1220–1222` sets `call_closed=yes` even if the bank rejected the close (bad outcome/reason combo — exactly the PUB-08 failure mode in §13's baseline). The ledger then has no outcome and the agent lied about closing. Needs a retry-or-fix branch or a compile-time guarantee (see schema-drift X3).
- **F4 — Mandatory sentences hardcoded in code, not IR. [rule-compliance risk / generalization]** `compile.py:668` (debt statement), `:669` ("Can you make this payment today?"), `:844` (hardship sympathy/support offer), `:535, :566, :581, :608, :619` (question wrappers) bake practice-brief wording. A hidden brief dictating different required wording (esp. the raw-material one) cannot be expressed without editing compile.py after briefs open.
- **F5 — Many IR booleans are decorative. [reproducibility risk]** Zero references in compile.py: `asking_purpose_counts_as_decline`, `wrong_count_source`, `remaining_slot`, `promise_today_allowed`, `full_first`, `never_ask_how_much`, `accept_between_floor_and_full`, `one_promise_per_product`, `ask_once_first`, `before_persuasion`, `recorded_promise_change_reply`, `special_cases[].trigger`, all of `multi_product.*` except `common_date_clamped_per_product`, `goodbye_before_close`, `state_all_before_asking`, `ask_all_today_once`, `per_product_attempts`, `one_confirmation_for_batch`, `recorded_promises_survive_transfer`. Synthetic-brief tests that assert behavior changes via these flags will show false "no change needed"; and a brief needing different semantics (e.g., purpose-question not counting as decline) has no lever.
- **F6 — Hint handling requires `hint_field` non-empty (`compile.py:607`); an extraction miss silently turns hint retries into wrong answers (counted via API `left`).** [blocks score, low-probability] Add an IR-validation rule: date-format requirements must carry `hint_field` when the API exposes a hint property.
- **F7 — "unknown response" is treated as failure.** `api_node` timeouts/5xx leave `w_ok` unset → retry → potential duplicate recorded promise if the first write actually landed (also seen live in drift-test X2). Brief: "never duplicate a promise". [blocks score, low-probability] Consider treating unknown outcome distinctly (don't re-assert recorded; don't claim recorded).
- **F8 — Common date+amount across products records full amounts.** `compile.py:1035` passes `amount=None` when `len(targets) > 1`, so "I can pay 300 on Friday for everything" records each product at `full`. Brief B6 only speaks of a common *date*, but nothing forbids a common amount. [blocks score for that script shape]
- **F9 — Outcome/note vocabulary coupling.** Disposition literals (`'refused'/'paid'/'dispute'/'hardship'/'service_error'`) at `:708,834,850,886,1131…` vs IR `notes.reasons` gate at `:1198` and reason passthrough at `:1175`. Works iff the hidden brief reuses practice names. See schema-drift X3 for the silent failure. [blocks score on rename]

## What looked strong
Per-product attempt/deadline math, write-failure ladder, batch read-back/clamp, transfer-no-notes rule, global wrong-count, decline-vs-question separation in identity (P2), callback window edges (P4/P14) — all matched the brief under probes.

Repro: `.venv/bin/python results/audit/offline_probes.py` from repo root (also printed in `offline-state-machine.md`).
