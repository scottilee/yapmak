"""Shared monotonic build budget, inherited by subprocesses on this machine."""
import contextlib
import os
import signal
import subprocess
import time

DEADLINE_ENV = 'FREYA_BUILD_DEADLINE_MONOTONIC'


class DeadlineExceeded(TimeoutError):
    pass


def remaining():
    value = os.environ.get(DEADLINE_ENV)
    return max(0.0, float(value) - time.monotonic()) if value else float('inf')


def timeout(cap):
    seconds = min(float(cap), remaining())
    if seconds <= 0:
        raise DeadlineExceeded('build deadline exceeded')
    return seconds


def sleep(seconds):
    time.sleep(timeout(seconds))
    timeout(1)


@contextlib.contextmanager
def deadline(seconds):
    """Cap even a stalled socket/SDK at the wall-clock deadline on POSIX main threads."""
    previous = os.environ.get(DEADLINE_ENV)
    end = min(time.monotonic() + seconds, float(previous) if previous else float('inf'))
    os.environ[DEADLINE_ENV] = str(end)
    old_handler = signal.getsignal(signal.SIGALRM)
    old_timer = signal.getitimer(signal.ITIMER_REAL)
    started = time.monotonic()
    def expired(signum, frame):
        raise DeadlineExceeded('build deadline exceeded')
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, max(0.001, end - time.monotonic()))
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
        if old_timer[0]:
            signal.setitimer(signal.ITIMER_REAL, max(0.001, old_timer[0] - (time.monotonic() - started)), old_timer[1])
        if previous is None:
            os.environ.pop(DEADLINE_ENV, None)
        else:
            os.environ[DEADLINE_ENV] = previous


def run(args, *, seconds, **kwargs):
    """Terminate the child's entire process group on timeout (not just its launcher)."""
    budget = timeout(seconds)
    with subprocess.Popen(args, start_new_session=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, **kwargs) as child:
        try:
            stdout, stderr = child.communicate(timeout=budget)
        except BaseException:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.communicate()
            raise
        return subprocess.CompletedProcess(args, child.returncode, stdout, stderr)
