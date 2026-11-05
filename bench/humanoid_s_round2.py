"""R2 correctness only, no timing/FPS claims. Synthetic GT auxiliary."""
import json,subprocess,types,copy
import numpy as np,mujoco
from sim.humanoid_env import HumanoidEnv
from sim.humanoid_teleop import HumanoidServo
from sim.humanoid_ik import ArmIK,rotation_error
from tools import humanoid_synth as hs

def ang(a,b):return float(np.degrees(np.arccos(np.clip(a@b/np.linalg.norm(a)/np.linalg.norm(b),-1,1))))
def geometry():
 e=HumanoidEnv();s=HumanoidServo(e);rows=[]
 try:
  for t in (0.,4.,6.5,7.5,9.5,12.5):
   p,gt=hs.payload(t)
   for side in ('left','right'):s.q_ik[side]=s.iks[side].rest.copy()
   for _ in range(24):s._retarget(p)
   for side in ('left','right'):
    ik=s.iks[side];d=ik.fk(e.data.qpos,s.q_ik[side]);g=s.geom[side];R=d.xmat[s.torso_body].reshape(3,3);pt=d.xpos[s.torso_body]
    S=d.xpos[e.model.body(f'{side}_shoulder_roll_link').id];E=d.site_xpos[ik.site['elbow_site']];W=d.site_xpos[ik.site['wrist_site']];P=d.xpos[e.model.body(f'{side}_shoulder_pitch_link').id]
    u1=np.array(gt[side]['u1']);u2=np.array(gt[side]['u2'])
    rows.append(dict(t=t,side=side,roll_shoulder_drift_mm=float(np.linalg.norm(R.T@(S-pt)-g['S'])*1000),pitch_to_roll_mm=float(np.linalg.norm(P-S)*1000),L1_rest_mm=g['L1']*1000,L1_actual_mm=float(np.linalg.norm(E-S)*1000),L2_rest_mm=g['L2']*1000,L2_actual_mm=float(np.linalg.norm(W-E)*1000),forearm_axis_offset_deg=ang(W-E,d.xmat[e.model.body(f'{side}_elbow_link').id].reshape(3,3)[:,0]),u1_deg=ang(R.T@(E-S),u1),u2_deg=ang(R.T@(W-E),u2),wrist_actualS_mm=float(np.linalg.norm(W-(S+R@(g['L1']*u1+g['L2']*u2)))*1000),limit_margin_deg=float(np.degrees(np.min(np.minimum(s.q_ik[side]-ik.lo,ik.hi-s.q_ik[side]))))))
  return rows
 finally:e.close()
def dropout():
 src=subprocess.check_output(['git','show','1da4b93:sim/humanoid_teleop.py'],text=True)
 mod=types.ModuleType('sim._s_baseline');mod.__package__='sim';exec(compile(src,'baseline','exec'),mod.__dict__)
 orig=ArmIK.solve
 def no_relative(self,*a,**kw):kw.pop('relative_targets',None);return orig(self,*a,**kw)
 out={};ArmIK.solve=no_relative
 oldframe=hs.frame
 def fr(t):
  _,_,f,tor=oldframe(0);return True,{z:(.9,.2,1.,0,1.2) for z in ('left','right')},f,tor
 hs.frame=fr
 try:
  for name,cls in [('baseline',mod.HumanoidServo),('a7_only',HumanoidServo),('full_current',HumanoidServo)]:
   ArmIK.solve=orig if name=='full_current' else no_relative
   e=HumanoidEnv();s=cls(e);m=e.model;d=e.data;qprev=None;vprev=None;Rs={};jumps=[];cmdjumps=[];maxv=np.zeros(len(s.controlled));maxa=maxv.copy();cmdv=maxv.copy();cmda=maxv.copy();ix=[e.dadr[n] for n in s.controlled];lastcmd=s.cmd.copy();lastvel=s.vel.copy();nextinput=0;sample=None
   for i in range(6000):
    t=i*.002
    if i>=nextinput:
     p,_=hs.payload(0);p=copy.deepcopy(p)
     if t>=3 and int((t-3)/1.5)%2==1:p['hands']={}
     p['received_at']=100+t;sample=p;nextinput+=17 if (nextinput//17)%3 else 16
    did=s.tick(sample,{'enabled':True},100+t)
    if did:
     cmdv=np.maximum(cmdv,np.abs(s.vel));cmda=np.maximum(cmda,np.abs(s.vel-lastvel)/.02);lastvel=s.vel.copy()
    e.step()
    if t>=3:
     v=d.qvel[ix].copy();maxv=np.maximum(maxv,np.abs(v))
     if vprev is not None:maxa=np.maximum(maxa,np.abs(v-vprev)/.002)
     vprev=v
     if i%17==0:
      for side in ('left','right'):
       R=d.xmat[m.body(f'{side}_wrist_yaw_link').id].reshape(3,3).copy()
       if side in Rs:jumps.append(float(np.degrees(np.linalg.norm(rotation_error(R,Rs[side])))))
       Rs[side]=R
   out[name]=dict(max_actual_frame_rotation_deg=max(jumps),actual_velocity_max=float(maxv.max()),actual_acceleration_max=float(maxa.max()),actual_velocity_cap_ratio=float(np.max(maxv/s.vmax)),actual_acceleration_cap_ratio=float(np.max(maxa/s.amax)),cmd_velocity_cap_ratio=float(np.max(cmdv/s.vmax)),cmd_acceleration_cap_ratio=float(np.max(cmda/s.amax)),frame_dt_ms=34,n_frames=len(jumps))
   e.close()
 finally:ArmIK.solve=orig;hs.frame=oldframe
 return out
def dynamic_actual():
 e=HumanoidEnv();s=HumanoidServo(e);ix=[e.dadr[n] for n in s.controlled];maxv=np.zeros(len(ix));maxa=maxv.copy();lastv=e.data.qvel[ix].copy();sample=None
 try:
  for i in range(6000):
   t=i*.002
   if i%17==0:
    sample,_=hs.payload(0 if t<3 else 5+t-3);sample['received_at']=100+t
   s.tick(sample,{'enabled':True},100+t);e.step();v=e.data.qvel[ix].copy()
   if t>=3:maxv=np.maximum(maxv,np.abs(v));maxa=np.maximum(maxa,np.abs(v-lastv)/.002)
   lastv=v
  iv=int(np.argmax(maxv/s.vmax));ia=int(np.argmax(maxa/s.amax))
  return dict(velocity_max=float(maxv.max()),acceleration_max=float(maxa.max()),velocity_cap_ratio=float(np.max(maxv/s.vmax)),acceleration_cap_ratio=float(np.max(maxa/s.amax)),worst_velocity_joint=s.controlled[iv],worst_acceleration_joint=s.controlled[ia],physics_dt_ms=2,active_seconds=9)
 finally:e.close()
if __name__=='__main__':print(json.dumps(dict(geometry=geometry(),dropout=dropout(),dynamic_actual=dynamic_actual()),indent=2))