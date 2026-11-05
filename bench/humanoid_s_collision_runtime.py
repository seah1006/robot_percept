import json,math,time,numpy as np
from pathlib import Path
from sim.humanoid_env import HumanoidEnv
from sim.humanoid_teleop import HumanoidServo
from tools import humanoid_synth as hs

def main():
 e=HumanoidEnv();s=HumanoidServo(e);old=hs.frame;_,_,f,tor=old(0);nextsample=0.;sample=None;ticks=[];qraw=[]
 def frame(t):
  k=.5-.5*math.cos(2*math.pi*(t%12)/12)
  return True,{z:(.4+k,.15-.75*k,.9+.5*k,0,0) for z in ('left','right')},f,tor
 hs.frame=frame
 try:
  for i in range(12500):
   t=i*.002
   if t>=nextsample-1e-10:sample,_=hs.payload(t);sample['received_at']=100+t;nextsample+=1/30
   t0=time.perf_counter();did=s.tick(sample,{'enabled':True,'options':{'collision_avoidance':True}},100+t)
   if did:ticks.append((time.perf_counter()-t0)*1000)
   e.step();qraw.append(e.data.qpos.copy())
  np.savez_compressed("bench/humanoid_s_out/20261105_collision_runtime_path.npz",qpos=np.array(qraw),dt=.002)
  m=e.collision_monitor;r=e.collision_reference_monitor
  result=dict(load=open('/proc/loadavg').read().strip(),actual_min_exact_mm=m.min_actual*1000,actual_penetration_checks=m.penetrating,actual_uncertified_intervals=m.uncertified,actual_exact_checks=m.exact_checks,reference_min_exact_mm=r.min_actual*1000,reference_penetration_checks=r.penetrating,reference_uncertified_intervals=r.uncertified,reference_exact_checks=r.exact_checks,tick_p95_ms=float(np.percentile(ticks,95)),collision_status=e.collision_status,note='reference proxy capsules only; excludes fingers/face; monitor is NOT a certified emergency stop')
  Path('bench/humanoid_s_out/20261105_collision_runtime.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
 finally:e.close();hs.frame=old
if __name__=='__main__':main()