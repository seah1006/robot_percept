"""Scripted Dex3 skills; GT-assisted pose targets (not policy observations)."""
from __future__ import annotations
import math
import time
import mujoco as mj
import numpy as np
from m2a.scene._geometry import contains, corners, geometric_tray, inset, obb, overlaps, size_xyz, tray_box, tray_rect
from .g1_manip_env import ARMS, FIXTURE_BIT, GATE_RULES, TRAY_FLOOR, half_height
from .grasp_profiles import PROFILES, grasp_profile, hand_command

# P-gate (default): GT-assisted weld grasp approximation, proposal definition (>=2 fingertips,
# thumb optional; release after 200 ms with zero contacts). P-gate-strict: thumb required,
# release after 200 ms with <=1 contact. P-phys: friction only. P-oracle: debug only.
MODES = ('P-phys', 'P-gate', 'P-gate-strict', 'P-oracle')
SKILLS = ('reach_pregrasp', 'grasp_lift', 'transport_place', 'put_aside')
PLATES = ('P01', 'P02', 'P03')
PREGRASP_RISE = .08           # imposed extra height of the approach waypoint
PLACE_CLEAR = .002            # imposed footprint clearance to tray inner walls
CARRY_BOTTOM = .10            # imposed object-bottom height above support while carrying
RELEASE_BOTTOMS = (.006, .016, None)  # imposed release heights above support; None = over wall top
RELEASE_PRESS = .008          # imposed guarded-descent overshoot below the release height


