# Audit 2 — Hardcoding sweep of compile.py / policy.py / bankcal.py

Repro: `grep -n "2026-\|2027-\|minimum_payment\|instalment_amount\|day_month_swapped\|You will receive a text message\|Freya\|wrong_number\|not_reached\|no_promise\|restructuring\|12th\|45" compile.py policy.py bankcal.py` from repo root (pinned hashes in `snapshot-sha256.txt`).

## Result: no literal practice-brief *values* in the compiler core — clean for the stated rule

- Holiday dates, band thresholds (1–7 / 8–45), 12/7 business days, outcome/reason/queue enum values, `minimum_payment`/`instalment_amount`, `day_month_swapped`, "You will receive a text message…", "Freya Bank": **none present as values** in compile.py/policy.py/bankcal.py. All flow through the IR fixtures (`tests/fixtures/*.policy.json`, allowed) and `SLOTS`/`POLICY` at runtime. The slot-needle `"instalment"` at compile.py:89 is used as an **exclusion** filter for slot mapping, not as policy values — fine, though see note N3.
- Product IDs, customer IDs, amounts: never synthesized (carried from `get_account`), per plan §3.2. Good.

## Reported anyway (practice-brief text and semantics baked into template code/prompts)

The hackathon rule prohibits putting **hidden**-brief values into the builder after briefs open; practice-brief wording is not itself a disqualifier. But these are the exact places where a reviewer grep lands, and each is a generalization ceiling (see rule-coverage F4/F5):

- **C1 [rule-compliance risk]** `compile.py:668` — `'I am calling from the ' + bank_name + ' collections team about …'` and `:669` `'Can you make this payment today?'` / `'Can you pay all of them today?'`: debt-statement wording baked in code, not IR (Brief A rule 17/28 sentences). The IR carries no field for the debt-statement/first-ask sentences. The raw-material hidden brief may dictate different mandatory wording.
- **C2 [rule-compliance risk]** `compile.py:844` hardship instruction ("Say one short sentence of sympathy … Offer to connect them with the customer support team") duplicates rule 32 wording in code while the IR `special_cases.hardship.say` sits unused.
- **C3 [nit]** Extraction descriptions at `compile.py:1548–1551` restate A/B triggers verbatim ("illness, a death in the family or losing their job", "closed or paid off before", "lower instalments"). These should be assembled from `special_cases[].trigger` + the IR phrase fields; today `trigger` is dead data (rule-coverage F5), so the extractor's own vocabulary is what the compiled agent will use regardless of the brief.
- **C4 [nit]** `policy.py:23` docstring example carries `"2026-11-30"` and `policy.py:43` mentions `date_of_birth` in a comment — harmless, but greppable by a reviewer agent; consider neutral examples (`YYYY-MM-DD`).
- **C5 [reproducibility risk]** `_ask_text` word count, `['First','Second','Third','Fourth','Fifth'][k]` ordinal list (compile.py:666), `range(8)` fallback product scan (`:383`): numeric/lexical assumptions beyond practice scale (≤3 products) — low risk, keep in mind if a hidden brief says "up to five".
- **C6 [rule-compliance risk — biggest optics problem, outside the three files]** `out/gen_brief_a.py` (tracked in git) is a **hand-written generator drenched in Brief A literals**: holidays list (`:153`), bands `late <= 7 → nth_biz(12)/nth_biz(7)` (`:243–250`), outcome/reason name arrays (`:99–100`), mandatory sentences ("You will receive a text message…" `:61`), "Freya Bank" throughout, and `out/brief-a.workflow.json` its compiled output. It is not referenced by `build.py` (verified: `grep -n gen_brief_a build.py` → 0) — it's a legacy pre-compiler artifact. A reviewer checking the commit for "hidden brief values" greps exactly these strings; and per the rules, if this file were ever used to produce the submitted agents it looks like hand-building. Recommend deleting both files from the submission tree (or moving under `tests/fixtures/` with an explicit "legacy example" note), before Sunday's commit.

Summary: the compiler core honors the no-hardcoding rule for values; the residual risk is mandatory-sentence and trigger vocabulary frozen in code (C1–C3) and the tracked legacy artifacts (C6).
