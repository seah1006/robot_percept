"""GT 보조 정적12자세 순차 및 chest→abd45, wall-paced async."""
import json,time,subprocess
from pathlib import Path
import numpy as np
from sim.humanoid_env import HumanoidEnv
from sim.humanoid_teleop import HumanoidServo
from bench.humanoid_s2_static_split import POSES,angle
from tools import humanoid_synth as hs
OUT=Path('bench/humanoid_s4_out');OUT.mkdir(exist_ok=True)
def errors(e,s,gt):
 out=[]
 for z in ('left','right'):
  ik=s.iks[z];q=e.data.qpos;d=ik.fk(q,q[ik.qadr]);R=d.xmat[s.torso_body].reshape(3,3);S=d.xpos[e.model.body(f'{z}_shoulder_roll_link').id];E=d.site_xpos[ik.site['elbow_site']];W=d.site_xpos[ik.site['wrist_site']]
  out.extend((angle(R.T@(E-S),gt[z]['u1']),angle(R.T@(W-E),gt[z]['u2'])))
 return out

def execute(e,s,arms,seconds,enabled):
 old=hs.frame;_,_,fingers,torso=old(0);hs.frame=lambda t:(True,{z:arms for z in ('left','right')},fingers,torso)
 deadline=time.monotonic();next_input=0.;sample=None;errs=[];q=[];first8=None
 try:
  _,gt=hs.payload(0)
  for i in range(int(seconds/.002)):
   t=i*.002
   if t>=next_input-1e-9:sample,_=hs.payload(0);sample['received_at']=time.time();next_input+=1/30
   if s.tick(sample,{'enabled':True,'options':{'collision_avoidance':enabled}},time.time()):
    er=errors(e,s,gt);errs.append(er)
    if max(er)<=8 and first8 is None:first8=t
   e.step();q.append(e.data.qpos.copy());deadline+=.002;left=deadline-time.monotonic()
   if left>0:time.sleep(left)
  if enabled:e.collision_status['actual']['minimum_exact_clearance']=float(e.collision_monitor.min_actual)
  snapshot={}
  if enabled:
   result=e.collision_planner.latest();pending=getattr(e.collision_planner,'_pending',None)
   target=pending[2] if pending is not None else result[1] if result is not None else None
   ids=[s.index[n] for n in e.collision_model.names];qadr=e.collision_model.qadr
   snapshot=dict(state=e.collision_status.get('collision_state'),braking=e.collision_braking,brake=e.collision_status.get('brake'),plan=e.collision_plan,planner_diag=None if result is None else result[3],cmd_des_max_rad=float(np.max(np.abs(s.cmd[ids]-s.des[ids]))),actual_cmd_max_rad=float(np.max(np.abs(e.data.qpos[qadr]-s.cmd[ids]))))
   if target is not None:
    normals=dict(e.collision_model.previous_normals)
    snapshot.update(target_actual_max_rad=float(np.max(np.abs(target[qadr]-e.data.qpos[qadr]))),target_cmd_max_rad=float(np.max(np.abs(target[qadr]-s.cmd[ids]))),target_clearance_mm=e.collision_model.minimum_distance(target)*1000)
    e.collision_model.previous_normals=normals
  return dict(final_errors_deg=errs[-1],tail_max_deg=float(np.max(errs[-50:])),first_within8_s=first8,actual=dict(e.collision_status.get('actual',{})),snapshot=snapshot)
 finally:hs.frame=old

def main():
 result={'GT_auxiliary':True,'load':Path('/proc/loadavg').read_text(),'gpu':subprocess.getoutput('nvidia-smi --query-gpu=name,utilization.gpu,memory.used --format=csv,noheader'),'cases':[]}
 for enabled in (False,True):
  e=HumanoidEnv();s=HumanoidServo(e)
  try:
   for name,fl,ab,el,hu in POSES:
    row=execute(e,s,(fl,ab,el,hu,0),4.,enabled);row.update(pose=name,enabled=enabled);result['cases'].append(row);print(json.dumps(row),flush=True)
    (OUT/'function.json').write_text(json.dumps(result,indent=2))
  finally:e.close()
 e=HumanoidEnv();s=HumanoidServo(e)
 try:
  execute(e,s,(1.2,-1.,1.8,0,0),3.,True)
  result['release']=execute(e,s,(.05,.8,.1,0,0),8.,True)
 finally:e.close()
 (OUT/'function.json').write_text(json.dumps(result,indent=2));print('RELEASE',result['release'],flush=True)
if __name__=='__main__':
 import sys
 subprocess.run(['flock','-w','120','/tmp/rp_gpu.lock',sys.executable,'-m','bench.humanoid_s4_lifecycle'],check=False)
 main()
 # Frozen-source regression in the same measurement slot (outer timeout 280s).
 with (OUT/'ready_r3'/'pytest_same_slot.txt').open('w') as pytest_log:
  subprocess.run(['flock','-w','10','/tmp/rp_gpu.lock',sys.executable,'-m','pytest','-q'],stdout=pytest_log,stderr=subprocess.STDOUT,timeout=85)
 # Same-slot final dynamic retest after pending-request fix.
 from bench.humanoid_s4_async import main as dynamic_main
 dynamic_main()
