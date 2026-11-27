"""Fixed-base G1 manipulation, with public geometric arguments in table frame."""
from __future__ import annotations
import math
import xml.etree.ElementTree as ET
import mujoco as mj
import numpy as np
from m2a.common import load_layout, load_parts
from sim.humanoid_env import HAND, REST, URDF_EFFORT, _effort_key, build_g1_xml
from sim.humanoid_ik import ArmIK
from .grasp_profiles import grasp_profile, hand_command

HAND_BIT, OBJECT_BIT, FIXTURE_BIT = 1, 2, 4
TRAY_FLOOR, TRAY_WALL = .004, .006
WELD_CONTACT_GRACE_S = .200  # Imposed continuous contact-loss threshold.
ARMS = ('left', 'right')
CAMERAS = {'head': (640, 480), 'front': (640, 480), 'wrist_l': (256, 256), 'wrist_r': (256, 256)}


def _vec(values):
    return ' '.join(str(float(v)) for v in values)


def _collision(kind):
    accept = {HAND_BIT: OBJECT_BIT | FIXTURE_BIT,
              OBJECT_BIT: HAND_BIT | OBJECT_BIT | FIXTURE_BIT,
              FIXTURE_BIT: HAND_BIT | OBJECT_BIT}
    return dict(contype=str(kind), conaffinity=str(accept[kind]), condim='6',
                friction='1.8 .025 .003', solref='.008 1', solimp='.95 .99 .001')


def half_height(part):
    return part['size'][-1] / 2


def build_manip_xml(spec, layout, parts):
    root = ET.fromstring(build_g1_xml())
    world = root.find('worldbody')
    bodies = {b.get('name'): b for b in world.iter('body')}
    fixed = {j.get("name") for j in world.iter("joint") if not any(
        key in j.get("name", "") for key in ("shoulder", "elbow", "wrist", "_hand_"))}
    for body in bodies.values():
        for j in body.findall("joint"):
            if j.get("name") in fixed:
                body.remove(j)
    actuator = root.find("actuator")
    for servo in list(actuator):
        if servo.get("joint") in fixed:
            actuator.remove(servo)
    for name, body in bodies.items():
        for geom in body.findall('geom'):
            geom.attrib.update(contype='0', conaffinity='0')
            if geom.get('class') == 'collision' and ('_hand_' in name or
                    (name.endswith('_wrist_yaw_link') and '_hand_palm_' in geom.get('mesh', ''))):
                geom.attrib.update(_collision(HAND_BIT))
    for arm, sign in zip(ARMS, (1, -1)):
        hand = bodies[f'{arm}_wrist_yaw_link']
        ET.SubElement(hand, 'site', name=f'{arm}_grip', pos=_vec((.135, -.057 * sign, 0)),
                      size='.003', rgba='0 0 0 0')
        ET.SubElement(hand, 'camera', name=f'wrist_{arm[0]}', pos=_vec((.066, .018*sign, 0)),
                      xyaxes=_vec((0, 0, sign, .74, .67 * sign, 0)), fovy='78')
    ET.SubElement(bodies['torso_link'], 'camera', name='head', pos='.095 0 .37',
                  xyaxes='0 -1 0 .72 0 .69', fovy='83')
    world.find("camera[@name='front']").attrib.update(pos='1.36 -1.05 1.46', xyaxes='.75 .66 0 -.29 .32 .90', fovy='48')
    T = np.asarray(layout['table']['T_world_table'], float)
    if T.shape != (4, 4) or not np.isclose(T[2, 3], layout['table']['top_z_world']):
        raise ValueError('layout table needs a consistent 4x4 T_world_table')
    table = ET.SubElement(world, 'body', name='m2a_table_frame', pos=_vec(T[:3, 3]),
                          xyaxes=_vec(np.r_[T[:3, 0], T[:3, 1]]))

    def box(name, pos, size, rgb):
        ET.SubElement(table, 'geom', name=name, type='box', pos=_vec(pos),
                      size=_vec(size), rgba=_vec([*rgb, 1]), **_collision(FIXTURE_BIT))

    sx, sy = np.asarray(layout['table']['size_xy']) / 2
    render = spec.get('render', {})
    if 'light_seed' in render:
        factors = np.random.default_rng(render['light_seed']).uniform(.9, 1.1, 2)
        for lamp, scale in zip(world.findall('light'), factors):
            lamp.set('diffuse', _vec(np.clip(np.fromstring(lamp.get('diffuse'), sep=' ') * scale, 0, 1)))
    box('m2a_table', (0, 0, -.02), (sx, sy, .02), render.get('table_rgb', [.55, .45, .35]))
    for (tray, tr), color in zip(layout['trays'].items(), [(.23, .43, .71), (.26, .56, .36), (.71, .39, .23)], strict=True):
        x, y = tr['center']; a, b = np.asarray(tr['inner']) / 2
        w = tr.get('wall_thickness', TRAY_WALL); h = tr['wall_h']; floor = tr.get('floor_z', TRAY_FLOOR)
        box(f'{tray}_floor', (x, y, floor / 2), (a+w, b+w, floor / 2), color)
        for sign in (-1, 1):
            box(f'{tray}_x{sign}', (x+sign*(a+w/2), y, floor+h/2), (w/2, b+w, h/2), color)
            box(f'{tray}_y{sign}', (x, y+sign*(b+w/2), floor+h/2), (a, w/2, h/2), color)
    equality = ET.SubElement(root, 'equality')
    seen = set()
    for obj in spec['objects']:
        oid = obj['oid']
        if oid in seen:
            raise ValueError(f'duplicate oid: {oid}')
        seen.add(oid)
        part = parts[obj['part_id']]; xyz = T[:3, :3] @ obj['xyz'] + T[:3, 3]
        cy, syaw = math.cos(obj['yaw']), math.sin(obj['yaw'])
        axes = np.column_stack(([cy, syaw, 0], [-syaw, cy, 0]))
        ob = ET.SubElement(world, 'body', name=f'm2a_obj_{oid}', pos=_vec(xyz),
                           xyaxes=_vec((T[:3, :3] @ axes).T.flat))
        ET.SubElement(ob, 'freejoint', name=f'm2a_free_{oid}')
        size = np.asarray(part['size'], float).copy(); size[-1] /= 2
        if part['shape'] == 'box':
            size[:2] /= 2
        elif part['shape'] != 'cylinder':
            raise ValueError(f"unsupported shape {part['shape']}")
        ET.SubElement(ob, 'geom', name=f'm2a_geom_{oid}', type=part['shape'], size=_vec(size),
                      mass=str(part['mass']), rgba=_vec([*part['rgb'], 1]), **_collision(OBJECT_BIT))
        for arm in ARMS:
            ET.SubElement(equality, 'weld', name=f'm2a_weld_{arm}_{oid}',
                          body1=f'{arm}_wrist_yaw_link', body2=f'm2a_obj_{oid}',
                          active='false', solref='.012 1', torquescale='.05')
    return ET.tostring(root, encoding='unicode')


