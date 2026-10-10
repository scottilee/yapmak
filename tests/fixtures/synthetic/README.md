# Synthetic scripts against existing practice customers

Each JSON file contains one case in the official `public-test-set.json` format.
The case ID, identity and products are unchanged. Run variant files separately:
combining variants with the same ID in one file collides in the official runner.

Supported directly by the official runner (simulation-slot coordination required):

```bash
.venv/bin/python tools/run_cases.py AGENT_ID --cases tests/fixtures/synthetic/readback_amount_correction.json --out results/correction.json
.venv/bin/python tools/run_cases.py AGENT_ID --cases tests/fixtures/synthetic/below_floor_then_accept.json --out results/floor.json
.venv/bin/python tools/run_cases.py AGENT_ID --cases tests/fixtures/synthetic/dispute_second_of_three.json --out results/dispute.json
```

`transfer_after_recorded_promise.json` also uses the official runner, but depends
on the agent yielding a customer turn after recording p1 and before flushing notes
or closing. It cannot prove interruption handling in a workflow that performs all
those actions in the same turn. Use controlled chat for deterministic trigger timing.

The official runner ignores the fixture's `variables.now`; it uses the bank's
fixed practice-session clock. Use the explicit adapter for Friday:

```bash
.venv/bin/python scripts/run_synthetic_cases.py AGENT_ID --cases tests/fixtures/synthetic/next_friday_from_friday.json --out results/friday.json
```

`double_write_failure.json` is **offline only**. The official runner does not send
fault definitions to the practice API; PUB-10 supplies one built-in failure, not
two. A double-failure-on-p2 simulation requires documented server fault injection
or a controlled test double, neither of which is supplied by this kit. The adapter
rejects this fixture rather than silently running a different scenario.

These scripts and expected records are test inputs, not measured pass claims.
See `manifest.json` for capability labels. Mutated briefs in `../mutated_briefs/`
are likewise offline extraction/generalization inputs, not runnable mock bank policies.