class SkillRunner:
    def __init__(self, env, grasp_mode='P-phys'):
        if grasp_mode not in MODES:
            raise ValueError(grasp_mode)
        self.env = env
        self.mode = grasp_mode
        self._data = None
        self.events = {}

    def run(self, skill, arm, oid=None, target=None, *, obj_pose_T=None, approach=None):
        """An optional absolute table-frame yaw (rad) constrains picking, not object pose.

        A predicted grasp replans from its latest pose; pass the yaw to that call too.
        An observed/GT grasp without it consumes the matching cached pregrasp as before.
        """
        if skill not in SKILLS or arm not in ARMS:
            raise ValueError((skill, arm))
        if self._data is not self.env.data:
            self._data = self.env.data
            self.pre = {}; self.held = {}; self.events = {}
        if self.mode in GATE_RULES:
            self.env.set_gate_mode(self.mode)
        predicted = obj_pose_T is not None
        picking = skill in ('reach_pregrasp', 'grasp_lift')
        if approach is not None and (not picking or not math.isfinite(approach)):
            raise ValueError('approach must be a finite yaw in radians for picking')
        if predicted and not picking:
            raise ValueError('obj_pose_T is only used for picking')
        if predicted and self.mode == 'P-oracle':
            raise ValueError('predicted picking cannot use P-oracle')
        if oid is None and not picking:
            oid = self.held.get(arm, (None, None))[0]
        if not predicted and oid not in self.env.object_parts and (picking or oid is not None):
            raise KeyError(oid)
        t0 = time.perf_counter()
        kwargs = {} if not predicted else {'obj_pose_T': obj_pose_T}
        if approach is not None:
            kwargs['approach'] = float(approach)
        reason = getattr(self, '_' + skill)(arm, oid, target, **kwargs)
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

    def _reach_pregrasp(self, arm, oid, target, *, obj_pose_T=None, approach=None):
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
        legacy = getattr(self, 'legacy_place', False)
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
        if approach is not None:
            headings = [approach]
        headings = list({round(yaw % (2*math.pi), 5): yaw for yaw in headings}.values())
        nominal = xyz + [0, 0, .003 + profile.get('grasp_dz', 0.)]
        self.events.update(profile=profile['name'], stage='pregrasp', source_tray=source_tray)
        best = None
        viable_ik = False
        wall_shift = np.zeros(3)
        if source_tray and pid in PLATES and not legacy:
            lo_x, hi_x, lo_y, hi_y = tray_rect(e.layout['trays'][source_tray])
            wall_dist = [xyz[0]-lo_x, hi_x-xyz[0], xyz[1]-lo_y, hi_y-xyz[1]]
            normal = np.asarray(([1,0],[-1,0],[0,1],[0,-1])[int(np.argmin(wall_dist))])
            axis = np.asarray([math.cos(gt['yaw']), math.sin(gt['yaw'])])
            along = np.dot(normal, axis)
            wall_shift[:2] = .012 * (math.copysign(1., along)*axis if abs(along) >= .4 else normal)
        # O0 only: use nearby footprints to keep the thumb side away from neighbours.
        # O3 picks never query GT neighbour poses; only source pose and fixture geometry.
        neighbors = []
        if obj_pose_T is None and not legacy:
            for key, other in e.get_gt_objects().items():
                delta = np.subtract(other['xyz'], xyz)
                if key != oid and abs(delta[2]) < .06 and np.linalg.norm(delta[:2]) < .125:
                    neighbors.append(delta[:2])
        tiers = [(0., False)]
        if source_tray:
            tiers += ([(0., True), (.006, True), (.012, True), (.024, True)]
                      if np.any(wall_shift) else [(h, False) for h in (.012, .024)])
        options = [(yaw, height, shifted) for height, shifted in tiers for yaw in headings]
        for yaw, height, shifted in options:
            if height and best is not None:
                break
            R = e.topdown(arm, yaw)
            at = nominal + R @ profile['offset_hand_m'] + [0, 0, height]
            if shifted:
                at += wall_shift
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
            score = np.linalg.norm(q-e.data.qpos[e.ik[arm].qadr]) + height * 50.
            if neighbors:
                # Tool +x extends toward the distal fingertips; penalize pointing at clutter.
                axis = R[:2, 0]
                score += sum(2.8 * max(0., 1-np.linalg.norm(d)/.125) *
                             max(0., np.dot(d, axis)/max(.001, np.linalg.norm(d)))
                             for d in neighbors)
            if source_tray and pid in PLATES and not legacy:
                dev = abs(((yaw - base + math.pi/2) % math.pi) - math.pi/2)
                score += 1.3 * dev - (.28 if shifted else 0.)
            if center and pid in PLATES:
                # Centre-zone plates: across-width first, then diagonal; along-axis slips in lift
                # (round3_center_diag_P01.jsonl). Tier weight is an imposed value.
                dev = abs(((yaw - base + math.pi/2) % math.pi) - math.pi/2)
                score += 100. * (0 if dev < 1e-3 else 1 if dev < math.pi/3 else 2)
            if best is None or score < best[0]:
                best = (score, above, at, R, q, down, lift)
        if best is None:
            return 'COLLISION' if viable_ik else 'IK_FAIL'
        _, above, at, R, q, down, lift = best
        self.events.update(approach_xyz=above.tolist(), grasp_xyz=at.tolist(),
                           approach_yaw=float(math.atan2(R[1, 0], R[0, 0])))
        # Round 4: approach via a point PREGRASP_RISE above the pregrasp pose so the joint-space
        # sweep from rest does not drag the hand through tray walls / neighbours (TIMEOUT cases).
        qh, dh = e.solve_ik(arm, above + [0, 0, PREGRASP_RISE], R, q0=q, restarts=0)
        if dh['ok'] and not getattr(self, 'legacy_place', False):
            reason = self._move(arm, qh, .6) or self._move(arm, q, .45)
        else:
            reason = self._move(arm, q, 1.0)
        if reason is None:
            self.pre[arm] = (oid, above, at, R, down, lift, profile)
        return reason

    def _fixture_free(self, arm, path, geoms=None):
        """Reject tray descent paths intersecting a tray wall with the open hand.

        Floor/table penetration of the kinematic open-hand preview (thumb ~25 mm, see
        round3_tray_diag) is the same as in table picks and is resolved by contact physics,
        so only wall geoms block (round 3 change). Placing passes all fixture geoms."""
        e = self.env; m = e.model
        walls = geoms if geoms is not None else {m.geom(f'{tray}_{axis}{sign}').id for tray in e.layout['trays']
                 for axis in 'xy' for sign in (-1, 1)}
        preview = mj.MjData(m)
        preview.qpos[:] = e.data.qpos
        joints = m.jnt_qposadr[m.actuator_trnid[e.hand_act[arm], 0]]
        preview.qpos[joints] = e.data.ctrl[e.hand_act[arm]]
        for q in path:
            preview.qpos[e.ik[arm].qadr] = q
            mj.mj_forward(m, preview)
            for con in preview.contact:
                if con.dist < -.002 and ((con.geom1 in e.arm_geom[arm] and con.geom2 in walls)
                                         or (con.geom2 in e.arm_geom[arm] and con.geom1 in walls)):
                    return False
        return True

    def _grasp_lift(self, arm, oid, target, *, obj_pose_T=None, approach=None):
        e = self.env
        predicted = obj_pose_T is not None
        cached = self.pre.get(arm)
        same_heading = (cached is not None and (approach is None or abs(math.remainder(
            approach - math.atan2(cached[3][1, 0], cached[3][0, 0]), 2*math.pi)) < 1e-6))
        if predicted or not same_heading or cached[0] != oid:
            result = self._reach_pregrasp(arm, oid, target, obj_pose_T=obj_pose_T, approach=approach)
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
            early = getattr(self, 'legacy_place', False) or self.mode == 'P-oracle'
            # Let the commanded closure reach its final shape before requesting the same gate.
            if e.closed[arm] and (early or f >= 1.) and not attached and candidate is not None and self.mode != 'P-phys':
                attached = e.attach(arm, candidate, oracle=self.mode == 'P-oracle')
                if attached:
                    selected = contacts
        if self.mode == 'P-phys':
            thumb = candidate is not None and 'thumb' in e.contact_fingers(arm, candidate)
        else:
            thumb = bool(attached and 'thumb' in selected)
        self.events.update(stage='closure', peak_fingers=peak, weld=attached, weld_fingers=selected,
                           thumb_opposed=thumb, min_contacts_during_lift=None,
                           palm_relative=e.palm_relative(arm, candidate).tolist() if candidate is not None else None)
        if candidate is None or (self.mode != 'P-phys' and not attached):
            return 'GRASP_SLIP'
        if e.grasp_slips[arm] != slips:
            return 'GRASP_SLIP'
        e.watch_contacts(arm, candidate)
        try:
            for q in lift:
                result = self._move(arm, q, .24)
                if e.grasp_slips[arm] != slips:
                    self.events['stage'] = 'lift'
                    return 'GRASP_SLIP'
                if result:
                    self.events['stage'] = 'lift'
                    return result
        finally:
            self.events['min_contacts_during_lift'] = e.unwatch_contacts(arm)
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

    def _empty_slot(self, oid, region, yaw=None, limit=1, tray=None):
        """Free footprint centres (non-overlapping other objects and tray boxes/walls).

        Default call keeps the round-1 behaviour (first slot for the current yaw or None).
        With tray=<id> the footprint must sit inside the tray inner rectangle minus
        PLACE_CLEAR and the centre inside the judge inset."""
        e = self.env
        gt = e.get_gt_objects()
        part = e.parts[e.object_parts[oid]]
        size = size_xyz(part)
        if yaw is None:
            yaw = gt[oid]['yaw'] if part['shape'] == 'box' else 0.
        occupied = [obb(o['xyz'], size_xyz(e.parts[o['part_id']]), o['yaw'])
                    for other, o in gt.items() if other != oid and not any(
                        self.is_attached(a, other) for a in ARMS)]
        if tray is None:
            x, X, y, Y = rect = e.layout['regions'][region]
            inner = rect; centre = rect
            occupied.extend(tray_box(tr) for tr in e.layout['trays'].values())
        else:
            x, X, y, Y = rect = tray_rect(e.layout['trays'][tray])
            inner = inset(rect, PLACE_CLEAR); centre = inset(rect, e.layout['judge']['tray_margin'])
        middle = np.array([(x+X)/2, (y+Y)/2])
        nx, ny = (13, 13) if tray is None else (17, 27)  # finer tray grid: 2xP01 side by side is .12 of .13
        grid = [(a, b) for a in np.linspace(x, X, nx) for b in np.linspace(y, Y, ny)]
        margin = .003 if tray is None else .002
        if tray is None:
            order = lambda xy: np.linalg.norm(xy - middle)
        else:
            # Round 4: pack against a long (y) wall first so the rest of the tray stays usable.
            order = lambda xy: (round(min(xy[1] - y, Y - xy[1]), 4), abs(xy[0] - middle[0]))
        found = []
        for pos in sorted(grid, key=order):
            box = obb(pos, size, yaw)
            if (contains(centre, pos) and all(contains(inner, v) for v in corners(box))
                    and not any(overlaps(box, ob, margin) for ob in occupied)):
                if limit == 1 and tray is None:
                    return pos
                found.append(np.asarray(pos, float))
                if len(found) >= limit:
                    break
        if limit == 1 and tray is None:
            return None
        return found

    def _place_yaws(self, pid, part, yaw0, tray):
        """Candidate final object yaws ordered by |hand rotation|."""
        if pid in PLATES:
            axis = 0. if tray else math.pi/2   # tray long axis = x; centre zone long axis = y
            # Footprint test in _empty_slot filters the yaws that do not fit (imposed offsets).
            finals = [axis + k*math.pi + s for k in (0, 1) for s in (0., .12, -.12, .25, -.25, .4, -.4)]
            deltas = [(f - yaw0 + math.pi) % (2*math.pi) - math.pi for f in finals]
        else:
            deltas = [0.] + [s*k*math.pi/6 for k in range(1, 7) for s in (1, -1)][:-1]
        return sorted(deltas, key=abs)

    def _plan_place(self, arm, oid, target, tray):
        """Search hand yaw x slot x release height; return the best IK-feasible placement."""
        e = self.env; m = e.model
        pid = e.object_parts[oid]; part = e.parts[pid]; h = half_height(part)
        gt = e.get_gt_objects()[oid]
        grip_xyz, _ = e.ee_pose(arm)
        d = np.asarray(gt['xyz']) - grip_xyz
        _, R0 = self.held[arm]
        h0 = math.atan2(R0[1, 0], R0[0, 0])
        if tray:
            loc = e.layout['trays'][target]
            support = loc.get('floor_z', TRAY_FLOOR); wall_top = support + loc['wall_h']
        else:
            support = 0.; wall_top = 0.
        fixtures = {g for g in range(m.ngeom) if m.geom_contype[g] == FIXTURE_BIT}
        best = None; tried = 0; free = 0
        for delta in self._place_yaws(pid, part, gt['yaw'], tray):
            final = gt['yaw'] + delta if part['shape'] == 'box' else 0.
            slots = self._empty_slot(oid, target, yaw=final, limit=3, tray=target if tray else None)
            free += bool(slots)
            c, s = math.cos(delta), math.sin(delta)
            dr = np.array([c*d[0]-s*d[1], s*d[0]+c*d[1], d[2]])
            R = e.topdown(arm, h0 + delta)
            if pid == 'P04' and not tray:
                # Upright dowel: align its measured cylinder axis with gravity before release.
                actual_R = (e.T_world_table[:3, :3].T @
                            e.data.xmat[e.object_bodies[oid]].reshape(3, 3))
                u = actual_R[:, 2].copy()
                if u[2] < 0:
                    u *= -1
                u = np.array([c*u[0]-s*u[1], s*u[0]+c*u[1], u[2]])
                axis = np.cross(u, [0., 0., 1.])
                n = np.linalg.norm(axis)
                if n > 1e-6:
                    axis /= n
                    a = min(math.atan2(n, u[2]), .52)
                    x, y, z = axis
                    K = np.array([[0,-z,y],[z,0,-x],[-y,x,0]])
                    correction = np.eye(3) + math.sin(a)*K + (1-math.cos(a))*(K@K)
                    R = correction @ R
                    dr = correction @ dr
            for xy in slots:
                above_item = np.array([*xy, support + CARRY_BOTTOM + h])
                above = above_item - dr
                q, diag = e.solve_ik(arm, above, R, restarts=2)
                tried += 1
                if not diag['ok']:
                    continue
                for bottom in RELEASE_BOTTOMS:
                    z = (wall_top + .018 if bottom is None else support + bottom) + h
                    at = np.array([*xy, z]) - dr
                    down = self._segment(arm, above, at, R, q, count=4)
                    if down is None:
                        continue
                    if bottom is not None and not self._fixture_free(arm, down, fixtures):
                        continue
                    if bottom is not None:
                        # Guarded descent target slightly below contact; execution stops on touch.
                        extra = self._segment(arm, at, at - [0, 0, RELEASE_PRESS], R, down[-1], count=1)
                        if extra is not None:
                            down = down + extra
                    score = .3*abs(delta) + np.linalg.norm(q - e.data.qpos[e.ik[arm].qadr]) + 5.*(bottom or .05)
                    if best is None or score < best[0]:
                        best = (score, dict(delta=delta, R=R, above=above, at=at, q=q, down=down,
                                            slot=[float(v) for v in xy], release_bottom=bottom))
                    break
                if best is not None and best[1]['delta'] == delta:
                    break
            if best is not None and tried >= 6:
                break
        self.events.update(place_candidates_tried=tried, place_free_yaws=free)
        return None if best is None else best[1]

    def _touching_support(self, oid):
        e = self.env; g = e.object_geoms[oid]; m = e.model
        for i in range(e.data.ncon):
            c = e.data.contact[i]
            if g in (c.geom1, c.geom2):
                other = c.geom2 if c.geom1 == g else c.geom1
                if m.geom_contype[other] == FIXTURE_BIT and c.dist < .001:
                    return True
        return False

    def _carry_waypoint(self, arm, start_xyz, above, h0, delta):
        """Pull toward the body between lift and target (imposed .03 m pull, +.02 m height)."""
        e = self.env
        mid = (np.asarray(start_xyz) + above) / 2
        for pull in (.03, 0.):
            w = np.array([max(min(start_xyz[0], above[0]) - pull, -.24), mid[1],
                          max(start_xyz[2], above[2]) + .02])
            q, diag = e.solve_ik(arm, w, e.topdown(arm, h0 + delta/2), restarts=1)
            if diag['ok']:
                return q
        return None

    def _place(self, arm, oid, target, tray):
        if not getattr(self, 'legacy_place', False):
            return self._place_v2(arm, oid, target, tray)
        return self._place_v1(arm, oid, target, tray)

    def _place_v2(self, arm, oid, target, tray):
        e = self.env
        if arm not in self.held or self.held[arm][0] != oid:
            return 'GRASP_SLIP'
        if not self.is_attached(arm, oid):
            self.held.pop(arm)
            return 'GRASP_SLIP'
        reach = e.layout.get('reach', {}).get(arm)
        if reach is not None and target not in reach:
            self.events.update(place_reject='reach_table')
            return 'IK_FAIL'
        plan = self._plan_place(arm, oid, target, tray)
        if plan is None:
            # No free footprint at any candidate yaw = no space (COLLISION); otherwise IK.
            return 'COLLISION' if not self.events.get('place_free_yaws') else 'IK_FAIL'
        self.events.update(place_slot=plan['slot'], place_delta_yaw=float(plan['delta']),
                           release_bottom=plan['release_bottom'])
        _, R0 = self.held[arm]
        h0 = math.atan2(R0[1, 0], R0[0, 0])
        start, _ = e.ee_pose(arm)
        way = self._carry_waypoint(arm, start, plan['above'], h0, plan['delta'])
        path = ([(way, .55)] if way is not None else []) + [(plan['q'], .7 if way is not None else .95)]
        path += [(p, .16) for p in plan['down']]
        touched = False
        for i, (waypoint, sec) in enumerate(path):
            descending = i >= len(path) - len(plan['down'])
            reason = self._move(arm, waypoint, sec)
            if not self.is_attached(arm, oid):
                self.held.pop(arm, None)
                return 'GRASP_SLIP'
            if reason:
                return reason
            if descending and plan['release_bottom'] is not None and self._touching_support(oid):
                touched = True
                break
        self.events.update(place_touched=touched)
        pid = e.object_parts[oid]
        profile = grasp_profile(pid)
        if pid == 'P06':
            # Dwell at fixed arm control before releasing the smooth block.
            e.step(math.ceil(.24/e.model.opt.timestep))
            if not self.is_attached(arm, oid):
                self.held.pop(arm, None)
                return 'GRASP_SLIP'
        self.events['release_speed'] = e.get_gt_objects()[oid]['lin_speed']
        self._open(arm, profile)
        self.held.pop(arm)
        e.step(math.ceil((.12 if pid == 'P04' and not tray else .25)/e.model.opt.timestep))
        if pid == 'P04' and not tray:
            xyz, _ = e.ee_pose(arm)
            up, diag = e.solve_ik(arm, xyz + [0,0,.035], plan['R'], restarts=0)
            if diag['ok']:
                self._move(arm, up, .23)
        retreat = self._move(arm, plan['q'], .4)
        if retreat:
            self.events.update(retreat_reason=retreat)
        e.step(math.ceil(.35/e.model.opt.timestep))
        return None

    def _place_v1(self, arm, oid, target, tray):
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
