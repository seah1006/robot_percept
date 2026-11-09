"""c5 검증, 외부 measure→gpu 락. 각 프로세스/블롭 분리."""
import os,sys,subprocess
from pathlib import Path
OUT=Path('bench/humanoid_s4_out/c5');OUT.mkdir(exist_ok=True)
env=dict(os.environ,OUTD=str(OUT))
def measure(pattern):
 subprocess.run([sys.executable,'bench/humanoid_s4_c5_inproc.py',pattern,'1','c5_'+pattern,'24'],env=env,check=True)
if __name__=='__main__':
 measure('jump')
 with (OUT/'pytest.txt').open('w') as log:subprocess.run([sys.executable,'-m','pytest','-q'],stdout=log,stderr=subprocess.STDOUT,check=False)
 for pattern in ('chest','sweep','twist'):measure(pattern)
 from bench.humanoid_s4_final import main
 # Do not invoke main(): it would start a second render matrix. Static-only pass below.
 from bench.humanoid_s4_function import execute
 from bench.humanoid_s2_static_split import POSES
 from sim.humanoid_env import HumanoidEnv
 from sim.humanoid_teleop import HumanoidServo
 import json
 e=HumanoidEnv();s=HumanoidServo(e);rows=[]
 try:
  for name,fl,ab,el,hu in POSES:
   row=execute(e,s,(fl,ab,el,hu,0),4.,True);row['pose']=name;rows.append(row)
 finally:e.close()
 e=HumanoidEnv();s=HumanoidServo(e)
 try:
  execute(e,s,(1.2,-1.,1.8,0,0),3.,True);release=execute(e,s,(.05,.8,.1,0,0),8.,True)
 finally:e.close()
 (OUT/'function.json').write_text(json.dumps(dict(GT_auxiliary=True,cases=rows,release=release),indent=2))