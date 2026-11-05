"""Physics-frequency diagnostic, 500Hz velocity finite differences unchanged."""
import json,numpy as np,mujoco
from sim.humanoid_env import HumanoidEnv
from sim.humanoid_teleop import HumanoidServo
from tools.humanoid_synth import payload

def peaks(x,dt=.002,low=1.,upper=250.):
 x=np.asarray(x);x=x-x.mean();power=np.abs(np.fft.rfft(x*np.hanning(len(x))))**2;f=np.fft.rfftfreq(len(x),dt)
 valid=np.where((f>=low)&(f<=upper))[0];best=valid[np.argsort(power[valid])[-5:][::-1]]
 return [{'hz':float(f[i]),'power_fraction':float(power[i]/max(power.sum(),1e-20))} for i in best]
def matrix(m,d):
 M=np.zeros((m.nv,m.nv))
 try:mujoco.mj_fullM(m,d,M)
 except TypeError:mujoco.mj_fullM(m,M,d.qM)
 return M

def run(scale):
 e=HumanoidEnv(setpoint_scale=scale);s=HumanoidServo(e);m=e.model;d=e.data;names=['right_wrist_roll_joint','right_shoulder_yaw_joint'];ids=[e.dadr[n] for n in names];aids=[e.act[n] for n in names];velprev=d.qvel[ids].copy();rows=[];peak=0;peakq=None;sample=None
 try:
  for i in range(6000):
   t=i*.002
   if i%17==0:sample,_=payload(0 if t<3 else 5+t-3);sample['received_at']=100+t
   s.tick(sample,{'enabled':True},100+t);e.step();vel=d.qvel[ids].copy();fd=(vel-velprev)/.002;velprev=vel
   if t>=3:
    ref=np.zeros(2) if e.setpoint is None else e.setpoint.acceleration[aids].copy()
    rows.append([t,*fd,*d.qacc[ids],*ref,*d.actuator_force[aids]])
    if abs(fd[0])>peak:peak=abs(fd[0]);peakq=d.qpos.copy();peakt=t
  a=np.array(rows);out=[]
  # Rest/peak mass and damping: coordinate diagonal and coupled effective inertia.
  datas=[]
  for name,q in [('rest',None),('peak',peakq)]:
   dd=mujoco.MjData(m)
   if q is None:
    e2=e.data.qpos.copy();e.reset();q=e.data.qpos.copy();e.data.qpos[:]=e2
   dd.qpos[:]=q;mujoco.mj_forward(m,dd);M=matrix(m,dd);inv=np.linalg.inv(M)
   for n,j,aid in zip(names,ids,aids):
    I=float(M[j,j]);Ieff=float(1/inv[j,j]);kp=float(m.actuator_gainprm[aid,0]);kv=float(-m.actuator_biasprm[aid,2]);wn=np.sqrt(kp/I);wne=np.sqrt(kp/Ieff)
    datas.append(dict(configuration=name,joint=n,mass_diagonal=I,effective_inertia=Ieff,armature=float(m.dof_armature[j]),kp=kp,kv=kv,natural_hz=float(wn/(2*np.pi)),coupled_natural_hz=float(wne/(2*np.pi)),wn_dt=float(wn*.002),damping_ratio=float(kv/(2*np.sqrt(kp*I)))))
  for k,n in enumerate(names):
   x=a[:,1+k];qacc=a[:,3+k];ref=a[:,5+k]
   high=np.fft.rfftfreq(len(x),.002);power=np.abs(np.fft.rfft((x-x.mean())*np.hanning(len(x))))**2
   out.append(dict(joint=n,fd_max=float(np.max(np.abs(x))),qacc_max=float(np.max(np.abs(qacc))),fd_qacc_rmse=float(np.sqrt(np.mean((x-qacc)**2))),reference_acceleration_max=float(np.max(np.abs(ref))),dominant_fft=peaks(x),residual_fft=peaks(x-ref),high_band_fft=peaks(x,.002,10,100),peak_local_fft=peaks(x[max(0,int((peakt-3)/.002)-125):min(len(x),int((peakt-3)/.002)+125)]),power_above_100hz=float(power[high>100].sum()/power.sum())))
  return dict(scale=scale,physics_dt_ms=2,nyquist_hz=250,peak_wrist_time=peakt,inertia=datas,signals=out)
 finally:e.close()
if __name__=='__main__':
 for scale in (None,.6):print(json.dumps(run(scale)),flush=True)