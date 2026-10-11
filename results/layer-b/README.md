# Layer B — extraction accuracy on generated policies

`scripts/layer_b.py run` rendered 8 of the 40 generated policy IRs (`results/permutations/`) as documents, ran the real
extractor (`extract.py`, claude-opus-5-5, 3 passes) on each, and compared the extracted IR with the generator's IR:

- **clean** (4): one self-contained brief in the hidden-brief style, natural language only (no DSL hints).
- **thread** (4, round 2): one mail thread, newest first: a stale 1 October policy, a 7 October memo changing four rules (one of them wrongly), a 9 October correction reversing that one change.
- **raw** (4): cover mail quoting obsolete settings + stale base policy + signed memo that overrides identity order,
  wrong-answer limit, one band's deadline, retries, human handling and callback days + code list. The generator IR is
  what the memo says.

Two comparisons per sample: (1) every operative field (identity set/formats/limits, callback window, calendar, bands and
deadline rules, floors, product count, notes, outcome vocabulary and table, special-case actions, retries), with
meaningless differences canonicalized (`digits` on non-digit formats; `adjustment` on business-basis month ends);
(2) **functional**: the extracted IR is compiled and the seven IR-parameterized invariant scenarios run with the
generator's IR as the truth (`tests/invariants.py`).

| sample | style | extraction | operative diffs | functional | unresolved notes |
|---|---|---|---|---|---|
| lb-00 | clean | 150 s | 0 | all pass | 5 |
| lb-01 | clean | 158 s | 0 | all pass | 5 |
| lb-03 | clean | 168 s | 0 | all pass | 9 |
| lb-04 | raw | 158 s | 0 | all pass | 6 |
| lb-05 | raw | 149 s | 0 | all pass | 3 |
| lb-06 | raw | 165 s | 0 | all pass | 4 |
| lb-07 | thread | 157 s | 0 | all pass | 3 |
| lb-09 | clean | 155 s | 0 | all pass | 6 |
| lb-10 | clean | 142 s | 0 | all pass | 5 |
| lb-11 | thread | 151 s | 0 | all pass | 4 |
| lb-13 | raw | 149 s | 0 | all pass | 2 |
| lb-14 | raw | 155 s | 0 | all pass | 5 |
| lb-15 | thread | 160 s | 0 | all pass | 6 |
| lb-17 | thread | 167 s | 0 | all pass | 4 |
| lb-20 | clean | 141 s | 0 | all pass | 4 |
| lb-26 | raw | 183 s | 0 | all pass | 8 |

**Result: 16/16 match on every operative field and 16/16 behave as the generator's policy in all scenarios** (round 1: 4 clean + 4 raw packs; round 2, 10 Oct 23:52 UTC: 2 clean, 2 raw packs, 4 **mail threads** where a later message reverses one change of an earlier memo — the generator IR is the state after the last mail), incl. hyphenated
vocabularies, 1–4 identity questions, Mon–Thu and Saturday calendars, calendar-day / end-of-month / fixed-date deadlines,
and all four memo packs (the memo wins; the obsolete mail quotes are ignored and logged as historical).
Extraction took 141–183 s per sample (quiet Claude), about $1 each (~$8 total).

What the extractor flagged as `unresolved` (good behaviour, worth knowing): the practice-kit prose left in the mutated
OpenAPI ("three wrong answers", "both questions", "four digits") conflicts with the documents — it used the documents and
logged the conflict; un-dictated sentences (sympathy, cannot-answer) were written and logged. Hand-written-brief artefacts
found by this run (fixed in `layer_b.py` for the next run): the rendered brief skipped section 7 for single-product
policies, and the OpenAPI copies kept practice descriptions (now scrubbed).

Round 3 (11 Oct 03:11 UTC, after the floor-rule / deadline-kind additions): perm 10 and 14 (percent / fixed floors, clean), 6 and 24 (threads),
1 and 9 (raw packs incl. "the 15th of next month" and "end of next month" deadlines) — the extractor encoded `floor_rules` ("*" wildcard,
percent 20 min 50 / fixed 75) and the new deadline kinds correctly; 0 operative diffs on the 5 finished samples (16 samples overall). The
run-time functional column of that round was polluted by a concurrent revert of the runtime (see results/audit/review-v22.md) and was re-checked
offline afterwards: all pass.

Re-run: `.venv/bin/python scripts/layer_b.py run --perms 1:clean,5:raw,...` (Claude only, ~3 min and ~$1 per sample).
