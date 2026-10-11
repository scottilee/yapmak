# Independent current-state review

Reviewed HEAD `e870198928fc39621bda89d8c409efec034f3b6c` plus the staged working tree, not HEAD alone. Review date: 2026-10-10. Read `../AGENTS.md` and the referenced hackthon kit instructions. The kit's npm verification gate cannot apply literally: this checkout has no package.json. Ran the actual Python suite independently: **99 passed in 7.22 s** (`.venv/bin/python -m pytest tests/ -q`). No paid models, simulations, publication, commits or pushes were performed. Historical results below were inspected as saved evidence, not rerun or assumed current.

## Prioritized findings

1. **High — unresolved extraction text becomes authoritative global instructions.** `compile.py:210–212` copies up to 12 unresolved descriptions, truncated to 400 characters, under “Further rules ... apply throughout the call.” This conflates a rule with an uncertainty, unsupported policy, or conflict; truncation can discard a qualification. Model-generated prose can consequently override carefully staged dialogue restrictions. Tool/file isolation does not address this semantic instruction boundary. Preserve uncertainties as diagnostics; only explicitly represented and validated rules should become executable instructions. Add a fixture containing an unresolved conflicting rule and verify generated prompts/routing.
2. **High — build success does not mean submission readiness.** Suspect platform read-back differences are logged without failing (`build.py:116–125`), chat failures are informational (`169–184`), and the run still ends `success=True` (`155`). This preserves a deliverable under service failures, but callers must not interpret exit zero as a correctness certificate. Exported field removals or runtime errors need an explicit degraded/readiness status and a submission gate. The two pre-bank chats do not validate payment, multi-product outcomes or spoken consent.
3. **Medium — audit/repair fallback can misattribute changes to the final policy.** When audited JSON and repair fail validation, `extract.py:285–289` restores the first pass but retains the audit file for the rejected candidate. `299–300` then logs its `fixed` claims alongside the restored policy. The timeout fallback correctly labels its output unaudited (`257–264`); repair fallback should likewise invalidate/rewrite the audit and bind it to the final policy hash. This is a concrete provenance defect, independent of whether the fallback policy is usable.
4. **Medium — structural validity is weaker than complete rule extraction.** Defaults such as three wrong answers, two holder checks and 10:00–19:00 callbacks remain (`policy.py:58–63,73–78`); `extract.py:31–32` explicitly allows defaults for unspecified fields. Missing extraction can look valid, and a shared schema/guide creates correlated omissions across extractor and auditor. Require source-backed explicit values for operative fields, or distinguish truly unspecified from defaulted/unsupported behavior. The supported DSL and named special cases deliberately constrain generalization; this is acceptable engineering scope only if unsupported hidden rules are surfaced honestly.

## Five direct answers

**1. How good is the existing baseline?** Strong hackathon engineering, not a demonstrated perfect final submission. The deterministic policy IR/compiler/runtime separation puts bank writes, arithmetic and routing behind code guards; tests cover meaningful drift, consent, retry and input-safety cases. The independent current offline run is 99/99. Raw `results/gen/a-reps3-frozen.json` has ten customers passing all three runs, while `b-reps3-frozen.json` has only two of three (PUB-13 passed twice); `a-reps3-v21.json` has nine of ten. These are different historical revisions, not one current 12/13 or 13/13 score. Current end-to-end consistency remains unmeasured. Saved current-schema extraction observations also contain real disagreements (`results/extraction/20261010T144657Z-priority/evaluated-results.json`), and their inert chat setup cannot establish bank-outcome correctness.

**2. Does an independent rule audit improve correctness?** Yes on concrete saved examples, with limited causal scope. I inspected both `results/generalization/*/consistent-input-run/audit-applied-diff.json` files: both change refusal from fixed close outcome to note/finalization, preserving existing-promise precedence; clean-eom also adds `cannot_answer.before_persuasion=true`. These are substantive corrections, not merely the auditor claiming success. They establish benefit in those examples, not an average accuracy lift or net regression rate. The “independence” is a fresh context sharing the same model, schema and guide (`extract.py:27,242–253`). Repeated audited outputs still vary in behavior (`results/extraction/determinism.md`, refusal and precedence flags). Measure frozen first-pass versus audited outputs against independently authored rule oracles, retaining both repaired and regressed rules and downstream behavioral checks.

