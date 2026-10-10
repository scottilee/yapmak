"""Run a declarative simulation batch with bounded waits and fresh per-attempt evidence.

    .venv/bin/python scripts/run_batch.py --config scripts/batches/batch_v17.json --dry-run

Agent IDs are read from the local slot registry. No IDs are hardcoded in the runner.
"""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import freya
import runcontrol
from trace import Trace, _scrub


def wait_for(predicate, seconds, label):
    try:
        with runcontrol.deadline(seconds):
            while not predicate():
                print(f'waiting: {label}', flush=True)
                runcontrol.sleep(30)
    except runcontrol.DeadlineExceeded as e:
        raise runcontrol.DeadlineExceeded(label + ' timed out') from e


def healthy():
    try:
        freya.api('GET', '/api/v2/workspaces')
        req = urllib.request.Request('https://freya-bank-mock.freyavoice.workers.dev/v1/practice/sessions',
            data=b'{"case":"PUB-01"}', headers={'Content-Type': 'application/json',
            'x-team-key': os.environ['FREYA_BANK_TEAM_KEY'], 'User-Agent': 'freya-bank-scorer/0.1'})
        with urllib.request.urlopen(req, timeout=runcontrol.timeout(20)) as response:
            return response.status == 200
    except runcontrol.DeadlineExceeded:
        raise
    except Exception:
        return False


def job_command(job, registry, output):
    return [sys.executable, '-u', str(ROOT / job.get('runner', 'tools/run_cases.py')),
            registry[job['slot']]['agent_id'], *job.get('args', []), '--out', str(output)]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config', required=True)
    ap.add_argument('--deadline', type=int, default=21600)
    ap.add_argument('--wait-seconds', type=int, default=3600)
    ap.add_argument('--health-seconds', type=int, default=600)
    ap.add_argument('--job-seconds', type=int, default=1800)
    ap.add_argument('--attempts', type=int, default=3)
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    if min(a.deadline, a.wait_seconds, a.health_seconds, a.job_seconds, a.attempts) <= 0:
        ap.error('budgets and attempts must be positive')
    config = json.loads(Path(a.config).read_text())
    if a.dry_run:
        print(json.dumps(config, indent=2))
        return
    with runcontrol.deadline(a.deadline):
        tr = Trace(ROOT / 'traces' / ('batch-' + Path(a.config).stem + '.jsonl'))
        failed = []
        try:
            tr.event('batch_start', config=a.config, deadline_s=a.deadline)
            wait = config.get('wait_for')
            if wait:
                path = ROOT / wait['path']
                wait_for(lambda: path.exists() and re.search(wait['pattern'], path.read_text(), re.M), a.wait_seconds, 'predecessor')
            wait_for(healthy, a.health_seconds, 'platform and bank')
            for publish in config.get('publish', []):
                result = runcontrol.run([sys.executable, str(ROOT / 'scripts/publish_check.py'), publish['slot'],
                                         publish['path'], '--no-chat'], seconds=a.job_seconds, cwd=ROOT)
                print(_scrub(result.stdout + result.stderr), flush=True)
                if result.returncode:
                    raise RuntimeError('publication failed; batch stopped')
            registry = json.loads((ROOT / '.freya-agents.json').read_text())
            for job in config['jobs']:
                output = ROOT / 'results/gen' / (job['output'] + '.json')
                output.parent.mkdir(parents=True, exist_ok=True)
                success = False
                for attempt in range(1, a.attempts + 1):
                    wait_for(healthy, a.health_seconds, 'platform and bank')
                    evidence = output.with_name(f'{output.stem}.{tr.run_id}.{attempt}.json')
                    print(f"start {job['name']} attempt {attempt}", flush=True)
                    try:
                        result = runcontrol.run(job_command(job, registry, evidence), seconds=a.job_seconds, cwd=ROOT)
                        evidence.with_suffix('.log').write_text(_scrub(result.stdout + result.stderr))
                        success = result.returncode == 0 and evidence.exists()
                        if success:
                            freya.atomic_json(output, json.loads(evidence.read_text()))
                        tr.event('batch_job', name=job['name'], attempt=attempt, exit_code=result.returncode,
                                 success=success, result_path=str(evidence))
                    except runcontrol.DeadlineExceeded:
                        raise
                    except Exception as e:
                        tr.event('batch_job', name=job['name'], attempt=attempt, success=False, error=repr(e))
                    if success:
                        break
                    if attempt < a.attempts:
                        runcontrol.sleep(30)
                print(f"exit {job['name']} {0 if success else 1}", flush=True)
                if not success:
                    failed.append(job['name'])
            tr.event('batch_end', success=not failed, failed=failed)
        except BaseException as e:
            tr.event('batch_end', success=False, error=repr(e))
            raise
        finally:
            tr.close()
        if failed:
            raise SystemExit(1)


if __name__ == '__main__':
    main()
