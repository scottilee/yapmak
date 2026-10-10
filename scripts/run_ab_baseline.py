"""Run the untouched example A+B builder in an isolated copy of the starter kit."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/example-builder' / ('ab-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
OUT.mkdir(parents=True, exist_ok=True)
KIT = OUT / 'kit'
if KIT.exists():
    raise SystemExit('A+B kit already exists; inspect its measurement before starting another run.')
KIT.mkdir()
with zipfile.ZipFile(ROOT / 'build-the-builder-v3.zip') as z:
    for member in z.infolist():
        parts = Path(member.filename).parts
        relative = Path(*parts[1:])
        if not parts[1:] or member.is_dir():
            continue
        target = KIT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(z.read(member))
# Match the installed baseline entrypoint and restored skill, leaving root source untouched.
shutil.copy2(ROOT / 'examples/agent_builder.py', KIT / 'examples/agent_builder.py')
shutil.copytree(ROOT / '.claude', KIT / '.claude', dirs_exist_ok=True)
start = time.monotonic()
report = {'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'kit': str(KIT), 'entrypoint_sha256': hashlib.sha256((KIT / 'examples/agent_builder.py').read_bytes()).hexdigest()}
(OUT / 'measurement.json').write_text(json.dumps(report, indent=2))
env = dict(os.environ)
env['PATH'] = str(ROOT / '.venv/bin') + os.pathsep + env.get('PATH', '')
with (OUT / 'ab.log').open('w') as log:
    log.write('start ' + report['started_at'] + '\n'); log.flush()
    process = subprocess.Popen([sys.executable, '-u', str(KIT / 'examples/agent_builder.py'),
                                'briefs/brief-a.md', 'briefs/brief-b.md'], cwd=KIT, env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        report['exit_code'] = process.wait(timeout=1800)
    except subprocess.TimeoutExpired:
        process.terminate()
        report['exit_code'] = process.wait(timeout=30)
        report['timeout'] = True
    report['elapsed_seconds'] = round(time.monotonic() - start, 2)
    report['ended_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    log.write('\nexit ' + str(report['exit_code']) + ' elapsed ' + str(report['elapsed_seconds']) + ' s\n')
(OUT / 'measurement.json').write_text(json.dumps(report, indent=2))
for name in ('traces', 'results', 'out'):
    if (KIT / name).exists():
        shutil.copytree(KIT / name, OUT / name, dirs_exist_ok=True)
# Retain reviewable artifacts outside the ignored kit copy and scrub known keys.
for path in OUT.rglob('*'):
    if path.is_file() and KIT not in path.parents and path.suffix in ('.json', '.jsonl', '.log', '.py'):
        text = path.read_text()
        for key in ('FREYA_API_KEY', 'FREYA_BANK_TEAM_KEY', 'ANTHROPIC_API_KEY'):
            if os.environ.get(key):
                text = text.replace(os.environ[key], '[REDACTED]')
        path.write_text(text)
print(json.dumps(report, indent=2))
raise SystemExit(report['exit_code'])
