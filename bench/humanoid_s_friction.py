"""Ablation of Coulomb friction, not production configuration."""
import json
from bench import humanoid_s_round3 as b
from bench import humanoid_s_round2 as r
Base=b.HumanoidEnv
class NoCoulomb(Base):
 def __init__(self,*a,**kw):
  super().__init__(*a,**kw)
  for group in self.groups.values():
   for name in group:self.model.dof_frictionloss[self.dadr[name]]=0.
if __name__=='__main__':
 out=[]
 for friction,Cls in [('original',Base),('zero',NoCoulomb)]:
  for scale in (.6,.8,1.):
   r.HumanoidEnv=lambda *a,**kw:Cls(*a,setpoint_scale=scale,**kw)
   b.HumanoidEnv=Cls
   row=dict(friction=friction,scale=scale,actual=r.dynamic_actual())
   if friction=='zero':row['latency']=b.latency(scale);row['step_response']=b.step_response(scale)
   out.append(row);print(json.dumps(row),flush=True)
 print('RESULT='+json.dumps(out),flush=True)