class GripIK(ArmIK):
    """Use the grip point itself and its Jacobian, not the upstream wrist."""
    def __init__(self, model, arm, **kwargs):
        super().__init__(model, arm, **kwargs)
        self.site["wrist_site"] = model.site(f"{arm}_grip").id


class G1ManipEnv:
    def __init__(self, layout=None):
        self.layout = load_layout() if layout is None else layout
        self._renderers = {}

    def reset(self, spec):
        self.close()
        if spec['schema'] != 'm2a.scene.v1':
            raise ValueError(spec['schema'])
        self.spec = spec
        self.parts = load_parts(spec['product'])['parts']
        self.T_world_table = np.asarray(self.layout['table']['T_world_table'], float)
        m = self.model = mj.MjModel.from_xml_string(build_manip_xml(spec, self.layout, self.parts))
        d = self.data = mj.MjData(m)
        self.object_parts = {o['oid']: o['part_id'] for o in spec['objects']}
        self.object_bodies = {oid: m.body(f'm2a_obj_{oid}').id for oid in self.object_parts}
        self.object_geoms = {oid: m.geom(f'm2a_geom_{oid}').id for oid in self.object_parts}
        self.closed = dict.fromkeys(ARMS, False)
        self._ee_profile = dict.fromkeys(ARMS)
        self._grasp_target = dict.fromkeys(ARMS)
        self._gate_welds = {}
        self.grasp_slips = dict.fromkeys(ARMS, 0)
        self.slip_events = []
        self.robot_nv = min((int(m.joint(f'm2a_free_{oid}').dofadr[0]) for oid in self.object_parts), default=m.nv)
        self.ik = {}; self.rest = {}; self.arm_act = {}; self.hand_act = {}; self.tip_geoms = {}; self.arm_geom = {}
        m.opt.integrator = mj.mjtIntegrator.mjINT_IMPLICITFAST
        for i in range(m.nu):
            name = m.actuator(i).name
            e = URDF_EFFORT.get(_effort_key(name))
            if e is not None:
                m.actuator_forcerange[i] = (-e, e); m.actuator_forcelimited[i] = 1
            if '_hand_' in name:
                m.actuator_gainprm[i, 0] = 10; m.actuator_biasprm[i, 1:3] = (-10, -.35)
            elif any(n in name for n in ('shoulder', 'elbow', 'wrist')):
                m.actuator_gainprm[i, 0] = 160; m.actuator_biasprm[i, 1:3] = (-160, -5.)
        for arm, sign in zip(ARMS, (1, -1)):
            ik = self.ik[arm] = GripIK(m, arm, w_rot=.22, k_post=.015, lam0=.005, lam_max=.035)
            q = np.array([v * (sign if j in ('shoulder_roll', 'shoulder_yaw', 'wrist_roll', 'wrist_yaw') else 1)
                          for j, v in REST.items()])
            ik.rest = q.copy(); self.rest[arm] = q
            d.qpos[ik.qadr] = q
            self.arm_act[arm] = np.array([m.actuator(n).id for n in ik.names])
            self.hand_act[arm] = np.array([m.actuator(f'{arm}_hand_{j}_joint').id for j in HAND])
            self.tip_geoms[arm] = {}; self.arm_geom[arm] = set()
            for gid in np.flatnonzero(m.geom_contype == HAND_BIT):
                name = m.body(m.geom_bodyid[gid]).name
                if not name.startswith(arm + '_'):
                    continue
                self.arm_geom[arm].add(int(gid))
                for finger, suffix in [('thumb', 'thumb_2'), ('index', 'index_1'), ('middle', 'middle_1')]:
                    if name == f'{arm}_hand_{suffix}_link':
                        self.tip_geoms[arm][int(gid)] = finger
        d.ctrl[:] = d.qpos[m.jnt_qposadr[m.actuator_trnid[:, 0]]]
        mj.mj_forward(m, d)
        for side, sign in zip(ARMS, (1, -1)):
            q, diag = self.solve_ik(side, [-.115, .33*sign, .105], self.topdown(side), restarts=2)
            if diag["ok"]:
                self.rest[side] = q.copy()
                d.qpos[self.ik[side].qadr] = q
                d.ctrl[self.arm_act[side]] = q
        mj.mj_forward(m, d)
        return self.get_gt_objects()

    def to_world(self, xyz):
        return self.T_world_table[:3, :3] @ xyz + self.T_world_table[:3, 3]

    def to_table(self, xyz):
        return self.T_world_table[:3, :3].T @ (xyz - self.T_world_table[:3, 3])

    def step(self, n=1):
        m, d = self.model, self.data
        for _ in range(n):
            d.qfrc_applied[:self.robot_nv] = d.qfrc_bias[:self.robot_nv]
            mj.mj_step(m, d)
            for arm, (oid, eq, missing) in tuple(self._gate_welds.items()):
                if not d.eq_active[eq]:
                    del self._gate_welds[arm]
                    continue
                fingers = self.contact_fingers(arm, oid)
                missing = 0 if len(fingers) >= 2 else missing + 1
                if missing * m.opt.timestep >= WELD_CONTACT_GRACE_S:
                    d.eq_active[eq] = False
                    del self._gate_welds[arm]
                    self.grasp_slips[arm] += 1
                    self.slip_events.append(dict(arm=arm, oid=oid, sim_time=float(d.time),
                                                 fingers=sorted(fingers), reason_code='GRASP_SLIP'))
                else:
                    self._gate_welds[arm] = (oid, eq, missing)
        if n:
            mj.mj_forward(m, d)

    def get_gt_objects(self):
        d, m = self.data, self.model
        velocity = np.empty(6)
        out = {}
        for oid, bid in self.object_bodies.items():
            p = self.to_table(d.xpos[bid]); R = self.T_world_table[:3, :3].T @ d.xmat[bid].reshape(3, 3)
            mj.mj_objectVelocity(m, d, mj.mjtObj.mjOBJ_BODY, bid, velocity, 0)
            out[oid] = dict(part_id=self.object_parts[oid], xyz=p.tolist(),
                            yaw=math.atan2(R[1, 0], R[0, 0]), lin_speed=float(np.linalg.norm(velocity[3:])))
        return out

    def topdown(self, arm, yaw=0.):
        x = np.array([math.cos(yaw), math.sin(yaw), 0.]); y = np.array([0., 0., 1. if arm == 'left' else -1.])
        return np.column_stack((x, y, np.cross(x, y)))

    def solve_ik(self, arm, xyz, rotation, q0=None, restarts=3):
        """Grip-site pose in table frame. Returns (q7, diagnostics including ok)."""
        ik = self.ik[arm]; m, d = self.model, self.data
        R = self.T_world_table[:3, :3] @ rotation
        p = self.to_world(xyz)
        q, diag = ik.solve(d.qpos, d.qpos[ik.qadr] if q0 is None else q0, p, R,
                           iters=48, pos_tol=.0016, rot_tol=.025, restarts=restarts)
        diag['ok'] = diag['pos_err_mm'] <= 2.5 and diag['rot_err_deg'] <= 2.5
        return q, diag

    def ee_pose(self, arm):
        """Return copies of the grip-site xyz (m) and wxyz quaternion, both in T."""
        site = self.data.site(f'{arm}_grip')
        R = self.T_world_table[:3, :3].T @ site.xmat.reshape(3, 3)
        quat = np.empty(4)
        mj.mju_mat2Quat(quat, R.ravel())
        return self.to_table(site.xpos), quat

    def arm_q(self, arm):
        """Measured seven joints in shoulder-through-wrist IK order (rad)."""
        return self.data.qpos[self.ik[arm].qadr].copy()

    def set_grasp_target(self, arm, oid):
        """Select an explicit P-gate candidate/synergy; None means auto-selection."""
        if arm not in ARMS:
            raise ValueError(arm)
        if oid is not None and oid not in self.object_parts:
            raise KeyError(oid)
        self._grasp_target[arm] = oid
        self._ee_profile[arm] = None

    def apply_ee_delta(self, arm, dpos_T, daxisangle, grip01, dt=0.1):
        """Apply one T-frame increment (m, rotation vector in rad) and grip [0,1].

        Uses GT only for choosing the nearby object's synergy and P-gate weld
        candidate. Reports ok/reason_code/held_oid; an IK failure keeps the last
        arm target but still applies the hand command and advances simulation.
        """
        dp, dr = (np.asarray(v, dtype=float) for v in (dpos_T, daxisangle))
        grip, dt = float(grip01), float(dt)
        if (dp.shape != (3,) or dr.shape != (3,) or not np.isfinite(np.r_[dp, dr, grip, dt]).all()
                or not 0 <= grip <= 1 or dt <= 0):
            raise ValueError('expected finite 3-vectors, grip in [0,1], dt > 0')
        xyz, quat = self.ee_pose(arm)
        angle = np.linalg.norm(dr)
        if angle:
            delta, result = np.empty(4), np.empty(4)
            mj.mju_axisAngle2Quat(delta, dr / angle, angle)
            mj.mju_mulQuat(result, delta, quat)
            quat = result
        R = np.empty(9)
        mj.mju_quat2Mat(R, quat)
        q, diag = self.solve_ik(arm, xyz + dp, R.reshape(3, 3), restarts=1)
        if diag['ok']:
            self.data.ctrl[self.arm_act[arm]] = q
        if grip < .85:
            self.release(arm)
        if self._ee_profile[arm] is None:
            nearest = self._grasp_target[arm] or min(self.object_parts, key=lambda oid: np.linalg.norm(
                self.to_table(self.data.xpos[self.object_bodies[oid]]) - xyz), default=None)
            profile = grasp_profile(self.object_parts.get(nearest))
            if grip > 0:
                self._ee_profile[arm] = profile
        else:
            profile = self._ee_profile[arm]
        sign = 1 if arm == 'left' else -1
        ctrl = hand_command(profile, grip, sign)
        if not profile['close_from_open']:
            ctrl += (1 - grip) * sign * np.asarray(profile['open'])
        self.data.ctrl[self.hand_act[arm]] = ctrl
        if grip == 0:
            self._ee_profile[arm] = None
        self.closed[arm] = grip >= .85
        held = self._held_oid(arm)
        slips = self.grasp_slips[arm]
        target = self._grasp_target[arm]
        candidates = (target,) if target is not None else self.object_parts
        for _ in range(max(1, round(dt / self.model.opt.timestep))):
            self.step()
            if self.closed[arm] and held is None and slips == self.grasp_slips[arm]:
                for oid in candidates:
                    if self.attach(arm, oid):
                        held = oid
                        break
        reason = ('GRASP_SLIP' if slips != self.grasp_slips[arm] else
                  None if diag['ok'] else 'IK_FAIL')
        attached = self._held_oid(arm)
        contact_oid = attached or held or target
        return dict(ok=reason is None, reason_code=reason, held_oid=attached,
                    ik_ok=diag['ok'], pos_err_m=diag['pos_err_mm'] / 1000,
                    attached_oid=attached, contact_fingers=sorted(self.contact_fingers(arm, contact_oid))
                    if contact_oid is not None else [])

    def _held_oid(self, arm):
        return next((oid for oid in self.object_parts if self.data.eq_active[
            self.model.equality(f'm2a_weld_{arm}_{oid}').id]), None)

    def contact_fingers(self, arm, oid):
        target = self.object_geoms[oid]; tips = self.tip_geoms[arm]
        out = set()
        for i in range(self.data.ncon):
            c = self.data.contact[i]
            other = c.geom2 if c.geom1 == target else c.geom1 if c.geom2 == target else -1
            if other in tips and c.efc_address >= 0 and c.dist <= .001:
                out.add(tips[other])
        return out

    def palm_relative(self, arm, oid):
        hand = self.data.body(f'{arm}_wrist_yaw_link')
        return hand.xmat.reshape(3, 3).T @ (self.data.xpos[self.object_bodies[oid]] - hand.xpos)

    def in_palm(self, arm, oid):
        x, y, z = self.palm_relative(arm, oid)
        y *= 1 if arm == 'left' else -1
        return .085 <= x <= .181 and -.09 <= y <= -.008 and abs(z) <= .043

    def attach(self, arm, oid, *, oracle=False):
        if self._held_oid(arm) is not None:
            return False
        if not oracle:
            fingers = self.contact_fingers(arm, oid)
            if not (self.closed[arm] and len(fingers) >= 2 and 'thumb' in fingers and self.in_palm(arm, oid)):
                return False
        m, d = self.model, self.data
        if any(d.eq_active[m.equality(f'm2a_weld_{side}_{oid}').id] for side in ARMS):
            return False
        a = m.equality(f'm2a_weld_{arm}_{oid}').id
        hand = d.body(f'{arm}_wrist_yaw_link'); obj = d.body(self.object_bodies[oid])
        # MuJoCo weld: first anchor in body2, relative position in body1.
        m.eq_data[a, :3] = 0
        m.eq_data[a, 3:6] = self.palm_relative(arm, oid)
        inverse = np.empty(4)
        mj.mju_negQuat(inverse, hand.xquat)
        mj.mju_mulQuat(m.eq_data[a, 6:10], inverse, obj.xquat)
        d.eq_active[a] = True
        if not oracle:
            self._gate_welds[arm] = (oid, a, 0)
        return True

    def release(self, arm):
        self.closed[arm] = False
        self._gate_welds.pop(arm, None)
        for oid in self.object_parts:
            self.data.eq_active[self.model.equality(f'm2a_weld_{arm}_{oid}').id] = False

    def camera_K(self, cam='head'):
        """Pinhole intrinsics in pixels (integer-indexed pixel centres)."""
        width, height = CAMERAS[cam]
        fovy = self.model.camera(cam).fovy[0]
        f = .5 * height / np.tan(np.deg2rad(fovy) * .5)
        return np.array([[f, 0., (width-1)*.5], [0., f, (height-1)*.5], [0., 0., 1.]])

    def T_world_cam(self, cam='head'):
        """Current camera-to-world transform (OpenCV x right, y down, z forward)."""
        cid = self.model.camera(cam).id
        T = np.eye(4)
        T[:3, :3] = self.data.cam_xmat[cid].reshape(3, 3) @ np.diag([1., -1., -1.])
        T[:3, 3] = self.data.cam_xpos[cid]
        return T

    def T_table_cam(self, cam='head'):
        """Current camera-to-table transform at the same state as render(cam)."""
        return np.linalg.solve(self.T_world_table, self.T_world_cam(cam))

    def render(self, cam='head'):
        """Return (uint8 RGB, float32 depth in metres), channel-last RGB."""
        width, height = CAMERAS[cam]
        if cam not in self._renderers:
            self._renderers[cam] = mj.Renderer(self.model, height=height, width=width)
        r = self._renderers[cam]
        opt = mj.MjvOption(); opt.geomgroup[3:] = 0; opt.sitegroup[5] = 0
        r.disable_depth_rendering(); r.update_scene(self.data, camera=cam, scene_option=opt)
        rgb = r.render()
        r.enable_depth_rendering()
        try:
            return rgb, r.render()
        finally:
            r.disable_depth_rendering()

    def close(self):
        for r in self._renderers.values():
            r.close()
        self._renderers.clear()
