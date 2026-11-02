"""Panda joint position control + physics throughput (no rendering)."""
import json
import time
from pathlib import Path

import mujoco
import numpy as np

HERE = Path(__file__).resolve().parent
m = mujoco.MjModel.from_xml_path(str(HERE / "scene_panda.xml"))
d = mujoco.MjData(m)
mujoco.mj_resetDataKeyframe(m, d, m.key("home").id)
res = dict(timestep=m.opt.timestep, nq=m.nq, nu=m.nu)

jids = [m.joint(f"joint{i}").id for i in range(1, 8)]
qadr = np.array([m.jnt_qposadr[j] for j in jids])
target = np.array([0.3, -0.3, 0.2, -2.2, 0.1, 2.0, 0.6])
d.ctrl[:7] = target
d.ctrl[7] = 255  # gripper open
hand = m.body("hand").id

traj = []
t_sim = 0.0
for k in range(int(3.0 / m.opt.timestep)):
    mujoco.mj_step(m, d)
    if k % 50 == 0:
        traj.append(float(np.abs(d.qpos[qadr] - target).max()))
err = np.abs(d.qpos[qadr] - target)
res["target"] = target.tolist()
res["final_q"] = d.qpos[qadr].round(4).tolist()
res["max_abs_err_rad_after_3s"] = float(err.max())
res["t_to_err_lt_0.01rad_s"] = next((i * 50 * m.opt.timestep for i, e in enumerate(traj) if e < 0.01), None)
res["hand_pos_world"] = d.xpos[hand].round(4).tolist()

# gripper close
d.ctrl[7] = 0
for _ in range(int(1.0 / m.opt.timestep)):
    mujoco.mj_step(m, d)
fj = [m.jnt_qposadr[m.joint(n).id] for n in ("finger_joint1", "finger_joint2")]
res["finger_qpos_after_close"] = d.qpos[fj].round(4).tolist()

obj = m.body("obj").id
res["obj_pos_after_4s"] = d.xpos[obj].round(4).tolist()

# throughput
mujoco.mj_resetDataKeyframe(m, d, m.key("home").id)
d.ctrl[:7] = target
N = 20000
t = time.perf_counter()
for _ in range(N):
    mujoco.mj_step(m, d)
dt = time.perf_counter() - t
res["steps_per_s"] = round(N / dt)
res["realtime_factor"] = round(N * m.opt.timestep / dt, 1)
print(json.dumps(res, indent=1))
(HERE / "results").mkdir(exist_ok=True)
(HERE / "results" / "physics.json").write_text(json.dumps(res, indent=2))
