"""Unitree G1 (29 DoF + Dex3-1 hands) fixed-pelvis upper-body simulation.

Model: MuJoCo Menagerie unitree_g1/g1_with_hands.xml (derived from Unitree's
official g1_29dof_with_hand_rev_1_0 description).  Changes made here:
  * pelvis is welded to the world (freejoint removed): upper-body imitation only,
    legs are position-held at the stand pose.
  * joint effort limits are re-applied from the official URDF
    (unitreerobotics/unitree_ros g1_29dof_with_hand_rev_1_0.urdf, <limit effort>)
    as actuator force ranges (menagerie uses 50 Nm for waist roll/pitch and ankles,
    the URDF says 35 Nm).
  * contacts are disabled (kinematic imitation display; self-collision is not
    simulated), gravity is compensated like sim.env.SimEnv (qfrc_applied=qfrc_bias).
  * lab-like scene: grey floor, gradient skybox, key/fill lights, optional shadows.
"""
from __future__ import annotations
import re
from pathlib import Path
import numpy as np
import mujoco

ROOT = Path(__file__).resolve().parents[1]
G1_DIR = ROOT / 'assets/mujoco_menagerie/unitree_g1'

# Official URDF limits (effort Nm, velocity rad/s as printed in the URDF).  The URDF
# velocity values (20-37 rad/s) are motor-side maxima; the teleop servo uses the much
# lower TELEOP_VEL caps below for smooth, human-like motion.
URDF_EFFORT = {
    'hip_pitch': 88, 'hip_roll': 139, 'hip_yaw': 88, 'knee': 139, 'ankle_pitch': 35, 'ankle_roll': 35,
    'waist_yaw': 88, 'waist_roll': 35, 'waist_pitch': 35,
    'shoulder_pitch': 25, 'shoulder_roll': 25, 'shoulder_yaw': 25, 'elbow': 25,
    'wrist_roll': 25, 'wrist_pitch': 5, 'wrist_yaw': 5,
    'hand_thumb_0': 2.45, 'hand_thumb_1': 1.4, 'hand_thumb_2': 1.4,
    'hand_middle_0': 1.4, 'hand_middle_1': 1.4, 'hand_index_0': 1.4, 'hand_index_1': 1.4,
}
URDF_VELOCITY = {
    'hip_pitch': 32, 'hip_roll': 20, 'hip_yaw': 32, 'knee': 20, 'ankle_pitch': 30, 'ankle_roll': 30,
    'waist_yaw': 32, 'waist_roll': 30, 'waist_pitch': 30,
    'shoulder_pitch': 37, 'shoulder_roll': 37, 'shoulder_yaw': 37, 'elbow': 37,
    'wrist_roll': 37, 'wrist_pitch': 22, 'wrist_yaw': 22,
    'hand_thumb_0': 3.14, 'hand_thumb_1': 12, 'hand_thumb_2': 12,
    'hand_middle_0': 12, 'hand_middle_1': 12, 'hand_index_0': 12, 'hand_index_1': 12,
}
# Teleop caps (rad/s, rad/s^2): well below the URDF maxima.
TELEOP_VEL = {'arm': 3.0, 'wrist': 4.0, 'waist': 1.2, 'hand': 3.0}
TELEOP_ACC = {'arm': 25.0, 'wrist': 30.0, 'waist': 8.0, 'hand': 30.0}

ARM = ('shoulder_pitch', 'shoulder_roll', 'shoulder_yaw', 'elbow', 'wrist_roll', 'wrist_pitch', 'wrist_yaw')
HAND = ('thumb_0', 'thumb_1', 'thumb_2', 'index_0', 'index_1', 'middle_0', 'middle_1')
WAIST = ('waist_yaw', 'waist_roll', 'waist_pitch')
LABELS = {
    'shoulder_pitch': '어깨 피치', 'shoulder_roll': '어깨 롤', 'shoulder_yaw': '어깨 요', 'elbow': '팔꿈치',
    'wrist_roll': '손목 롤', 'wrist_pitch': '손목 피치', 'wrist_yaw': '손목 요',
    'waist_yaw': '허리 요', 'waist_roll': '허리 롤', 'waist_pitch': '허리 피치',
    'thumb_0': '엄지 회전', 'thumb_1': '엄지 1', 'thumb_2': '엄지 2', 'index_0': '검지 1', 'index_1': '검지 2',
    'middle_0': '중지 1', 'middle_1': '중지 2',
}
SHORT = {'shoulder_pitch': 'SP', 'shoulder_roll': 'SR', 'shoulder_yaw': 'SY', 'elbow': 'EL',
         'wrist_roll': 'WR', 'wrist_pitch': 'WP', 'wrist_yaw': 'WY', 'waist_yaw': 'TY', 'waist_roll': 'TR', 'waist_pitch': 'TP'}
