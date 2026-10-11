# Submission email draft

To: yavuz@freyavoice.ai  
Subject: Freya hackathon submission — yapmak

Hi Yavuz,

Please find the final submission for team **yapmak** (Scott Lee).

- Repository: https://github.com/scottilee/yapmak
- Artifacts commit: **<COPY submission.json commit AFTER FINAL PUSH>**
- Mock: https://yapmak-bank-mock.winter-mountain-4405.workers.dev
- Run command: `python3 build.py {case_folder} {mock_url}`
- Submission manifest: attached `submission.json` (also committed in the repository).

The traces in `traces/` document the authoring run, checker fix and resumed build. They also record the live-findings repair pass, so you can follow how the final workflow was produced.

Best,  
Scott Lee  
Team yapmak

---

# Pre-send checklist — do not include this section in the email

Run from the repository root after the final artifacts and submission manifest have been committed and pushed. Do not send until the placeholder above is replaced and all checks pass. This draft has not been sent.

- [ ] `submission.json` is the **final-case** manifest, not the older `submission/form.json` rehearsal form. Team, members, repository, mock URL and run command match the email; workflow is `out/final.workflow.json` and trace is `traces/final.jsonl`.
- [ ] The manifest's `commit` is the pushed **artifacts commit**. `submit_final.sh` subsequently creates a separate manifest commit, so the field need not equal HEAD. Both must be reachable on the submitted remote branch.
- [ ] Every local artifact/input/script path referenced by the manifest is tracked and present in the appropriate commit. `{case_folder}` and `{mock_url}` are organizer-substituted parameters, not literal local paths.
- [ ] The final workflow reviewed and tested is byte-for-byte the artifact in the manifest's commit. The repaired export has not been replaced after review.
- [ ] The authoring, checker-fix, resume and live-findings repair trace history is tracked under `traces/` and pushed. Read those events before retaining the email's two-sentence claim; a directory name or unfinished `run_start` alone is not evidence of a completed pass.
- [ ] The mock `/health` and `/openapi.json` both answer successfully and return JSON; inspect their contents.
- [ ] The final mock replay reports **617/617 entries match**, with no `MISMATCH` and no `BAD` contract checks. The verifier's exit status alone is insufficient.
- [ ] Attach the exact committed `submission.json`, replace the email's commit placeholder, and send only the email section.

## Local manifest and pushed-commit checks

First refresh the remote tracking ref (read-only with respect to the remote):

```bash
git fetch origin main
.venv/bin/python - <<'PY'
import json, subprocess
from pathlib import Path

def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()

def checked(*args):
    subprocess.run(['git', *args], check=True)

s = json.loads(Path('submission.json').read_text())
assert s['team'] == 'yapmak'
assert s['repo'] == 'https://github.com/scottilee/yapmak'
assert s['mock_url'] == 'https://yapmak-bank-mock.winter-mountain-4405.workers.dev'
assert s['run_command'] == 'python3 build.py {case_folder} {mock_url}'
assert s['workflow'] == 'out/final.workflow.json'
assert s['trace'] == 'traces/final.jsonl'
assert s.get('members'), 'Missing team members'
commit = s['commit']
assert len(commit) == 40 and all(c in '0123456789abcdef' for c in commit.lower())
checked('cat-file', '-e', commit + '^{commit}')
checked('merge-base', '--is-ancestor', commit, 'origin/main')
checked('merge-base', '--is-ancestor', 'HEAD', 'origin/main')
tracked = set(git('ls-files').splitlines())
paths = {s['workflow'], s['trace'], 'build.py', 'submission.json'}
# Also inspect any future additional path-valued manifest fields manually.
for p in paths:
    assert p in tracked, 'Untracked manifest/run path: ' + p
    assert Path(p).is_file(), 'Missing local path: ' + p
    checked('cat-file', '-e', 'origin/main:' + p)
for p in (s['workflow'], s['trace'], 'build.py'):
    committed = subprocess.check_output(['git', 'show', commit + ':' + p])
    assert committed == Path(p).read_bytes(), 'Local file differs from artifacts commit: ' + p
assert subprocess.check_output(['git', 'show', 'HEAD:submission.json']) == Path('submission.json').read_bytes()
assert subprocess.check_output(['git', 'show', 'origin/main:submission.json']) == Path('submission.json').read_bytes()
print('Manifest, tracked paths, artifact bytes and pushed ancestry verified.')
print('Email artifacts commit:', commit)
print('Members:', s['members'])
print('Review trace history:', git('ls-files', 'traces/final*'))
PY
```

If submitting a branch other than `main`, replace both `main` and `origin/main` consistently above with that branch. Check any extra manifest fields containing paths as well; the assertions cover the current final-case schema.

## Live mock checks immediately before sending

```bash
.venv/bin/python - <<'PY'
import json, urllib.request
base = 'https://yapmak-bank-mock.winter-mountain-4405.workers.dev'
for path in ('/health', '/openapi.json'):
    req = urllib.request.Request(base + path, headers={'User-Agent': 'submission-check/1.0', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as response:
        assert response.status == 200
        body = json.load(response)
    if path == '/openapi.json':
        assert isinstance(body.get('paths'), dict) and body['paths']
    print(path, 'HTTP 200; valid JSON', json.dumps(body, ensure_ascii=False)[:600])
PY
.venv/bin/python scripts/verify_mock.py https://yapmak-bank-mock.winter-mountain-4405.workers.dev
```

Require `617/617 entries match` and all subsequent contract checks marked `OK`. A traceback, `MISMATCH`, `BAD`, or a partial count blocks sending until investigated. Do not infer success merely because the script exits zero.