**3. Does a different model reduce extraction errors?** Unknown. I found no controlled cross-model comparison in the inspected evidence. Distinguish builder document extraction from Freya speech extraction: `BUILDER_MODEL` changes the former; the final phone-agent model is fixed by the kit rules (`README.md`, Rules). A model swap cannot be inferred from nine same-model repeats or isolated speech tests. Compare equal-budget models on identical unseen documents, schema and oracle, with repeated runs and exact operative-field/behavioral errors, before changing the builder.

**4. Does provider diversity catch unique omissions?** Plausible, unmeasured. There is no inspected matched provider-pair corpus with independently adjudicated unique catches. Different providers can still share schema-induced blind spots and introduce contradictory fixes. A useful experiment freezes extractor output, runs same-provider and alternate-provider auditors with identical budgets, and measures unique true omissions, false corrections, overlap, runtime and net post-merge correctness. Do not equate disagreement with a recovered rule.

**5. Would Rust or C++ help now?** No evidence supports a rewrite. Python execution is not the demonstrated bottleneck; saved latency evidence (`results/latency/README.md`) implicates remote stage/hop latency, with confounded version/load comparisons. The platform executes embedded Python code nodes, so a host-language rewrite would not remove those hops. It would invalidate well-tested calendar/runtime logic while leaving model extraction and remote service variability intact. Profile local compilation first; optimize graph transitions only with platform regression evidence.

## Architecture, security and readiness

Architecture is sensible and relatively mature: explicit IR, separated OpenAPI mapping/node construction/static checks, deterministic runtime, and shared request/trace controls. Complexity remains concentrated in the large state machine and language-to-IR boundary. Security strengths include exact-path Read/Write allowlists with path resolution and denial of other model tools (`extract.py:89–112`), separate extraction workspace, and credential artifact gates (`artifact_security.py`). Those controls do not prove semantic prompt-injection resistance or full secret discovery; avoid presenting them as such. No credential values were inspected or printed.

Freeze the final source/input/export set, resolve or explicitly label the findings above, then verify the exact exported current build under the final three-pass scoring criterion when authorized. Historical results and successful offline structured-input tests are insufficient for unconditional submission sign-off. New experiments suggested above were not run by this review.

## Reviewed state

Source hashes captured during review (SHA-256):

```json
{
  "extract.py": "5d58406f7b8b8d58ed6953d19bfa3c145698fb1f3c1d5aedd955e4ca663137fa",
  "build.py": "6a718c346dfec7f50b0752aec69c29fb4aff796e69966e089c4551c5cb6ad29b",
  "policy.py": "f0ef340379d1ead5c20b788690da8189819ef5bb095af288426afbca5bb224f9",
  "workflow_runtime.py": "55b635dee96a7bc2b4229e8a02082d4cae2e230a44b923e082ea0ce279e23c2d",
  "compile.py": "80688058231595c7f1e5cd3468e6a427041e6e9604e75a77909c9212d23d8708",
  "compiler_nodes.py": "7a7586d8a5d346b0271e65e801cb20ffe5ddaa047bda304c63e9442337807aec",
  "compiler_openapi.py": "4ae869cf4f33509e3bfcb11ec4d37765b146078072aceda559aee548581027eb",
  "artifact_security.py": "059654067db07df29fc0048539368f65e2b904d51b5f166e900a6c544bc4c971"
}
```

Working-tree status at review start/end (before this report was added):

```
M  extract.py
M  out/gen-a.workflow.json
M  out/gen-ab.workflow.json
M  policy.py
M  results/audit/drift-out/wf_m1_remaining_rename.json
M  results/audit/drift-out/wf_m4_required_field.json
M  results/audit/drift-out/wf_r1_request_renames.json
M  results/audit/drift-out/wf_x2_write_ok_rename.json
M  results/audit/drift-out/wf_x3_note_reason_rename.json
M  results/audit/drift-out/wf_x4_dayslate_rename.json
A  results/audit/review-v22.md
M  scripts/check_provenance.py
M  tests/invariants.py
A  tests/test_v23_regressions.py
M  workflow_runtime.py
?? scripts/make_edge_cases.py
?? tests/fixtures/edge/
```
