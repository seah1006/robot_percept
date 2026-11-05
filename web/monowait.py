"""CLOCK_REALTIME-step-safe waits for threads and polling loops."""
from __future__ import annotations

import time

DEFAULT_SLICE_S = .005


def wait_until(stop_event, deadline_monotonic, slice_s=DEFAULT_SLICE_S):
    """Return True when *stop_event* is set, False at the monotonic deadline."""
    quantum = max(.0005, min(float(slice_s), .01))
    while not stop_event.is_set():
        remaining = deadline_monotonic - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(remaining, quantum))
    return True


def wait_event(event, timeout, slice_s=DEFAULT_SLICE_S):
    return wait_until(event, time.monotonic() + max(0., float(timeout)), slice_s)


def sleep_until(deadline_monotonic, stop_event=None, slice_s=DEFAULT_SLICE_S):
    """Sleep to a monotonic deadline; return False if cancelled first."""
    quantum = max(.0005, min(float(slice_s), .01))
    while True:
        if stop_event is not None and stop_event.is_set():
            return False
        remaining = deadline_monotonic - time.monotonic()
        if remaining <= 0:
            return True
        time.sleep(min(remaining, quantum))


def wait_for(predicate, timeout, slice_s=DEFAULT_SLICE_S, stop_event=None):
    """Poll a cheap predicate without Condition/Lock timed waits."""
    deadline = time.monotonic() + max(0., float(timeout))
    quantum = max(.0005, min(float(slice_s), .01))
    while True:
        if predicate():
            return True
        if stop_event is not None and stop_event.is_set():
            return False
        now = time.monotonic()
        if now >= deadline:
            return bool(predicate())
        if not sleep_until(min(deadline, now + quantum), stop_event, quantum):
            return False


def join_thread(thread, timeout, slice_s=DEFAULT_SLICE_S):
    """Join a thread without threading.Lock.acquire(timeout)."""
    deadline = time.monotonic() + max(0., float(timeout))
    quantum = max(.0005, min(float(slice_s), .01))
    while thread.is_alive() and time.monotonic() < deadline:
        sleep_until(min(deadline, time.monotonic() + quantum), slice_s=quantum)
    if not thread.is_alive():
        thread.join(0)
        return True
    return False
