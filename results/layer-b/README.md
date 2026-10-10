# Layer B — extraction accuracy on generated policies

`scripts/layer_b.py run` rendered 8 of the 40 generated policy IRs (`results/permutations/`) as documents, ran the real
extractor (`extract.py`, claude-opus-5-5, 3 passes) on each, and compared the extracted IR with the generator's IR:

- **clean** (4): one self-contained brief in the hidden-brief style, natural language only (no DSL hints).
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
| lb-03 | clean | 168 s | 0 | all pass | 9 |
| lb-10 | clean | 142 s | 0 | all pass | 5 |
| lb-20 | clean | 141 s | 0 | all pass | 4 |
| lb-04 | raw | 158 s | 0 | all pass | 6 |
| lb-06 | raw | 165 s | 0 | all pass | 4 |
| lb-14 | raw | 155 s | 0 | all pass | 5 |
| lb-26 | raw | 183 s | 0 | all pass | 8 |

**Result: 8/8 match on every operative field and 8/8 behave as the generator's policy in all scenarios**, incl. hyphenated
vocabularies, 1–4 identity questions, Mon–Thu and Saturday calendars, calendar-day / end-of-month / fixed-date deadlines,
and all four memo packs (the memo wins; the obsolete mail quotes are ignored and logged as historical).
Extraction took 141–183 s per sample (quiet Claude), about $1 each (~$8 total).

What the extractor flagged as `unresolved` (good behaviour, worth knowing): the practice-kit prose left in the mutated
OpenAPI ("three wrong answers", "both questions", "four digits") conflicts with the documents — it used the documents and
logged the conflict; un-dictated sentences (sympathy, cannot-answer) were written and logged. Hand-written-brief artefacts
found by this run (fixed in `layer_b.py` for the next run): the rendered brief skipped section 7 for single-product
policies, and the OpenAPI copies kept practice descriptions (now scrubbed).

Re-run: `.venv/bin/python scripts/layer_b.py run --perms 1:clean,5:raw,...` (Claude only, ~3 min and ~$1 per sample).
