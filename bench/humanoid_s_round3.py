"""P1b physics-step setpoint sweep. Run under /tmp/rp_measure.lock."""
import json,time,copy,numpy as np
from sim.humanoid_env import HumanoidEnv
from sim.humanoid_teleop import HumanoidServo
from tools import humanoid_synth as hs
from bench import humanoid_s_round2 as r2

def lag(reference,actual,dt):
 reference=np.asarray(reference);actual=np.asarray(actual)
 maxlag=int(.8/dt);scores=[]
 for k in range(maxlag):
  x=reference[:len(reference)-k or None];y=actual[k:]
  x=x-x.mean();y=y-y.mean();scores.append(float(x@y/(np.linalg.norm(x)*np.linalg.norm(y)+1e-12)))
 return int(np.argmax(scores))*dt*1000

def latency(scale):
 e=HumanoidEnv(setpoint_scale=scale);s=HumanoidServo(e);old=hs.frame;_,_,fingers,torso=old(0);rows=[];sample=None;nextsample=0.;ticks=[]
 try:
  for i in range(7000):
   t=i*.002
   if t>=nextsample:
    flex=.8+.25*np.sin(2*np.pi*.35*t)
    hs.frame=lambda _: (True,{z:(flex,.2,1.,0,0) for z in ('left','right')},fingers,torso)
    sample,_=hs.payload(0);sample['received_at']=100+t;nextsample+=1/30
   t0=time.perf_counter();did=s.tick(sample,{'enabled':True},100+t)
   if did:ticks.append((time.perf_counter()-t0)*1000)
   e.step()
   if t>=3 and 'right' in s.targets_world:
    rows.append([s.des[s.index['right_shoulder_pitch_joint']],e.data.qpos[e.qadr['right_shoulder_pitch_joint']],s.targets_world['right']['wrist'][0],e.data.site_xpos[e.model.site('right_wrist_site').id][0]])
  a=np.array(rows);windows=[]
  for begin in range(0,len(a)-2000,250):windows.append(lag(a[begin:begin+2000,2],a[begin:begin+2000,3],.002))
  return dict(command_to_actual_phase_ms=lag(a[:,0],a[:,1],.002),input_to_wrist_p50_ms=float(np.percentile(windows,50)),input_to_wrist_p95_ms=float(np.percentile(windows,95)),tick_p95_ms=float(np.percentile(ticks,95)),method='0.35Hz sinusoid; x-position cross-correlation,4s windows/0.5s stride; offline receive-to-actual, not capture/network latency')
 finally:e.close();hs.frame=old

def step_response(scale):
 e=HumanoidEnv(setpoint_scale=scale);s=HumanoidServo(e);old=hs.frame;_,_,f,tor=old(0);rows=[];sample=None
 try:
  for i in range(5000):
   t=i*.002
   if i%17==0:
    fl=.3 if t<3 else 1.2
    hs.frame=lambda _:(True,{z:(fl,.2,1.,0,0) for z in ('left','right')},f,tor)
    sample,_=hs.payload(0);sample['received_at']=100+t
   s.tick(sample,{'enabled':True},100+t);e.step()
   rows.append((t,s.cmd[s.index['right_shoulder_pitch_joint']],e.data.qpos[e.qadr['right_shoulder_pitch_joint']],s.des[s.index['right_shoulder_pitch_joint']]))
  a=np.array(rows);target=a[-1,3];start=a[1499,2];amp=target-start;out={'joint':'right_shoulder_pitch_joint','target_step_rad':float(amp)}
  for col,name in ((1,'command'),(2,'actual')):
   frac=(a[:,col]-start)/amp;vals=[]
   for level in (.1,.9):
    hit=np.where((a[:,0]>=3)&(frac>=level))[0];vals.append(None if not len(hit) else float((a[hit[0],0]-3)*1000))
   out[name+'_t10_ms'],out[name+'_t90_ms']=vals
   out[name+'_10_90_ms']=None if None in vals else vals[1]-vals[0]
  return out
 finally:e.close();hs.frame=old
def recovery():
 out={};good,_=hs.payload(12.)
 cases={}
 zero=copy.deepcopy(good);zero['pose']=[[0,0,0,.95] for _ in range(33)];zero['hands']={};cases['zeros']=zero
 col=copy.deepcopy(good);col['pose']=[[i*.01,i*.01,i*.01,.95] for i in range(33)];col['hands']={};cases['collinear']=col
 arm=copy.deepcopy(good);arm['pose'][13][:3]=arm['pose'][11][:3];arm['pose'][15][:3]=arm['pose'][11][:3];cases['zero_arm_len']=arm
 hand=copy.deepcopy(good);hand['hands']={z:[[0.,0.,0.]]*21 for z in ('left','right')};cases['hand_degenerate']=hand
 for name,bad in [('control',good),*cases.items()]:
  e=HumanoidEnv();s=HumanoidServo(e)
  try:
   for i in range(2750):
    t=i*.002;p=copy.deepcopy(good if t<3 or t>=3.5 else bad);p['received_at']=100+t
    s.tick(p,{'enabled':True},100+t);e.step()
   # Compare recovered FK with control, independent of target orientation convention.
   S=e.data.xpos[e.model.body('left_shoulder_roll_link').id];E=e.data.site_xpos[e.model.site('left_elbow_site').id]
   out[name]=dict(u1=((E-S)/np.linalg.norm(E-S)).tolist(),finite=bool(np.isfinite(e.data.qpos).all()))
  finally:e.close()
 ref=np.array(out['control']['u1'])
 for row in out.values():row['recovery_delta_deg']=float(np.degrees(np.arccos(np.clip(ref@row['u1'],-1,1))))
 return out
if __name__=='__main__':
 result={'load':open('/proc/loadavg').read().strip(),'settings':[]}
 Base=r2.HumanoidEnv
 for scale in (None,.6,.8,1.):
  r2.HumanoidEnv=lambda *a,**k:Base(*a,setpoint_scale=scale,**k)
  metrics=r2.dynamic_actual();metrics.update(latency(scale));metrics['step_response']=step_response(scale);result['settings'].append(dict(scale=scale,**metrics));print(json.dumps(result['settings'][-1]),flush=True)
 r2.HumanoidEnv=Base;result['recovery']=recovery()
 print('RESULT='+json.dumps(result),flush=True)