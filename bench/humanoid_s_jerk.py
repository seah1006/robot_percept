"""Bounded jerk sensitivity sweep, no friction/damping changes."""
import json
from bench import humanoid_s_round2 as r
from bench import humanoid_s_round3 as b
Base=b.HumanoidEnv
if __name__=='__main__':
 out=[]
 for jerk_factor in (.2,.1):
  for scale in (.6,.8,1.):
   class E(Base):
    def __init__(self,*a,**kw):
     super().__init__(*a,**kw)
     if self.setpoint is not None:self.setpoint.jmax*=jerk_factor
   r.HumanoidEnv=lambda *a,**kw:E(*a,setpoint_scale=scale,**kw)
   b.HumanoidEnv=E
   row=dict(jerk_factor=jerk_factor,scale=scale,actual=r.dynamic_actual())
   if row['actual']['velocity_cap_ratio']<=1 and row['actual']['acceleration_cap_ratio']<=1:
    row['latency']=b.latency(scale);row['step_response']=b.step_response(scale)
   out.append(row);print(json.dumps(row),flush=True)
 print('RESULT='+json.dumps(out),flush=True)