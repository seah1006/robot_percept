"""V-B: 기동 직후(ready 전) 신호. 사용: sig_early.py <delay_s> [reps]
각 회: 서버 기동 -> delay 후 신호 -> 서버 종료 시간, 포착된 자손 소멸 시간, cwd==ROOT 인 잔존 프로세스, /dev/shm 증가량.
"""
import os,sys,time,json,subprocess,signal,threading,socket
ROOT=os.path.expanduser("~/work/robot_percept"); PORT=5093
delay=float(sys.argv[1]); reps=int(sys.argv[2]) if len(sys.argv)>2 else 5
def procs():
    rows={}
    for e in os.listdir("/proc"):
        if e.isdigit():
            try:
                t=open(f"/proc/{e}/stat").read().rsplit(")",1)[1].split()
                rows[int(e)]=(int(t[1]),t[0])
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
def alive(k,rows=None):
    try:
        t=open(f"/proc/{k}/stat").read().rsplit(")",1)[1].split()
        return t[0]!="Z"
    except Exception: return False
def shmn(): return len(os.listdir("/dev/shm"))
def port_busy():
    s=socket.socket();s.settimeout(.2)
    try: return s.connect_ex(("127.0.0.1",PORT))==0
    finally: s.close()
res=[]
for sig in [getattr(signal,x) for x in os.environ.get("SIGS","SIGTERM,SIGINT,SIGKILL").split(",")]:
    for rep in range(reps):
        for k in rootprocs(os.getpid()):
            try: os.kill(k,9)
            except Exception: pass
        time.sleep(.3)
        assert not port_busy(),"port 5094 busy before run"
        shm0=shmn()
        env=dict(os.environ,PORT=str(PORT),HOST="127.0.0.1",PERCEPTION="stub",RP_PERCEPTION_WARMUP="0",PYTHONPATH=ROOT)
        log=open("/tmp/vb_sig.log","wb")
        t0=time.monotonic()
        p=subprocess.Popen([sys.executable,"-m","web.app"],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        seen=set();stop=threading.Event()
        def samp():
            while not stop.is_set():
                seen.update(desc(p.pid,procs()));time.sleep(.02)
        th=threading.Thread(target=samp);th.start()
        time.sleep(max(0,delay-(time.monotonic()-t0)))
        tsig=time.monotonic()
        seen.update(desc(p.pid,procs()));n_at_sig=len(seen)
        os.kill(p.pid,sig)
        try:
            p.wait(timeout=15);t_exit=time.monotonic()-tsig
        except subprocess.TimeoutExpired:
            t_exit=None
        # wait for captured descendants to disappear (max 10s)
        t_clear=None
        while time.monotonic()-tsig<15:
            if not any(alive(k) for k in seen) and not [k for k in rootprocs(os.getpid()) if alive(k)]:
                t_clear=time.monotonic()-tsig;break
            time.sleep(.02)
        stop.set();th.join()
        left=[k for k in rootprocs(os.getpid()) if alive(k)]
        left+= [k for k in seen if alive(k) and k not in left]
        row=dict(delay=delay,sig=sig.name,rep=rep,desc_at_signal=n_at_sig,seen_total=len(seen),exit_s=None if t_exit is None else round(t_exit,2),
                 clear_s=None if t_clear is None else round(t_clear,2),left=len(left),over5=(t_clear is None or t_clear>5 or t_exit is None or t_exit>5),
                 shm_delta=shmn()-shm0,port_busy=port_busy(),rc=p.returncode)
        row_cmd=[]
        for k in left:
            try: row_cmd.append(open(f"/proc/{k}/cmdline","rb").read().replace(b"\0",b" ").decode()[:110]+" ppid="+str(procs().get(k,(0,))[0]))
            except Exception: pass
            try: os.kill(k,9)
            except Exception: pass
        try: os.killpg(p.pid,9)
        except Exception: pass
        time.sleep(.3)
        row["after_cleanup_left"]=len([k for k in rootprocs(os.getpid()) if alive(k)])
        row["left_cmd"]=row_cmd
        print(json.dumps(row),flush=True);res.append(row)
json.dump(res,open(os.path.expanduser(f"~/work/robot_percept/bench/verify_h/out/early_kill_{delay}_{os.environ.get("TAG","")}.json"),"w"),indent=1)
