import importlib.util,json,math,time,sys
from pathlib import Path
import numpy as np
from sim.humanoid_env import HumanoidEnv
from sim.humanoid_teleop import HumanoidServo
import sim.humanoid_collision as cur
from tools import humanoid_synth as hs
spec=importlib.util.spec_from_file_location('baseline_humanoid_collision','bench/humanoid_s3_out/baseline_humanoid_collision.py'); old=importlib.util.module_from_spec(spec);sys.modules[spec.name]=old;spec.loader.exec_module(old)
FING={s:({k:(.05,.05,.03) for k in ('index','middle','ring','pinky')},(.25,.15,.1),0.) for s in ('left','right')}
def fr(p,t):
 if p=='sweep':
  k=.5-.5*math.cos(2*math.pi*(t%12)/12);a={s:(.4+k,.15-.75*k,.9+.5*k,0,0) for s in ('left','right')};w=(0,0,0)
 elif p=='chest':a={s:(1.2,-1.,1.8,0,0) for s in ('left','right')};w=(0,0,0)
 elif p=='jump':a={s:((1.2,-1.,1.6,0,0) if int(t/.6)%2 else (.15,.15,.35,0,0)) for s in ('left','right')};w=(0,0,0)
 else:a={s:(1.,-.6,1.3,0,0) for s in ('left','right')};w=(.6*math.sin(2*math.pi*t/6),.2*math.sin(2*math.pi*t/4),.15*math.sin(2*math.pi*t/5))
 return True,a,FING,w
def make(use_old):
 saved=(cur.CapsuleModel,cur.CollisionPathMonitor)
 if use_old:cur.CapsuleModel,cur.CollisionPathMonitor=old.CapsuleModel,old.CollisionPathMonitor
 e=HumanoidEnv(320,240,False);s=HumanoidServo(e,50)
 cur.CapsuleModel,cur.CollisionPathMonitor=saved
 return e,s
def run(p,seconds=3):
 eb,sb=make(True);en,sn=make(False);ctrl={'enabled':True,'options':{'collision_avoidance':True,'safety_brake':True,'arm_target':'wrist'}};dt=eb.model.opt.timestep
 nexts=0;sample=None;seq=0;maxq=maxcmd=maxwp=maxpath=0.;mism=[];ticks=0
 hs.frame=lambda t:fr(p,t)
 try:
  for i in range(int(seconds/dt)):
   t=i*dt
   if t+1e-12>=nexts:
    sample,_=hs.payload(t);seq+=1;sample.update(received_at=100+t,seq=seq);nexts+=1/30
   db=sb.tick(sample,ctrl,100+t);dn=sn.tick(sample,ctrl,100+t)
   if db!=dn:mism.append(['did',i,db,dn])
   if db:
    ticks+=1;maxcmd=max(maxcmd,float(np.max(np.abs(sb.cmd-sn.cmd))))
    a=eb.collision_status.get('goal_projection') or {};b=en.collision_status.get('goal_projection') or {}
    for k in ('route','accepted','endpoint_modified'):
     if a.get(k)!=b.get(k):mism.append([k,i,a.get(k),b.get(k)])
    for k in ('path_min','distance','start_gap','first_min','second_min','progress_fraction'):
     if k in a or k in b:
      d=abs(float(a.get(k,999))-float(b.get(k,999)));maxpath=max(maxpath,d)
      if d>1e-9:mism.append([k,i,a.get(k),b.get(k)])
    ga=getattr(eb,'collision_resume_goal',None);gb=getattr(en,'collision_resume_goal',None)
    if ga is not None and gb is not None:maxwp=max(maxwp,float(np.max(np.abs(ga-gb))))
    elif (ga is None)!=(gb is None):mism.append(['goal_none',i,ga is None,gb is None])
   eb.step();en.step();maxq=max(maxq,float(np.max(np.abs(eb.data.qpos-en.data.qpos))))
  return {'pattern':p,'ticks':ticks,'max_qpos_abs':maxq,'max_cmd_abs':maxcmd,'max_waypoint_abs':maxwp,'max_path_diag_abs':maxpath,'mismatches':mism[:20],'mismatch_count':len(mism),'qpos_array_equal':bool(np.array_equal(eb.data.qpos,en.data.qpos)),'cmd_array_equal':bool(np.array_equal(sb.cmd,sn.cmd))}
 finally:eb.close();en.close()
out={p:run(p,float(sys.argv[1]) if len(sys.argv)>1 else 3) for p in ('sweep','chest','jump','twist')}
json.dump(out,open('bench/humanoid_s3_out/equivalence.json','w'),indent=2);print(json.dumps(out,indent=2))
