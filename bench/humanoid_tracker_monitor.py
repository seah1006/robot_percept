"""Monitor server-accepted tracker rates after startup; no synthetic tracker data."""
import argparse,json,time,urllib.request,numpy as np,os
p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:5091');p.add_argument('--seconds',type=float,default=25);a=p.parse_args()
def get(path):return json.load(urllib.request.urlopen(a.url+path,timeout=5))
for _ in range(120):
 try:
  urllib.request.urlopen(urllib.request.Request(a.url+'/humanoid/mode',data=b'{"enabled":true}',headers={'Content-Type':'application/json'}),timeout=20).read();break
 except Exception:time.sleep(.5)
for _ in range(120):
 h=get('/humanoid/status')
 if h.get('human_detected'):break
 time.sleep(.5)
else:raise RuntimeError('no real tracker input')
time.sleep(2);start=time.monotonic();rows=[];load0=os.getloadavg()
while time.monotonic()-start<a.seconds:
 h=get('/humanoid/status');t=get('/teleop/status');rows.append(dict(input_hz=h.get('input_hz',0),preview_hz=t.get('preview_hz',0),robot_fps=h.get('fps',0),fresh=h.get('human_detected',False),panda_paused=get('/status').get('humanoid_render_paused',False)));time.sleep(.5)
print(json.dumps({'samples':len(rows),'seconds':time.monotonic()-start,'load_start':load0,'load_end':os.getloadavg(),'fresh_samples':sum(r['fresh'] for r in rows),'panda_paused_samples':sum(r['panda_paused'] for r in rows),**{key:{'p50':float(np.median([r[key] for r in rows])),'p95':float(np.percentile([r[key] for r in rows],95)),'min':min(r[key] for r in rows)} for key in ['input_hz','preview_hz','robot_fps']}}),flush=True)
