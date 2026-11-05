"""Same-time reference/actual acceleration comparison, no performance metrics."""
import json,numpy as np
from sim.humanoid_env import HumanoidEnv,TELEOP_ACC
from sim.humanoid_teleop import HumanoidServo
from tools.humanoid_synth import payload
from bench.humanoid_s_spectrum import peaks

def run():
 e=HumanoidEnv(setpoint_scale=.6);s=HumanoidServo(e);n='right_wrist_roll_joint';j=e.dadr[n];a=e.act[n];qa=e.qadr[n];dt=.002;rows=[];sample=None
 try:
  for i in range(6000):
   t=i*dt
   if i%17==0:sample,_=payload(0 if t<3 else 5+t-3);sample['received_at']=100+t
   s.tick(sample,{'enabled':True},100+t);e.step()
   rows.append([t,e.data.ctrl[a],e.data.qpos[qa],e.data.qvel[j],e.setpoint.acceleration[a],e.data.qacc[j],e.data.actuator_force[a],e.data.qfrc_constraint[j],e.data.qfrc_bias[j],e.data.qfrc_applied[j]])
  r=np.array(rows);ref_acc=(r[2:,1]-2*r[1:-1,1]+r[:-2,1])/dt**2;actual_acc=np.diff(r[:,3])/dt
  # Ref 2nd difference centered at t_i; actual velocity difference centered half a step.
  valid=np.where(r[1:,0]>=3)[0];k=int(valid[np.argmax(np.abs(actual_acc[valid]))])+1
  table=[]
  for i in range(k-10,k+11,2):
   table.append(dict(t=float(r[i,0]),ref_q=float(r[i,1]),actual_q=float(r[i,2]),error_q=float(r[i,1]-r[i,2]),ref_second_difference=float(ref_acc[i-1]),reference_acceleration_state=float(r[i,4]),actual_velocity_difference=float(actual_acc[i-1]),actual_qacc=float(r[i,5]),actuator_torque=float(r[i,6]),constraint_torque=float(r[i,7])))
  jid=e.model.joint(n).id;ix=valid+1;ix=ix[ix<len(r)-1]
  np.savez('/tmp/humanoid_s_alignment.npz',rows=r,reference_second_difference=ref_acc,actual_velocity_difference=actual_acc)
  return dict(load=open('/proc/loadavg').read().strip(),joint=n,dof_index=j,actuator_index=a,cap=TELEOP_ACC['wrist'],scaled_reference_cap=float(e.setpoint.amax[a]),ref_state_max=float(np.max(np.abs(r[ix,4]))),ref_second_difference_max=float(np.max(np.abs(ref_acc[ix-1]))),actual_fd_max=float(np.max(np.abs(actual_acc[ix-1]))),reference_joint_range=e.model.jnt_range[jid].tolist(),ref_position_range=[float(r[ix,1].min()),float(r[ix,1].max())],actual_position_range=[float(r[ix,2].min()),float(r[ix,2].max())],max_error_rad=float(np.max(np.abs(r[ix,1]-r[ix,2]))),error_fft=peaks(r[ix,1]-r[ix,2]),max_constraint_torque=float(np.max(np.abs(r[ix,7]))),peak_table=table)
 finally:e.close()
if __name__=='__main__':print(json.dumps(run(),indent=2))