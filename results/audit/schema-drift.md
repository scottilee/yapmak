# Audit 3 — Schema-drift robustness (offline mutation of tools/openapi.json + matching IR edits)

Repro: `.venv/bin/python results/audit/drift_mutations.py` (writes workflows to `results/audit/drift-out/`; never calls Freya). End-to-end behavior confirmations via `results/audit/offline_probes.py`-style drivers against mocks matching the mutated responses. Line refs: pinned compile.py `008ef977…`.

## Fails loudly (as plan §3.2 requires) ✔

| Mutation | Behavior |
|---|---|
| close_call outcome enum changed, IR untouched (`m3`) | exit 1 — `policy invalid: outcome promise not in close_call enum` (policy.py `validate()` vs `tool_enums`) |
| New **required** field on create_promise (`m4`) | exit 1 — static check `required field channel missing` (compile.py:1674) |
| add_note reason renamed, IR **not** updated | exit 1 — `note reason dispute not in add_note enum` |
| `wrong_answers_left → attempts_left` | **adapts** — needles `left/remaining/attempts` (compile.py:81) map correctly; verify_0 mapping bakes `data.attempts_left` |
| `products → loans` response list | **adapts** — array-type detection (compile.py:74) finds it regardless of name |
| outcome enum renamed *with* IR updated (`promise→promised` everywhere) | compiles; close bodies are `{{final_*}}` vars fed from IR — coherent |

## Silently emits a wrong agent ✘ [blocks score]

**F10 — `_pick` defaults resurrect the practice field names.** Every slot has `default="<stock name>"` (compile.py:60–66, 78–82, 90–93). When a renamed response property matches **no needle**, the mapper returns the *stock* name, the baked `response_mapping` points at a property that does not exist, and compile exits 0 with "static check ok". There is **no unmapped-slot failure branch anywhere in response_slots()**, contrary to plan §3.2 ("fail compilation with an actionable error when a slot required for verification, authorization or write success cannot be mapped").

Evidence (mutations → compiled → run against a mock that speaks the *mutated* language):

- **X1** `verify_identity` `ok→ack`, `verified→passed`: mapping stays `data.ok`/`data.verified` (both unset at runtime) → **a correct DOB answer is treated as a wrong answer** ("That does not match our records"); identity can never pass; probe terminates with the agent still at `ask_0`, no `get_account`. Offline repro: `wf_x1_verify_renames.json` + `Ren({"ok":"ack","verified":"passed"})` mock.
- **X2** `create_promise` `ok→executed` (the generic `"ok"` slot, compile.py:93, only *queries create_promise's schema*, but with needles ok/success and default "ok"): mapping stays `data.ok` → `w_ok` unset → `write_step` (compile.py:1124–1149) counts a failure, **re-issues create_promise (double-recorded promise in the ledger!)** and closes `no_promise/service_error` while the bank holds two identical promises. Verified offline: promises `[420.0 p1, 420.0 p1]`, outcome `('no_promise','service_error')`. Same slot feeds `cb_ok`/`n_ok`/`t_ok` for all other write tools, so one rename poisons every write path and honesty grading ("never says recorded when it failed" is satisfied; "recorded promise exists + says not" breaks Outcome **and** Honesty).
- **X4** `days_late → overdue_since` (matches no needle): slot stays `days_late` → `_int(None) or 0` (compile.py:637) → **every product lands in the last band via `_band()` fallback (compile.py:~656 `return POLICY['bands'][-1]`)** → wrong deadlines/attempt counts for all cases, silently. The fallback-to-last-band on *out-of-range* days_late is itself suspect (a brief with `days_late=60` would get the 8–45 band).
- **X3** add_note reason renamed *consistently through IR* (`dispute→claimed_dispute` in enum, outcomes table, special_cases, notes.reasons): compiles clean, but the engine's **internal disposition literal** is `'dispute'` (compile.py:850 `reason = 'paid' if intent == 'already_paid' else 'dispute'`), and the note gate tests membership `p['disposition'] in N['reasons']` (compile.py:1198) → **add_note silently skipped for the disputed product** (offline: notes for `refused` products written, dispute note missing, outcome still `promise`). Same class at compile.py:1175: close reason passes dispositions through verbatim except `service_error`. See rule-coverage F9.

## Recommendations (ordered)

1. `response_slots()` should return `None` instead of a stock default for enforcement slots (`verify.ok/verified/all_verified/remaining`, `account.list/id/past_due/days_late`, generic `ok`), and `compile_workflow` should abort with "slot X unmapped in <tool> response" (list candidates). Cheap, prevents the entire X1/X2/X4 silent class.
2. Same treatment for `_band()`: out-of-range `days_late` → unresolved/block, not last-band fallback; `_int(raw.get(A['days_late'])) or 0` → block when the key is absent (the default can't be *present* after fix 1, but keep both).
3. Replace disposition literals with an IR `vocabulary` map (`intent → disposition → note reason / close reason / outcome`), defaulted from the outcome table; add a **static check** that every disposition literal the compiler emits is in `notes.reasons` (when notes enabled) and in the close_call reason vocabulary — closing the X3 class.
4. Derive the generic `ok` slot **per tool** (verify/get_account/create/… each own response schema), not from create_promise only.
5. Decide a policy for unknown/unmapped-but-optional fields (hint, card_last4): a logged `unresolved[]` entry (currently compile.py:1277 force-clears `d["unresolved"] = []`, so extraction doubts are erased from the artifact and the trace loses them).

---

## Recheck — 06:23 build (compile.py `050a8c62…`)

Every previously-silent mutation now either fails loudly or adapts correctly (`.venv/bin/python results/audit/drift_mutations.py`, then drivers from `offline_probes.py`-style runs against matching mocks):

| Mutation | Before | Now |
|---|---|---|
| X1 `ok→ack` (+`verified→passed`) | silent stale `data.ok` | **exit 1: `cannot map response slots from the tool API: verify_identity.ok; verify_identity has [ack, all_verified, error, hint, passed, wrong_answers_left]`** — enforcement-slot guard added (compile.py:98–104); `passed` is now a verified needle so only the unmappable `ack` trips it |
| X2 `create_promise ok→executed` | silent: double-write + `no_promise/service_error` while ledger held promises | **compiles correctly** — per-tool `ok_by_tool` with `executed/accepted` needles (compile.py:96); baked `data.executed`; offline run vs renamed mock: 1 write, 1 promise, outcome `promise` |
| X4 `days_late→overdue_since` | silent wrong band for every product | **compiles correctly** — needle added (compile.py:91); PUB-06 ladder still floors at deadline 2026-10-23 |
| X3 note reason renamed in API+IR | note silently skipped | **adapts** — `_special` uses IR `action.reason` (compile.py:933) and dispositions route through `refused_reason`/`service_error_reason`/hardship reason; dispute note now written as `claimed_dispute` |
| M3/M4 loud paths | loud | still loud |

Residual: optional slots still default to `""`→sentinel `__none__` with runtime fallbacks (hint/remaining/all_verified/card_last4) — reasonable, documented at compile.py:105–111. `_band()` still silently assigns the **last band** to out-of-range `days_late` (compile.py:375–379) and `_int(...) or 0` remains at compile.py:704 — a renamed *near-miss* needle match (e.g. `days_since_open` matches needle `days`) would still pick the wrong band silently; only fully unmatched renames now fail. The close-vocabulary class moved from literals to IR, but the **close-rejection** behavior gap (schema-drift recommendation against `st_close_after`) reappears in offline-state-machine P17.
