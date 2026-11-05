import json,time,pathlib,hashlib,os
from bench.humanoid_s_round3 import step_response
from sim.humanoid_teleop import TELEOP_VEL,TELEOP_ACC
root=pathlib.Path(__file__).resolve().parents[1]
out={'definition':'production default scale=None, bilateral synthetic flex .3->1.2rad after 3s settling, 2ms physics, sample every34ms; command/actual right shoulder pitch 10%-90% relative to actual start and final desired joint angle; simulation-time response not wall-time software latency','response':step_response(None),'velocity_caps':TELEOP_VEL,'acceleration_caps':TELEOP_ACC,'load':os.getloadavg(),'source_sha':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in ['sim/humanoid_env.py','sim/humanoid_teleop.py']}}
print(json.dumps(out,ensure_ascii=False))