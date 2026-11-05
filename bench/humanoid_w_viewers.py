import json,time,requests
from humanoid_w_idle import measure,BASE
idle=measure(6);t=time.monotonic();ts=[]
with requests.get(BASE+'/video',stream=True,timeout=5) as r:
 buf=b''
 for chunk in r.iter_content(4096):
  buf+=chunk
  while b'\xff\xd9' in buf:
   _,buf=buf.split(b'\xff\xd9',1);ts.append(time.monotonic())
  if ts and time.monotonic()-ts[0]>=31:break
chosen=[x for x in ts if ts[0]+1<=x<ts[0]+31]
time.sleep(3)
print(json.dumps({'idle_cpu_before_view_pct':idle,'first_frame_ms':(ts[0]-t)*1000,'frames30':len(chosen),'fps30':len(chosen)/30,'idle_cpu_after_view_pct':measure(6),'status_after':requests.get(BASE+'/status').json()},ensure_ascii=False),flush=True)