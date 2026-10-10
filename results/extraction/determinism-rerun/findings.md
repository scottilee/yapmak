**Result: all nine runs succeeded, but extraction is not byte-for-byte deterministic.** Three repetitions each of A, A+B and clean-eom, all using the same frozen source/input snapshot at `2064600d6ff207fa43df8ea27c1e643bc282bbe3`. Total wall-clock **533.4 seconds (8m 53s)** with three input groups in parallel and repetitions sequential within each group; reported model cost **$9.2575**. Every run used extraction + audit, with **no repair**, no publication and no simulation. Individual extraction durations: 143.0–179.7 seconds.

| Input | Differing effective leaf paths | Prior sweep | Additional raw-only differences |
|---|---:|---:|---:|
| A | 7 | 19 | 0 |
| A+B | 15 | 54 | 0 |
| clean-eom | 20 | 15 | 0 |

The tables below enumerate every differing field and all three exact values. “Effective” means dataclass defaults have been applied, **not** that every field is consumed by the runtime. The previous report is preserved in `determinism-rerun/previous-report.md`.

### What matters for behavior

- **The previous A+B already-paid/dispute close-vs-note flip did not recur:** all three use note actions and `ends_call: false`. Identity question order, band ranges/deadline rules, holidays, floor-field mappings, outcome/reason enums and write-retry counts agree within each input group. Three repetitions are evidence of improved consistency, not proof of future determinism.
- **Spoken wording still changes:** A's failed-identity instruction and sympathy sentence; A+B's phone-digits question, pay-all-today question, cannot-answer reply, floor wording and sympathy sentence. No missing required phrase flip recurred. These alternatives are mostly semantically similar, but they change generated prompts and can change a stochastic judge's result.
- **Non-wording flips remain, without a demonstrated routing difference in this compiler:** late-band attempt 2 `floor_if_full_refused` flips, but its amount is explicitly `floor` in every run, making that flag redundant at `_start_attempt`. `refuse_to_talk.ask_once_first` and `before_persuasion` flags vary; the runtime uses fixed handling for those cases rather than those flags. `ask_once_first` is read for the human-transfer case, which did not flip.
- **Synthetic refusal action changes:** clean-eom runs 1/2 emit `{type: note, reason: lark_refused}`; run 3 emits `{type: close, outcome: lark_no_deal, reason: lark_refused}`. The independently authored oracle expects the latter. Runs 1/2 match **119/120** oracle fields; run 3 **120/120**. The current refusal handler ignores this action object, marks remaining products refused and finalizes after the second refusal, so this is an IR representation discrepancy, not proof of a wrong close outcome. It still deserves canonical extraction wording.
- Clean-eom additionally varies a band label, special-case order, trigger text, outcome explanatory text and whether `openapi.json` appears in `source_docs`. These are not deadline/outcome enum changes.

### Excluded text can still affect the generated agent

As requested, source spans and unresolved text are excluded from the field-difference count. **That exclusion does not make the workflows equivalent:** the compiler appends unresolved text to the dialogue system prompt. A+B run 1 adds `Rule 33 (never offer a discount, a waiver, an instalment plan or any term not in the brief) has no structural IR field; it must be carried by the prompt text.` Runs 2/3 do not. This reintroduces the exact negative-offer vocabulary removed from the hand-written prompts. Keep diagnostics separate from dialogue rules; generate the positive rule “Only discuss terms supplied in your current instruction” instead. This is the highest-value finding from the rerun.

### Proposed extraction-description changes

1. Define one canonical representation for refusal-to-talk: a close action naming the final outcome/reason, `ask_once_first: true` for a two-refusal policy, and explicit `ends_call`; defer product notes to the notes/outcome policy. Do not encode the same rule sometimes as a note and sometimes as a close.
2. Define `floor_if_full_refused` only for a `full` attempt; use false for an explicit floor attempt. Define `before_persuasion` consistently for priority special cases. These changes reduce representational variance without changing supported behavior.
3. Copy dictated phrases exactly. For content-only phrases, specify one canonical sentence/normalization rather than asking for a fresh paraphrase on each pass; do not normalize mandated verbatim text. Keep the current requirement that mandatory content cannot be left empty.
4. Fix `source_docs` to the caller's ordered brief paths; use a stable special-case ordering and band naming convention. Keep explanatory `when`/trigger wording out of comparisons used to decide whether routing changed.

These are recommendations only; the extractor prompt was not edited during measurement.

### Validation and scope

All nine policies compile with **zero static errors** (A/A+B: 33 nodes; clean-eom: 41). Offline scripts pass **39/39** across the three A and three B policies; these inject structured extraction values and do not test Freya's natural-language classification. Detailed compile/oracle/transcript checks and generated system prompts: `determinism-rerun/output-checks.json`.

All **18 SDK sessions** have start/end records; **160 assistant-message events** have IDs/usage, corresponding to **61 distinct message IDs**, and **96 tool calls** have matching allow/deny decisions (all allowed, no unexplained tool calls). Multiple SDK events can share a message ID: do not count message events as separate HTTP requests or sum their usage naively. There are **zero Freya HTTP calls** in these extraction traces. Provider-internal requests/retries remain outside SDK visibility.

Concurrent edits occurred after the snapshot, including `policy.py`; see `../audit/current/concurrent-changes.patch`. The nine-run comparison measures the frozen revision, **not the later schema**. No commits or pushes were made.

Re-run into a new evidence directory after loading credentials:

```bash
set -a
source .env
set +a
.venv/bin/python results/extraction/determinism-rerun/run.py --out results/extraction/determinism-next
```

The original executed runner is retained as `run-executed.py`; the reusable runner additionally captures all test/helper dependencies and refuses to overwrite an existing evidence directory. Exact per-input CLI form inside the frozen snapshot: `.venv/bin/python -u extract.py <comma-separated briefs> <openapi> det-<a|ab|clean-eom>-<1|2|3>` (use the repository venv's absolute interpreter path from that directory).
