"""Builder trace: one JSONL line per event (plan §10). Plain, append-only, flushed on every write."""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import time


def git_head(root: pathlib.Path) -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return ""


class Trace:
    """One file per run. A previous trace for the same slot is archived next to it (`<slot>.<time>.jsonl`), so the
    submitted `traces/<slot>.jsonl` always holds exactly the run that produced `out/<slot>.workflow.json`."""

    def __init__(self, path: pathlib.Path):
        self.path = pathlib.Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists() and self.path.stat().st_size:
            stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(self.path.stat().st_mtime))
            self.path.rename(self.path.with_name(f"{self.path.stem}.{stamp}{self.path.suffix}"))
        self.t0 = time.monotonic()
        self.f = self.path.open("w", encoding="utf-8")

    def event(self, name: str, **fields):
        rec = {"event": name, "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "elapsed_s": round(time.monotonic() - self.t0, 1)}
        rec.update(_scrub(fields))
        self.f.write(json.dumps(rec, default=str) + "\n")
        self.f.flush()
        return rec

    def close(self):
        self.f.close()


_SECRETS = [v for k, v in os.environ.items() if k in ("FREYA_API_KEY", "FREYA_BANK_TEAM_KEY", "ANTHROPIC_API_KEY") and v]


def _scrub(o):
    if isinstance(o, str):
        for s in _SECRETS:
            o = o.replace(s, "[REDACTED]")
        return o
    if isinstance(o, dict):
        return {k: _scrub(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_scrub(v) for v in o]
    return o
