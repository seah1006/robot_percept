"""V-H: 기동 중 SIGKILL 경쟁 상태 반복. env ROOT, PORT(5092), MODE=kill, N, LO, HI(초), TAG, SEED.
각 회 delay~U(LO,HI) 뒤 신호. 매회 트리 정리 후 잔존 0 확인. 잔존 프로세스 cmdline 기록."""
import os,sys,time,json,subprocess,signal,threading,socket,random
ROOT=os.environ["ROOT"]; PORT=int(os.environ.get("PORT","5092"))
N=int(os.environ.get("N","40")); LO=float(os.environ.get("LO","0.3")); HI=float(os.environ.get("HI","0.8"))
SIG=getattr(signal,os.environ.get("SIG","SIGKILL")); TAG=os.environ.get("TAG","x")
random.seed(int(os.environ.get("SEED","1")))
OUT=os.environ.get("OUT",os.path.expanduser("~/work/robot_percept/bench/verify_h"))
def procs():
    rows={}
    for e in os.listdir("/proc"):
        if e.isdigit():
            try:
                t=open(f"/proc/{e}/stat").read().rsplit(")",1)[1].split(); rows[int(e)]=(int(t[1]),t[0])
            except Exception: pass
    return rows
def desc(root,rows):
    f=[];fr=[root]
    while fr:
        p=fr.pop()
        for k,(pp,s) in rows.items():
            if pp==p and k not in f: f.append(k);fr.append(k)
    return f
def rootprocs(me):
    r=[]
    for k in procs():
        if k==me: continue
        try:
            if os.readlink(f"/proc/{k}/cwd")==ROOT:
                c=open(f"/proc/{k}/cmdline","rb").read()
                if b"multiprocessing" in c or b"web.app" in c: r.append(k)
        except Exception: pass
    return r
def alive(k):
    try: return open(f"/proc/{k}/stat").read().rsplit(")",1)[1].split()[0]!="Z"
    except Exception: return False
def port_busy():
    s=socket.socket();s.settimeout(.2)
    try: return s.connect_ex(("127.0.0.1",PORT))==0
    finally: s.close()
def cmd(k):
    try: return open(f"/proc/{k}/cmdline","rb").read().replace(b"\0",b" ").decode()[:140]
    except Exception: return "?"
res=[]
for rep in range(N):
    for k in rootprocs(os.getpid()):
        try: os.kill(k,9)
        except Exception: pass
    time.sleep(.3)
    assert not port_busy(),"port busy before run"
    delay=random.uniform(LO,HI)
    env=dict(os.environ,PORT=str(PORT),HOST="127.0.0.1",PERCEPTION="stub",RP_PERCEPTION_WARMUP="0",PYTHONPATH=ROOT)
    log=open(f"/tmp/vh_sig_{TAG}.log","wb")
    t0=time.monotonic()
    p=subprocess.Popen([sys.executable,"-m","web.app"],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    seen=set();stop=threading.Event()
    def samp():
        while not stop.is_set():
            seen.update(desc(p.pid,procs()));time.sleep(.01)
    th=threading.Thread(target=samp);th.start()
    time.sleep(max(0,delay-(time.monotonic()-t0)))
    tsig=time.monotonic(); seen.update(desc(p.pid,procs())); n_at=len(seen)
    os.kill(p.pid,SIG)
    try: p.wait(timeout=15)
    except subprocess.TimeoutExpired: pass
    t_clear=None
    while time.monotonic()-tsig<12:
        if not any(alive(k) for k in seen) and not [k for k in rootprocs(os.getpid()) if alive(k)]:
            t_clear=time.monotonic()-tsig;break
        time.sleep(.02)
    stop.set();th.join()
    left=[k for k in rootprocs(os.getpid()) if alive(k)]
    left+=[k for k in seen if alive(k) and k not in left]
    lc=[cmd(k)+" ppid="+str(procs().get(k,(0,))[0]) for k in left]
    for k in left:
        try: os.kill(k,9)
        except Exception: pass
    try: os.killpg(p.pid,9)
    except Exception: pass
    time.sleep(.3)
    after=len([k for k in rootprocs(os.getpid()) if alive(k)])
    row=dict(rep=rep,delay=round(delay,3),desc_at_sig=n_at,seen=len(seen),clear_s=None if t_clear is None else round(t_clear,2),left=len(left),left_cmd=lc,after_cleanup=after,port_busy=port_busy())
    print(json.dumps(row),flush=True);res.append(row)
json.dump(res,open(f"{OUT}/sig_h_{TAG}.json","w"),indent=1)
print("SUMMARY",TAG,"n",len(res),"left_runs",sum(1 for r in res if r["left"]>0),"after_cleanup_nonzero",sum(1 for r in res if r["after_cleanup"]))
