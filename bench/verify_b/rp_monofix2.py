from pathlib import Path


def rep(path, old, new):
    p = Path(path); s = p.read_text()
    if old not in s: raise SystemExit(f"missing in {path}: {old[:100]!r}")
    p.write_text(s.replace(old, new))

p=Path('web/app.py');s=p.read_text()
marker='from werkzeug.utils import secure_filename\n'
if 'from .monowait import' not in s:s=s.replace(marker,marker+'from .monowait import sleep_until, wait_for, join_thread\n')
p.write_text(s)
rep('web/app.py','if thread is not None:thread.join(timeout=3)','if thread is not None:join_thread(thread,3)')
rep('web/app.py','''  end=time.time()+timeout
  while time.time()<end:
   last=dict(self.status).get("last_command")
   if last and last.get("id")==cid: return last
   time.sleep(.05)''','''  end=time.monotonic()+timeout
  while time.monotonic()<end:
   last=dict(self.status).get("last_command")
   if last and last.get("id")==cid: return last
   sleep_until(min(end,time.monotonic()+.05))''')
rep('web/app.py',''' def cached_video(show_gt,last_seq=None):
  with video_condition:
   video_access[show_gt]=time.monotonic()
   if show_gt not in video_threads:
    video_threads.add(show_gt);threading.Thread(target=produce_video,args=(show_gt,),daemon=True).start()
   video_condition.wait_for(lambda:show_gt in video_cache and video_cache[show_gt][0]!=last_seq,timeout=2)
   return video_cache.get(show_gt)''',''' def cached_video(show_gt,last_seq=None):
  with video_condition:
   video_access[show_gt]=time.monotonic()
   if show_gt not in video_threads:
    video_threads.add(show_gt);threading.Thread(target=produce_video,args=(show_gt,),daemon=True).start()
  wait_for(lambda: show_gt in video_cache and video_cache[show_gt][0] != last_seq, 2, slice_s=.005)
  with video_condition:
   return video_cache.get(show_gt)''')

p=Path('web/teleop.py');s=p.read_text()
if 'from .monowait import wait_for' not in s:s=s.replace('from flask import Blueprint,request,jsonify,Response\n','from flask import Blueprint,request,jsonify,Response\nfrom .monowait import wait_for\n')
p.write_text(s)
rep('web/teleop.py','''    with mutex:
     mutex.wait_for(lambda:preview['seq']!=seq,timeout=2)
     raw=preview['jpeg'];next_seq=preview['seq']''','''    wait_for(lambda: preview['seq'] != seq, 2, slice_s=.005)
    with mutex:
     raw=preview['jpeg'];next_seq=preview['seq']''')

p=Path('web/perception_stub.py');s=p.read_text()
if 'from .monowait import sleep_until' not in s:
    marker='import numpy as np\n';s=s.replace(marker,marker+'from .monowait import sleep_until\n')
p.write_text(s)
rep('web/perception_stub.py','''                    try:
                        rid,ok,payload=self.res_q.get(timeout=min(.1, max(.001, deadline-time.monotonic())))
                    except queue.Empty:
                        if time.monotonic() >= deadline:
                            raise TimeoutError('Perception RPC timed out')
                        continue''','''                    try:
                        rid,ok,payload=self.res_q.get_nowait()
                    except queue.Empty:
                        if time.monotonic() >= deadline:
                            raise TimeoutError('Perception RPC timed out')
                        sleep_until(min(deadline, time.monotonic() + .01), self.warmup_cancel if is_warmup else None)
                        continue''')
