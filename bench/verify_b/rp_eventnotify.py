from pathlib import Path
p=Path('web/app.py');s=p.read_text()
s=s.replace('video_condition=threading.Condition(); video_cache={}; video_threads=set(); video_consumers={}; video_access={}', 'video_condition=threading.Condition(); video_cache={}; video_threads=set(); video_consumers={}; video_access={}; video_events={}')
s=s.replace("     video_cache[show_gt]=(seq,jpg.tobytes());video_condition.notify_all()", "     video_cache[show_gt]=(seq,jpg.tobytes());video_condition.notify_all()\n     video_events.setdefault(show_gt,threading.Event()).set()")
s=s.replace(''' def cached_video(show_gt,last_seq=None):
  with video_condition:
   video_access[show_gt]=time.monotonic()
   if show_gt not in video_threads:
    video_threads.add(show_gt);threading.Thread(target=produce_video,args=(show_gt,),daemon=True).start()
  wait_for(lambda: show_gt in video_cache and video_cache[show_gt][0] != last_seq, 2, slice_s=.01)
  with video_condition:
   return video_cache.get(show_gt)''',''' def cached_video(show_gt,last_seq=None,timeout=2):
  with video_condition:
   video_access[show_gt]=time.monotonic()
   event=video_events.setdefault(show_gt,threading.Event())
   if show_gt not in video_threads:
    video_threads.add(show_gt);threading.Thread(target=produce_video,args=(show_gt,),daemon=True).start()
  if timeout is None:
   while True:
    with video_condition:
     item=video_cache.get(show_gt)
     if item is not None and item[0]!=last_seq:return item
     event.clear()
    event.wait()  # untimed lock wait: notify-driven and not sem_timedwait
  wait_for(lambda: show_gt in video_cache and video_cache[show_gt][0] != last_seq, timeout, slice_s=.01)
  with video_condition:return video_cache.get(show_gt)''')
s=s.replace('item=cached_video(show_gt,last_seq)', 'item=cached_video(show_gt,last_seq,timeout=None)')
p.write_text(s)

p=Path('web/teleop.py');s=p.read_text()
s=s.replace("bp=Blueprint('teleop',__name__); st=runtime.status; preview={'jpeg':None,'seq':0}; mutex=threading.Condition();", "bp=Blueprint('teleop',__name__); st=runtime.status; preview={'jpeg':None,'seq':0}; mutex=threading.Condition(); preview_event=threading.Event();")
s=s.replace("preview['jpeg']=raw;preview['seq']+=1;preview_times.append(time.monotonic());mutex.notify_all()", "preview['jpeg']=raw;preview['seq']+=1;preview_times.append(time.monotonic());mutex.notify_all();preview_event.set()")
s=s.replace('''    wait_for(lambda: preview['seq'] != seq, 2, slice_s=.01)
    with mutex:
     raw=preview['jpeg'];next_seq=preview['seq']''','''    while True:
     with mutex:
      raw=preview['jpeg'];next_seq=preview['seq']
      if next_seq!=seq:break
      preview_event.clear()
     preview_event.wait()  # untimed notify-driven wait, immune to realtime steps''')
p.write_text(s)
