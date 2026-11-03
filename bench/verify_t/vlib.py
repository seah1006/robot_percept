import json,time,math,urllib.request,sys
import numpy as np
B='http://127.0.0.1:5090'
def req(path,data=None):
    r=urllib.request.Request(B+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'},method='GET' if data is None else 'POST')
    try:
        with urllib.request.urlopen(r,timeout=10) as f: return json.loads(f.read() or b'null')
    except urllib.error.HTTPError as e: return {'http':e.code,'body':e.read().decode()[:200]}
def st(): return req('/status')
def upd(x,y,s,p=0.8,det=True):
    d={'detected':det,'sent_at':time.time()}
    if det: d.update(x=x,y=y,scale=s,pinch=p)
    return req('/teleop/update',d)
def stream(fn,dur,hz=30,pinch=lambda t:0.8,rec=None):
    t0=time.time();n=0
    while True:
        t=time.time()-t0
        if t>dur:break
        x,y,s=fn(t); upd(x,y,s,pinch(t))
        if rec is not None:
            q=st(); rec.append((time.time(),t,(x,y,s),np.array(q['ee_pose']),np.array(q['arm_qpos']),q.get('teleop_target')))
        n+=1; time.sleep(max(0,t0+n/hz-time.time()))
    return n/dur