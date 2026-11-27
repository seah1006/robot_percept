"""Scripted Dex3 skills; GT-assisted pose targets (not policy observations)."""
from __future__ import annotations
import math
import time
import mujoco as mj
import numpy as np
from m2a.scene._geometry import contains, corners, geometric_tray, obb, overlaps, size_xyz, tray_box
from .g1_manip_env import ARMS, FIXTURE_BIT, TRAY_FLOOR, half_height
from .grasp_profiles import PROFILES, grasp_profile, hand_command

MODES = ('P-phys', 'P-gate', 'P-oracle')
SKILLS = ('reach_pregrasp', 'grasp_lift', 'transport_place', 'put_aside')


class SkillRunner:
    def __init__(self, env, grasp_mode='P-phys'):
        if grasp_mode not in MODES:
            raise ValueError(grasp_mode)
        self.env = env
        self.mode = grasp_mode
        self._data = None
        self.events = {}

    def run(self, skill, arm, oid=None, target=None, *, obj_pose_T=None):
        if skill not in SKILLS or arm not in ARMS:
            raise ValueError((skill, arm))
        if self._data is not self.env.data:
            self._data = self.env.data
            self.pre = {}; self.held = {}; self.events = {}
        predicted = obj_pose_T is not None
        picking = skill in ('reach_pregrasp', 'grasp_lift')
        if predicted and not picking:
            raise ValueError('obj_pose_T is only used for picking')
        if predicted and self.mode == 'P-oracle':
            raise ValueError('predicted picking cannot use P-oracle')
        if oid is None and not picking:
            oid = self.held.get(arm, (None, None))[0]
        if not predicted and oid not in self.env.object_parts and (picking or oid is not None):
            raise KeyError(oid)
        t0 = time.perf_counter()
        reason = (getattr(self, '_' + skill)(arm, oid, target, obj_pose_T=obj_pose_T) if predicted else
                  getattr(self, '_' + skill)(arm, oid, target))
        result = dict(ok=reason is None, reason_code=reason, internal_done=reason is None,
                      t_ms=int((time.perf_counter() - t0) * 1000))
        if predicted:
            result['grasped_oid'] = self.held.get(arm, (None, None))[0] if reason is None and skill == 'grasp_lift' else None
        return result

    def _move(self, arm, q, secs, check_fixture=True):
        e = self.env; ids = e.arm_act[arm]
        steps = math.ceil(secs / e.model.opt.timestep)
        start = e.data.ctrl[ids].copy(); collided = False
        for i in range(1, steps + 1, 4):
            end = min(i + 3, steps); f = end / steps; s = f*f*(3-2*f)
            e.data.ctrl[ids] = start + s*(q-start)
            e.step(end-i+1)
            if check_fixture:
                for j in range(e.data.ncon):
                    c = e.data.contact[j]
                    pair = {c.geom1, c.geom2}
                    if c.dist < -.004 and pair & e.arm_geom[arm] and any(e.model.geom_contype[g] == FIXTURE_BIT for g in pair):
                        collided = True
        e.step(math.ceil(.20 / e.model.opt.timestep))
        e.step(math.ceil(.20 / e.model.opt.timestep))
        if collided:
            return 'COLLISION'
        if np.max(np.abs(e.data.qpos[e.ik[arm].qadr] - q)) > .23:
            self.events["tracking_error"] = (e.data.qpos[e.ik[arm].qadr] - q).tolist()
            return 'TIMEOUT'
        return None

    def _segment(self, arm, a, b, R, q0, count=3):
        qs = []
        for j in range(1, count + 1):
            q0, diag = self.env.solve_ik(arm, a + (b-a)*j/count, R, q0=q0, restarts=0)
            if not diag['ok']:
                return None
            qs.append(q0)
        return qs

    def _open(self, arm, profile):
        self.env.release(arm)
        self.env.data.ctrl[self.env.hand_act[arm]] = np.asarray(profile['open']) * (1 if arm == 'left' else -1)

    def _reach_pregrasp(self, arm, oid, target, *, obj_pose_T=None):
        e = self.env
        if arm in self.held:
            if self.is_attached(arm, self.held[arm][0]):
                return 'COLLISION'
            self.held.pop(arm)
        if obj_pose_T is None:
            gt = e.get_gt_objects()[oid]
            pid = gt['part_id']
            part = e.parts[pid]
        else:
            gt = obj_pose_T
            size = np.asarray(gt['size'], dtype=float)
            xyz = np.asarray(gt['xyz'], dtype=float)
            if (xyz.shape != (3,) or size.shape not in ((2,), (3,)) or
                    not np.isfinite(np.r_[xyz, size, gt['yaw']]).all() or np.any(size <= 0)):
                raise ValueError('invalid predicted pose: expected xyz[3], yaw, positive size[2 or 3]')
            pid = gt.get('part_id')
            part = dict(shape=gt.get('shape', e.parts.get(pid, {}).get('shape', 'cylinder' if len(size)==2 else 'box')))
        profile = grasp_profile(pid)
        self._open(arm, profile)
        source_tray = geometric_tray(gt['xyz'], e.layout)
        center = contains(e.layout['regions']['center_zone'], gt['xyz']) and source_tray is None
        xyz = np.asarray(gt['xyz'])
        # Across the narrow side; cylindrical control uses a free yaw.
        base = gt['yaw'] + profile.get('approach_yaw_offset', math.pi/2) if part['shape'] == 'box' else 0.
        headings = [base, base+math.pi]
        if part['shape'] == 'cylinder':
            headings += [math.pi/2, -math.pi/2]
        elif pid == 'P06':
            headings += [base+math.pi/2, base-math.pi/2]
        if source_tray or center:
            headings += [base + turn for turn in (math.pi/2, -math.pi/2, math.pi/4, -math.pi/4, 3*math.pi/4, -3*math.pi/4)]
        if source_tray:
            headings = [0., math.pi] + headings  # Along the long axis of the current trays.
        headings = list({round(yaw % (2*math.pi), 5): yaw for yaw in headings}.values())
        nominal = xyz + [0, 0, .003]
        self.events.update(profile=profile['name'], stage='pregrasp', source_tray=source_tray)
        best = None
        viable_ik = False
        for yaw in headings:
            R = e.topdown(arm, yaw)
            at = nominal + R @ profile['offset_hand_m']
            above = at + [0, 0, .072]
            q, diag = e.solve_ik(arm, above, R, restarts=2)
            if not diag['ok']:
                continue
            down = self._segment(arm, above, at, R, q)
            if down is None:
                continue
            lift = self._segment(arm, at, at+[0, 0, .10], R, down[-1])
            if lift is None:
                continue
            viable_ik = True
            if source_tray and not self._fixture_free(arm, [q, *down, *lift]):
                continue
            score = np.linalg.norm(q-e.data.qpos[e.ik[arm].qadr])
            if best is None or score < best[0]:
                best = (score, above, at, R, q, down, lift)
        if best is None:
            return 'COLLISION' if viable_ik else 'IK_FAIL'
        _, above, at, R, q, down, lift = best
        self.events.update(approach_xyz=above.tolist(), grasp_xyz=at.tolist())
        reason = self._move(arm, q, 1.0)
        if reason is None:
            self.pre[arm] = (oid, above, at, R, down, lift, profile)
        return reason

    def _fixture_free(self, arm, path):
        """Reject tray descent paths intersecting a fixture with the open hand."""
        e = self.env; m = e.model
        preview = mj.MjData(m)
        preview.qpos[:] = e.data.qpos
        joints = m.jnt_qposadr[m.actuator_trnid[e.hand_act[arm], 0]]
        preview.qpos[joints] = e.data.ctrl[e.hand_act[arm]]
        for q in path:
            preview.qpos[e.ik[arm].qadr] = q
            mj.mj_forward(m, preview)
            for con in preview.contact:
                if con.dist < -.002 and ((con.geom1 in e.arm_geom[arm] and m.geom_contype[con.geom2] == FIXTURE_BIT)
                                         or (con.geom2 in e.arm_geom[arm] and m.geom_contype[con.geom1] == FIXTURE_BIT)):
                    return False
        return True

    def _grasp_lift(self, arm, oid, target, *, obj_pose_T=None):
        e = self.env
        predicted = obj_pose_T is not None
        if predicted or arm not in self.pre or self.pre[arm][0] != oid:
            result = self._reach_pregrasp(arm, oid, target, obj_pose_T=obj_pose_T)
            if result:
                return result
        _, above, at, R, down, lift, profile = self.pre.pop(arm)
        for q in down:
            result = self._move(arm, q, .22)
            if result:
                self.events['stage'] = 'descend'
                return result
        sign = 1 if arm == 'left' else -1
        candidate = None if predicted else oid
        h = e.hand_act[arm]; steps = math.ceil(.4/e.model.opt.timestep)
        attached = False; peak = []; selected = None
        slips = e.grasp_slips[arm]
        for i in range(1, steps+1, 4):
            end = min(i+3, steps); f = min(1., end / (steps*.7))
            e.data.ctrl[h] = hand_command(profile, f, sign)
            e.closed[arm] = f >= .85
            e.step(end-i+1)
            if predicted and not attached:
                possible = [(o, e.contact_fingers(arm,o)) for o in e.object_parts if e.in_palm(arm,o)]
                possible = [(o,f) for o,f in possible if f]
                candidate = max(possible, key=lambda pair: ('thumb' in pair[1], len(pair[1])), default=(None, ()))[0]
            contacts = sorted(e.contact_fingers(arm, candidate)) if candidate is not None else []
            if len(contacts) > len(peak):
                peak = contacts
            if e.closed[arm] and not attached and candidate is not None and self.mode != 'P-phys':
                attached = e.attach(arm, candidate, oracle=self.mode == 'P-oracle')
                if attached:
                    selected = contacts
        self.events.update(stage='closure', peak_fingers=peak, weld=attached, weld_fingers=selected,
                           palm_relative=e.palm_relative(arm, candidate).tolist() if candidate is not None else None)
        if candidate is None or (self.mode != 'P-phys' and not attached):
            return 'GRASP_SLIP'
        if e.grasp_slips[arm] != slips:
            return 'GRASP_SLIP'
        for q in lift:
            result = self._move(arm, q, .24)
            if e.grasp_slips[arm] != slips:
                self.events['stage'] = 'lift'
                return 'GRASP_SLIP'
            if result:
                self.events['stage'] = 'lift'
                return result
        self.events['stage'] = 'post_lift'
        oid = candidate
        if e.get_gt_objects()[oid]['xyz'][2] < at[2] + .055 or not self.is_attached(arm, oid):
            return 'GRASP_SLIP'
        self.held[arm] = (oid, R)
        return None

    def is_attached(self, arm, oid):
        e = self.env
        eq = e.model.equality(f'm2a_weld_{arm}_{oid}').id
        if self.mode != 'P-phys':
            return bool(e.data.eq_active[eq] and e.in_palm(arm, oid))
        return e.closed[arm] and e.in_palm(arm, oid) and bool(e.contact_fingers(arm, oid))

    def _transport_place(self, arm, oid, target):
        return self._place(arm, oid, target, tray=True)

    def _put_aside(self, arm, oid, target):
        return self._place(arm, oid, 'center_zone' if target is None else target, tray=False)

    def _empty_slot(self, oid, region):
        e = self.env
        gt = e.get_gt_objects()
        x, X, y, Y = rect = e.layout['regions'][region]
        part = e.parts[e.object_parts[oid]]
        size = size_xyz(part)
        yaw = gt[oid]['yaw'] if part['shape'] == 'box' else 0.
        occupied = [obb(o['xyz'], size_xyz(e.parts[o['part_id']]), o['yaw'])
                    for other, o in gt.items() if other != oid]
        occupied.extend(tray_box(tr) for tr in e.layout['trays'].values())
        middle = np.array([(x+X)/2, (y+Y)/2])
        grid = [(a, b) for a in np.linspace(x, X, 13) for b in np.linspace(y, Y, 13)]
        for pos in sorted(grid, key=lambda xy: np.linalg.norm(xy - middle)):
            box = obb(pos, size, yaw)
            if all(contains(rect, v) for v in corners(box)) and not any(overlaps(box, ob, .003) for ob in occupied):
                return pos
        return None

    def _place(self, arm, oid, target, tray):
        e = self.env
        if arm not in self.held or self.held[arm][0] != oid:
            return 'GRASP_SLIP'
        if not self.is_attached(arm, oid):
            self.held.pop(arm)
            return 'GRASP_SLIP'
        _, R = self.held[arm]
        wall = floor = 0.
        if tray:
            loc = e.layout['trays'][target]
            xy = loc['center']; wall = loc['wall_h']; floor = loc.get('floor_z', TRAY_FLOOR)
        else:
            xy = self._empty_slot(oid, target)
            if xy is None:
                return 'COLLISION'
        h = half_height(e.parts[e.object_parts[oid]])
        grip_xyz, _ = e.ee_pose(arm)
        item_xyz = e.get_gt_objects()[oid]['xyz']
        at = np.array([*xy, floor+wall+h+.018]) + grip_xyz - item_xyz
        above = at + [0, 0, .06]
        q, diag = e.solve_ik(arm, above, R)
        if not diag['ok']:
            return 'IK_FAIL'
        down = self._segment(arm, above, at, R, q)
        if down is None:
            return 'IK_FAIL'
        for waypoint, sec in [(q, .95), *((p, .18) for p in down)]:
            reason = self._move(arm, waypoint, sec)
            if not self.is_attached(arm, oid):
                self.held.pop(arm, None)
                return 'GRASP_SLIP'
            if reason:
                return reason
        self._open(arm, grasp_profile(e.object_parts[oid]))
        self.held.pop(arm)
        e.step(math.ceil(.25/e.model.opt.timestep))
        reason = self._move(arm, q, .4)
        e.step(math.ceil(.35/e.model.opt.timestep))
        return reason
