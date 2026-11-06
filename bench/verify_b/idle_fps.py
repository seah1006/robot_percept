import os,sys,time,json,subprocess,signal,urllib.request,threading
ROOT=os.environ.get("RPROOT",os.path.expanduser("~/work/rp_vb")); PORT=5094
env=dict(os.environ,PORT=str(PORT),HOST="127.0.0.1",PERCEPTION="stub",RP_PERCEPTION_WARMUP="0",PYTHONPATH=ROOT)
log=open("/tmp/vb_idle.log","wb")
p=subprocess.Popen([sys.executable,"-m","web.app"],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
def st():
    return json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/status",timeout=2).read())
out={}
try:
    t0=time.monotonic()
    while True:
        try:
            s=st()
            if s.get("ready") or s.get("frame_seq",0)>0:break
        except Exception: pass
        if time.monotonic()-t0>120: raise SystemExit("not ready")
        time.sleep(.5)
    out["ready_s"]=round(time.monotonic()-t0,2)
    print("keys",{k:s.get(k) for k in("fps","ready","state","render_idle","video_viewers","frame_seq")},flush=True)
    def seqrate(sec):
        a=st()["frame_seq"];t=time.monotonic();time.sleep(sec);b=st()["frame_seq"];return (b-a)/(time.monotonic()-t)
    time.sleep(3)
    out["idle_fps_frame_seq"]=[round(seqrate(5),2) for _ in range(2)]
    out["idle_render_idle_flag"]=st().get("render_idle")
    ts=[];stop=threading.Event();t_conn=[None]
    def view():
        t_conn[0]=time.monotonic()
        r=urllib.request.urlopen(f"http://127.0.0.1:{PORT}/video",timeout=10)
        buf=b""
        while not stop.is_set():
            c=r.read(4096)
            if not c:break
            buf+=c
            while True:
                i=buf.find(b"\xff\xd8")
                j=buf.find(b"\xff\xd9",i+2) if i>=0 else -1
                if i<0 or j<0:break
                ts.append(time.monotonic());buf=buf[j+2:]
        r.close()
    th=threading.Thread(target=view);th.start()
    time.sleep(8)
    fr=[x-t_conn[0] for x in ts]
    out["mjpeg_first_frame_s"]=round(fr[0],3) if fr else None
    reach=None
    for i in range(len(fr)-10):
        if fr[i+10]-fr[i]<=0.4: reach=fr[i];break
    out["reach_30fps_s"]=round(reach,3) if reach is not None else None
    w=[x for x in fr if 3<=x<=8];out["viewer_fps_3to8s"]=round((len(w)-1)/(w[-1]-w[0]),2) if len(w)>1 else None
    out["viewer_frame_seq_fps"]=round(seqrate(3),2);s=st();out["viewer_flag"]=[s.get("render_idle"),s.get("video_viewers")]
    stop.set();th.join(timeout=12)
    tdis=time.monotonic();back=None
    for _ in range(100):
        s=st()
        if s.get("render_idle"):back=time.monotonic()-tdis;break
        time.sleep(.1)
    out["after_disconnect_idle_flag_s"]=round(back,2) if back else None
    time.sleep(2);out["post_idle_fps"]=round(seqrate(5),2)
finally:
    try:os.killpg(p.pid,signal.SIGTERM)
    except Exception:pass
    time.sleep(3)
    try:os.killpg(p.pid,signal.SIGKILL)
    except Exception:pass
print(json.dumps(out))
json.dump(out,open(os.path.expanduser("~/work/robot_percept/bench/verify_b/idle_fps_%s.json"%sys.argv[1]),"w"))