# Fingertip colours (RGB 0-1) shared with the webcam overlay: thumb, index, middle(+ring/pinky).
TIP_COLORS = {'thumb': (1.0, .42, .42), 'index': (1.0, .80, .25), 'middle': (.30, .85, .45)}
# Rest posture: arms relaxed beside the body, forearm slightly forward.
REST = {'shoulder_pitch': .15, 'shoulder_roll': .18, 'shoulder_yaw': 0., 'elbow': .95,
        'wrist_roll': 0., 'wrist_pitch': 0., 'wrist_yaw': 0.}


def _effort_key(joint):
    j = joint.replace('left_', '').replace('right_', '').replace('_joint', '')
    return j


LOWPOLY_DIR = ROOT / 'assets/g1_lowpoly'   # tools/g1_lowpoly.py output (630k -> 112k triangles)


def build_g1_xml(width=640, height=480, shadows=False, lowpoly=True):
    src = (G1_DIR / 'g1_with_hands.xml').read_text()
    meshdir = LOWPOLY_DIR if lowpoly and (LOWPOLY_DIR / 'torso_link_rev_1_0.STL').exists() else G1_DIR / 'assets'
    src = src.replace('meshdir="assets"', f'meshdir="{meshdir}"')
    src = src.replace('<freejoint name="floating_base_joint"/>', '')
    src = re.sub(r'\s*<keyframe>.*?</keyframe>', '', src, flags=re.S)
    # Remove the model's own light; lighting is defined below.
    src = re.sub(r'<light [^>]*/>', '', src, count=1)
    sites = []
    for side in ('left', 'right'):
        sites.append((f'{side}_elbow_link', f'{side}_elbow_site', '0 0 0'))
        sites.append((f'{side}_wrist_pitch_link', f'{side}_wrist_site', '0 0 0'))
        sites.append((f'{side}_wrist_yaw_link', f'{side}_palm_site', '0.08 0 0'))
        for f, link, pos in (('thumb', 'thumb_2', '0 -0.045 0' if side == 'left' else '0 0.045 0'),
                             ('index', 'index_1', '0.042 0 0'), ('middle', 'middle_1', '0.042 0 0')):
            sites.append((f'{side}_hand_{link}_link', f'{side}_{f}_tip', pos))
    for body, name, pos in sites:
        src = re.sub(rf'(<body name="{body}"[^>]*>)', rf'\1<site name="{name}" pos="{pos}" size="0.006" group="5"/>', src, count=1)
    extra = f'''
  <visual>
    <headlight diffuse=".35 .35 .35" ambient=".25 .25 .27" specular=".05 .05 .05"/>
    <quality shadowsize="{2048 if shadows else 0}" offsamples="4"/>
    <global offwidth="{max(1280, width)}" offheight="{max(960, height)}"/>
    <map znear=".02" zfar="40"/>
  </visual>
  <asset>
    <texture type="skybox" builtin="gradient" rgb1=".93 .94 .96" rgb2=".62 .66 .72" width="256" height="1536"/>
    <texture type="2d" name="lab_floor" builtin="checker" mark="edge" rgb1=".56 .58 .60" rgb2=".52 .54 .56" markrgb=".42 .44 .47" width="512" height="512"/>
    <material name="lab_floor" texture="lab_floor" texuniform="true" texrepeat="2 2" reflectance="0"/>
    <material name="lab_mat" rgba=".18 .30 .45 1" specular=".1"/>
    <material name="target_wrist" rgba="0.2 0.85 0.6 1"/>
    <material name="target_elbow" rgba="0.3 0.6 1 1"/>
  </asset>
  <worldbody>
    <light name="key" pos="2.2 1.6 3.2" dir="-.55 -.4 -.73" directional="true" diffuse=".55 .55 .53" specular=".2 .2 .2" castshadow="{'true' if shadows else 'false'}"/>
    <light name="fill" pos="-1.5 -2 2.5" dir=".4 .55 -.73" directional="true" diffuse=".22 .23 .26" specular="0 0 0" castshadow="false"/>
    <geom name="floor" type="plane" size="3 3 .5" material="lab_floor" contype="0" conaffinity="0"/>
    <geom name="mat" type="box" size=".45 .45 .004" pos="0 0 .004" material="lab_mat" contype="0" conaffinity="0"/>
    <camera name="front" pos="1.75 0 1.05" xyaxes="0 1 0 -0.11 0 1" fovy="45"/>
    <camera name="side" pos="1.4 1.6 1.2" xyaxes="-0.75 0.66 0 -0.2 -0.23 0.95" fovy="45"/>
'''
    for side in ('left', 'right'):
        extra += f'    <body name="{side}_wrist_target" mocap="true" pos="0 0 -1"><geom type="sphere" size=".022" material="target_wrist" contype="0" conaffinity="0" group="1"/></body>\n'
        extra += f'    <body name="{side}_elbow_target" mocap="true" pos="0 0 -1"><geom type="sphere" size=".016" material="target_elbow" contype="0" conaffinity="0" group="1"/></body>\n'
    extra += '  </worldbody>\n'
    src = src.replace('<worldbody>', extra.split('<worldbody>')[0] + '<worldbody>' + extra.split('<worldbody>')[1].replace('  </worldbody>\n', ''), 1)
    return src


