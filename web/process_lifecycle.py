"""Small process-lifecycle helpers shared by the web parent and spawn workers."""
from __future__ import annotations

import os
import threading
import time


def exit_if_parent_changed(expected_parent_pid):
    """Exit immediately when a spawned child starts after its parent died."""
    if expected_parent_pid is not None and os.getppid() != int(expected_parent_pid):
        os._exit(0)


def start_parent_pid_watch(expected_parent_pid, interval=.25):
    """Exit a child after its process parent disappears.

    PPID is process-scoped, unlike Linux PDEATHSIG which is tied to the thread
    that created the child.  The monotonic sleep loop wakes four times per
    second and is only needed by workers that can block indefinitely.
    """
    if expected_parent_pid is None:
        return None
    expected_parent_pid = int(expected_parent_pid)
    exit_if_parent_changed(expected_parent_pid)

    def watch():
        deadline = time.monotonic()
        while True:
            if os.getppid() != expected_parent_pid:
                os._exit(0)
            deadline += interval
            time.sleep(max(0., deadline - time.monotonic()))

    thread = threading.Thread(target=watch, name="parent-pid-watch", daemon=True)
    thread.start()
    return thread


def manager_parent_watch_initializer(expected_parent_pid):
    start_parent_pid_watch(expected_parent_pid)


def stop_process(proc, deadline, cooperative_seconds=3.0):
    """Reap a multiprocessing child by deadline: join, terminate, then kill."""
    if proc is None:
        return True

    def remaining():
        return max(0.0, deadline - time.monotonic())

    proc.join(timeout=min(cooperative_seconds, remaining()))
    if proc.is_alive() and remaining() > 0:
        proc.terminate()
        proc.join(timeout=min(1.0, remaining()))
    if proc.is_alive():
        try:
            proc.kill()
        except AttributeError:
            proc.terminate()
        proc.join(timeout=remaining())
    return not proc.is_alive()


def run_manager_watchdog(parent_pid, manager_pid, interval=.25):
    """Kill the Manager if the web parent vanishes, then exit."""
    parent_pid, manager_pid = int(parent_pid), int(manager_pid)
    deadline = time.monotonic()
    while os.getppid() == parent_pid:
        try:
            os.kill(manager_pid, 0)
        except ProcessLookupError:
            return
        deadline += interval
        time.sleep(max(0., deadline - time.monotonic()))
    try:
        os.kill(manager_pid, 15)
    except ProcessLookupError:
        return
    limit = time.monotonic() + 1.
    while time.monotonic() < limit:
        try:
            os.kill(manager_pid, 0)
        except ProcessLookupError:
            return
        time.sleep(.05)
    try:
        os.kill(manager_pid, 9)
    except ProcessLookupError:
        pass
