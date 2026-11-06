from pathlib import Path


def rep(path, old, new):
    p = Path(path)
    s = p.read_text()
    if old not in s:
        raise SystemExit(f"missing in {path}: {old[:80]!r}")
    p.write_text(s.replace(old, new))


Path("web/monowait.py").write_text('''"""CLOCK_REALTIME-step-safe waits for threads and polling loops."""
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
        thread.join()
        return True
    return False
''')

rep("web/shm_channel.py", "import struct, time, uuid\n", "import struct, time, uuid\nfrom .monowait import wait_event\n")
old_wait = '''\n\ndef wait_monotonic(event, timeout, quantum=.005):
    """Interruptible relative wait immune to CLOCK_REALTIME steps.

    Some Conda builds use sem_timedwait (not sem_clockwait) for Event.wait.
    time.sleep uses clock_nanosleep/CLOCK_MONOTONIC on our Linux runtime.
    """
    deadline = time.monotonic() + max(0., timeout)
    while not event.is_set():
        remaining = deadline - time.monotonic()
        if remaining <= 0: return False
        time.sleep(min(remaining, quantum))
    return True
'''
rep("web/shm_channel.py", old_wait, '''\n\ndef wait_monotonic(event, timeout, quantum=.005):
    """Backward-compatible alias; new code imports web.monowait directly."""
    return wait_event(event, timeout, quantum)
''')

rep("web/humanoid_worker.py", "from web.shm_channel import Blob, wait_monotonic", "from web.shm_channel import Blob\n    from web.monowait import wait_event, join_thread")
rep("web/humanoid_worker.py", "wait_monotonic(render_stop,max(0.,deadline-time.monotonic()))", "wait_event(render_stop,max(0.,deadline-time.monotonic()))")
rep("web/humanoid_worker.py", "if not wait_monotonic(render_ready,60):", "if not wait_event(render_ready,60):")
rep("web/humanoid_worker.py", "render_stop.set(); render_thread.join(timeout=5)", "render_stop.set(); join_thread(render_thread,5)")
rep("web/humanoid_worker.py", "if render_thread: render_thread.join(timeout=5)", "if render_thread: join_thread(render_thread,5)")

p = Path("web/app.py")
s = p.read_text()
marker = "from flask import Flask,request,jsonify,Response,send_from_directory\n"
if marker in s and "from .monowait import" not in s:
    s = s.replace(marker, marker + "from .monowait import sleep_until, wait_for, join_thread\n")
elif "from .monowait import" not in s:
    raise SystemExit("app import marker missing")
p.write_text(s)
rep("web/app.py", "if thread is not None:thread.join(timeout=3)", "if thread is not None:join_thread(thread,3)")
rep("web/app.py", '''  end=time.time()+timeout
  while time.time()<end:
   last=dict(self.status).get("last_command")
   if last and last.get("id")==cid: return last
   time.sleep(.05)''', '''  end=time.monotonic()+timeout
  while time.monotonic()<end:
   last=dict(self.status).get("last_command")
   if last and last.get("id")==cid: return last
   sleep_until(min(end,time.monotonic()+.05))''')
rep("web/app.py", ''' def cached_video(show_gt,last_seq=None):
  with video_condition:
   video_access[show_gt]=time.monotonic()
   if show_gt not in video_threads:
    video_threads.add(show_gt);threading.Thread(target=produce_video,args=(show_gt,),daemon=True).start()
   video_condition.wait_for(lambda:show_gt in video_cache and video_cache[show_gt][0]!=last_seq,timeout=2)
   return video_cache.get(show_gt)''', ''' def cached_video(show_gt,last_seq=None):
  with video_condition:
   video_access[show_gt]=time.monotonic()
   if show_gt not in video_threads:
    video_threads.add(show_gt);threading.Thread(target=produce_video,args=(show_gt,),daemon=True).start()
  wait_for(lambda: show_gt in video_cache and video_cache[show_gt][0] != last_seq, 2, slice_s=.005)
  with video_condition:
   return video_cache.get(show_gt)''')

p = Path("web/teleop.py")
s = p.read_text().replace("from flask import Blueprint,request,jsonify,Response\n", "from flask import Blueprint,request,jsonify,Response\nfrom .monowait import wait_for\n")
p.write_text(s)
rep("web/teleop.py", '''    with mutex:
     mutex.wait_for(lambda:preview['seq']!=seq,timeout=2)
     raw=preview['jpeg'];next_seq=preview['seq']''', '''    wait_for(lambda: preview['seq'] != seq, 2, slice_s=.005)
    with mutex:
     raw=preview['jpeg'];next_seq=preview['seq']''')

p = Path("web/perception_stub.py")
s = p.read_text()
if "from .monowait import sleep_until" not in s:
    lines = s.splitlines(True)
    idx = 0
    while idx < len(lines) and (lines[idx].startswith(("import ", "from ")) or not lines[idx].strip()):
        idx += 1
    lines.insert(idx, "from .monowait import sleep_until\n")
    s = ''.join(lines)
p.write_text(s)
rep("web/perception_stub.py", '''                    try:
                        rid,ok,payload=self.res_q.get(timeout=min(.1, max(.001, deadline-time.monotonic())))
                    except queue.Empty:
                        if time.monotonic() >= deadline:
                            raise TimeoutError('Perception RPC timed out')
                        continue''', '''                    try:
                        rid,ok,payload=self.res_q.get_nowait()
                    except queue.Empty:
                        if time.monotonic() >= deadline:
                            raise TimeoutError('Perception RPC timed out')
                        sleep_until(min(deadline, time.monotonic() + .01), self.warmup_cancel if is_warmup else None)
                        continue''')
