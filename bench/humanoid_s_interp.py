"""Experiment only. No production env/worker change. Actual q cap comparison."""
import json,numpy as np
from bench import humanoid_s_round2 as r2
Base=r2.HumanoidEnv
class InterpolatedEnv(Base):
 def __init__(self,*a,**k):
  super().__init__(*a,**k);self.start=self.data.ctrl.copy();self.end=self.start.copy();self.t0=self.data.time
 def set_targets(self,qd):
  self.start=self.data.ctrl.copy();super().set_targets(qd);self.end=self.data.ctrl.copy();self.data.ctrl[:]=self.start;self.t0=self.data.time
 def step(self,n=1):
  for _ in range(n):
   a=np.clip((self.data.time+self.model.opt.timestep-self.t0)/.02,0,1)
   self.data.ctrl[:]=self.start+a*(self.end-self.start)
   super().step(1)
if __name__=='__main__':
 r2.HumanoidEnv=InterpolatedEnv
 print(json.dumps(dict(interpolation_ms=20,actual=r2.dynamic_actual(),note='Additional target ramp horizon20ms. Motion-response lag not yet measured.'),indent=2))