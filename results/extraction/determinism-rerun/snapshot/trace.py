"""Append-only builder trace shared by the parent and its subprocesses."""
from __future__ import annotations
import json
import os
import pathlib
import subprocess
import time
import uuid
import fcntl
from artifact_security import redact


def git_head(root):
    try:
        return subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return ''


def _scrub(o):
    if isinstance(o, str):
        return redact(o)
    if isinstance(o, dict):
        return {k: _scrub(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_scrub(v) for v in o]
    return o


def append_event(trace_path, trace_run_id, started, event_name, **fields):
    rec = dict(event=event_name, run_id=trace_run_id, pid=os.getpid(), time=time.strftime('%Y-%m-%dT%H:%M:%S%z'),
               elapsed_s=round(time.monotonic() - started, 3))
    rec.update(_scrub(fields))
    with open(trace_path, 'a', encoding='utf-8') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(rec, default=str) + '\n')
        f.flush()
    return rec


def inherited_event(event_name, **fields):
    """HTTP clients in child processes append to the same run, without archiving it."""
    path = os.environ.get('FREYA_TRACE_PATH')
    if path:
        return append_event(path, os.environ['FREYA_RUN_ID'], float(os.environ['FREYA_TRACE_STARTED']), event_name, **fields)


class Trace:
    def __init__(self, path):
        self.path = pathlib.Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.run_id = uuid.uuid4().hex
        if self.path.exists() and self.path.stat().st_size:
            stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime(self.path.stat().st_mtime))
            self.path.rename(self.path.with_name(f'{self.path.stem}.{stamp}.{self.run_id[:8]}{self.path.suffix}'))
        self.path.touch()
        self.t0 = time.monotonic()
        values = dict(FREYA_TRACE_PATH=str(self.path), FREYA_RUN_ID=self.run_id, FREYA_TRACE_STARTED=str(self.t0))
        self.previous = {k: os.environ.get(k) for k in values}
        os.environ.update(values)

    def event(self, event_name, **fields):
        return append_event(self.path, self.run_id, self.t0, event_name, **fields)

    def close(self):
        for k, v in self.previous.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
