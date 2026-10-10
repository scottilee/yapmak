# Audit index (auditor pass, 10 Oct ~13:05–13:15 UTC)

Scope: offline only. No simulations started, no Freya writes beyond nothing, no source files edited. Findings → `rule-coverage.md`, `hardcoding-sweep.md`, `schema-drift.md`, `offline-state-machine.md`. Repro: `offline_probes.py`, `drift_mutations.py` (artifacts in `drift-out/`), `snapshot-sha256.txt`.

Caveat: `compile.py` changed twice during the audit (05:48 → 06:03 builds; the latest drift run shows 31 nodes vs the pinned 32). Line references are pinned to the hashes in `snapshot-sha256.txt` — re-run the two scripts and `git diff` before acting on line numbers.

Top findings by severity:

1. **[blocks score] Rule 3 second-ask counter** — question turns consume the re-ask budget; "hello"→"who is this?"→"yes" closes `not_reached/unclear` (offline-state-machine P3b).
2. **[blocks score] Silent slot-mapping failures** — `_pick` defaults resurrect stock field names; renames of `ok`/`verified`/`days_late` compile clean and produce agents that fail identity, double-record promises, or pick the wrong deadline band (schema-drift X1/X2/X4). No unmapped-slot failure branch despite plan §3.2.
3. **[blocks score on vocab rename] Disposition/reason literals** — internal `'refused'/'dispute'/'paid'/…` vs IR reasons/enums; notes silently skipped, close reasons can go out-of-enum; and `st_close_after` ignores `close_ok` (rule-coverage F9/F3, schema-drift X3).
4. **[blocks score] Rule 36 has no enforcement path** — post-record conversation is structurally impossible; `recorded_promise_change_reply` is dead IR (rule-coverage F2).
5. **[reproducibility risk] ~20 IR booleans/fields unused by the compiler** (rule-coverage F5) — synthetic-brief mutation tests can pass while nothing changes.
6. **[rule-compliance risk] `out/gen_brief_a.py` + `out/brief-a.workflow.json`** — tracked hand-built artifacts full of Brief A literals; unused by `build.py`; delete before the submission commit (hardcoding-sweep C6).

Clean: hardcoding sweep of the compiler core (no dates/bands/enums/values outside fixtures), compile reproducibility (byte-identical), offline_sim 13/13, and the 14 non-rule-3 probes all matching the brief — including the floors/vague/write-failure/transfer-no-notes ladders. The one deliberate violation demo is P3b (finding 1).
