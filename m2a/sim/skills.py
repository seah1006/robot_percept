"""Scripted Dex3 skills; GT-assisted pose targets (not policy observations)."""
from __future__ import annotations
import json
import math
from pathlib import Path
import time
import numpy as np
from .g1_manip_env import ARMS, TRAY_FLOOR, half_height

MODES = ('P-phys', 'P-gate', 'P-oracle')
SKILLS = ('reach_pregrasp', 'grasp_lift', 'transport_place', 'put_aside')
PROFILES = json.loads(Path(__file__).with_name('grasp_profiles.json').read_text(encoding='utf-8'))


def grasp_profile(part_id):
    return PROFILES['parts'].get(part_id, PROFILES['default'])


def hand_command(profile, progress, sign):
    # Nominal Dex3 targets in HAND order: thumb, index, middle.
    cmd = progress * np.array(profile['close'], dtype=float)
    if profile['close_from_open']:
        delay = profile['thumb_delay']
        thumb = np.clip((progress-delay)/(1-delay), 0, 1)
        cmd[:3] = (1-thumb)*np.array(profile['open'][:3]) + thumb*np.array(profile['close'][:3])
    return sign * cmd


class SkillRunner:
    def __init__(self, env, grasp_mode='P-phys'):
        if grasp_mode not in MODES:
            raise ValueError(grasp_mode)
        self.env = env
        self.mode = grasp_mode
        self._data = None
        self.events = {}

    def run(self, skill, arm, oid, target=None):
        if skill not in SKILLS or arm not in ARMS:
            raise ValueError((skill, arm))
        if oid not in self.env.object_parts:
            raise KeyError(oid)
        if self._data is not self.env.data:
            self._data = self.env.data
            self.pre = {}; self.held = {}; self.events = {}
        t0 = time.perf_counter()
        reason = getattr(self, '_' + skill)(arm, oid, target)
        return dict(ok=reason is None, reason_code=reason, internal_done=reason is None,
                    t_ms=int((time.perf_counter() - t0) * 1000))

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
                    if c.dist < -.004 and pair & e.arm_geom[arm] and any(e.model.geom_contype[g] == 4 for g in pair):
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

    def _reach_pregrasp(self, arm, oid, target):
        e = self.env
        if arm in self.held:
            return 'COLLISION'
        profile = grasp_profile(e.object_parts[oid])
        self._open(arm, profile)
        gt = e.get_gt_objects()[oid]
        xyz = np.asarray(gt['xyz']); part = e.parts[gt['part_id']]
        # Across the narrow side; cylindrical control uses a free yaw.
        base = gt['yaw'] + math.pi/2 if part['shape'] == 'box' else 0.
        headings = [base, base+math.pi]
        if part['shape'] == 'cylinder':
            headings += [math.pi/2, -math.pi/2]
        elif gt['part_id'] == 'P06':
            headings += [base+math.pi/2, base-math.pi/2]
        nominal = xyz + [0, 0, .003]
        self.events.update(profile=profile['name'], stage='pregrasp')
        best = None
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
            score = np.linalg.norm(q-e.data.qpos[e.ik[arm].qadr])
            if best is None or score < best[0]:
                best = (score, above, at, R, q, down, lift)
        if best is None:
            return 'IK_FAIL'
        _, above, at, R, q, down, lift = best
        self.events.update(approach_xyz=above.tolist(), grasp_xyz=at.tolist())
        reason = self._move(arm, q, 1.0)
        if reason is None:
            self.pre[arm] = (oid, above, at, R, down, lift)
        return reason

    def _grasp_lift(self, arm, oid, target):
        e = self.env
        if arm not in self.pre or self.pre[arm][0] != oid:
            result = self._reach_pregrasp(arm, oid, target)
            if result:
                return result
        _, above, at, R, down, lift = self.pre.pop(arm)
        for q in down:
            result = self._move(arm, q, .22)
            if result:
                self.events['stage'] = 'descend'
                return result
        sign = 1 if arm == 'left' else -1
        profile = grasp_profile(e.object_parts[oid])
        h = e.hand_act[arm]; steps = math.ceil(.4/e.model.opt.timestep)
        attached = False; peak = []; selected = None
        for i in range(1, steps+1, 4):
            end = min(i+3, steps); f = min(1., end / (steps*.7))
            e.data.ctrl[h] = hand_command(profile, f, sign)
            e.closed[arm] = f >= .85
            e.step(end-i+1)
            contacts = sorted(e.contact_fingers(arm, oid))
            if len(contacts) > len(peak):
                peak = contacts
            if e.closed[arm] and not attached and self.mode != 'P-phys':
                attached = e.attach(arm, oid, oracle=self.mode == 'P-oracle')
                if attached:
                    selected = contacts
        self.events.update(stage='closure', peak_fingers=peak, weld=attached, weld_fingers=selected,
                           palm_relative=e.palm_relative(arm, oid).tolist())
        if self.mode != 'P-phys' and not attached:
            return 'GRASP_SLIP'
        for q in lift:
            result = self._move(arm, q, .24)
            if result:
                self.events['stage'] = 'lift'
                return result
        self.events['stage'] = 'post_lift'
        if e.get_gt_objects()[oid]['xyz'][2] < at[2] + .055 or not self.is_attached(arm, oid):
            return 'GRASP_SLIP'
        self.held[arm] = (oid, R)
        return None

    def is_attached(self, arm, oid):
        e = self.env
        eq = e.model.equality(f'm2a_weld_{arm}_{oid}').id
        return bool(e.data.eq_active[eq] and e.in_palm(arm, oid) or
                    (e.closed[arm] and e.in_palm(arm, oid) and bool(e.contact_fingers(arm, oid))))

    def _transport_place(self, arm, oid, target):
        return self._place(arm, oid, target, tray=True)

    def _put_aside(self, arm, oid, target):
        return self._place(arm, oid, target, tray=False)

    def _place(self, arm, oid, target, tray):
        e = self.env
        if arm not in self.held or self.held[arm][0] != oid or not self.is_attached(arm, oid):
            return 'GRASP_SLIP'
        _, R = self.held[arm]
        wall = floor = 0.
        if tray:
            loc = e.layout['trays'][target]
            xy = loc['center']; wall = loc['wall_h']; floor = loc.get('floor_z', TRAY_FLOOR)
        else:
            x0, x1, y0, y1 = e.layout['regions'][target]
            xy = [(x0+x1)/2, (y0+y1)/2]
        h = half_height(e.parts[e.object_parts[oid]])
        at = np.array([*xy, floor+wall+h+.018]); above = at + [0, 0, .06]
        q, diag = e.solve_ik(arm, above, R)
        if not diag['ok']:
            return 'IK_FAIL'
        down = self._segment(arm, above, at, R, q)
        if down is None:
            return 'IK_FAIL'
        for waypoint, sec in [(q, .95), *((p, .18) for p in down)]:
            reason = self._move(arm, waypoint, sec)
            if reason:
                return reason
            if not self.is_attached(arm, oid):
                self.held.pop(arm, None)
                return 'GRASP_SLIP'
        self._open(arm, grasp_profile(e.object_parts[oid]))
        self.held.pop(arm)
        e.step(math.ceil(.25/e.model.opt.timestep))
        reason = self._move(arm, q, .4)
        e.step(math.ceil(.35/e.model.opt.timestep))
        return reason
