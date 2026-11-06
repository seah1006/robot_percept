import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.request

import pytest


def _proc_info(pid):
    try:
        tail = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return {"pid": pid, "ppid": int(tail[1]), "state": tail[0]}
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None


def _descendants(root):
    rows = {}
    for entry in Path("/proc").iterdir():
        if entry.name.isdigit():
            info = _proc_info(int(entry.name))
            if info:
                rows[info["pid"]] = info
    found, frontier = [], [root]
    while frontier:
        parent = frontier.pop(0)
        children = [row for row in rows.values() if row["ppid"] == parent and row not in found]
        found.extend(children)
        frontier.extend(row["pid"] for row in children)
    return found


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_ready(port, proc):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise AssertionError(f"server exited early: {proc.returncode}")
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/status", timeout=.3).read()
            return
        except OSError:
            time.sleep(.05)
    raise AssertionError("server readiness timeout")


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT, signal.SIGKILL])
def test_server_signal_reaps_spawn_children(sig, tmp_path):
    port = _free_port()
    env = os.environ.copy()
    env.update(PORT=str(port), HOST="127.0.0.1", PERCEPTION="stub", RP_PERCEPTION_WARMUP="0")
    log_path = tmp_path / f"server-{sig.name}.log"
    with log_path.open("wb") as log:
        proc = subprocess.Popen(
            [sys.executable, "-m", "web.app"], cwd=Path(__file__).parents[1], env=env,
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
        )
        captured = []
        try:
            _wait_ready(port, proc)
            captured = _descendants(proc.pid)
            assert captured, "expected multiprocessing children"
            os.kill(proc.pid, sig)
            proc.wait(timeout=7)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and any(_proc_info(row["pid"]) for row in captured):
                time.sleep(.05)
            alive = [_proc_info(row["pid"]) for row in captured]
            assert not [row for row in alive if row is not None], log_path.read_text(errors="replace")
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=3)
            for row in reversed(captured):
                if _proc_info(row["pid"]):
                    try:
                        os.kill(row["pid"], signal.SIGKILL)
                    except ProcessLookupError:
                        pass


def _pid_watched_child(expected_parent_pid, ready):
    from web.process_lifecycle import start_parent_pid_watch
    start_parent_pid_watch(expected_parent_pid)
    ready.set()
    while True:
        time.sleep(.1)


def test_parent_watch_is_independent_of_spawning_thread():
    import multiprocessing as mp
    import threading

    ctx = mp.get_context("spawn")
    ready = ctx.Event()
    holder = {}

    def spawn_from_short_lived_thread():
        child = ctx.Process(target=_pid_watched_child, args=(os.getpid(), ready), daemon=True)
        child.start()
        holder["child"] = child

    starter = threading.Thread(target=spawn_from_short_lived_thread)
    starter.start(); starter.join(timeout=3)
    child = holder["child"]
    try:
        assert ready.wait(3)
        time.sleep(.5)
        assert child.is_alive(), "worker must outlive the thread that called Process.start"
    finally:
        if child.is_alive():
            child.terminate(); child.join(timeout=2)
