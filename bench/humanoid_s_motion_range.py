import json,numpy as np
from pathlib import Path
from sim.humanoid_env import HumanoidEnv
p=Path('bench/humanoid_s_out');q=np.load(p/'20261105_collision_runtime_path.npz')['qpos'];np.savez_compressed(p/'20261105_directional_runtime_path.npz',qpos=q)
e=HumanoidEnv();names=e.groups['left_arm']+e.groups['right_arm'];ranges={n:float(np.degrees(np.ptp(q[:,e.qadr[n]]))) for n in names};out={'arm_range_deg':ranges,'max_arm_range_deg':max(ranges.values())};print(json.dumps(out));(p/'20261105_directional_motion.json').write_text(json.dumps(out,indent=2));e.close()