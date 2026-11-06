"""G1 30초 창(V-Q2): Windows py 트래커(update=WS /tracker/ws 또는 HTTP, preview=HTTP) 30Hz + status/ws push 1(또는 폴링 3) + MJPEG 2 시청.
사용: q2_win.py URL SERVERPID 라벨 출력.json WD_L WD_W transport(ws|http) status(push|poll)
프레임 개수 fps는 sender가 출력하는 T0~END 구간(WSL monotonic으로 스탬프)에서 /humanoid/video JPEG 개수로 계산."""
import sys, os, time, json, subprocess, threading, http.client, urllib.parse, socket, statistics
import numpy as np
url=sys.argv[1]; PID=int(sys.argv[2]); LBL=sys.argv[3]; OUT=sys.argv[4]; WDL=sys.argv[5]; WDW=sys.argv[6]; TR=sys.argv[7]; STM=sys.argv[8]
u=urllib.parse.urlparse(url); HERE=os.path.dirname(os.path.abspath(__file__)); TK=os.sysconf("SC_CLK_TCK")
def tree(pid):
    ch={}
    for d in os.listdir("/proc"):
        if d.isdigit():
            try: ch.setdefault(int(open(f"/proc/{d}/stat").read().rsplit(")",1)[1].split()[1]),[]).append(int(d))
            except Exception: pass
    out=[pid]; i=0
    while i<len(out): out+=ch.get(out[i],[]); i+=1
    return out
def cpu(pid):
    m=0;tot=0;n=0
    for p in tree(pid):
        try:
            f=open(f"/proc/{p}/stat").read().rsplit(")",1)[1].split(); v=int(f[11])+int(f[12]); tot+=v; n+=1
            if p==pid: m=v
        except Exception: pass
    return m/TK,tot/TK,n
def req(m,p,b=None):
    c=http.client.HTTPConnection(u.hostname,u.port,timeout=70); c.request(m,p,json.dumps(b) if b is not None else None,{"Content-Type":"application/json"}); r=c.getresponse(); d=r.read(); c.close(); return json.loads(d)
res={"label":LBL,"transport":TR,"status_mode":STM,"load0":open("/proc/loadavg").read().split()[:3]}
req("POST","/humanoid/mode",{"enabled":True})
dl=time.monotonic()+70
while time.monotonic()<dl and req("GET","/humanoid/status").get("state")!="ready": time.sleep(.1)
time.sleep(2)
st0=req("GET","/humanoid/status"); res["flags"]={k:st0.get(k) for k in ("safety_brake","collision_avoidance","state")}
stop=[False]; ts=[]; cnt={}; lat={}; pushc={}; jumps=[]
def vid():
    c=http.client.HTTPConnection(u.hostname,u.port,timeout=10); c.request("GET","/humanoid/video"); r=c.getresponse(); buf=b""
    while not stop[0]:
        ch=r.read1(65536)
        if not ch: break
        buf+=ch
        while True:
            i=buf.find(b"\xff\xd8"); j=buf.find(b"\xff\xd9",i+2) if i>=0 else -1
            if i<0 or j<0: break
            ts.append(time.monotonic()); buf=buf[j+2:]
    c.close()
def viewer(path):
    try:
        s=socket.create_connection((u.hostname,u.port)); s.settimeout(2); s.sendall(f"GET {path} HTTP/1.0\r\nHost: x\r\n\r\n".encode()); b=0
        while not stop[0]:
            try: d=s.recv(262144); b+=len(d)
            except socket.timeout: continue
            if not d: break
        cnt["view:"+path]=b
    except Exception as e: cnt["view:"+path]="err "+str(e)
def pusher():
    from simple_websocket import Client
    c=Client.connect("ws://%s:%d/status/ws"%(u.hostname,u.port)); pushc["bytes"]=0
    while not stop[0]:
        try: m=c.receive(timeout=.5)
        except Exception: continue
        if m is None: continue
        pushc["bytes"]+=len(m); k=json.loads(m)["type"]; pushc[k]=pushc.get(k,0)+1
    c.close()
def poller(path,hz):
    c=http.client.HTTPConnection(u.hostname,u.port,timeout=5); n=0; t0=time.monotonic(); lat[path]=[]
    while not stop[0]:
        a=time.perf_counter()
        try: c.request("GET",path); r=c.getresponse(); r.read(); lat[path].append((time.perf_counter()-a)*1000)
        except Exception: c.close()
        n+=1; d=t0+n/hz-time.monotonic()
        if d>0: time.sleep(d)
