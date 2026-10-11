# Sunday v24 fresh-clone rehearsal — 2026-10-11 UTC

Publication/export and local submission commits completed. GitHub push is **blocked by authentication**. All three builds recorded failed chat checks (HTTP 503), despite successful build exits. No simulation was started by this rehearsal.

## Provenance and isolation

Source HEAD: `70ce3b4f73b54d433ff29fffa182ce993f6ee890`. A copied Git index was exported with `git archive`, preserving staged files and excluding unstaged/untracked concurrent work. Snapshot tree: `4664bcea7da154a35c5fd94ab77d286e8c3b2564`; isolated snapshot commit: `bc5890079984745401f0623c9c850093153e8079`. Snapshot timestamp: 04:16:35 UTC. This is a staged-v24 snapshot, not a claim that main HEAD contains v24 or that later fixture work is included.

Fresh clone: `/tmp/sunday-v24-zqeph3qj/clone`, cloned with `git clone --no-hardlinks` from `/tmp/sunday-v24-zqeph3qj/snapshot`. `.env` and `.freya-agents.json` were copied privately mode 0600, never committed. Copying the registry ensured existing rehearsal/hidden slots were reused. Main repository index, branch, pipeline, and out directory were not changed; only this report directory was written.

## Commands and timing

- 04:16:35: snapshot/fresh clone completed.
- Approximately 04:16:40: `uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt` succeeded (35 packages, Python 3.14.4).
- 04:16:54–04:17:32: `TMPDIR=/tmp/sunday-v24-zqeph3qj/logs scripts/preflight.sh --with-build` exited 0, 3 warnings, 0 failures. Offline tests: 133 passed in 16.72s. Claude credential probe: OK. Freya and bank mock health: OK. Policy build duration: 14.5s.
- Preflight warnings: incomplete git identity; no origin at initial check; existing simulation `8b49ceea-c43f-460a-8800-4ec4288f060d` running. The rehearsal did not modify that simulation.
- Configured clone-only origin with `git remote add origin https://github.com/scottilee/temsilci.git`, normalizing the existing submission/config.json www GitHub URL. No repository was created. `git ls-remote ... HEAD refs/heads/rehearsal` failed credentials; repository existence/access remains unverified. `gh auth status` separately reports invalid GH_TOKEN.
- 04:17:49 UTC: checked current time against 2026-10-11 16:00 UTC publication cutoff; passed with over eleven hours remaining.
- 04:17:49–04:18:11: exact requested command `scripts/submit.sh hidden/dry-1 hidden/dry-2 --fast --branch rehearsal --push`. Inputs already committed. Hidden-1 build 12.9s; hidden-2 build 8.1s. Artifact credential scan passed. Artifacts commit `6181252ce0e71420dac66380d62a3cd90ddc1ff4`; form commit `c80b97511a3b63b216ed02e4b3f4f2e60bf85820`. form.commit correctly references the artifacts commit.
- Push error: `fatal: could not read Username for 'https://github.com': terminal prompts disabled`. **The script nevertheless exited 0**, because its `git push && log` failure is followed by a successful final build-status test. Do not use exit 0 as proof of push.

## Published exports

| Slot | Workflow ID | Published version | Chat checks |
|---|---|---:|---|
| rehearsal-a | a54d4355-f820-4a39-94c3-112c2eb70460 | 4 | failed, HTTP 503 |
| hidden-1 | 011f407c-9d02-4a7e-af9d-6aa151c9ab96 | 3 | failed, HTTP 503 |
| hidden-2 | 4d95c143-210e-471d-a014-65cf8adcf4f8 | 3 | failed, HTTP 503 |

All exports and matching traces are copied under this directory; build-summary.json contains exact timestamps, workflow/agent IDs, code hashes, and check results. Platform trace times use -0700; times above are UTC. Each run_end has success:true but checks_passed:false. The preflight label “green” does not imply a passing chat smoke test. Failed chat POSTs were not used to infer agent behavior.

## Setup omissions and scope limits

No required repository files were missing. README's `npm install -g @anthropic-ai/claude-code` was omitted because the CLI was already installed and the actual credential probe succeeded. `.env` was copied confidentially rather than regenerated from a placeholder template. Login was unnecessary. The offline pytest and credential steps ran inside preflight rather than twice. The kit context's npm typecheck/lint/format/test/build gate does not apply to this Python repository, which has no package.json. No source edits were made.

`--fast` skips extraction and ignores supplied dry briefs/API for generation: it uses tests/fixtures/brief_a.policy.json and tools/openapi.json for both slots. This proves submission mechanics only, not extraction of unseen briefs. Static audit confirmed simulations are conditional on --cases, absent here; preflight only GETs simulations and creates a practice bank session. Build traces contain zero simulation events. The build's offline invariants use a local mock bank, not the platform simulation service.

The fresh clone began clean, but builds modify tracked output/trace files. run_start tree_dirty:true is expected because the trace rotates/writes before this check; preflight's rehearsal outputs also remain dirty in the isolated clone. No dirty pipeline changes were introduced.

## Remaining blocker

Push authentication must be configured before retrying `git push -u origin rehearsal` in the isolated clone. /Users/sl/sbx/AGENTS.md, Git Authentication, directs the user to configure the sandbox GitHub secret on the host: `sbx secret set github --sandbox hackathon2 -t "$(gh auth token)"`. This is an auth remedy, not proof that the repository exists or access is granted. Do not rerun publication solely to retry pushing, and do not force push. No remote SHA verification is possible until authentication succeeds.

## Final authentication recheck

At 04:20:55 UTC, `git ls-remote origin HEAD refs/heads/rehearsal` in the retained clone again exited 128 with the same missing GitHub username/authentication error. No push was retried, and no rebuild or publication occurred. Remote branch existence/conflicts remain unverified. See auth-retry.log.
