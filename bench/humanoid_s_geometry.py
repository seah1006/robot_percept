"""A1 robot-FK reachable targets vs human synthetic targets, GT auxiliary."""
import json
import numpy as np
from sim.humanoid_env import HumanoidEnv
from sim.humanoid_teleop import HumanoidServo
from sim.humanoid_ik import ArmIK
from tools.humanoid_synth import payload

def main():
 e=HumanoidEnv();s=HumanoidServo(e);out=[]
 try:
  for t in (0.,4.,6.5,7.5,9.5,12.5):
   p,_=payload(t)
   for _ in range(20):s._retarget(p)
   for side in ('left','right'):
    ik=s.iks[side];d=ik.fk(e.data.qpos,s.q_ik[side]);R=d.xmat[s.torso_body].reshape(3,3);pt=d.xpos[s.torso_body]
    shoulder=R.T@(d.xpos[e.model.body(f'{side}_shoulder_roll_link').id]-pt)
    out.append(dict(t=t,side=side,shoulder_drift_mm=round(float(np.linalg.norm(shoulder-s.geom[side]['S']))*1000,3),limit_margin_deg=round(float(np.degrees(np.min(np.minimum(s.q_ik[side]-ik.lo,ik.hi-s.q_ik[side])))),2),**s.diag[side]))
  reachable=[]
  for side in ('left','right'):
   ik=ArmIK(e.model,side,rest=s.iks[side].rest);sign=1 if side=='left' else -1
   for pitch in (-.2,-.9,-1.57,-2.4):
    qgt=np.array([pitch,sign*.2,sign*.3,.8,sign*.1,.1,sign*.2]);d=ik.fk(e.data.qpos,qgt)
    p=d.site_xpos[ik.site['wrist_site']].copy();el=d.site_xpos[ik.site['elbow_site']].copy();rot=d.xmat[ik.hand_body].reshape(3,3).copy();q=ik.rest.copy()
    for _ in range(20):q,dg=ik.solve(e.data.qpos,q,p,rot,el,iters=8)
    reachable.append(dict(side=side,pitch=pitch,**dg))
  print(json.dumps(dict(synthetic=out,robot_fk_gt=reachable),indent=2))
 finally:e.close()
if __name__=='__main__':main()