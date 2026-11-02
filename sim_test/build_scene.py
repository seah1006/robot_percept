"""Build sim_test/scene_panda.xml: menagerie Panda + table + free box object + fixed RGB-D camera (+ wrist camera)."""
import re
from pathlib import Path

import numpy as np

R = Path.home() / "work/robot_percept"
MEN = R / "assets/mujoco_menagerie/franka_emika_panda"
OUT = R / "sim_test"
OUT.mkdir(parents=True, exist_ok=True)

# 1) panda_mod.xml: absolute meshdir, keyframe removed (re-added in scene with the object's free joint), wrist camera
src = (MEN / "panda.xml").read_text()
src = src.replace('meshdir="assets"', f'meshdir="{MEN / "assets"}"')
src = re.sub(r"\s*<keyframe>.*?</keyframe>", "", src, flags=re.S)
hand = '<body name="hand" pos="0 0 0.107" quat="0.9238795 0 0 -0.3826834">'
assert hand in src
# camera looks along its -Z; hand approach axis is +Z -> rotate 180deg about X
src = src.replace(hand, hand + '\n                      <camera name="wrist" pos="0.06 0 0.02" quat="0 1 0 0" fovy="70"/>', 1)
(OUT / "panda_mod.xml").write_text(src)


def look_at_xyaxes(pos, target, up=(0, 0, 1)):
    f = np.asarray(target, float) - np.asarray(pos, float)
    f /= np.linalg.norm(f)
    x = np.cross(f, up)
    x /= np.linalg.norm(x)
    z = -f
    y = np.cross(z, x)
    return " ".join(f"{v:.6f}" for v in np.r_[x, y])


CAM_POS = (1.35, 0.0, 0.95)
CAM_TARGET = (0.55, 0.0, 0.30)
TABLE_TOP = 0.30
OBJ = dict(pos=(0.55, 0.05, TABLE_TOP + 0.04 + 0.001), half=(0.025, 0.03, 0.04))
HOME = "0 0 0 -1.57079 0 1.57079 -0.7853 0.04 0.04"
HOME_CTRL = "0 0 0 -1.57079 0 1.57079 -0.7853 255"
obj_qpos = " ".join(str(v) for v in OBJ["pos"]) + " 1 0 0 0"

scene = f"""<mujoco model="panda rgbd test scene">
  <include file="panda_mod.xml"/>
  <statistic center="0.4 0 0.4" extent="1.2"/>
  <visual>
    <headlight diffuse="0.6 0.6 0.6" ambient="0.3 0.3 0.3" specular="0 0 0"/>
    <map znear="0.01" zfar="50"/>
    <global offwidth="1920" offheight="1080" azimuth="120" elevation="-20"/>
  </visual>
  <asset>
    <texture type="skybox" builtin="gradient" rgb1="0.3 0.5 0.7" rgb2="0 0 0" width="512" height="3072"/>
    <texture type="2d" name="groundplane" builtin="checker" mark="edge" rgb1="0.2 0.3 0.4" rgb2="0.1 0.2 0.3"
      markrgb="0.8 0.8 0.8" width="300" height="300"/>
    <material name="groundplane" texture="groundplane" texuniform="true" texrepeat="5 5" reflectance="0.2"/>
    <material name="table" rgba="0.55 0.4 0.25 1"/>
    <material name="obj" rgba="0.9 0.2 0.15 1"/>
  </asset>
  <worldbody>
    <light pos="0 0 1.5" dir="0 0 -1" directional="true"/>
    <geom name="floor" size="0 0 0.05" type="plane" material="groundplane"/>
    <body name="table" pos="0.55 0 {TABLE_TOP / 2}">
      <geom name="table_top" type="box" size="0.25 0.40 {TABLE_TOP / 2}" material="table"/>
    </body>
    <body name="obj" pos="{' '.join(map(str, OBJ['pos']))}">
      <freejoint name="obj_free"/>
      <geom name="obj_geom" type="box" size="{' '.join(map(str, OBJ['half']))}" material="obj" mass="0.15"/>
    </body>
    <camera name="rgbd" mode="fixed" pos="{' '.join(map(str, CAM_POS))}" xyaxes="{look_at_xyaxes(CAM_POS, CAM_TARGET)}" fovy="58"/>
  </worldbody>
  <keyframe>
    <key name="home" qpos="{HOME} {obj_qpos}" ctrl="{HOME_CTRL}"/>
  </keyframe>
</mujoco>
"""
(OUT / "scene_panda.xml").write_text(scene)

import mujoco  # noqa: E402

m = mujoco.MjModel.from_xml_path(str(OUT / "scene_panda.xml"))
print("compiled: nq", m.nq, "nv", m.nv, "nu", m.nu, "ncam", m.ncam, "nbody", m.nbody, "timestep", m.opt.timestep)
print("cameras:", [mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_CAMERA, i) for i in range(m.ncam)])
