import json, os, signal, subprocess, sys, time, urllib.request
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/"bench/shutdown_probe/out"; OUT.mkdir(parents=True,exist_ok=True)
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

rows=[]
for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGKILL):
    for run in range(1,11):
        env=os.environ.copy();env.update(PORT=str(PORT),HOST="127.0.0.1",PERCEPTION="stub",RP_PERCEPTION_WARMUP="0",PYTHONPATH=str(ROOT))
        log_path=OUT/f"current_{sig.name}_{run}.log"
        with log_path.open("wb") as log:
            proc=subprocess.Popen([sys.executable,"-m","web.app"],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            captured=[]
            try:
                wait_server(proc);g1=wait_g1();time.sleep(.2);captured=descendants(proc.pid)
                t0=time.monotonic();os.kill(proc.pid,sig)
                try:proc.wait(timeout=7)
                except subprocess.TimeoutExpired:pass
                deadline=t0+7
                while time.monotonic()<deadline and (alive(proc.pid) or any(alive(r["pid"]) for r in captured)):time.sleep(.01)
                elapsed=time.monotonic()-t0;remaining=[alive(r["pid"]) for r in captured];remaining=[r for r in remaining if r]
                row={"signal":sig.name,"run":run,"elapsed_s":round(elapsed,4),"children":captured,"child_count":len(captured),"remaining":remaining,"remaining_count":len(remaining),"parent_alive":bool(alive(proc.pid)),"g1_fps":g1.get("fps")}
                rows.append(row);print(json.dumps({k:v for k,v in row.items() if k!="children"},ensure_ascii=False),flush=True)
            finally:
                if proc.poll() is None:
                    proc.kill();proc.wait(timeout=3)
                for row in reversed(captured):
                    if alive(row["pid"]):
                        try:os.kill(row["pid"],signal.SIGKILL)
                        except ProcessLookupError:pass
                time.sleep(.15)
summary={"rows":rows,"by_signal":{}}
for sig in ("SIGTERM","SIGINT","SIGKILL"):
    group=[r for r in rows if r["signal"]==sig]
    summary["by_signal"][sig]={"runs":len(group),"remaining_total":sum(r["remaining_count"] for r in group),"max_remaining":max(r["remaining_count"] for r in group),"elapsed_p50_s":round(float(np.percentile([r["elapsed_s"] for r in group],50)),4),"elapsed_p95_s":round(float(np.percentile([r["elapsed_s"] for r in group],95)),4),"elapsed_max_s":max(r["elapsed_s"] for r in group),"child_counts":sorted(set(r["child_count"] for r in group))}
(OUT/"signals_current.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print(json.dumps(summary["by_signal"],ensure_ascii=False,indent=2))
