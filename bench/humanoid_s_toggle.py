"""V-S exact t5..8 stream window, 500Hz physical velocity differences."""
import json,numpy as np
from sim.humanoid_env import HumanoidEnv
from sim.humanoid_teleop import HumanoidServo
from tools.humanoid_synth import payload
TIMES=(.3,.6,.9,1.2)
def capture(initial,final,toggle,sample_hz=None):
 e=HumanoidEnv(setpoint_scale=.6 if initial else None);s=HumanoidServo(e);ix=[e.dadr[n] for n in s.controlled];qa=[e.qadr[n] for n in s.controlled];vprev=e.data.qvel[ix].copy();rows=[];sample=None;next_sample=0.
 try:
  for i in range(1500):
   t=i*.002;mode=final if t>=toggle else initial
   if (sample_hz is None and i%17==0) or (sample_hz is not None and t>=next_sample-1e-10):
    sample,_=payload(5+t);sample['received_at']=100+t
    if sample_hz is not None:next_sample+=1/sample_hz
   s.tick(sample,{'enabled':True,'options':{'safety_brake':mode}},100+t);e.step();v=e.data.qvel[ix].copy();a=(v-vprev)/.002;vprev=v
   rows.append((t,v.copy(),a,e.data.qpos[qa].copy(),e.data.ctrl[[e.act[n] for n in s.controlled]].copy(),s.des.copy(),e.data.qacc[ix].copy()))
  return rows,s.vmax.copy(),s.amax.copy(),s.controlled,dict(sample_hz=sample_hz or (1/.034),catchup_s=e.brake_catchup_s,still_catching_up=e._brake_transition is not None,final_goal_error_rad=float(np.max(np.abs(e.data.ctrl-e._fast_goal))))
 finally:e.close()
def summarize(data,toggle):
 rows,vmax,amax,names,meta=data;post=[r for r in rows if r[0]>=toggle];v=np.array([r[1] for r in post]);a=np.array([r[2] for r in post]);q=np.array([r[3] for r in post]);stride=17
 env=np.max(np.abs(v)/vmax,axis=1);peak=int(np.argmax(env));mono=bool(np.all(np.diff(env[peak:])<=.005))
 return dict(toggle_s=toggle,v_ratio=float(np.max(np.abs(v)/vmax)),a_ratio=float(np.max(np.abs(a)/amax)),worst_v=names[int(np.argmax(np.max(np.abs(v),axis=0)/vmax))],worst_a=names[int(np.argmax(np.max(np.abs(a),axis=0)/amax))],max_frame_dq_deg=float(np.degrees(np.max(np.abs(q[stride:]-q[:-stride])))),monotone_after_peak_tol005=mono,**meta)
if __name__=='__main__':
 print('LOAD='+open('/proc/loadavg').read().strip(),flush=True)
 off=capture(False,False,99);on=capture(True,True,99)
 for t in TIMES:
  control=summarize(off,t);print(json.dumps(dict(case='off_control',**control)),flush=True)
  print(json.dumps(dict(case='on_control',**summarize(on,t))),flush=True)
  for repeat in range(2):
   for initial,final,label in ((True,False,'on_to_off'),(False,True,'off_to_on')):
    result=summarize(capture(initial,final,t),t)
    result.update(speed_vs_off=result['v_ratio']/control['v_ratio'],dq_vs_off=result['max_frame_dq_deg']/control['max_frame_dq_deg'])
    result['pass']=bool(result['a_ratio']<=1) if final else bool(result['speed_vs_off']<=1.1 and result['dq_vs_off']<=1.1)
    print(json.dumps(dict(case=label,repeat=repeat,**result)),flush=True)