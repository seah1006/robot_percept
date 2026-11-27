import json, sys
import numpy as np
from m2a.sim.g1_manip_env import G1ManipEnv
from m2a.sim.gate_grasp import run_batch
import m2a.sim.gate_grasp as gg
import m2a.sim.g1_manip_env as ge
import m2a.sim.skills as sk
from m2a.common import load_parts
from pathlib import Path
case=sys.argv[1]; profile=case!='baseline'; large=case=='pinch_large'
text=Path(sk.__file__).read_text()
text=text.replace('at = xyz.copy(); at[2] += .003','at = xyz.copy(); at[2] += .003\n        self.events["approach_z"] = [float(at[2] + .072), float(at[2])]')
if profile:
 text=text.replace('q, diag = e.solve_ik(arm, above, R, restarts=2)','offset = R @ np.array([-.020, 0, -.018])\n            at = xyz + [0,0,.003] + offset\n            above = at + [0,0,.072]\n            q, diag = e.solve_ik(arm, above, R, restarts=2)')
 text=text.replace('e.data.ctrl[h] = f * synergy','cmd = f * synergy\n            cmd[:3] = np.clip((f-.52)/.48, 0, 1) * synergy[:3]\n            cmd[1] += sign*.45*(1-np.clip((f-.52)/.48, 0, 1))\n            cmd[5:] = 0\n            e.data.ctrl[h] = cmd')
namespace={'__name__':'m2a.sim.skills_variant','__package__':'m2a.sim'}; exec(compile(text,'skills_variant','exec'),namespace); gg.SkillRunner=namespace['SkillRunner']
if large:
 def load(*a, **kw):
  d=load_parts(*a, **kw); d['parts']['P04']['size']=[.016,.08]; return d
 gg.load_parts=load; ge.load_parts=load
base=G1ManipEnv.in_palm
if case=='pinch_wider':
 def in_palm(self, arm, oid):
  x,y,z=self.palm_relative(arm,oid);y*=1 if arm=='left' else -1
  return .075<=x<=.20 and -.105<=y<=-.008 and abs(z)<=.06
 G1ManipEnv.in_palm=in_palm
with open(f'm2a/notes/wsa_gate_raw/P04_diagnostic_{case}.jsonl','w') as f:
 for row in run_batch(G1ManipEnv(),'P04','P-gate',0,20):
  a=row['arm']; evt=row['events']; p=np.array(evt.get('palm_relative',[0,0,0])); p[1]*=1 if a=='left' else -1
  evt['point_to_nominal_palm_m']=float(np.linalg.norm(p-np.clip(p,[.085,-.09,-.043],[.181,-.008,.043])))
  evt['peak_tip_count']=len(evt.get('peak_fingers',[])); row['diagnostic']=case; row['size']=ge.load_parts()['parts']['P04']['size']; f.write(json.dumps(row)+'\n'); f.flush()
