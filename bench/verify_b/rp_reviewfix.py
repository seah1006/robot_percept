from pathlib import Path
p=Path('web/perception_stub.py');s=p.read_text()
s=s.replace('from .monowait import sleep_until\n','')
s=s.replace('''                    try:
                        rid,ok,payload=self.res_q.get_nowait()
                    except queue.Empty:
                        if time.monotonic() >= deadline:
                            raise TimeoutError('Perception RPC timed out')
                        sleep_until(min(deadline, time.monotonic() + .01), self.warmup_cancel if is_warmup else None)
                        continue''','''                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError('Perception RPC timed out')
                    # Queue's timed semaphore lock is CLOCK_REALTIME-sensitive in this build;
                    # the reader Connection.poll path uses selectors + a monotonic deadline.
                    if not self.res_q._reader.poll(min(.1, remaining)):
                        continue
                    try:
                        rid,ok,payload=self.res_q.get_nowait()
                    except queue.Empty:
                        continue''')
s=s.replace('''            if proc is not None:
                proc.join(timeout=2)''','''            if proc is not None:
                # multiprocessing Process.join(timeout) uses connection.wait(selector + monotonic).
                proc.join(timeout=2)''')
p.write_text(s)

p=Path('web/humanoid.py');s=p.read_text()
s=s.replace('''            if proc is not None:
                proc.join(timeout=3)''','''            if proc is not None:
                # multiprocessing Process.join(timeout) uses connection.wait(selector + monotonic).
                proc.join(timeout=3)''')
p.write_text(s)

for name in ('web/app.py','web/teleop.py'):
 p=Path(name);s=p.read_text().replace('slice_s=.005','slice_s=.01');p.write_text(s)

p=Path('tests/test_monowait.py');s=p.read_text()
s=s.replace('''def test_wait_event_uses_monotonic_deadline(monkeypatch, wall_step):
    real_wall = time.time''','''def test_wait_event_uses_monotonic_deadline(monkeypatch, wall_step):
    # This is not a kernel CLOCK_REALTIME step: monkeypatch cannot reproduce the
    # old sem_timedwait failure. It only proves our deadline path ignores wall time;
    # integration runs record real WSL clock jumps with clock_probe_ts.py.
    real_wall = time.time''')
p.write_text(s)
