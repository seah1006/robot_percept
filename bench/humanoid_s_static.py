"""Independent pose list compatibility check, synthetic GT auxiliary."""
import json,numpy as np
from sim.humanoid_env import HumanoidEnv
from sim.humanoid_teleop import HumanoidServo
from tools import humanoid_synth as hs
POSES=[('rest',.15,.15,.35,0),('abd45',.05,.8,.1,0),('abd85',.05,1.48,.1,0),('fwd45',.8,.1,.1,0),('fwd90',1.57,.1,.1,0),('fwd90_el60',1.57,.1,1.05,0),('el90',.3,.15,1.57,0),('fwd60_el100',1.,.2,1.75,0),('abd60_el90',.1,1.05,1.57,0),('cross_chest',1.,-.35,1.2,0),('hum80',.17,1.4,1.1,1.4),('up120',2.1,.1,.3,0)]
def run():
 e=HumanoidEnv();s=HumanoidServo(e);old=hs.frame;rows=[];_,_,fingers,tor=old(0)
 try:
  for name,fl,ab,el,hu in POSES:
   hs.frame=lambda t:(True,{z:(fl,ab,el,hu,0) for z in ('left','right')},fingers,tor)
   p,gt=hs.payload(0)
   for z in ('left','right'):s.q_ik[z]=s.iks[z].rest.copy()
   for _ in range(30):s._retarget(p)
   row={'pose':name}
   for z in ('left','right'):
    ik=s.iks[z];d=ik.fk(e.data.qpos,s.q_ik[z]);R=d.xmat[s.torso_body].reshape(3,3)
    S=d.xpos[e.model.body(f'{z}_shoulder_roll_link').id];E=d.site_xpos[ik.site['elbow_site']];W=d.site_xpos[ik.site['wrist_site']]
    a=[]
    for v,k in ((E-S,'u1'),(W-E,'u2')):
     v=R.T@v;u=np.array(gt[z][k]);a.append(float(np.degrees(np.arccos(np.clip(v@u/np.linalg.norm(v)/np.linalg.norm(u),-1,1)))))
    row[z]=dict(u1_deg=a[0],u2_deg=a[1],wrist_mm=s.diag[z]['pos_err_mm'],limit_margin_deg=float(np.degrees(np.min(np.minimum(s.q_ik[z]-ik.lo,ik.hi-s.q_ik[z])))))
   rows.append(row)
  mx={k:max(r[z][k] for r in rows for z in ('left','right')) for k in ('u1_deg','u2_deg','wrist_mm')}
  mx['lr_diff_deg']=max(abs(r['left'][k]-r['right'][k]) for r in rows for k in ('u1_deg','u2_deg'))
  print(json.dumps(dict(rows=rows,max=mx),indent=2))
 finally:e.close();hs.frame=old
if __name__=='__main__':run()