"""Nonblocking Cartesian hand imitation, simulation only."""
import time
import numpy as np
from sim.ik import arm_indices, _pose_jac, _rotation_error
class TeleopServo:
 def __init__(self,env,status):
  self.status=status; self.ticks=0; self.rebind(env)
 def rebind(self,env):
  self.env=env; self.last=None; self.was=False; self.closed=False
  self.qadr,self.dofs,self.limits=arm_indices(env.model)
  self.command=env.arm_qpos().copy()
 def tick(self):
  now=float(self.env.data.time)
  if self.last is not None and 0<=now-self.last<.019999:return
  dt=min(.1,max(.002,now-self.last)) if self.last is not None else .02; self.last=now; st=self.status
  if not st.get('teleop_enabled',False):
   if self.was:self.env.set_arm_target(np.clip(self.env.arm_qpos(),self.limits[:,0]+.002,self.limits[:,1]-.002))
   self.was=False; return
  if not self.was:self.origin=self.env.ee_pose().copy(); self.command=self.env.arm_qpos().copy(); self.was=True
  sample=st.get('teleop_sample',{}); age=time.time()-sample.get('received_at',0)
  valid=sample.get('detected',False) and 0<=age<=.3; st['teleop_tracking']=bool(valid)
  if not valid:self.command=np.clip(self.env.arm_qpos(),self.limits[:,0]+.002,self.limits[:,1]-.002); self.env.set_arm_target(self.command); return
  neutral=st.get('teleop_neutral')
  if not neutral:st['teleop_neutral']=sample; neutral=sample; self.origin=self.env.ee_pose().copy()
  if st.get('teleop_calibration',0)!=getattr(self,'calibration',None):
   self.calibration=st.get('teleop_calibration',0); self.origin=self.env.ee_pose().copy()
  st['teleop_origin']=self.origin[:3,3].tolist()
  target=self.origin.copy()
  delta=np.array([-(sample['scale']-neutral['scale'])*1.2,(sample['x']-neutral['x'])*.7,-(sample['y']-neutral['y'])*.7])
  target[:3,3]=np.clip(self.origin[:3,3]+delta,[.25,-.35,.36],[.70,.35,.85])
  current=self.env.ee_pose(); J=_pose_jac(self.env.model,self.env.data,'tcp',self.dofs)
  error=np.r_[np.clip(target[:3,3]-current[:3,3],-.05,.05),.35*_rotation_error(target[:3,:3],current[:3,:3])]
  dq=J.T@np.linalg.solve(J@J.T+.04**2*np.eye(6),error*4)
  dq-=.6*self.env.data.qvel[self.dofs]
  q=self.env.arm_qpos(); qnext=np.clip(self.command+np.clip(dq,-.45,.45)*dt,self.limits[:,0]+.002,self.limits[:,1]-.002)
  qnext=np.clip(np.clip(qnext,q-.04,q+.04),self.limits[:,0]+.002,self.limits[:,1]-.002)
  self.command=qnext
  self.env.set_arm_target(qnext)
  self.ticks+=1
  st['teleop_ticks']=self.ticks
  if sample['pinch']<.28:self.closed=True
  elif sample['pinch']>.42:self.closed=False
  self.env.set_gripper(0 if self.closed else .08)
  st['teleop_target']=target[:3,3].round(5).tolist(); st['teleop_closed']=self.closed
