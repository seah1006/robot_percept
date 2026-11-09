"""GT 보조, wall-paced 500 Hz 실제 q + 50 Hz servo, lock externally."""
import json,os,time,subprocess
from pathlib import Path
import numpy as np
from sim.humanoid_env import HumanoidEnv
from sim.humanoid_teleop import HumanoidServo
from bench.humanoid_s3_profile import frame_for,stats
from tools import humanoid_synth as hs

def run(pattern,enabled,seconds):
 init_start=time.monotonic();e=HumanoidEnv(320,240,shadows=False);env_prepare_ms=(time.monotonic()-init_start)*1000;s=HumanoidServo(e);old=hs.frame
 hs.frame=lambda t:frame_for(pattern,t)
 ticks=[];first_profile={};qs=[];planner=[];warmup_ticks=[];ready_ticks=[];ready_status={};actual={};wall=[];started=time.monotonic();deadline=time.monotonic();next_input=0.;sample=None
 try:
  for i in range(int(seconds/.002)):
   t=i*.002
   if t>=next_input-1e-9:
    sample,_=hs.payload(t);sample['received_at']=time.time();next_input+=1/30
   did=s.tick(sample,{'enabled':True,'options':{'collision_avoidance':enabled}},time.time())
   if did:
    ticks.append(s.tick_ms)
    if len(ticks)==1:first_profile=dict(s.profile)
    if enabled:
     ready_status=dict(e.collision_status)
     (ready_ticks if ready_status.get('planner_ready') else warmup_ticks).append(s.tick_ms)
     result=e.collision_planner.latest()
     if result:planner.append(result[3].get('planner_ms',0))
   e.step();qs.append(e.data.qpos.copy());wall.append(time.monotonic())
   if enabled:actual=dict(e.collision_status.get('actual',{}))
   deadline+=.002;remaining=deadline-time.monotonic()
   if remaining>0:time.sleep(remaining)
  q=np.array(qs);Path('bench/humanoid_s4_out').mkdir(exist_ok=True)
  np.savez_compressed(f'bench/humanoid_s4_out/{pattern}_{int(enabled)}.npz',qpos=q,tick_ms=np.array(ticks),wall_mono=np.array(wall))
  if enabled:actual['minimum_exact_clearance']=float(e.collision_monitor.min_actual)
  ids=[e.qadr[n] for n in e.groups['left_arm']+e.groups['right_arm']]
  return dict(pattern=pattern,enabled=enabled,first_tick_profile=first_profile,env_prepare_ms=env_prepare_ms,planner_ready=ready_status.get('planner_ready',False),planner_prepare_ms=ready_status.get('planner_prepare_ms'),ready_tick_ms=stats(ready_ticks),warmup_tick_ms=stats(warmup_ticks),tick_ms=stats(ticks),first_tick_ms=ticks[0],steady_tick_ms=stats(ticks[1:]),wall_elapsed_s=time.monotonic()-started,chest_tail_range_deg=np.degrees(np.max(np.ptp(q[len(q)//2:,ids],axis=0))),planner_ms=stats(planner),range_deg=np.degrees(np.ptp(q[:,ids],axis=0)).tolist(),actual=actual,plan=e.collision_plan,state=e.collision_status.get('collision_state'))
 finally:hs.frame=old;e.close()

def main():
 out={'note':'GT auxiliary, capsule proxy only; real-time paced; no render fps claim','load':Path('/proc/loadavg').read_text(),'gpu':subprocess.getoutput('nvidia-smi --query-gpu=name,utilization.gpu,memory.used --format=csv,noheader'),'concurrent_processes':subprocess.getoutput('ps -eo pid,pcpu,args --sort=-pcpu | head -10'),'cases':[]}
 for pattern in ('sweep','chest','jump','twist'):
  for enabled in (False,True):
   row=run(pattern,enabled,float(os.environ.get('SECONDS','4')));out['cases'].append(row);print(json.dumps(row),flush=True)
   Path('bench/humanoid_s4_out').mkdir(exist_ok=True);Path('bench/humanoid_s4_out/async.json').write_text(json.dumps(out,indent=2))
if __name__=='__main__':main()
