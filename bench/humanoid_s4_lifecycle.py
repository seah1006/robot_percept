import json, os, signal, subprocess, sys, time, urllib.request
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"bench/shutdown_probe/out"; OUT.mkdir(parents=True,exist_ok=True)
PORT=5093

def info(pid):
    try:
        raw=Path(f"/proc/{pid}/stat").read_text(); tail=raw.rsplit(")",1)[1].split()
        cmd=Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0",b" ").decode(errors="replace")
        return {"pid":pid,"ppid":int(tail[1]),"state":tail[0],"cmd":cmd}
    except (FileNotFoundError,ProcessLookupError,PermissionError): return None

def alive(pid):
    row=info(pid); return row if row and row["state"]!="Z" else None

def descendants(root):
    rows={}
    for p in os.listdir("/proc"):
        if p.isdigit():
            row=info(int(p))
            if row: rows[row["pid"]]=row
    found=[]; frontier=[root]
    while frontier:
        parent=frontier.pop(0)
        kids=[r for r in rows.values() if r["ppid"]==parent and r not in found]
        found.extend(kids); frontier.extend(r["pid"] for r in kids)
    return found

def request(method,path,body=None,timeout=70):
    data=None if body is None else json.dumps(body).encode()
    req=urllib.request.Request(f"http://127.0.0.1:{PORT}{path}",data=data,method=method,headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=timeout) as response:return response.status,json.loads(response.read())

def wait_server(proc):
    end=time.monotonic()+40
    while time.monotonic()<end:
        if proc.poll() is not None: raise RuntimeError(f"server exited rc={proc.returncode}")
        try: request("GET","/humanoid/status",timeout=.4);return
        except Exception:time.sleep(.05)
    raise TimeoutError("server readiness")

def wait_g1():
    status,payload=request("POST","/humanoid/mode",{"enabled":True})
    if status!=200:raise RuntimeError(payload)
    end=time.monotonic()+70
    while time.monotonic()<end:
        _,payload=request("GET","/humanoid/status",timeout=2)
        if payload.get("state")=="ready":return payload
        time.sleep(.05)
    raise TimeoutError("g1 readiness")

from tools import humanoid_synth as hs
OUT=ROOT/'bench/humanoid_s4_out';OUT.mkdir(exist_ok=True)

def plans(root):
 return [x for x in descendants(root) if '--planner-fd' in x['cmd'] and x['state']!='Z']
def wait_planner(proc):
 end=time.monotonic()+10
 while time.monotonic()<end:
  found=plans(proc.pid)
  if found:return found
  time.sleep(.05)
 raise TimeoutError('planner start')
def new_server(tag):
 import socket
 with socket.socket() as probe:
  assert probe.connect_ex(('127.0.0.1',PORT))!=0,'5093 already in use; do not touch listener'
 env=dict(os.environ,PORT=str(PORT),HOST='127.0.0.1',PERCEPTION='stub',RP_PERCEPTION_WARMUP='0',PYTHONPATH=str(ROOT))
 log=(OUT/f'life_{tag}.log').open('wb')
 proc=subprocess.Popen([sys.executable,'-m','web.app'],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 try:
  wait_server(proc);wait_g1();request('POST','/humanoid/options',{'collision_avoidance':True})
  p,_=hs.payload(0);request('POST','/humanoid/update',p);wait_planner(proc)
  return proc,log
 except Exception:
  children=descendants(proc.pid)
  if proc.poll() is None:proc.terminate()
  try:proc.wait(timeout=7)
  except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=2)
  for x in children:
   if alive(x['pid']):os.kill(x['pid'],signal.SIGKILL)
  log.close();raise
rows=[]
for sig in (signal.SIGTERM,signal.SIGKILL):
 for i in range(2):
  baseline_shm=set(Path('/dev/shm').glob('psm_*'))
  proc,log=new_server(f'{sig.name}_{i}');children=descendants(proc.pid);shm=set(Path('/dev/shm').glob('psm_*'));t0=time.monotonic()
  try:
   os.kill(proc.pid,sig);proc.wait(timeout=7)
   while time.monotonic()-t0<7 and any(alive(x['pid']) for x in children):time.sleep(.02)
   left=[x for x in children if alive(x['pid'])]
   rows.append(dict(signal=sig.name,children=len(children),planners=sum('--planner-fd' in x['cmd'] for x in children),remaining=left,new_shm_remaining=[str(p) for p in set(Path('/dev/shm').glob('psm_*'))-baseline_shm],elapsed_s=time.monotonic()-t0))
   print(json.dumps(rows[-1]),flush=True)
  finally:
   if proc.poll() is None:proc.kill();proc.wait(timeout=3)
   for x in children:
    if alive(x['pid']):os.kill(x['pid'],signal.SIGKILL)
   log.close()
  (OUT/'lifecycle.json').write_text(json.dumps({'signals':rows},indent=2))
proc,log=new_server('toggle');toggles=[]
try:
 for i in range(10):
  before=plans(proc.pid);request('POST','/humanoid/options',{'collision_avoidance':False});end=time.monotonic()+5
  while time.monotonic()<end and plans(proc.pid):time.sleep(.02)
  off=plans(proc.pid);request('POST','/humanoid/options',{'collision_avoidance':True});p,_=hs.payload(0);request('POST','/humanoid/update',p);on=wait_planner(proc)
  row=dict(iteration=i,off_count=len(off),on_count=len(on));toggles.append(row);print(json.dumps(row),flush=True)
 # full mode cycles (3), collision option persists across worker restart.
 modes=[]
 for i in range(3):
  captured=descendants(proc.pid);request('POST','/humanoid/mode',{'enabled':False});time.sleep(.3)
  left=[x for x in captured if '--planner-fd' in x['cmd'] and alive(x['pid'])]
  wait_g1();request('POST','/humanoid/options',{'collision_avoidance':True});on=wait_planner(proc)
  modes.append(dict(iteration=i,old_planners_remaining=len(left),new_planners=len(on)))
 (OUT/'lifecycle.json').write_text(json.dumps(dict(signals=rows,collision_toggles=toggles,mode_toggles=modes),indent=2))
finally:
 children=descendants(proc.pid)
 if proc.poll() is None:proc.terminate();proc.wait(timeout=8)
 for x in children:
  if alive(x['pid']):os.kill(x['pid'],signal.SIGKILL)
 log.close()
