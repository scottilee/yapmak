# Auditor re-run on the working tree (10 Oct, 15:25 UTC)

Tree: HEAD `d5b14c4` plus the uncommitted compiler changes of the last hour (question routing in negotiation, no conversation
self-transitions, softer identity question-back reply, 40 s code timeout, stale-flag dispatch guards on every engine-fired call,
close retry with the same pair first). Compiled outputs `out/gen-a.workflow.json` / `out/gen-ab.workflow.json` are from this tree and are
what is published as gen-a v13 / gen-ab v12.

| Check | Result |
|---|---|
| `pytest tests/` | 20 passed |
| `compile.py` static checklist (A, A+B) | ok, ok |
| `tests/offline_sim.py` (13 public scripts + pieces variant) | 14 / 14 |
| `results/audit/offline_probes.py` | 15 / 15 (P3b rule-3 question, P16 turn-cap, P17 close rejection all pass) |
| `results/audit/drift_mutations.py` | X1 (verify `ok`/`verified` renamed) exits loud: "cannot map response slots … verify_identity.ok"; X2/X3/X4 compile and adapt (`data.executed` baked, renamed note reason written, `overdue_since` keeps band math); m3 (outcome enum without IR) and m4 (new required field) exit loud; m1 (`attempts_left`) adapts |
| Compiled diff vs the `23a4582` checkpoint export | no nodes added/removed; routing changes only where intended: every code-node dispatch to an engine-fired call is now an AND of `next == <call>` and "previous result flag not true"; `close_reason`/`close_noreason` → `close_retry_same` → `close_retry` → `end`; conversation nodes no longer carry a self-transition |

Open by design: rule 36 (no post-record turn). Open risk: platform sandbox stalls (a skipped code node leaves the dialogue model
without an instruction; mitigated by the guards, the 40 s timeout and the "never invent, ask to hold" prompt rule, not eliminated).
