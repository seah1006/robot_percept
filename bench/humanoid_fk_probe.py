"""Compare FK directions to synthetic GT; GT-assisted diagnostic, not camera accuracy."""
import time,json,os,numpy as np
from sim.humanoid_env import HumanoidEnv
from sim.humanoid_teleop import HumanoidServo
from sim.humanoid_retarget import B_CAM,arm_directions,torso_frame
from tools.humanoid_synth import payload

def run():
 env=HumanoidEnv();servo=HumanoidServo(env);sample,gt=payload(7)
 for ik in servo.iks.values():ik.w_elbow=float(os.getenv('W_ELBOW','.35'));ik.w_rot=float(os.getenv('W_ROT','.25'))
 for t in np.arange(0,7.001,1/30):
  sample,gt=payload(float(t));sample['received_at']=time.time();servo._retarget(sample)
 result={}
 for side in ['left','right']:
  ik=servo.iks[side];d=ik.fk(env.data.qpos.copy(),servo.q_ik[side]);m=env.model
  S=d.xpos[m.body(f'{side}_shoulder_roll_link').id];E=d.site_xpos[m.site(f'{side}_elbow_site').id];W=d.site_xpos[m.site(f'{side}_wrist_site').id]
  u1=(E-S)/np.linalg.norm(E-S);u2=(W-E)/np.linalg.norm(W-E)
  result[side]={'q_deg':np.degrees(servo.q_ik[side]).tolist(),'fk_flex_deg':float(np.degrees(np.arctan2(u1[0],-u1[2]))),'u1_error_deg':float(np.degrees(np.arccos(np.clip(u1@np.array(gt[side]['u1']),-1,1)))),'u2_error_deg':float(np.degrees(np.arccos(np.clip(u2@np.array(gt[side]['u2']),-1,1)))),'ik':servo.diag[side]}
 print(json.dumps(result));env.close()
if __name__=='__main__':run()
