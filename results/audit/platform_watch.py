"""Minute health timeline; no simulations. Run with exported .env variables."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import signal
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / 'results/platform-watch-20261011.jsonl'


def emit(event, **values):
    with LOG.open('a') as f:
        f.write(json.dumps(dict(time=datetime.now(timezone.utc).isoformat(),
                               event=event, **values)) + '\n')
        f.flush()


def probe(service):
    start = time.monotonic()
    result = {'service': service, 'http_status': None, 'ok': False}
    key = 'FREYA_API_KEY' if service == 'freya' else 'FREYA_BANK_TEAM_KEY'
    if not os.environ.get(key):
        return dict(result, error='missing credential', duration_ms=0)
    if service == 'freya':
        url = os.environ.get('FREYA_API_URL', 'https://staging-app.freyavoice.ai').rstrip('/') + '/api/v2/workspaces'
        headers = {'Authorization': 'Bearer ' + os.environ[key],
                   'User-Agent': 'Mozilla/5.0 (build-the-builder)'}
        data = None
    else:
        url = 'https://freya-bank-mock.freyavoice.workers.dev/v1/practice/sessions'
        headers = {'x-team-key': os.environ[key], 'Content-Type': 'application/json',
                   'User-Agent': 'freya-bank-scorer/0.1'}
        data = b'{"case":"PUB-01"}'
    try:
        request = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(request, timeout=20) as response:
            result['http_status'] = response.status
            body = json.load(response)
            result['ok'] = 200 <= response.status < 300 and isinstance(body, (dict, list))
            if isinstance(body, dict) and (body.get('success') is False or body.get('error')):
                result['ok'] = False
            if not result['ok']:
                result['error'] = 'unsuccessful response'
    except urllib.error.HTTPError as e:
        result.update(http_status=e.code, error='HTTPError')
        # Read for transport cleanup, but never log response bodies or credentials.
        e.read()
    except Exception as e:
        result['error'] = type(e).__name__
    result['duration_ms'] = round((time.monotonic() - start) * 1000)
    return result


def sample(event='sample', scheduled=None):
    with ThreadPoolExecutor(max_workers=2) as pool:
        checks = list(pool.map(probe, ('freya', 'bank_mock')))
    emit(event, scheduled=scheduled, checks=checks, healthy=all(c['ok'] for c in checks))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    if args.once:
        sample('precheck')
        return
    lock = (ROOT / 'results/platform-watch-20261011.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    start = datetime(2026, 10, 11, 16, tzinfo=timezone.utc).timestamp()
    end = datetime(2026, 10, 11, 20, 5, tzinfo=timezone.utc).timestamp()
    emit('watch_scheduled', pid=os.getpid(), start_utc='2026-10-11T16:00:00Z',
         end_utc='2026-10-11T20:05:00Z', interval_seconds=60)
    (ROOT / 'results/platform-watch-20261011.pid').write_text(str(os.getpid()) + '\n')
    def stop(signum, frame):
        emit('watch_stopped', signal=signum)
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    tick = start
    while tick <= end:
        now = time.time()
        if now < tick:
            time.sleep(min(30, tick - now))
            continue
        if now > end:
            break
        sample(scheduled=datetime.fromtimestamp(tick, timezone.utc).isoformat())
        # Skip missed ticks after a stall, rather than sending a burst of probes.
        tick = max(tick + 60, start + (int((time.time() - start) // 60) + 1) * 60)
    emit('watch_finished')


if __name__ == '__main__':
    main()
