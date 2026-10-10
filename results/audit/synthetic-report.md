# Synthetic briefs #3 and #4 — IR validation, compile, publish (extract-accuracy blocked on Claude creds)

Auditor pass, 10 Oct ~07:05–07:20 UTC. No simulations run; Freya writes limited to two new scratch slots via `scripts/publish_check.py` (dry-run + publish + read-back diff + export + two chat turns each, which the standing rules allow for chat).

## What was built

Two new brief shapes + matching mutated OpenAPI + hand-written ground-truth IR (the "perfect extractor" fixture) + flattened expectations:

| | Shape | New-for-the-kit aspects |
|---|---|---|
| `results/audit/synthetic/meridian-brief.md` + `meridian-openapi.json` | clean spec, 13 numbered sections | **four** identity questions incl. a `founded_year`-style year and `postcode` text; numeric dates read **mdy**; **end_of_month basis=calendar adjustment=following** deadline; **Mon–Thu** business week; renamed API: `facilities` list, `facility_id/facility_type/amount_overdue/overdue_days`, floors `minimum_due/fixed_instalment/line_payment`, `checks_left`, **no hint property**, outcome/queue/reason enums all new |
| `results/audit/synthetic/cobalt-brief.md` + `cobalt-openapi.json` | messy forwarded email thread | signed amendment **M9 explicitly reverses five v2 rules** (promise retry→0; human ask-once barrier→immediate; callback window→12:00–18:00; condolence sentence; already-paid no longer ends the call) + **renames the whole close vocabulary** (v2 names retired → Section F codes) + a **December memo not yet in force** (wrong cap 3→5 effective 1 Dec — must be ignored) + noise; API renamed `accounts/account_id/product_kind/outstanding_balance/late_days`, `remaining_attempts`, note reasons `already_settled/failure` |
| `meridian.policy.json` / `cobalt.policy.json` | hand-written IR per the briefs | ground truth for the compile/publish leg and for the future extractor diff |
| `*-expected.json` + `diff_ir.py` | flattened-path ground truth + comparator | runs against `out/<slot>.policy.json` once extraction is possible |

Existing fixtures (`clean-eom-*`, `reversal-thread-*`, `memo-brief`) were checked first so these two differ in shape, not just in vocabulary.

## Pipeline results (all on the 07:0x build; note `compile.py` landed the rule-3 `question` intent and the close-retry mid-run — both synthetic slots were compiled **after** that and include them)

1. `policy.P.validate()` vs mutated enums — **MERIDIAN OK, COBALT OK** (all outcomes, note reasons, queues, identity fields exist in the respective OpenAPI).
2. `compile.py` — MERIDIAN: 40 nodes, static check ok (4× `ask_i`/`verify_i` generated, floors/`overdue_since`-style renames slot-mapped, missing `card_last4` and `hint` degrade via the `__none__` sentinel path); COBALT: 32 nodes, ok.
3. Baked math verified offline: Meridian early deadline (EOM 2026-10-31 Sat → following Mon–Thu business day, 11-02 holiday) = **2026-11-03**; late 4-business-day = 2026-10-21; Cobalt 16–40 band (21 calendar days → 2026-11-04) — all correct via `bankcal.deadline()`; Cobalt `retry_on_failure=0`, `ask_once_first=false`, callback 12:00–18:00 confirmed inside the embedded POLICY.
4. `scripts/publish_check.py audit-eom` and `audit-rev` — dry-run ok, published, stored-vs-candidate diffs were **platform additions only** (`mode`, defaults, `truncation_window_size`, etc. — no content stripping), exports to `out/audit-*.export.json`. Chat smoke: Meridian asked the right **four-question** intro line after confirmation, Cobalt the right two-question intro with the phone-last-4 wording; `state_json`/`today_text` populated from simulated `now` (Wed 14 October 2026).

## Findings

- **S1 [blocks score — external]** `extract.py` **could not run**: every model pass dies with `Claude Code returned an error result: Invalid API key` (`env -u ANTHROPIC_API_KEY` → "Not logged in"; `/etc/sandbox-persistent.sh` is 0 bytes — the proxy credentials that worked for the earlier `xa`/`xmemo` extractions at 05:3x are gone). The requested *extractor-accuracy diff* is therefore not yet produced; everything else above substitutes the hand-IR for a perfect extractor. Commands to run the moment creds are back (≈40 min total):
  ```
  .venv/bin/python extract.py results/audit/synthetic/meridian-brief.md results/audit/synthetic/meridian-openapi.json audit-eom
  .venv/bin/python results/audit/synthetic/diff_ir.py out/audit-eom.policy.json results/audit/synthetic/meridian-expected.json
  .venv/bin/python extract.py results/audit/synthetic/cobalt-brief.md results/audit/synthetic/cobalt-openapi.json audit-rev
  .venv/bin/python results/audit/synthetic/diff_ir.py out/audit-rev.policy.json results/audit/synthetic/cobalt-expected.json
  ```
  (Caveat for whoever runs this: `extract.py` overwrites `out/<slot>.policy.json` — the hand-IRs are safe under `results/audit/synthetic/`; expect diff_ir to report ~20 field mismatches + `unresolved` for a first-pass extractor against these deliberately awkward briefs.)
- **S2 [rule-compliance risk]** compile.py:1629–1630 **regex-rewrites mandated opening text**: both briefs say the opening sentence is exact ("This call is recorded." / "…; this call is recorded."), but every compiled workflow now speaks "We record this call." The inline comment explains the motive (judges reading "recorded" as a promise-recording claim), but the hackathon checks "policy-compliant conversation" against the brief's own words — an exact-phrasing judge fails it, and this is a *silent* rewrite of an IR value. If the tradeoff is intentional, the second regex (`call is on record`) should cover Cobalt's semicolon variant consistently (it does here via the first rule); recommend surfacing any rewrite as a trace event, and consider only rewording when the brief doesn't say "exactly".
- **S3 [nit]** Cobalt ground-truth carries the one legitimately `unresolved` item (the "adjust the greeting word" ambiguity); Meridian's IR resolved everything. If the future extractor reports *more* unresolved entries than these, that is extractor error, not brief error — diff_ir prints them separately.
- **S4 [nit]** `close_retry` retries without the reason even for outcomes whose reason is required; a transient rejection that is *not* caused by the reason pair ends with a second, semantically-different close attempt (see offline-state-machine second recheck).
- Verified the new compiler fixes hold on genuinely different shapes: renamed response fields now either adapt or fail loudly (`cannot map response slots` never fired here because every slot matched), 4-question identity generates 4 engine-fired verify nodes, `end_of_month`/`calendar_days` DSL validated with explicit basis/adjustment, the Mon–Thu calendar computes correctly, and both workspaces slots stay inside the 200-workflow budget (audit-eom/audit-rev are reused-slot).
