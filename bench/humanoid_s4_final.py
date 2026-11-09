"""cap .04 최종 ON12자세+release+4패턴. 안전 PASS일때만 30fps4창. measure→GPU 외부락."""
import json
from pathlib import Path
from sim.humanoid_env import HumanoidEnv
from sim.humanoid_teleop import HumanoidServo
from bench.humanoid_s2_static_split import POSES
from bench.humanoid_s4_function import execute
from bench.humanoid_s4_async import main as dynamic
from bench.humanoid_s4_render30 import main as render
OUT=Path('bench/humanoid_s4_out/round5');OUT.mkdir(exist_ok=True)
def main():
 e=HumanoidEnv();s=HumanoidServo(e);result={'GT_auxiliary':True,'cases':[]}
 try:
  for name,fl,ab,el,hu in POSES:
   row=execute(e,s,(fl,ab,el,hu,0),4.,True);row.update(pose=name,enabled=True);result['cases'].append(row)
   (OUT/'function_final.json').write_text(json.dumps(result,indent=2));print('STATIC',name,max(row['final_errors_deg']),flush=True)
 finally:e.close()
 e=HumanoidEnv();s=HumanoidServo(e)
 try:
  execute(e,s,(1.2,-1.,1.8,0,0),3.,True)
  result['release']=execute(e,s,(.05,.8,.1,0,0),8.,True)
 finally:e.close()
 (OUT/'function_final.json').write_text(json.dumps(result,indent=2))
 dynamic();data=json.loads(Path('bench/humanoid_s4_out/async.json').read_text());(OUT/'async_final.json').write_text(json.dumps(data,indent=2))
 unsafe=any(r['enabled'] and (r['actual'].get('penetration_checks',0)>0 or r['actual'].get('uncertified_intervals',0)>0) for r in data['cases'])
 if unsafe:
  (OUT/'render_blocked.txt').write_text('안전 gate FAIL: 침투/미인증 존재. 30fps 측정 생략, 기본OFF.');print('RENDER_BLOCKED_UNSAFE',flush=True)
 else:render()
if __name__=='__main__':main()