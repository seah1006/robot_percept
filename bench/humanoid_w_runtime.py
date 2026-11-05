"""Dedicated 5091 server benchmark; invoke under measurement flock."""
import json,time,threading,requests
from tools.humanoid_synth import payload
BASE='http://127.0.0.1:5091'
def post(path,data):
 r=requests.post(BASE+path,json=data,timeout=75);r.raise_for_status();return r.json()
def frames(stop,ts):
 with requests.get(BASE+'/humanoid/video',stream=True,timeout=3) as r:
  buf=b''
  for chunk in r.iter_content(4096):
   buf+=chunk
   while b'\xff\xd9' in buf:
    _,buf=buf.split(b'\xff\xd9',1);ts.append(time.monotonic())
    if stop.is_set():return
out={'cold':[]}
for i in range(3):
 t=time.monotonic();post('/humanoid/mode',{'enabled':True});ready=time.monotonic()
 ts=[];stop=threading.Event();th=threading.Thread(target=frames,args=(stop,ts),daemon=True);th.start();time.sleep(1.1);stop.set();th.join(3)
 out['cold'].append({'start_ready_ms':round((ready-t)*1000,2),'ready_first_ms':round((ts[0]-ready)*1000,2) if ts else None,'max_gap_ms':round(max([b-a for a,b in zip(ts,ts[1:])] or [0])*1000,2)})
 if i<2:
  post('/humanoid/mode',{'enabled':False});time.sleep(.3)
stop=threading.Event();ts=[];th=threading.Thread(target=frames,args=(stop,ts),daemon=True);th.start();t=time.monotonic();n=0
while time.monotonic()-t<35:
 p,_=payload((time.monotonic()-t)%20);post('/humanoid/update',p);n+=1;time.sleep(max(0,t+n/30-time.monotonic()))
stop.set();th.join(3);selected=[x for x in ts if t+5<=x<t+35]
out.update(frames30=len(selected),fps30=len(selected)/30,input_count=n,status=requests.get(BASE+'/humanoid/status').json())
bad,_=payload(0);bad['pose'][0]=bad['pose'][0][:3]
out['bad_http']=requests.post(BASE+'/humanoid/update',json=bad).status_code
out['alive_after_bad']=requests.get(BASE+'/humanoid/status').json()['state']
post('/humanoid/mode',{'enabled':False});out['off']=requests.get(BASE+'/humanoid/status').json()['enabled']
print(json.dumps(out,ensure_ascii=False))