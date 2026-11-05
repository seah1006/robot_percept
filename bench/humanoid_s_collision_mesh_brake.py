import json,time,numpy as np
from pathlib import Path
from sim.humanoid_env import HumanoidEnv
from sim.humanoid_teleop import HumanoidServo
from sim.humanoid_collision import CapsuleModel,MESH_RADII
from tools import humanoid_synth as hs
OUT=Path('bench/humanoid_s_out')
def main():
 e=HumanoidEnv();s=HumanoidServo(e);g=CapsuleModel(e.model,MESH_RADII);source=OUT/'20261105_collision_runtime_path.npz';path=np.load(source)['qpos'];qset=[e.data.qpos.copy()]+[path[i] for i in np.linspace(0,len(path)-1,48,dtype=int)]
 cover={}
 for q in qset:
  audit=g.mesh_audit(q)
  for group,row in audit.items():
   v=cover.setdefault(group,dict(max_uncovered_mm=0.,max_uncovered_vertices=0))
   v['max_uncovered_mm']=max(v['max_uncovered_mm'],row['union_max_outside_mm']);v['max_uncovered_vertices']=max(v['max_uncovered_vertices'],row['union_uncovered_vertices'])
 rest=g.minimum(e.data.qpos)['distance']
 oldframe=hs.frame;_,_,f,tor=oldframe(0)
 hs.frame=lambda _:(True,{z:(1.4,-.6,1.4,0,0) for z in ('left','right')},f,tor)
 p,_=hs.payload(0)
 for _ in range(30):s._retarget(p)
 hs.frame=oldframe;target=e.data.qpos.copy()
 for z in ('left','right'):target[s.iks[z].qadr]=s.q_ik[z]
 target_gap=g.minimum(target)['distance']
 control=HumanoidEnv();control.set_targets({n:target[control.qadr[n]] for n in g.names});control_min=1.
 for _ in range(2000):control.step();control_min=min(control_min,g.minimum(control.data.qpos)['distance'])
 control.close()
 e.set_collision_avoidance(True);e.set_targets({n:target[e.qadr[n]] for n in e.collision_model.names});ix=[e.dadr[n] for n in s.controlled];last=e.data.qvel[ix].copy();maxa=np.zeros(len(ix));maxv=maxa.copy();raw=[];trigger=None;stop=None;minimum=1.;continuity=None
 for i in range(2000):
  t=i*.002
  if i%10==0 and not e.collision_braking:
   state=(e.data.qpos.copy(),e.data.qvel.copy(),e.setpoint.position.copy(),e.setpoint.velocity.copy(),e.setpoint.acceleration.copy())
   e.update_collision_brake()
   if e.collision_braking:
    trigger=t;after=(e.data.qpos,e.data.qvel,e.setpoint.position,e.setpoint.velocity,e.setpoint.acceleration);continuity=max(float(np.max(np.abs(a-b))) for a,b in zip(state,after))
  e.step();v=e.data.qvel[ix].copy();a=(v-last)/.002;last=v
  if trigger is not None:
   maxa=np.maximum(maxa,np.abs(a));maxv=np.maximum(maxv,np.abs(v))
   if stop is None and t-trigger>.1 and np.max(np.abs(v))<.01:stop=t
  distance=g.minimum(e.data.qpos)['distance'];minimum=min(minimum,distance);raw.append((t,*v,*a,distance))
 result=dict(load=open('/proc/loadavg').read().strip(),radii_mm={k:v*1000 for k,v in MESH_RADII.items()},audit_poses=len(qset),mesh_coverage=cover,all_mesh_uncovered_le2mm=all(x['max_uncovered_mm']<=2 for x in cover.values()),rest_clearance_mm=rest*1000,unsafe_target_clearance_mm=target_gap*1000,no_brake_control_min_mm=control_min*1000,brake_trigger_s=trigger,stop_after_trigger_s=None if stop is None or trigger is None else stop-trigger,state_jump_at_brake=continuity,actual_min_mm=minimum*1000,post_brake_v_ratio=float(np.max(maxv/s.vmax)),post_brake_a_ratio=float(np.max(maxa/s.amax)),worst_a=s.controlled[int(np.argmax(maxa/s.amax))],brake_reason=e.collision_status.get('brake'),note='49 sampled poses, selected torso/arm/palm mesh vertices; excludes head/fingers; finite measured scenario, not universal certification')
 OUT.mkdir(exist_ok=True);np.savez_compressed(OUT/'20261105_collision_brake_raw.npz',rows=np.array(raw),names=np.array(s.controlled),dt=.002)
 (OUT/'20261105_collision_mesh_brake.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));e.close()
if __name__=='__main__':main()