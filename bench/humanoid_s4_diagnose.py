"""동일 q500Hz bound 비교 + hum80→up120 지연 분리. 외부 측정 락 필요."""
import json,time
from pathlib import Path
import numpy as np
from sim.humanoid_env import HumanoidEnv
import importlib.util,sys
_spec=importlib.util.spec_from_file_location('sim._s4_baseline', 'bench/humanoid_s4_out/ready_r3/baseline_05_teleop.py')
_mod=importlib.util.module_from_spec(_spec);sys.modules[_spec.name]=_mod;_spec.loader.exec_module(_mod)
HumanoidServo=_mod.HumanoidServo
from sim.humanoid_collision import CollisionPathMonitor,MESH_RADII
from bench.humanoid_s4_function import execute
OUT=Path('bench/humanoid_s4_out/round4');OUT.mkdir(exist_ok=True)
def main():
 e=HumanoidEnv();s=HumanoidServo(e);out={'GT_auxiliary':True,'load':Path('/proc/loadavg').read_text()}
 try:
  q=np.load('bench/humanoid_s4_out/ready_r3/twist_1.npz')['qpos']
  replay=[]
  for adaptive in (False,True):
   m=CollisionPathMonitor(e.model,radii=MESH_RADII,adaptive_refresh=adaptive);events=[]
   for i,qi in enumerate(q):
    previous=m.uncertified;d=m.inspect(qi)
    if m.uncertified>previous:events.append(dict(step=i,time_s=i*.002,delta_max_rad=float(np.max(np.abs(qi[m.geometry.qadr]-q[i-1,m.geometry.qadr]))),**d))
   replay.append(dict(adaptive=adaptive,uncertified=m.uncertified,penetrating=m.penetrating,exact_checks=m.exact_checks,min_actual=m.min_actual,events=events))
  out['replay']=replay;print('REPLAY',json.dumps(replay),flush=True)
  out['hum80']=execute(e,s,(.17,1.4,1.1,1.4,0),4.,True)
  out['up120_4s']=execute(e,s,(2.1,.1,.3,0,0),4.,True)
  out['up120_8s']=execute(e,s,(2.1,.1,.3,0,0),4.,True)
  (OUT/'diagnose.json').write_text(json.dumps(out,indent=2));print(json.dumps(out),flush=True)
 finally:e.close()
if __name__=='__main__':main()