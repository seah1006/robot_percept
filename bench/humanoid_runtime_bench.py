"""GT-assisted input + exact MJPEG arrival intervals. Run inside WSL conda env."""
import argparse,json,time,urllib.request,threading,subprocess,sys,os,numpy as np
from web.monowait import wait_event, join_thread
p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:5091');p.add_argument('--seconds',type=float,default=33.5);a=p.parse_args()
def get():return json.load(urllib.request.urlopen(a.url+'/humanoid/status',timeout=5))
def mode(enabled):return urllib.request.urlopen(urllib.request.Request(a.url+'/humanoid/mode',data=json.dumps({'enabled':enabled}).encode(),headers={'Content-Type':'application/json'}),timeout=15).read()
mode(False);mode(True)
for _ in range(120):
 s=get()
 if s.get('state')=='ready':break
 if s.get('state')=='crashed':raise RuntimeError(s)
 time.sleep(.5)
rows=[];stop=threading.Event()
def poll():
 while not wait_event(stop,1):
  try:rows.append(get())
  except Exception:pass
sender=subprocess.Popen([sys.executable,'tools/humanoid_synth.py','--url',a.url,'--seconds',str(a.seconds+2)])
t=threading.Thread(target=poll,daemon=True);t.start();arrivals=[];buf=b'';start=time.monotonic();load0=os.getloadavg()
with urllib.request.urlopen(a.url+'/humanoid/video',timeout=5) as response:
 while time.monotonic()-start<a.seconds:
  buf+=response.read1(65536)
  while True:
   end=buf.find(b'\xff\xd9')
   if end<0:break
   now=time.monotonic();buf=buf[end+2:]
   if now-start<=a.seconds:arrivals.append(now)
stop.set();join_thread(t,6);sender.wait()
def metrics(key):
 v=[s[key] for s in rows if isinstance(s.get(key),(float,int))]
 return {k:round(float(np.percentile(v,n)),3) for k,n in [('p50',50),('p95',95)]} if v else None
print(json.dumps({'GT_assisted':True,'window_s':a.seconds,'frames':len(arrivals),'arrival_span_s':arrivals[-1]-arrivals[0] if len(arrivals)>1 else 0,'fps':(len(arrivals)-1)/(arrivals[-1]-arrivals[0]) if len(arrivals)>1 else 0,'max_gap_ms':max(np.diff(arrivals))*1000 if len(arrivals)>1 else 0,'load_start':load0,'load_end':os.getloadavg(),'status':{k:metrics(k) for k in ['fps','tick_hz','rtf','render_ms','jpeg_ms','snapshot_ms','ik_ms_p95','tick_ms_p95','input_hz']}}),flush=True)
