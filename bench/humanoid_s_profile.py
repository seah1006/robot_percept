import json,time,numpy as np
from pathlib import Path
from sim.humanoid_env import HumanoidEnv
from sim.humanoid_teleop import HumanoidServo
from tools.humanoid_synth import payload

def main(tag):
 e=HumanoidEnv();s=HumanoidServo(e);sample=None;nextinput=0.;rows=[]
 for i in range(11000):
  t=i*.002
  if t>=nextinput-1e-9:sample,_=payload(t%20);sample['received_at']=100+t;nextinput+=1/30
  did=s.tick(sample,{'enabled':True,'options':{'collision_avoidance':True}},100+t);e.step()
  if did:rows.append(dict(t=t,latched=e.collision_braking,**s.profile))
 out=dict(load=open('/proc/loadavg').read().strip(),tag=tag,rows=len(rows),summary={})
 for kind,selected in [('all',rows),('latched',[r for r in rows if r['latched']]),('moving',[r for r in rows if not r['latched']])]:
  out['summary'][kind]={key:dict(p50=float(np.percentile([r.get(key,0) for r in selected],50)),p95=float(np.percentile([r.get(key,0) for r in selected],95)),max=float(max(r.get(key,0) for r in selected))) for key in ('total_ms','ik_ms','retarget_ms','projection_ms','brake_ms','integration_ms','ik_fk_calls','projection_fk_calls')} if selected else {}
 Path(f'bench/humanoid_s_out/profile_{tag}.json').write_text(json.dumps(out,indent=2));print(json.dumps(out),flush=True);e.close()
if __name__=='__main__':
 import sys;main(sys.argv[1] if len(sys.argv)>1 else 'before')