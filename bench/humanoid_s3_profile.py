"""P1c ON 서보 tick 단계/호출/cProfile 프로파일러. 운영 코드 수정 없음."""
from __future__ import annotations
import cProfile, io, json, math, os, pstats, time
from collections import defaultdict
import numpy as np
from sim.humanoid_env import HumanoidEnv
from sim.humanoid_teleop import HumanoidServo
from tools import humanoid_synth as hs

OUTDIR=os.environ.get("OUTDIR","bench/humanoid_s3_out")
PATTERNS=("sweep","chest","jump","twist")
FING={s:({k:(.05,.05,.03) for k in ("index","middle","ring","pinky")},(.25,.15,.1),0.) for s in ("left","right")}

def frame_for(pattern,t):
    if pattern=="sweep":
        k=.5-.5*math.cos(2*math.pi*(t%12)/12)
        arms={s:(.4+1.0*k,.15-.75*k,.9+.5*k,0,0) for s in ("left","right")}; torso=(0.,0.,0.)
    elif pattern=="chest":
        arms={s:(1.2,-1.0,1.8,0,0) for s in ("left","right")}; torso=(0.,0.,0.)
    elif pattern=="jump":
        arms={s:((1.2,-1.0,1.6,0,0) if int(t/.6)%2 else (.15,.15,.35,0,0)) for s in ("left","right")}; torso=(0.,0.,0.)
    else:
        arms={s:(1.0,-.6,1.3,0,0) for s in ("left","right")}
        torso=(.6*math.sin(2*math.pi*t/6),.2*math.sin(2*math.pi*t/4),.15*math.sin(2*math.pi*t/5))
    return True,arms,FING,torso

def pct(v,p): return float(np.percentile(v,p)) if v else 0.
def stats(v): return {"n":len(v),"p50":pct(v,50),"p95":pct(v,95),"max":max(v) if v else 0.,"mean":float(np.mean(v)) if v else 0.}

def run(pattern, seconds=5., warmup=1., profiled=False):
    env=HumanoidEnv(320,240,shadows=False); servo=HumanoidServo(env,rate_hz=50)
    ctrl={"enabled":True,"options":{"collision_avoidance":True,"safety_brake":True,"arm_target":"wrist"}}
    calls=defaultdict(int); times=defaultdict(float)
    def wrap(obj,name,label):
        old=getattr(obj,name)
        def f(*a,**kw):
            t=time.perf_counter(); calls[label]+=1
            try:return old(*a,**kw)
            finally:times[label]+=(time.perf_counter()-t)*1000
        setattr(obj,name,f)
    wrap(env,"update_collision_brake","release_check")
    wrap(env,"request_collision_brake","brake_request")
    hs.frame=lambda t:frame_for(pattern,t)
    sample,_=hs.payload(0.); sample.update(received_at=time.time(),seq=0)
    servo.tick(sample,ctrl,time.time())
    g=env.collision_model
    for name,label in (("forward","collision_fk"),("distances","collision_distances"),("minimum","collision_minimum"),("project","collision_project"),("plan_safe_waypoint","waypoint_plan"),("approach_safe","approach_safe"),("sampled_path","sampled_path")):
        wrap(g,name,label)
    for side,ik in servo.iks.items(): wrap(ik,"solve",f"ik_solve_{side}")
    tick_rows=[]; dt=float(env.model.opt.timestep); total_steps=int((warmup+seconds)/dt)
    next_sample=0.; current=sample; seq=0
    pr=cProfile.Profile() if profiled else None
    if pr:pr.enable()
    for step in range(total_steps):
        simt=step*dt
        if simt+1e-12>=next_sample:
            current,_=hs.payload(simt); seq+=1; current.update(received_at=time.time(),seq=seq); next_sample+=1/30
        before_c=dict(calls); before_t=dict(times); fk0=g.fk_calls
        did=servo.tick(current,ctrl,time.time())
        if did and simt>=warmup:
            row=dict(servo.profile)
            row.update(total_ms=servo.tick_ms, collision_fk_calls=g.fk_calls-fk0)
            for k in set(calls)|set(before_c): row[k+"_calls"]=calls[k]-before_c.get(k,0)
            for k in set(times)|set(before_t): row[k+"_ms"]=times[k]-before_t.get(k,0.)
            tick_rows.append(row)
        env.step(1)
    if pr:
        pr.disable(); pr.dump_stats(os.path.join(OUTDIR,f"{pattern}.prof"))
        sio=io.StringIO(); pstats.Stats(pr,stream=sio).strip_dirs().sort_stats("cumtime").print_stats(35)
        open(os.path.join(OUTDIR,f"{pattern}_cprofile.txt"),"w").write(sio.getvalue())
    keys=sorted({k for r in tick_rows for k in r})
    summary={k:stats([float(r.get(k,0.)) for r in tick_rows]) for k in keys if k.endswith("_ms")}
    counts={k:{"total":int(sum(r.get(k,0) for r in tick_rows)),"per_tick_mean":float(np.mean([r.get(k,0) for r in tick_rows])),"per_tick_p95":pct([r.get(k,0) for r in tick_rows],95),"max":int(max(r.get(k,0) for r in tick_rows))} for k in keys if k.endswith("_calls")}
    route=(env.collision_status.get("goal_projection") or {}).get("route","none")
    raw_keys=("total_ms","retarget_ms","ik_ms","projection_ms","waypoint_plan_ms","release_check_ms","brake_ms","integration_ms")
    raw={k:[float(r.get(k,0.)) for r in tick_rows] for k in raw_keys}
    result={"pattern":pattern,"seconds":seconds,"warmup":warmup,"profiled":profiled,"ticks":len(tick_rows),"timing_ms":summary,"counts":counts,"raw_ms":raw,"final_route":route,"collision_state":env.collision_status.get("collision_state"),"load":open("/proc/loadavg").read().split()[:3]}
    env.close(); return result

def main():
    os.makedirs(OUTDIR,exist_ok=True); allout={"generated_at":time.strftime("%Y-%m-%dT%H:%M:%S%z"),"patterns":{}}
    for pattern in PATTERNS:
        print("PROFILE",pattern,flush=True)
        allout["patterns"][pattern]=run(pattern,seconds=float(os.environ.get("SECONDS","5")),warmup=1.,profiled=os.environ.get("CPROFILE","1")!="0")
        json.dump(allout,open(os.path.join(OUTDIR,"profile.json"),"w"),indent=2)
    print(json.dumps({p:{"tick_p95":v["timing_ms"]["total_ms"]["p95"],"plan_p95":v["timing_ms"].get("waypoint_plan_ms",{}).get("p95"),"fk_mean":v["counts"].get("collision_fk_calls",{}).get("per_tick_mean")} for p,v in allout["patterns"].items()},indent=2))
if __name__=="__main__":main()
