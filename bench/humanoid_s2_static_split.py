"""P1c static 12-pose history vs rest-seed split. Synthetic GT auxiliary."""
import json, time
from pathlib import Path
import numpy as np
from sim.humanoid_env import HumanoidEnv
from sim.humanoid_teleop import HumanoidServo
from sim.humanoid_collision import CapsuleModel, MESH_RADII
from tools import humanoid_synth as hs

POSES=[("rest",.15,.15,.35,0),("abd45",.05,.8,.1,0),("abd85",.05,1.48,.1,0),("fwd45",.8,.1,.1,0),("fwd90",1.57,.1,.1,0),("fwd90_el60",1.57,.1,1.05,0),("el90",.3,.15,1.57,0),("fwd60_el100",1.,.2,1.75,0),("abd60_el90",.1,1.05,1.57,0),("cross_chest",1.,-.35,1.2,0),("hum80",.17,1.4,1.1,1.4),("up120",2.1,.1,.3,0)]

def angle(a,b):
 a=np.asarray(a);b=np.asarray(b);return float(np.degrees(np.arccos(np.clip(a@b/max(np.linalg.norm(a)*np.linalg.norm(b),1e-12),-1,1))))

def measure(enabled, reset_each):
 e=HumanoidEnv();s=HumanoidServo(e);proxy=CapsuleModel(e.model,MESH_RADII);old=hs.frame;_,_,fingers,tor=old(0);rows=[]
 try:
  for name,fl,ab,el,hu in POSES:
   if reset_each:
    e.reset();s.reset_state()
   hs.frame=lambda t,fl=fl,ab=ab,el=el,hu=hu:(True,{z:(fl,ab,el,hu,0) for z in ("left","right")},fingers,tor)
   payload,gt=hs.payload(0);next_sample=0.;sample=None;tail=[];holding=0
   for i in range(2000):
    t=i*.002
    if t>=next_sample-1e-12:
     sample,_=hs.payload(0);sample["received_at"]=100+t;next_sample+=1/30
    if s.tick(sample,{"enabled":True,"options":{"collision_avoidance":enabled}},100+t):
     holding+=int(getattr(e,"collision_braking",False))
    e.step()
    if i>=1600:tail.append(e.data.qpos.copy())
   q=np.mean(tail,axis=0);proxy.forward(q);gap=min(r["distance"] for r in proxy.distances())
   row={"pose":name,"clearance_mm":gap*1000,"holding_ticks":holding,"state":e.collision_status.get("collision_state","clear"),"plan":{k:v for k,v in (e.collision_plan or {}).items() if isinstance(v,(str,bool,int,float))},"brake":e.collision_status.get("brake")}
   for z in ("left","right"):
    ik=s.iks[z];d=ik.fk(q,q[ik.qadr]);R=d.xmat[s.torso_body].reshape(3,3);S=d.xpos[e.model.body(f"{z}_shoulder_roll_link").id];E=d.site_xpos[ik.site["elbow_site"]];W=d.site_xpos[ik.site["wrist_site"]]
    row[z]={"u1_deg":angle(R.T@(E-S),gt[z]["u1"]),"u2_deg":angle(R.T@(W-E),gt[z]["u2"])}
   rows.append(row)
  vals=[r[z][k] for r in rows for z in ("left","right") for k in ("u1_deg","u2_deg")]
  safe=[r for r in rows if r["pose"] in ("fwd45","fwd90","fwd60_el100","up120")]
  return {"enabled":enabled,"reset_each":reset_each,"rows":rows,"max_dir_deg":max(vals),"mean_dir_deg":float(np.mean(vals)),"safe4_mean_dir_deg":float(np.mean([r[z][k] for r in safe for z in ("left","right") for k in ("u1_deg","u2_deg")])),"holding_ticks":sum(r["holding_ticks"] for r in rows)}
 finally:
  hs.frame=old;e.close()

def main():
 t=time.perf_counter();out={"note":"synthetic GT auxiliary; MESH capsule proxy, not physical safety certification","load0":Path("/proc/loadavg").read_text().strip(),"cases":[]}
 for enabled in (False,True):
  for reset_each in (False,True):out["cases"].append(measure(enabled,reset_each))
 out["elapsed_s"]=time.perf_counter()-t;out["load1"]=Path("/proc/loadavg").read_text().strip()
 p=Path("bench/humanoid_s2_out/static_split_round0.json");p.write_text(json.dumps(out,indent=2));print(json.dumps(out))
if __name__=="__main__":main()
