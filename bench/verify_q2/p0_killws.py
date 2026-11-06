"""WS 입력으로 G1 구동 중 humanoid worker kill -9. 사용: p0_killws.py URL SERVERPID 라벨 out.json WDW
순서: ON ready -> Windows sender(ws, 20s) 시작 -> T0+6s kill -9 worker -> 0.25s 간격 상태 12회 -> sender 종료 후 서버 생존/상태, 재ON, sender(ws,6s) 재실행으로 재개 확인"""
import sys, os, time, json, subprocess, http.client, urllib.parse
url=sys.argv[1]; PID=int(sys.argv[2]); LBL=sys.argv[3]; OUT=sys.argv[4]; WDW=sys.argv[5]; u=urllib.parse.urlparse(url)
def req(m,p,b=None):
    c=http.client.HTTPConnection(u.hostname,u.port,timeout=70); c.request(m,p,json.dumps(b) if b is not None else None,{"Content-Type":"application/json"}); r=c.getresponse(); d=r.read(); c.close()
    try: return r.status,json.loads(d)
    except Exception: return r.status,d[:80]
def kids(): return sorted(int(x) for x in subprocess.run(["pgrep","-P",str(PID)],capture_output=True,text=True).stdout.split())
def ready():
    dl=time.monotonic()+70
    while time.monotonic()<dl:
        if req("GET","/humanoid/status")[1].get("state")=="ready": return True
        time.sleep(.1)
    return False
def sender(tag,dur):
    cmd=["/mnt/c/Users/my/rp_vf/venv/Scripts/python.exe","-u",f"{WDW}\\sender_q2.py",url,str(dur),WDW,f"{WDW}\\{LBL}.{tag}.json","ws"]
    return subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
def fin(p):
    o,e=p.communicate(); ls=[l for l in o.splitlines() if l not in ("T0","END")]
    try: return json.loads(ls[-1])
    except Exception: return {"parse_fail":o[-300:],"err":e[-300:]}
res={"label":LBL,"load0":open("/proc/loadavg").read().split()[:3]}
before=kids(); res["mode_on"]=req("POST","/humanoid/mode",{"enabled":True})[0]; res["ready"]=ready(); time.sleep(1)
worker=sorted(set(kids())-set(before)); res["new_children_after_on"]=worker; res["children_all"]=kids()
w=worker[0] if worker else None
p=sender("a",20); t=time.monotonic()
for ln in p.stdout:
    if ln.strip()=="T0": break
time.sleep(6)
c0=req("GET","/humanoid/status")[1].get("input_count")
tk=time.monotonic(); os.kill(w,9)
seq=[]
for i in range(12):
    time.sleep(.25)
    try: s=req("GET","/humanoid/status")[1]; seq.append((round(time.monotonic()-tk,2),s.get("state"),s.get("enabled"),s.get("input_count")))
    except Exception as e: seq.append((round(time.monotonic()-tk,2),"exc",str(e)[:40]))
res["kill_w"]=w; res["input_count_before_kill"]=c0; res["status_after_kill"]=seq
res["sender_a"]=fin(p)
res["server_alive"]=os.path.exists(f"/proc/{PID}") and req("GET","/status")[0]==200
res["after_sender_a"]={k:req("GET","/humanoid/status")[1].get(k) for k in ("state","enabled","error")}
res["kids_after"]=kids()
res["reon"]=req("POST","/humanoid/mode",{"enabled":True})[0]; res["reon_ready"]=ready(); time.sleep(1)
n0=req("GET","/humanoid/status")[1].get("input_count"); p2=sender("b",6); res["sender_b"]=fin(p2)
n1=req("GET","/humanoid/status")[1]; res["input_count_resume"]=[n0,n1.get("input_count")]; res["state_end"]=n1.get("state")
req("POST","/humanoid/mode",{"enabled":False}); res["load1_end"]=open("/proc/loadavg").read().split()[:3]
json.dump(res,open(OUT,"w"),indent=1,default=str); print(json.dumps(res,indent=1,default=str))
