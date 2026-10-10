# Latency: per-code-node durations and per-stage turn totals (quiet vs loaded)

Deliverable per request. Numbers only. Source: all 44 `results/gen/*.json` run files; 111 unique simulation call transcripts fetched via `freya.get_call` (read-only; no simulations started) into `results/latency/calls/` (sampled: 10 calls per representative file × 15 files spanning the day and agent versions v8–v13, all reps-3 iterations for the two reps files where present).

**Condition split (data-driven):** each call bucketed by the median of its own `user→assistant` turn latencies: ≤6 s → **quiet** (n=91), >6 s → **loaded** (n=20). Loaded calls come from the 13:54–15:15 UTC windows (a-run1/2 early burst, reps3 finals, v11–v13 finals); quiet from 13:59–15:2x isolated windows (a-run3/4, pieces, b-run2, corrects/talkative at 4–6 s). Caveats: loaded bucket also mixes agent versions v10–v13 (prompts grew, turn times include generation); medians are not additive; conversation-node visit spans include simulated-customer pacing and are not interpreted.

Dwell = first-message-at-node → first-message-at-next-node (from `secondsFromStart`). Visit counts are per-call averages over calls that reached the node.

## 1. Code-node visit dwell (s)

| node | type | quiet | loaded |
|---|---|---|---|
| setup | code | n=91 med=0.62 p95=5.87 | n=20 med=3.60 p95=7.34 |
| opening_route | code | n=107 med=0.39 p95=5.48 | n=20 med=5.01 p95=6.60 |
| id_route_0 | code | n=141 med=0.44 p95=4.93 | n=17 med=5.11 p95=8.06 |
| id_route_1 | code | n=106 med=0.49 p95=6.00 | n=14 med=5.86 p95=8.04 |
| verify_after_0 | code | n=119 med=0.59 p95=5.97 | n=17 med=5.10 p95=6.32 |
| verify_after_1 | code | n=98 med=0.41 p95=5.42 | n=14 med=5.34 p95=8.20 |
| init_products | code | n=77 med=0.83 p95=6.15 | n=14 med=5.25 p95=6.51 |
| neg_route | code | n=145 med=0.80 p95=4.99 | n=21 med=5.84 p95=7.10 |
| readback_route | code | n=279 med=0.42 p95=2.32 | n=9 med=5.98 p95=10.65 |
| write_step | code | n=102 med=0.95 p95=4.87 | n=18 med=5.25 p95=8.49 |
| finalize | code | n=44 med=0.91 p95=4.70 | n=12 med=5.08 p95=10.79 |
| notes_step | code | n=9 med=1.27 p95=5.97 | — |
| cb_route / cb_after | code | med=1.02 / 0.75 | med=4.56 / 4.74 |
| close_after | code | n=12 med=1.99 p95=4.58 | n=3 med=2.71 |

## 2. api_request node dwell (bank HTTP in the span)

| node | quiet | loaded |
|---|---|---|
| verify_0 | n=119 med=0.10 p95=0.19 | n=17 med=0.08 |
| verify_1 | n=98 med=0.12 p95=0.21 | n=14 med=0.11 |
| get_account | n=77 med=0.08 | n=14 med=0.07 |
| create_promise | n=58 med=0.89 p95=5.33 | n=11 med=5.14 p95=10.75 |
| close_reason / close_noreason | med=0.10 / 0.12 | med=0.08 / 0.15 |
| add_note / schedule_callback / transfer | med 0.06–0.15 | med 0.06–0.08 |

Bank HTTP is flat ~0.1 s in both conditions; the platform's node-transition bookkeeping around code nodes is what grows 6–12× under load (0.4–1.0 s → ~5–6 s per hop).

## 3. `user→assistant` turn latency by stage (s)

| stage | quiet | loaded |
|---|---|---|
| identity (opening + ask_i) | n=308 med=1.41 p95=8.40 | n=31 med=6.81 p95=12.66 |
| third_party | n=6 med=1.66 | n=5 med=4.32 |
| negotiation (state_debt + negotiate) | n=512 med=1.04 p95=6.17 | n=21 med=15.61 p95=21.28 |
| confirm→close (readback + goodbyes) | n=384 med=1.43 p95=4.66 | n=28 med=7.70 p95=18.59 |

## 4. Extraction span (`user` → last `variable_extracted`, s) — stable across conditions

| node | quiet | loaded |
|---|---|---|
| opening | med=0.24 p95=0.46 | med=0.22 |
| ask_0 | med=0.98 p95=1.46 | med=0.97 |
| ask_1 | med=0.32 p95=0.66 | med=0.30 |
| state_debt | med=1.13 p95=1.69 | med=1.11 |
| negotiate | med=0.86 p95=1.33 | med=1.06 |
| readback | med=0.81 p95=1.10 | med=0.83 |
| third_party | med=1.34 | med=1.05 |

## 5. Per-call stage totals (s, sum of all node dwells in stage)

| stage | quiet med | loaded med | quiet code-part | loaded code-part | quiet api-part | loaded api-part |
|---|---|---|---|---|---|---|
| **identity** | **13.51** | **37.28** | 3.89 | **31.03** | 0.22 | 0.19 |
| account_load (get_account+init) | 0.97 | 5.39 | 0.83 | 5.25 | 0.08 | 0.07 |
| negotiation | 6.47 (p95 206 talkative tail) | 7.82 | 1.30 | 5.61 | — | — |
| confirm→close | 3.62 | 6.58 | 1.49 | 6.31 | 0.36 | 0.16 |
| third_party (PUB-02 type calls) | 5.26 | 11.00 | 1.08 | 8.27 | 0.06 | 0.08 |

Identity-chain non-conversation hops per call: 8 reached-node visits in a full pass — setup(1.0) opening_route(1.0) id_route_0(0.95) verify_0(0.95) verify_after_0(0.95) id_route_1(0.85) verify_1(0.85) verify_after_1(0.85).

## 6. The two questions, numerically

**Longest chain:** identity — 13.5 s quiet / 37.3 s loaded stage totals, ~2× the next stage (negotiation 6.5 / 7.8), 8 of its seconds are code-hop visits (quiet) growing to 31 of 37 s under load. Turn-count dominance is the other side: negotiation carries the most assistant turns per call (512 quiet turns across 77 reaching calls ≈ 6.6/call vs identity 308/91 ≈ 3.4/call), but its chain has ~half the non-conversation hops.

**Merging `verify_after_i` into `id_route_{i+1}` / dropping a node:**
- One dropped code visit ≈ 0.4–0.6 s quiet, ≈ 5.1–5.3 s loaded (verify_after rows, §1).
- Dropping both verify_after_0 and verify_after_1 (the merge case: one hop per question instead of two) ≈ **1.0 s/call quiet (≈7% of the 13.5 s identity total)**; ≈ **10.4 s/call loaded (≈28% of the 37.3 s identity total, ≈25% of a loaded call's whole duration)**.
- Any single node drop is the same order (table §1 per row); the load amplification is per-hop, so hops removed × ~5 s is the loaded benefit and hops removed × ~0.5 s the quiet benefit.
- Reference points for what is *not* hop-bound: extraction adds a flat 0.3–1.3 s per conversation turn (stable), bank HTTP ~0.1 s, assistant generation 1–16 s and stage-dominant when loaded (§3).

## Reproduce

```bash
source .env && .venv/bin/python results/latency/fetch_calls.py    # cached transcripts stay
.venv/bin/python results/latency/analyze_calls.py                 # all tables above
```
