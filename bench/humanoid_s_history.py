"""V-S base_s.py asym exact POSES/pairs, sample schedule; simulated-clock replay."""
import json,numpy as np
from sim.humanoid_env import HumanoidEnv
from sim.humanoid_teleop import HumanoidServo
from tools import humanoid_synth as hs
from bench.humanoid_s_static import POSES
PAIRS=[('fwd90','abd85'),('up120','cross_chest'),('fwd90_el60','hum80'),('fwd45','el90'),('fwd60_el100','abd45'),('rest','fwd90')]
P={n:(fl,ab,el,hu,0.) for n,fl,ab,el,hu in POSES}
def angle(a,b):return float(np.degrees(np.arccos(np.clip(a@b/np.linalg.norm(a)/np.linalg.norm(b),-1,1))))
def run(reset=False,settle=3.2):
 e=HumanoidEnv();s=HumanoidServo(e);old=hs.frame;_,_,f,tor=old(0);wall=0.;sample=None;rows=[]
 def advance(seconds,payload=None):
  nonlocal wall,sample
  nextinput=wall
  for _ in range(round(seconds/.002)):
   if payload is not None and wall>=nextinput-1e-10:
    sample=dict(payload,received_at=100+wall);nextinput+=1/30
   s.tick(sample,{'enabled':True},100+wall);e.step();wall+=.002
 def errors(side,gt,q):
  ik=s.iks[side];d=ik.fk(e.data.qpos,q);S=d.xpos[e.model.body(f'{side}_shoulder_roll_link').id];E=d.site_xpos[ik.site['elbow_site']];W=d.site_xpos[ik.site['wrist_site']]
  return [angle(E-S,np.array(gt[side]['u1'])),angle(W-E,np.array(gt[side]['u2']))]
 try:
  for a,b in PAIRS:
   for left,right in ((a,b),(b,a)):
    hs.frame=lambda _:(True,{'left':P[left],'right':P[right]},f,tor);p,gt=hs.payload(0.)
    if reset:e.reset();s.reset_state();advance(.5)
    advance(settle,p);samples=[]
    for _ in range(8):
     samples.append({z:errors(z,gt,e.q(e.groups[z+'_arm'])) for z in ('left','right')});advance(.1,p)
    row={'left_pose':left,'right_pose':right,'sides':{}}
    for z in ('left','right'):
     ix=[s.index[n] for n in e.groups[z+'_arm']];ik=s.iks[z]
     row['sides'][z]=dict(actual_deg=np.mean([v[z] for v in samples],axis=0).tolist(),ik_deg=errors(z,gt,s.q_ik[z]),cmd_deg=errors(z,gt,s.cmd[ix]),diag=s.diag[z],actual_q=e.q(e.groups[z+'_arm']).tolist(),cmd_q=s.cmd[ix].tolist(),ik_q=s.q_ik[z].tolist(),limit_margin_deg=float(np.degrees(np.min(np.minimum(s.q_ik[z]-ik.lo,ik.hi-s.q_ik[z])))))
    rows.append(row);print(json.dumps(row),flush=True)
  return dict(reset=reset,settle=settle,rows=rows)
 finally:e.close();hs.frame=old
if __name__=='__main__':
 import sys
 reset='--reset' in sys.argv;settle=6. if reset else 3.2
 print('LOAD='+open('/proc/loadavg').read().strip(),flush=True)
 result=run(reset,settle);print('RESULT='+json.dumps(result),flush=True)