"""Measure the untouched sample agent; source .env before invoking.

python3 scripts/measure_baseline.py [--brief A|B] [--only PUB-01]
Uses one stable workflow slot and the official serial simulation harness.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import freya


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--brief', choices=['A', 'B'], default='A')
    parser.add_argument('--only')
    args = parser.parse_args()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = ROOT / 'results' / 'baseline' / stamp
    out.mkdir(parents=True)
    start = time.monotonic()
    report = {'started_at': stamp, 'brief': args.brief, 'only': args.only,
              'status': 'running', 'phases': {}}
    def save():
        report['elapsed_seconds'] = round(time.monotonic() - start, 3)
        (out / 'measurement.json').write_text(json.dumps(report, indent=2))
    def phase(name, fn):
        t = time.monotonic()
        report['active_phase'] = name
        save()
        result = fn()
        report['phases'][name] = round(time.monotonic() - t, 3)
        save()
        return result
    try:
        missing = [k for k in ('FREYA_API_KEY', 'FREYA_BANK_TEAM_KEY') if not os.environ.get(k)]
        if missing:
            raise RuntimeError('Missing environment variables: ' + ', '.join(missing))
        workflow = json.loads((ROOT / 'examples/base-agent.json').read_text())
        phase('validate', lambda: freya.validate_workflow('baseline-base', workflow))
        ids = phase('publish', lambda: freya.save_workflow('baseline-base', workflow))
        report['ids'] = ids
        phase('checkpoint_export', lambda: freya.export_workflow(ids['workflow_id'], str(out / 'base.workflow.json')))
        command = [sys.executable, '-u', str(ROOT / 'tools/run_cases.py'), ids['agent_id'],
                   '--brief', args.brief, '--out', str(out / 'scores.json')]
        if args.only:
            command += ['--only', args.only]
        # Wait for the official harness; never launch a second simulation concurrently.
        with (out / 'simulation.log').open('w') as log:
            phase('simulation', lambda: subprocess.run(command, cwd=ROOT, stdout=log,
                                                       stderr=subprocess.STDOUT, check=True))
        scores = json.loads((out / 'scores.json').read_text())
        report['passed'] = scores['passed']
        report['total'] = scores['total']
        calls = {}
        for row in scores['rows']:
            if row.get('call_id'):
                calls[row['id']] = freya.get_call(row['call_id'])
        # Tool traces may contain credential-bearing request metadata. Redact known secrets.
        content = json.dumps(calls, indent=2)
        for key in ('FREYA_API_KEY', 'FREYA_BANK_TEAM_KEY'):
            secret = os.environ.get(key)
            if secret:
                content = content.replace(secret, '[REDACTED]')
        (out / 'calls.json').write_text(content)
        phase('final_export', lambda: freya.export_workflow(ids['workflow_id'], str(out / 'base.workflow.json')))
        report['status'] = 'completed'
    except Exception as exc:
        message = str(exc)
        for key in ('FREYA_API_KEY', 'FREYA_BANK_TEAM_KEY'):
            if os.environ.get(key):
                message = message.replace(os.environ[key], '[REDACTED]')
        report['status'] = 'failed'
        report['error'] = type(exc).__name__ + ': ' + message
    finally:
        report['ended_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save()
        print(json.dumps(report, indent=2))
        print('Artifacts:', out)
    return 0 if report['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
