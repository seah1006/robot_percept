import sys,threading;sys.path.insert(0,'/mnt/c/Users/USER/.aside/u/0/sessions/2026-10-19_5xmUwlu5vry7k9Rb/tmp/vt')
from vlib import *
def run(name,fn,dur):
    req('/teleop/mode',{'enabled':False});req('/reset',{});time.sleep(3)
    print(req('/teleop/mode',{'enabled':True}))
    for i in range(10): upd(.5,.5,.3);time.sleep(.03)
    rec=[];stop=[False]
    def poll():
        last=-1
        while not stop[0]:
            q=st()
            if q.get('frame_seq')!=last:
                last=q.get('frame_seq');rec.append((time.time(),np.array(q['ee_pose']),np.array(q['arm_qpos']),q.get('teleop_target'),q.get('timestamp')))
            time.sleep(.01)
    th=threading.Thread(target=poll);th.start()
    t0=time.time();n=0;sent=[]
    while time.time()-t0<dur:
        t=time.time()-t0;x,y,s=fn(t);upd(x,y,s);sent.append(time.time());n+=1;time.sleep(max(0,t0+n/30-time.time()))
    stop[0]=True;th.join()
    ts=np.array([r[0] for r in rec]);ee=np.array([r[1][:3,3] for r in rec]);q=np.array([r[2] for r in rec]);tg=np.array([r[3] if r[3] else [np.nan]*3 for r in rec],dtype=float)
    print(name,'send rate',n/dur,'status frames',len(rec),'status Hz',len(rec)/dur,'status.hz',req('/teleop/status'))
    dq=np.abs(np.diff(q,axis=0))/np.diff(ts)[:,None]
    print(' max joint vel rad/s (status-sampled)',dq.max(),'max single-step dq rad',np.abs(np.diff(q,axis=0)).max())
    np.savez(f'/tmp/vt_{name}.npz',ts=ts,ee=ee,q=q,tg=tg,t0=t0)
    # expected path: target; error ee vs target with best lag
    ok=~np.isnan(tg).any(1);e=ee[ok];g=tg[ok];tt=ts[ok]
    best=None
    for lag in np.arange(0,1.5,.05):
        gi=np.array([np.interp(tt[i]-lag,tt,g[:,k]) for i in range(len(tt)) for k in range(3)]).reshape(-1,3)
        r=np.sqrt(np.mean(np.sum((e-gi)**2,1)))*1000
        if best is None or r<best[1]:best=(lag,r)
    print(' ee-vs-teleop_target RMS mm (best lag s)',best, 'at zero lag',np.sqrt(np.mean(np.sum((e-g)**2,1)))*1000)
    # expected from raw mapping
    n0=(.5,.5,.3);org=ee[0]
    exp=[]
    for t in ts:
        x,y,s=fn(max(0,t-t0));exp.append(np.clip(org+np.array([-(s-n0[2])*1.2,(x-n0[0])*.7,-(y-n0[1])*.7]),[.25,-.35,.36],[.70,.35,.85]))
    exp=np.array(exp);b=None
    for lag in np.arange(0,1.5,.05):
        gi=np.array([[np.interp(tt0-lag,ts,exp[:,k]) for k in range(3)] for tt0 in ts]);r=np.sqrt(np.mean(np.sum((ee-gi)**2,1)))*1000
        if b is None or r<b[1]:b=(lag,r)
    print(' ee-vs-expected scaled path RMS mm (best lag)',b)
    return ee
def sq(t):
    k=(t%8)/2;f=k%1;c=[(-1,-1),(1,-1),(1,1),(-1,1),(-1,-1)];a=c[int(k)];b=c[int(k)+1]
    return .5+.15*(a[0]+(b[0]-a[0])*f),.5+.15*(a[1]+(b[1]-a[1])*f),.3
def ci(t):
    w=2*math.pi/8;return .5+.15*math.sin(w*t),.5-.15*math.cos(w*t)+.15,.3
run('square',sq,10);run('circle',ci,10)