class HumanoidEnv:
    def __init__(self, width=640, height=480, shadows=False, cam='front', lowpoly=True):
        self.width, self.height, self.cam = int(width), int(height), cam
        self.model = mujoco.MjModel.from_xml_string(build_g1_xml(width, height, shadows, lowpoly))
        m = self.model
        m.opt.disableflags |= int(mujoco.mjtDisableBit.mjDSBL_CONTACT)
        self.data = mujoco.MjData(m)
        self.joint_names = [m.joint(i).name for i in range(m.njnt)]
        self.qadr = {n: int(m.joint(n).qposadr[0]) for n in self.joint_names}
        self.dadr = {n: int(m.joint(n).dofadr[0]) for n in self.joint_names}
        self.act = {m.actuator(i).name: i for i in range(m.nu)}
        # Official effort limits -> actuator force range.
        for n in self.joint_names:
            e = URDF_EFFORT.get(_effort_key(n))
            if e is not None and n in self.act:
                a = self.act[n]
                m.actuator_forcerange[a] = (-e, e); m.actuator_forcelimited[a] = 1
                m.jnt_actfrcrange[m.joint(n).id] = (-e, e)
        self.groups = {
            'left_arm': [f'left_{j}_joint' for j in ARM], 'right_arm': [f'right_{j}_joint' for j in ARM],
            'waist': [f'{j}_joint' for j in WAIST],
            'left_hand': [f'left_hand_{j}_joint' for j in HAND], 'right_hand': [f'right_hand_{j}_joint' for j in HAND],
        }
        self.mocap = {n: int(m.body_mocapid[m.body(n).id]) for n in ('left_wrist_target', 'right_wrist_target', 'left_elbow_target', 'right_elbow_target')}
        self._renderer = None
        self._scene_opt = mujoco.MjvOption()
        self.reset()

    def rest_q(self):
        q = {}
        for side, s in (('left', 1), ('right', -1)):
            for j, v in REST.items():
                q[f'{side}_{j}_joint'] = v * (s if j in ('shoulder_roll', 'shoulder_yaw', 'wrist_roll', 'wrist_yaw') else 1)
        return q

    def reset(self):
        mujoco.mj_resetData(self.model, self.data)
        for n, v in self.rest_q().items():
            self.data.qpos[self.qadr[n]] = v
        self.data.ctrl[:] = 0
        for n in self.joint_names:
            if n in self.act:
                self.data.ctrl[self.act[n]] = self.data.qpos[self.qadr[n]]
        mujoco.mj_forward(self.model, self.data)

    def set_targets(self, qdict):
        lim = self.model.actuator_ctrlrange
        for n, v in qdict.items():
            a = self.act[n]
            self.data.ctrl[a] = float(np.clip(v, lim[a, 0], lim[a, 1]))

    def step(self, n=1):
        d = self.data
        for _ in range(n):
            d.qfrc_applied[:] = d.qfrc_bias
            mujoco.mj_step(self.model, d)

    def q(self, names):
        return np.array([self.data.qpos[self.qadr[n]] for n in names])

    def qd(self, names):
        return np.array([self.data.qvel[self.dadr[n]] for n in names])

    def tau(self, names):
        return np.array([self.data.actuator_force[self.act[n]] for n in names])

    def set_mocap(self, name, pos):
        self.data.mocap_pos[self.mocap[name]] = pos if pos is not None else (0, 0, -1)

    def camera_K(self, cam=None):
        cid = self.model.camera(cam or self.cam).id
        f = .5 * self.height / np.tan(np.deg2rad(self.model.cam_fovy[cid]) * .5)
        return np.array([[f, 0, (self.width - 1) / 2], [0, f, (self.height - 1) / 2], [0, 0, 1]])

    def T_world_cam(self, cam=None):
        cid = self.model.camera(cam or self.cam).id
        T = np.eye(4); T[:3, :3] = self.data.cam_xmat[cid].reshape(3, 3) @ np.diag([1., -1., -1.]); T[:3, 3] = self.data.cam_xpos[cid]
        return T

    def render(self, cam=None):
        if self._renderer is None:
            self._renderer = mujoco.Renderer(self.model, height=self.height, width=self.width)
        self._renderer.update_scene(self.data, camera=cam or self.cam, scene_option=self._scene_opt)
        return self._renderer.render()

    def close(self):
        if self._renderer is not None:
            self._renderer.close(); self._renderer = None
