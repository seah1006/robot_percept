"""Contact-enabled, fixed-pelvis Unitree G1 / Dex3 tabletop simulation."""
from __future__ import annotations

import math
import xml.etree.ElementTree as ET

import mujoco
import numpy as np

from .humanoid_env import ARM, HAND, REST, URDF_EFFORT, _effort_key, build_g1_xml
from .humanoid_ik import ArmIK, rotation_error

SIDES = ('left', 'right')
TABLE_XY = (.38, -.20)
TABLE_TOP = .83
DT = .002
# Body frame remains yaw-only, including for the horizontally oriented dowel.
OBJECTS = {
    'board': ('box', '.06 .025 .0125', .08, .0125),
    'dowel': ('cylinder', '.012 .04', .02, .012),
    'block': ('box', '.02 .02 .02', .05, .02),
}
HAND_BIT, TABLE_BIT, OBJECT_BIT = 1, 2, 4
FINGERS = ('thumb', 'index', 'middle', 'palm')
# Order follows humanoid_env.HAND; opposite signs on the left hand.
RIGHT_OPEN = np.array([0., .28, -.01, .01, .01, .01, .01])
RIGHT_CLOSED = np.array([-.05, -.88, -1.10, 1.27, 1.10, 1.27, 1.10])
CONTACT = dict(solref='.008 1', solimp='.95 .99 .001', margin='0', gap='0')


def _quat(rotation):
    result = np.empty(4)
    mujoco.mju_mat2Quat(result, rotation.flatten())
    return result


def pregrasp_pose(obj_pos, obj_yaw, height):
    """Top-down right-palm target with center-relative height (m), yaw (rad), wxyz.

    Local +Y closes down; local +X points toward the fingertips. Palm site
    is set back from the object to account for the length of the fingers.
    """
    forward = np.array([np.cos(obj_yaw), np.sin(obj_yaw), 0.])
    down = np.array([0., 0., -1.])
    rotation = np.column_stack((forward, down, np.cross(forward, down)))
    pos = np.asarray(obj_pos, dtype=float) - .052 * forward
    pos[2] += height
    return pos, _quat(rotation)


def _build_xml(obj, width, height):
    root = ET.fromstring(build_g1_xml(width, height))
    root.find('option').attrib.update(timestep=str(DT), cone='elliptic', impratio='10', noslip_iterations='3')
    root.find('visual/quality').set('offsamples', '0')
    world = root.find('worldbody')
    for geom in world.iter('geom'):
        geom.attrib.update(contype='0', conaffinity='0')
    for body in world.iter('body'):
        for geom in body.findall("geom[@class='collision']"):
            palm = geom.get('mesh', '').endswith('_hand_palm_link')
            finger = any(f'_hand_{f}_' in body.get('name', '') for f in FINGERS[:3])
            if palm or finger:
                geom.attrib.update(CONTACT, contype=str(HAND_BIT), conaffinity='6',
                                   friction='1.2 .005 .0001', condim='4')
    x, y = TABLE_XY
    ET.SubElement(world, 'geom', name='grasp_table', type='box', size='.115 .14 .025',
                  pos=f'{x} {y} {TABLE_TOP - .025}', rgba='.44 .33 .24 1',
                  contype=str(TABLE_BIT), conaffinity='5', friction='.8 .005 .0001', condim='4', **CONTACT)
    kind, size, mass, half_height = OBJECTS[obj]
    body = ET.SubElement(world, 'body', name='grasp_object', pos=f'{x} {y} {TABLE_TOP + half_height}')
    ET.SubElement(body, 'freejoint', name='grasp_object_joint')
    geom = ET.SubElement(body, 'geom', name='grasp_object_geom', type=kind, size=size, mass=str(mass),
                         rgba='.9 .54 .14 1', contype=str(OBJECT_BIT), conaffinity='3',
                         friction='1.2 .005 .0001', condim='6' if obj == 'dowel' else '4', **CONTACT)
    if obj == 'dowel':
        geom.set('axisangle', '0 1 0 1.5707963267948966')
    equality = ET.SubElement(root, 'equality')
    for side in SIDES:
        ET.SubElement(equality, 'weld', name=f'{side}_grasp_weld', body1=f'{side}_wrist_yaw_link',
                      body2='grasp_object', active='false', solref='.01 1', torquescale='.06')
    return ET.tostring(root, encoding='unicode')


