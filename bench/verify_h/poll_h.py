"""V-H: 10Hz /status 폴링 기동 N회. env ROOT PORT=5092 N TAG HZ(10) CAP(60). ready=st.ready 또는 frame_seq>0."""
import os,sys,time,json,subprocess,signal,urllib.request,socket
ROOT=os.environ["ROOT"];PORT=int(os.environ.get("PORT","5092"));N=int(os.environ.get("N","30"));TAG=os.environ.get("TAG","x")
HZ=float(os.environ.get("HZ","10"));CAP=float(os.environ.get("CAP","60"))
OUT=os.path.expanduser("~/work/robot_percept/bench/verify_h")
def rootprocs(me):
    r=[]
    for e in os.listdir("/proc"):
        if e.isdigit() and int(e)!=me:
            try:
                if os.readlink(f"/proc/{e}/cwd")==ROOT:
                    c=open(f"/proc/{e}/cmdline","rb").read()
                    if b"multiprocessing" in c or b"web.app" in c: r.append(int(e))
            except Exception: pass
    return r
def busy():
    s=socket.socket();s.settimeout(.2)
    try: return s.connect_ex(("127.0.0.1",PORT))==0
    finally: s.close()
res=[]
for rep in range(N):
    for k in rootprocs(os.getpid()):
        try: os.kill(k,9)
        except Exception: pass
    time.sleep(.5); assert not busy()
    env=dict(os.environ,PORT=str(PORT),HOST="127.0.0.1",PERCEPTION="stub",RP_PERCEPTION_WARMUP="0",PYTHONPATH=ROOT)
    log=open(f"/tmp/vh_poll_{TAG}.log","wb")
    p=subprocess.Popen([sys.executable,"-m","web.app"],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    t0=time.monotonic();ready=None;nreq=0;nerr=0;maxlat=0
    while time.monotonic()-t0<CAP:
        t1=time.monotonic()
        try:
            s=json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/status",timeout=2));nreq+=1
            if s.get("ready") or s.get("frame_seq",0)>0: ready=time.monotonic()-t0;break
        except Exception: nerr+=1
        maxlat=max(maxlat,time.monotonic()-t1)
        time.sleep(max(0,1/HZ-(time.monotonic()-t1)))
    p.send_signal(signal.SIGTERM)
    try: p.wait(timeout=15)
    except subprocess.TimeoutExpired: pass
    for k in rootprocs(os.getpid()):
        try: os.kill(k,9)
        except Exception: pass
    try: os.killpg(p.pid,9)
    except Exception: pass
    time.sleep(.5)
    left=len(rootprocs(os.getpid()))
    row=dict(rep=rep,ready_s=None if ready is None else round(ready,2),nreq=nreq,nerr=nerr,left_after=left,port_busy=busy())
    print(json.dumps(row),flush=True);res.append(row)
json.dump(res,open(f"{OUT}/poll_h_{TAG}.json","w"),indent=1)
rs=[r["ready_s"] for r in res]
print("SUMMARY",TAG,"n",len(res),"timeouts",sum(1 for x in rs if x is None),"ready_s",sorted(x for x in rs if x is not None)[:3],"...",sorted(x for x in rs if x is not None)[-3:],"left",sum(r["left_after"] for r in res))