def probe():
    pm,pr=time.monotonic(),time.time()
    while not stop[0]:
        time.sleep(.02); m,r=time.monotonic(),time.time(); sk=(r-pr)-(m-pm)
        if abs(sk)>.02: jumps.append((m,round(sk*1000,1)))
        pm,pr=m,r
ths=[threading.Thread(target=vid,daemon=True),threading.Thread(target=viewer,args=("/teleop/preview.mjpg",),daemon=True),threading.Thread(target=probe,daemon=True)]
if STM=="push": ths.append(threading.Thread(target=pusher,daemon=True))
else: ths+=[threading.Thread(target=poller,args=a,daemon=True) for a in (("/humanoid/status",10),("/teleop/status",10),("/status",3))]
for t in ths: t.start()
time.sleep(1.5)
SOUT=OUT.replace(".json",".sender.json")
cmd=[sys.executable,"-u",HERE+"/sender_q3.py","http://127.0.0.1:%d"%u.port,"30",WDL,SOUT,TR]
c0=None; T0=T1=None
p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
lines=[]
for ln in p.stdout:
    ln=ln.strip()
    if ln=="T0": T0=time.monotonic(); c0=(cpu(PID),time.monotonic())
    elif ln=="END": T1=time.monotonic(); c1=cpu(PID); c1t=time.monotonic()
    else: lines.append(ln)
p.wait(); err=p.stderr.read()
stop[0]=True; time.sleep(2.5)
if T0 is None or T1 is None:
    print("SENDER FAIL",lines,err[-1500:]); req("POST","/humanoid/mode",{"enabled":False}); sys.exit(2)
snd=json.load(open(SOUT)); ts_s=snd.pop("ts_send"); ts_r=snd.pop("ts_recv"); json.dump({"ts_send":ts_s,"ts_recv":ts_r},open(OUT.replace(".json",".ts.json"),"w"))
res["sender"]=snd; res["sender_err"]=err[-300:]
dt=T1-T0; a=np.array(ts); w=a[(a>=T0)&(a<=T1)]; gp=np.diff(w)*1000 if len(w)>1 else np.array([0.])
res["g1_window"]={"dur_s":round(dt,3),"frames":int(len(w)),"fps_count":round(len(w)/dt,3),"max_gap_ms":round(float(gp.max()),1),"gap_p95_ms":round(float(np.percentile(gp,95)),1),"gaps_gt200":int((gp>200).sum())}
def prox(tl):
    l=np.array([(a[i]-b)*1000 for b in tl for i in [int(np.searchsorted(a,b))] if i<len(a)])
    return {"n":int(len(l)),"p50":round(float(np.percentile(l,50)),1),"p95":round(float(np.percentile(l,95)),1),"max":round(float(l.max()),1)}
res["proxy_ws_send_complete_to_next_frame_ms"]=prox(ts_s); res["proxy_ws_reply_recv_to_next_frame_ms"]=prox(ts_r)
dc=c1t-c0[1]; res["cpu"]={"main_pct":round((c1[0]-c0[0][0])/dc*100,1),"tree_pct":round((c1[1]-c0[0][1])/dc*100,1),"procs":c1[2],"dur_s":round(dc,2)}
res["walljumps_in_window"]=[(round(m-T0,2),s) for m,s in jumps if T0<=m<=T1]; res["walljump_count"]=len(res["walljumps_in_window"])
stf=req("GET","/humanoid/status"); res["server_latency_ms"]=stf.get("server_latency_ms"); res["end_state"]=stf.get("state")
res["push"]={"msgs_per_s":round(sum(v for k,v in pushc.items() if k!="bytes")/dt,2),"by_type":dict(pushc),"bytes_per_s":round(pushc.get("bytes",0)/dt)}
res["poll"]={k:{"req_per_s":round(len(v)/dt,2),"p95_ms":round(sorted(v)[int(.95*len(v))],2) if v else None} for k,v in lat.items()}
res["viewer_bytes"]=dict(cnt); res["load1_end"]=open("/proc/loadavg").read().split()[:3]
req("POST","/humanoid/mode",{"enabled":False})
json.dump(res,open(OUT,"w"),indent=1,default=str); print(json.dumps(res,indent=1,default=str))