class G1GraspEnv:
    """Physics-only grip, contact-gated weld approximation, or debug oracle."""

    pregrasp_pose = staticmethod(pregrasp_pose)

    def __init__(self, obj: str = 'board', mode: str = 'phys', seed: int = 0, render: bool = False,
                 width=640, height=480):
        if obj not in OBJECTS or mode not in ('phys', 'gate', 'oracle'):
            raise ValueError(f'Unknown object or mode: {obj!r}, {mode!r}')
        self.obj, self.mode = obj, mode
        self.width, self.height = int(width), int(height)
        self._render_enabled = render
        self._renderer = None
        self._rng = np.random.default_rng(seed)
        self.model = m = mujoco.MjModel.from_xml_string(_build_xml(obj, self.width, self.height))
        self.data = mujoco.MjData(m)
        self._obj_q = int(m.joint('grasp_object_joint').qposadr[0])
        self._obj_dof = int(m.joint('grasp_object_joint').dofadr[0])
        self._robot_dofs = np.r_[0:self._obj_dof, self._obj_dof + 6:m.nv]
        self._obj_body = m.body('grasp_object').id
        self._obj_geom = m.geom('grasp_object_geom').id
        self._support = {m.geom(name).id for name in ('grasp_table', 'floor')}
        self._weld = {s: m.equality(f'{s}_grasp_weld').id for s in SIDES}
        self._eq_default = m.eq_data.copy()
        self._palm = {s: m.site(f'{s}_palm_site').id for s in SIDES}
        self._hand_geoms = {}
        for g in range(m.ngeom):
            if m.geom_contype[g] == HAND_BIT:
                body = m.body(m.geom_bodyid[g]).name
                side = body.split('_', 1)[0]
                kind = next((f for f in FINGERS[:3] if f'_hand_{f}_' in body), 'palm')
                self._hand_geoms[g] = (side, kind)
        self._qpos_for_act = m.jnt_qposadr[m.actuator_trnid[:, 0]]
        self._act = {m.actuator(i).name: i for i in range(m.nu)}
        for name, a in self._act.items():
            effort = URDF_EFFORT[_effort_key(name)]
            m.actuator_forcelimited[a] = 1
            m.actuator_forcerange[a] = (-effort, effort)
            m.jnt_actfrcrange[m.joint(name).id] = (-effort, effort)
            if '_hand_' in name:
                m.actuator_gainprm[a, 0] = 45.
                m.actuator_biasprm[a, 1:3] = (-45., -1.4)
                m.dof_frictionloss[int(m.joint(name).dofadr[0])] = .03
        self._arm_act = {s: np.array([self._act[f'{s}_{j}_joint'] for j in ARM]) for s in SIDES}
        self._hand_act = {s: np.array([self._act[f'{s}_hand_{j}_joint'] for j in HAND]) for s in SIDES}
        self._rest_arm = {s: np.array([REST[j] * (-1 if s == 'right' and j in
                               ('shoulder_roll', 'shoulder_yaw', 'wrist_roll', 'wrist_yaw') else 1)
                               for j in ARM]) for s in SIDES}
        self._ik = {s: ArmIK(m, s, rest=self._rest_arm[s], w_rot=.25, lam0=.004,
                             lam_max=.025, k_post=.025) for s in SIDES}
        self._rate = np.array([2.5 if ('_hand_' in n or '_wrist_' in n) else 1.8 for n in self._act])
        self.reset()

    def reset(self, seed: int | None = None) -> dict:
        if seed is not None:
            self._rng = np.random.default_rng(seed)
        m, d = self.model, self.data
        m.eq_data[:] = self._eq_default
        mujoco.mj_resetData(m, d)
        self._unstable = False
        self._closure = dict.fromkeys(SIDES, 0.)
        self._goal = np.zeros(m.nu)
        for s in SIDES:
            self._goal[self._arm_act[s]] = self._rest_arm[s]
            self.set_hand(0., s)
        d.ctrl[:] = self._goal
        d.qpos[self._qpos_for_act] = self._goal
        x, y = np.asarray(TABLE_XY) + self._rng.uniform(-.03, .03, 2)
        yaw = self._rng.uniform(-np.pi / 6, np.pi / 6)
        d.qpos[self._obj_q:self._obj_q + 7] = (x, y, TABLE_TOP + OBJECTS[self.obj][3] + .003,
                                               np.cos(yaw / 2), 0., 0., np.sin(yaw / 2))
        mujoco.mj_forward(m, d)
        self.step(.25)
        d.time = 0.
        self._rest_pose = (d.xpos[self._obj_body].copy(), d.xquat[self._obj_body].copy())
        return self.state()

    def object_rest_pose(self) -> tuple:
        return tuple(x.copy() for x in self._rest_pose)

    def set_hand(self, closure: float, side: str = 'right') -> None:
        if not np.isfinite(closure):
            raise ValueError('Nonfinite closure')
        closure = float(np.clip(closure, 0., 1.))
        self._closure[side] = closure
        goal = RIGHT_OPEN + closure * (RIGHT_CLOSED - RIGHT_OPEN)
        if side == 'left':
            goal = -goal
        aids = self._hand_act[side]
        lo, hi = self.model.actuator_ctrlrange[aids].T
        self._goal[aids] = np.clip(goal, lo, hi)
        if closure < .3:
            self.data.eq_active[self._weld[side]] = False

    def set_arm_target(self, pos, quat=None, side: str = 'right') -> bool:
        """Set a world-space palm-site target; failed IK preserves the old target."""
        p = np.asarray(pos, dtype=float)
        q = None if quat is None else np.asarray(quat, dtype=float)
        if p.shape != (3,) or not np.all(np.isfinite(p)):
            return False
        if q is not None and (q.shape != (4,) or not np.all(np.isfinite(q)) or np.linalg.norm(q) < 1e-10):
            return False
        ik, d = self._ik[side], self.data
        aids = self._arm_act[side]
        r = None
        if q is not None:
            r = np.empty(9)
            mujoco.mju_quat2Mat(r, q / np.linalg.norm(q))
            r = r.reshape(3, 3)
        # ArmIK uses a site named wrist_site as its default position objective.
        # Substitute the palm site to solve on the actual position Jacobian.
        previous = ik.site['wrist_site']
        ik.site['wrist_site'] = self._palm[side]
        seeds = [self._goal[aids], d.qpos[ik.qadr], self._rest_arm[side]]
        try:
            for i, seed in enumerate(seeds):
                q7, _ = ik.solve(d.qpos, seed, p, R_target=r, iters=65,
                                 pos_tol=.0025, rot_tol=np.deg2rad(2), restarts=5 if i == 2 else 0)
                fk = ik.fk(d.qpos, q7)
                pe = np.linalg.norm(fk.site_xpos[self._palm[side]] - p)
                re = 0. if r is None else np.linalg.norm(rotation_error(r, fk.site_xmat[self._palm[side]].reshape(3, 3)))
                if pe <= .005 and re <= np.deg2rad(4):
                    self._goal[aids] = q7
                    return True
            return False
        finally:
            ik.site['wrist_site'] = previous

    def _contacts(self):
        support, penetration = False, 0.
        fingers = {s: set() for s in SIDES}
        for c in self.data.contact[:self.data.ncon]:
            a, b = c.geom
            if a == self._obj_geom:
                other = b
            elif b == self._obj_geom:
                other = a
            else:
                continue
            if c.dist <= 0:
                support |= other in self._support
                if other in self._hand_geoms:
                    side, kind = self._hand_geoms[other]
                    fingers[side].add(kind)
                    penetration = max(penetration, -float(c.dist))
        return support, penetration, fingers

    def _inside_palm(self, side):
        d, p = self.data, self._palm[side]
        local = d.site_xmat[p].reshape(3, 3).T @ (d.xpos[self._obj_body] - d.site_xpos[p])
        y = local[1] if side == 'right' else -local[1]
        return -.015 <= local[0] <= .12 and -.015 <= y <= .10 and abs(local[2]) <= .060

    def _maybe_attach(self):
        if self.mode == 'phys' or max(self._closure.values()) < .3:
            return
        d, m = self.data, self.model
        if any(d.eq_active[e] for e in self._weld.values()):
            return
        fingers = self._contacts()[2] if self.mode == 'gate' else None
        for side in ('right', 'left'):
            if self._closure[side] < .3:
                continue
            if fingers is not None:
                f = fingers[side]
                if not ('thumb' in f and f.intersection(('index', 'middle')) and self._inside_palm(side)):
                    continue
            eq = self._weld[side]
            hand = m.eq_obj1id[eq]
            # Preserve the actual pose and use the object origin as the body2 anchor.
            r = d.xmat[hand].reshape(3, 3).T
            m.eq_data[eq, :3] = 0.
            m.eq_data[eq, 3:6] = r @ (d.xpos[self._obj_body] - d.xpos[hand])
            m.eq_data[eq, 6:10] = _quat(r @ d.xmat[self._obj_body].reshape(3, 3))
            d.eq_active[eq] = True
            break

    def step(self, seconds: float) -> dict:
        if not np.isfinite(seconds) or seconds < 0:
            raise ValueError('seconds must be finite and nonnegative')
        m, d = self.model, self.data
        dt = m.opt.timestep
        max_delta = self._rate * dt
        for _ in range(max(0, math.ceil(seconds / dt - 1e-10))):
            if self._unstable:
                break
            self._maybe_attach()
            d.ctrl[:] += np.clip(self._goal - d.ctrl, -max_delta, max_delta)
            d.qfrc_applied[self._robot_dofs] = d.qfrc_bias[self._robot_dofs]
            d.qfrc_applied[self._obj_dof:self._obj_dof + 6] = 0.
            mujoco.mj_step(m, d)
            self._unstable = any(d.warning[w].number for w in (
                mujoco.mjtWarning.mjWARN_BADQPOS, mujoco.mjtWarning.mjWARN_BADQVEL,
                mujoco.mjtWarning.mjWARN_BADQACC))
        # mj_step integrates qpos after computing contacts and sites. Synchronize the snapshot.
        if not self._unstable:
            mujoco.mj_forward(m, d)
            self._maybe_attach()
        return self.state()

    def state(self) -> dict:
        d, p = self.data, self._palm['right']
        support, penetration, fingers = self._contacts()
        return dict(t=float(d.time), obj_pos=d.xpos[self._obj_body].copy(),
                    obj_quat=d.xquat[self._obj_body].copy(), palm_pos=d.site_xpos[p].copy(),
                    palm_quat=_quat(d.site_xmat[p]), obj_table_contact=bool(support),
                    finger_contacts=[f for f in FINGERS if f in fingers['right']],
                    max_penetration=penetration, weld_active=any(d.eq_active[e] for e in self._weld.values()),
                    finite=bool(not self._unstable and all(np.isfinite(a).all() for a in (d.qpos, d.qvel, d.qacc))))

    def render(self, cam: str | None = None):
        if not self._render_enabled:
            raise RuntimeError('Create G1GraspEnv with render=True to enable RGB rendering')
        if self._renderer is None:
            self._renderer = mujoco.Renderer(self.model, height=self.height, width=self.width)
        self._renderer.update_scene(self.data, camera=cam or 'front')
        return self._renderer.render()

    def close(self):
        if self._renderer is not None:
            self._renderer.close()
            self._renderer = None
