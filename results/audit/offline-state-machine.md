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
