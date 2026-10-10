# Auditor sign-off — 10 October 2026

**Conditional sign-off for the frozen compiler's offline checks; no unconditional submission sign-off.** Frozen revision: `2064600d6ff207fa43df8ea27c1e643bc282bbe3`. Source/input hashes: `../../extraction/determinism-rerun/manifest.json`; starting Git state: `../../extraction/determinism-rerun/revision.json`. Other work was already staged at audit start. No production code edits, platform simulation, publication, commit or push were performed by this audit.

| Check | Result / evidence |
|---|---|
| Frozen source unit/regression suite | **81 passed**, `tests.log` |
| Fresh fixture A / A+B compile | **33 nodes each; zero static errors**, `a.workflow.json`, `ab.workflow.json` |
| Public scripted state-machine cases + split-answer variant | **14/14**, `offline.log` |
| Additional state-machine probes | **15/15 counted assertions**, plus printed diagnostics, `probes.log` |
| Schema drift | Four supported renames compile; unsupported identity mapping, mismatched outcome enum and new required request field fail loudly, `drift.log` |
| Existing A/A+B generated artifacts | All four workflow bodies contain the current candidate at the time checked, ignoring platform-added defaults; `artifact-comparison.json` |
| Credential gate | 13 audit/existing hidden artifacts passed; `credential-scan.log` |
| Trace accounting | See [trace-review.md](trace-review.md): old traces incomplete; newer rehearsal reconciles 18/18 requests but uses fixture mode |
| Judge wording | **Not clean**: hardship instruction contains discount/waiver; fresh extraction can inject the same wording through unresolved text; concurrent prompt edit adds pre-write “recorded promise.” See [judge-wording.md](judge-wording.md) |
| Extraction determinism | **9/9 succeeded**, 533.4 s / $9.2575; **7 / 15 / 20** differing fields in A / A+B / clean-eom. All compiled; 39/39 applicable offline public scripts passed. [Full comparison](../../extraction/determinism.md) |

These offline cases inject structured extraction values; they prove deterministic routing/math under those inputs, **not** the accuracy of Freya's speech extractor or the spoken response model. Existing live chat evidence is not a fresh test of this snapshot. Extraction repeatability also cannot prove correctness where all three runs agree on a wrong value.

## Conditions before a submission sign-off

1. Resolve the wording risks above (or explicitly accept them); recheck actual generated prompts, including unresolved-derived text, not only template source.
2. Resolve behavioral extraction flips identified by the sweep. Wording-only variation still makes workflows differ; distinguish that from routing, deadlines and outcome changes.
3. Preserve a clean committed source/input revision and run a new end-to-end build with the current trace instrumentation. Old traces cannot retroactively demonstrate all calls. Attach policy/audit artifacts and actual exported workflows; retain the timing and exact command in the trace review.
4. The working tree continued changing during this audit. `concurrent-changes.json` / `.patch` record observed differences; the frozen nine-run result does not certify those later schema/compiler changes.

Remaining generalization limitations are not hidden by passing public fixtures: `policy.py` retains brief-shaped defaults (callback hours, attempt limits, etc.); special-case recognition is template-authored rather than derived entirely from trigger text; the snapshot does not use every representable IR switch or the already-recorded-change reply. Later concurrent work addresses some of these, but requires its own revision-specific verification. See the trace report for exact limits on “not hand-built / no values in code” claims.

Reproduction of offline checks:

```bash
.venv/bin/python -m pytest results/extraction/determinism-rerun/snapshot/tests -q
.venv/bin/python tests/offline_sim.py results/audit/current/a.workflow.json results/audit/current/ab.workflow.json
.venv/bin/python results/audit/current/offline_probes.py
.venv/bin/python results/audit/current/drift_mutations.py
```

The copied probe and drift scripts resolve this checkout relative to their own location and use the frozen source/input snapshot.

Final checks: all 31 fresh extraction policy/audit/trace and report files scanned at completion passed the credential gate (`rerun-credential-scan.log`). The concurrently edited working tree also passed 81 tests (`working-tree-tests.log`); that does not extend the frozen extraction result to the new schema.

A concurrent fixture rehearsal also finished during this audit: run `767e7045`, 51.8 seconds, 17/17 paired HTTP requests, chat self-test passed and zero suspect workflow read-back differences. Both old and new traces were preserved and reviewed; see the trace report supplement. All six preserved traces passed credential scanning.
