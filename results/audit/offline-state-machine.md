# Audit 4 — Offline state-machine review

All checks offline; **no simulation, no Freya calls at all** (only `tests/offline_sim.py`'s Driver/MockBank reused; the workspace sim slot was never touched). Pinned inputs: `out/gen-a.workflow.json` `b4fc832c…`, `out/gen-ab.workflow.json` `7ab52614…` (hashes in `snapshot-sha256.txt`; both regenerate **byte-identically** from the fixtures with the pinned compiler — reproducibility ✓).

## Baseline

```
.venv/bin/python tests/offline_sim.py out/gen-a.workflow.json out/gen-ab.workflow.json   → 13 / 13 PASS
.venv/bin/python compile.py tests/fixtures/brief_a.policy.json tools/openapi.json <out>  → static check ok, identical to gen-a
```

## Extra scenarios (auditor scripts: `results/audit/offline_probes.py`)

15 probe scenarios for paths the 13 public scripts don't exercise. **All 14 enforcement probes match the brief; the separate P3b demo reproduces the rule-3 bug.**

| Probe | Path | Result |
|---|---|---|
| P1 | day/month swapped hint retry is not a wrong answer (A13) | ✔ both questions then pass, correct promise |
| P2 | decline once at question 2 → explanation → answer → recovery (A15) | ✔ |
| P3a | "who is this?" then confirm (A3) | ✔ |
| **P3b** | "hello" then "who is this?" then "yes" (A3: the ask after answering a question is the second ask) | ✘ **closes `not_reached/unclear` after the second unclear turn** — see rule-coverage F1 |
| P4 | third party offers 09:00 today, then 20:30 tomorrow (both outside 10–19) | ✔ ask-once retry then `no_callback`, `schedule_callback` never called (A6–7) |
| P14 | third party cannot say twice | ✔ `no_callback`, no schedule |
| P5 | too_much → floor offered → refused (flat refusal, attempt 1) → refused (attempt 2 floor@deadline) → accepts | ✔ promise 637.50 on 2026-10-23 (A26/30) |
| P6 | refuses → vague → vague | ✔ agent proposes full on deadline (A21) |
| P7 | correction at read-back (amount) → re-read → confirm | ✔ revised amount recorded (A35) |
| P8 | `create_promise` fails twice (single product) | ✔ exactly 2 write attempts, `no_promise/service_error`, nothing claimed recorded (A37) |
| P9 | 3rd-product write fails twice, others succeed | ✔ p1+p2 promises kept, note `service_error` on failed product (B11) |
| P10 | dispute on product 2 of 3 mid-negotiation | ✔ promise p1, notes `dispute`+`refused`, outcome `promise` (B8/9) |
| P11 | restructuring requested while p1 agreed-but-unrecorded | ✔ transfer, **no create_promise, no notes at all** (B10) |
| P12 | customer asks for human after agreeing a date (at read-back) | ✔ ask-once → transfer `general`, agreed value not written (A42) |
| P13 | hardship then customer names own date anyway | ✔ promise recorded per §7/8 (A32 tail) |
| P15 | 2 wrong DOB + 1 wrong phone | ✔ `not_verified/failed`, `get_account` never reached — wrong count is global (A12) |

Repro: `.venv/bin/python results/audit/offline_probes.py` (expects 14 PASS lines + the P3b printout showing `not_reached/unclear` where the brief requires a further ask).

## What these probes do NOT cover (residual risk before Sunday)

- **The extractor + dialogue model.** Every probe injects extraction outputs; the real failure surface on hidden briefs is the Freya extractor picking the wrong intent enum. The intent enums and their descriptions are compiler-fixed (see schema-drift/rule-coverage F5, C3) — a hidden brief with renamed/extra special cases has no routing at all. The chat checks under `results/baseline/` cover some extraction edges; the §5 contract matrix is still incomplete (revision-bound consent, tool-result freshness under simulation).
- **Post-record conversation.** The engine has no turn between the last write and `close_call`, so rule 36 ("change it in the mobile app") and any "corrects after recording" script cannot be answered — structurally silent, not just untested (rule-coverage F2).
- **Close rejection.** `st_close_after` ignores `close_ok` (rule-coverage F3); offline mocks reject nothing beyond the promise/paid-reason rule, so this can only surface on a hidden enum mismatch.
- **Talkative/stall paths**: `max_node_turns` + `max_turn_transition` are baked on every conversation node (static checklist covers presence); the transitions land in `*_route`/`cb_route` code nodes that then route to finalize — reasonable, but no probe drives a turn-cap hit. Suggest one probe: exhaust `negotiate` turns → expect safe close with the persisted state, not a hang.

---

## Recheck — 06:23 build (compile.py `050a8c62…`, gen-a `982047ec…`) — auditor 13:2x UTC

Compile reproduces the checked-in workflows byte-identically; pytest 20/20; offline_sim **14/14** (new `PUB-01-pieces` speech-style case passes). Probes re-run: `results/audit/offline_probes.py` updated in place.

- **P3b — NOT fixed.** The holder extraction enum is still `['confirmed','third_party','wrong_number','deceased','wants_human','refuses','unclear','none']` (no question intent; `st_opening_route` compile.py:424–464 unchanged — `'none'` is the schema empty-value convention at compile.py:191–197, not a question class). "hello"→"who is this?"→"yes" still closes `not_reached/unclear`. The probe is now verdict-bearing (FAILs against the brief) and adaptive: it sends a dedicated `holder:'question'` turn if a future build adds that enum value, else the unclear-fold form. [blocks score — finding F1 stands]
- **P16 (new) — negotiate turn-cap exhaustion: PASS.** Verified customer stalls after an offer is on the table; `CapDriver` enforces `max_node_turns`→`max_turn_transition` repeatedly; the new `_stuck` insurance (compile.py:1315–1335, route-visit > 30) closes cleanly: outcome `no_promise/refused`, exactly one `close_call`, no promise claimed, farewell "I cannot continue this call" spoken. [audit-suggested gap now covered and green]
- **P17 (new) — close rejection: FAIL (by design, documenting F3 — NOT fixed).** Mock rejects the first `close_call` ("may be repeated"); the close nodes transition unconditionally to `end` (compile.py:1704–1707) and nothing reads the mapped `close_ok` → the call ends with **no outcome in the ledger** while a promise was recorded. `write_step` got the analogous fix (`w_pending`; retry only on explicit `ok:false`, timeout not treated as failure — compile.py:1211–1243, my F7), close did not.
- 13 of the earlier probes unchanged in behavior; P2/P5/P9/P10/P11/P12/P13 all still match the brief on the rebuilt workflows.

Net: `14 / 15` probes as expected by the brief; the two known gaps are P3b (rule-3 counter) and P17 (close retry).

---

## Second recheck — 07:0x build (gen-a `d59c103e…`): P3b and P17 now PASS

The builders landed both open fixes mid-audit:
- **Rule 3 (F1)**: holder enum now has an explicit `question` value (compile.py:1636); `st_opening_route` answers the question via `neg_instruction` and re-asks without incrementing `holder_unclear` (compile.py:461–464). Adaptive probe P3b (question form) now continues to the promise. 15/15 probes match the brief.
- **Close rejection (F3)**: `close_reason`/`close_noreason` route on `close_ok` (both boolean spellings) and fall through to a `close_retry` node (compile.py:1739–1749). P17 passes (promise outcome recorded after one rejection).
- **Nit on the new code**: `close_retry` drops the reason unconditionally ("try once more without the reason", comment at :1740). For outcomes whose reason is *required* by the bank (no_promise/unverified/not_on_line family), a transient rejection now retries with a pair the bank is *more* likely to reject; if the mock validates reason-requiredness, ledger still ends outcome-less. Consider retrying with the same outcome+reason first, then reasonless as a last resort.

Repro unchanged: `.venv/bin/python results/audit/offline_probes.py` → 15/15 (gen-a `d59c103e…` / gen-ab).
