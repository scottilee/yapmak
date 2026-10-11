# Deferred process checks

No repository traces have been scanned, no clone has been made, no commit has been made, and no build has been run by this fixture task. The commands below are for a later explicitly authorized process run. Current authorization is fixture creation only. The helper is read-only and never calls the pipeline or a network API.

## Trace scan

From the repository root:

```bash
.venv/bin/python -B tests/fixtures/external/r2-index/process_checks.py traces traces/
```

Every regular file under traces is read, including nested paths and non-jsonl extensions. Output contains file, line and pattern category only, never secret text. An unreadable file or empty directory is not a passing audit. This is heuristic detection, not a guarantee: review possible keys privately and check unusual credential formats. Do not print matched lines or paste keys into a review. Exit codes: 0 = no pattern candidates in a nonempty readable tree, 1 = candidate findings, 2 = incomplete audit.

## Printed degraded field

Capture a future build's stdout to a fresh file and preserve its actual exit status. Then run:

```bash
.venv/bin/python -B tests/fixtures/external/r2-index/process_checks.py build-output PATH_TO_CAPTURED_STDOUT
```

The helper locates the last printed JSON object with slot/workflow/trace, including pretty-printed JSON, and checks its degraded field. Missing payload/field, malformed type or unreadable output is failure; a nonempty list is not a clean build. The helper prints only presence/count, not raw diagnostics. Read nonempty diagnostics locally and classify each against the package's source requirements. Intentional unsupported fixtures should report their limitation; that is diagnostic coverage, not an agent-policy pass. The pipeline's zero exit code alone is insufficient. An empty degraded list is also insufficient without the separate policy/API checks.

## Fresh-clone build after explicit commit/build authorization

1. Confirm the exact reviewed commit SHA is committed and contains every intended fixture and dependency declaration. Do not incorporate unrelated staged work. Record git version, commit SHA, dependency lock/requirements hash and `.venv/bin/python --version`.
2. Create a new, nonexisting clone path, independent of the current worktree and virtualenv. Use `git clone --no-local SOURCE_REPO NEW_CLONE`, then `git -C NEW_CLONE checkout --detach REVIEWED_SHA`. Do not copy out/, traces/, .venv/ or local generated policies into it. Credentials must be supplied through the approved environment, never committed or echoed.
3. Using the existing `.venv/bin/python`, create a new environment with `-m venv NEW_CLONE/.venv`. In the clone install declared dependencies using `.venv/bin/python -m pip install -r requirements.txt`; use a lockfile if the reviewed commit supplies one. A missing runtime dependency is a reproducibility finding, not permission to patch the pipeline during the check.
4. Only once live build/Freya writes are expressly authorized, run the reviewed entrypoint from that clone, for example `.venv/bin/python build.py --briefs tests/fixtures/external/r2-api-control/01-specification.md --openapi tests/fixtures/external/r2-api-control/openapi.json --slot APPROVED_ISOLATED_SLOT --no-smoke`. Omit --cases: this recipe authorizes no simulation. The --no-smoke option is not an offline-build guarantee; build.py still creates/updates Freya resources. Do not run it under the current fixture-only restrictions.
5. Preserve exit status and stdout/stderr without exposing credentials; inspect the printed degraded field with the helper. Check expected.json, api-expected.json and requirements.json separately. A clean control and an unsupported negative fixture have different acceptance criteria.
6. Scan every trace in that clone with the helper before sharing artifacts. Report reproducibility outcome, commit SHA, environment details, degraded count/categories (redacted), and all skipped checks. Do not commit, push, change pipeline files, or conceal a missing dependency to make the result green.

The malformed callback schema is an intentional negative input, and unsupported policy requirements must remain visible. No currently generated policy or handwritten expected file should be fed back as extraction output to claim this fresh-clone check passed.
