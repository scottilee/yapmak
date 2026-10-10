"""Bounded retry for reads and operations whose callers reconcile ambiguous writes."""
import urllib.error
import runcontrol
from trace import inherited_event


def retry(fn, what, trace=None, attempts=4, wait_s=20):
    if attempts < 1:
        raise ValueError('attempts must be positive')
    for attempt in range(1, attempts + 1):
        try:
            runcontrol.timeout(1)
            return fn()
        except (urllib.error.URLError, TimeoutError, RuntimeError) as error:
            status = getattr(error, 'status', None)
            transient = isinstance(error, (urllib.error.URLError, TimeoutError)) or (status is not None and (status >= 500 or status == 429))
            if isinstance(error, runcontrol.DeadlineExceeded) or not transient:
                raise
            emit = trace.event if trace else inherited_event
            emit('platform_retry', step=what, attempt=attempt, error=repr(error)[:300])
            if attempt == attempts:
                raise
            runcontrol.sleep(wait_s)
