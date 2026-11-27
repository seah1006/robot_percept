"""Real O3 adapter with persistent stable ids (O3 = sim-rendered head RGB-D prediction; no GT in plans/skills)."""
import numpy as np

from m2a.scene.symbolic import symbolic_from_gt

from .o3_policy import assign_boards, BOARDS
from .perception import Observation, held_from_env


def _assign(cost):
    """Minimum-cost one-to-one assignment (Hungarian). cost: 2-D array -> [(row, col)]."""
    from scipy.optimize import linear_sum_assignment
    if cost.size == 0:
        return []
    rows, cols = linear_sum_assignment(cost)
    return list(zip(rows.tolist(), cols.tolist()))


class IdTracker:
    """Stable ids (q0, q1, ...) over per-keyframe predictions (the O3 local ids p0.. are position order only).

    Rules (thresholds 임의 지정):
    1. same part_id and xy distance <= link_xy (Hungarian on xy distance) keep the stable id.
    2. A track whose object a successful place/put-aside just moved (note_moved) re-links to an unmatched
       prediction of the same part_id at any distance: the plan moved it.
    3. Other unmatched tracks (<= max_missing consecutive misses) re-link to unmatched same-part predictions at any
       distance (e.g. an external move). A different part_id never links (a classification flip appears as
       disappeared + appeared).
    4. Frozen (held) tracks are never matched and keep their last xy.
    Unmatched predictions get new ids; unmatched tracks count a miss."""

    def __init__(self, link_xy=0.03, max_missing=3):
        self.link_xy, self.max_missing = link_xy, max_missing
        self.tracks, self.moved, self.count = {}, set(), 0

    def note_moved(self, sid):
        self.moved.add(sid)

    def _match(self, track_ids, pred_ids, preds, limit):
        cost = np.full((len(track_ids), len(pred_ids)), 1e6)
        for i, t in enumerate(track_ids):
            for j, p in enumerate(pred_ids):
                if self.tracks[t]['part_id'] != preds[p]['part_id']:
                    continue
                d = float(np.hypot(self.tracks[t]['xy'][0]-preds[p]['xyz'][0], self.tracks[t]['xy'][1]-preds[p]['xyz'][1]))
                if limit is None or d <= limit:
                    cost[i, j] = d
        return [(track_ids[i], pred_ids[j]) for i, j in _assign(cost) if cost[i, j] < 1e6]

    def update(self, preds, frozen=()):
        """preds: {local oid: {part_id, xyz, ...}} -> {local oid: stable id}."""
        link, free_p = {}, list(preds)
        free_t = [t for t, v in self.tracks.items() if t not in frozen and v['missing'] <= self.max_missing]

        def take(pairs):
            for t, p in pairs:
                link[p] = t
                free_t.remove(t)
                free_p.remove(p)

        take(self._match(free_t, free_p, preds, self.link_xy))
        take(self._match([t for t in free_t if t in self.moved], free_p, preds, None))
        take(self._match(list(free_t), free_p, preds, None))
        for p, t in link.items():
            self.tracks[t].update(xy=tuple(preds[p]['xyz'][:2]), part_id=preds[p]['part_id'], missing=0, last=preds[p])
            self.moved.discard(t)
        for t in free_t:
            self.tracks[t]['missing'] += 1
        for p in free_p:
            sid = f'q{self.count}'
            self.count += 1
            self.tracks[sid] = dict(part_id=preds[p]['part_id'], xy=tuple(preds[p]['xyz'][:2]), missing=0, last=preds[p])
            link[p] = sid
        return link


class O3Perception:
    """Plans use stable ids q0..; skills only get obj_pose_T (pose_only). GT is used for (a) gripper-state sensing
    (which arm holds something; GT 보조) and (b) evaluation only: Observation.meta (never read by planner/skills)."""
    pose_only = True

    def __init__(self, o3=None, link_xy=0.03, gt_xy=0.03, hand_radius=0.09, embedder=None, gallery=None, board_capacity=None, reobserve_missing=True):
        self.o3, self.gt_xy, self.hand_radius = o3, gt_xy, hand_radius  # 임의 지정: 3 cm GT match, 9 cm hand mask
        self.embedder, self.gallery = embedder, gallery
        self.board_capacity = board_capacity or {}
        self.reobserve_missing = reobserve_missing
        self.tracker = IdTracker(link_xy)
        self.intended = {}  # arm -> stable id the last grasp_lift targeted
        self.perceive_calls = 0
        self.parked = {}  # arm -> grip-site xyz at the first keyframe (arms parked out of view)
        self.link_radius, self.unparked, self.occlusion_radius = 0.08, 0.05, 0.18  # 임의 지정 (m, xy)

    def _arm_points(self, env, arm):
        """Proprioceptive self-model: arm/hand link origins in T (robot kinematics, no object GT)."""
        if not (hasattr(env, 'ee_pose') and hasattr(env, 'to_table') and hasattr(env, 'model')):
            return []
        import mujoco as mj
        ee = np.asarray(env.ee_pose(arm)[0], float)
        parked = self.parked.setdefault(arm, ee)
        if np.linalg.norm(ee-parked) <= self.unparked:
            return []  # parked: out of the head view
        points = []
        for i in range(env.model.nbody):
            name = mj.mj_id2name(env.model, mj.mjtObj.mjOBJ_BODY, i) or ''
            if name.startswith(f'{arm}_') and name.endswith('_link') and any(
                    k in name for k in ('elbow', 'wrist', 'hand')):
                points.append(np.asarray(env.to_table(env.data.xpos[i]), float))
        return points

    def _o3(self, layout, parts):
        if self.o3 is None:
            from m2a.percept.o3 import O3
            self.o3 = O3(layout=layout, parts=parts, embedder=self.embedder, gallery=self.gallery)
        return self.o3

    def note_skill(self, call, result):
        if call.skill == 'grasp_lift':
            self.intended[call.arm] = call.oid
        elif call.skill in ('transport_place', 'put_aside') and result.get('ok'):
            self.tracker.note_moved(self.intended.pop(call.arm, call.oid))

    def observe(self, env, layout, parts):
        gt = env.get_gt_objects()
        held_gt = held_from_env(env, gt)
        self.perceive_calls += 1
        _, graph = self._o3(layout, parts).perceive(env)
        preds = dict(graph['objects'])
        points = []
        for arm in ('left', 'right'):  # drop arm/hand detections: a visible arm is not an object (self-model mask)
            for pt in self._arm_points(env, arm):
                points.append(pt)
                for k in [k for k, v in preds.items() if np.linalg.norm(np.asarray(v['xyz'][:2])-pt[:2]) <= self.link_radius]:
                    del preds[k]
        for arm in held_gt:
            if hasattr(env, 'ee_pose'):
                ee = np.asarray(env.ee_pose(arm)[0])
                for k in [k for k, v in preds.items() if np.linalg.norm(np.asarray(v['xyz'])-ee) <= self.hand_radius]:
                    del preds[k]  # the in-hand object is tracked by its grasp-time id, not re-detected
        for arm in [a for a in self.intended if a not in held_gt]:
            del self.intended[arm]
        held = {}
        for arm in held_gt:
            sid = self.intended.get(arm)
            held[arm] = sid if sid in self.tracker.tracks else f'held_{arm}'
        changes = assign_boards(preds, self.board_capacity)
        if changes:
            preds = {k: (dict(v, part_id=changes[k]) if k in changes else v) for k, v in preds.items()}
        link = self.tracker.update(preds, frozen=set(held.values()))
        objects = {link[k]: dict(part_id=v['part_id'], xyz=v['xyz'], yaw=v['yaw']) for k, v in preds.items()}
        poses = {link[k]: dict(v['obj_pose_T']) for k, v in preds.items()}
        occluded = []
        for sid, track in self.tracker.tracks.items():  # carry over objects hidden behind a visible arm
            if sid in objects or sid in held.values() or track.get('last') is None or track['missing'] == 0:
                continue
            if any(np.linalg.norm(np.asarray(track['xy'])-pt[:2]) <= self.occlusion_radius for pt in points):
                last = track['last']
                objects[sid] = dict(part_id=last['part_id'], xyz=last['xyz'], yaw=last['yaw'])
                poses[sid] = dict(last['obj_pose_T'])
                track['missing'] = 0
                occluded.append(sid)
        state = symbolic_from_gt(objects, layout, parts)
        for sid in held.values():
            state['objects'][sid] = dict(part_id=self.tracker.tracks.get(sid, {}).get('part_id'), region=None,
                                         in_tray=None, on=None)
        meta = self._evaluate(gt, held_gt, objects, graph, link, preds)
        meta['occluded_carried'] = occluded
        candidates = {link[k]: [x['part_id'] for x in v.get('top3', ())[:3]]
                                        for k, v in preds.items() if v.get('uncertain')}
        meta['board_assignment'] = {link[k]: changes[k] for k in changes}
        return Observation(state, held, poses, meta, candidates)

    def _evaluate(self, gt, held_gt, objects, graph, link, preds):
        ids = [o for o in gt if o not in held_gt.values()]
        sids = list(objects)
        cost = np.full((len(sids), len(ids)), 1e6)
        for i, s in enumerate(sids):
            for j, g in enumerate(ids):
                d = float(np.hypot(objects[s]['xyz'][0]-gt[g]['xyz'][0], objects[s]['xyz'][1]-gt[g]['xyz'][1]))
                if d <= self.gt_xy:
                    cost[i, j] = d
        gt_of = {sids[i]: ids[j] for i, j in _assign(cost) if cost[i, j] < 1e6}
        return dict(gt_of=gt_of, missed_gt=sorted(set(ids)-set(gt_of.values())), false_pos=sorted(set(sids)-set(gt_of)),
                    wrong_part=sorted(s for s, g in gt_of.items() if objects[s]['part_id'] != gt[g]['part_id']),
                    board_eval=[dict(raw=graph['objects'][k]['part_id'], assigned=preds[k]['part_id'],
                                     truth=gt[gt_of[link[k]]]['part_id'])
                                for k in preds if link[k] in gt_of and gt[gt_of[link[k]]]['part_id'] in BOARDS],
                    pose_unreliable=sorted(link[k] for k in preds if not graph['objects'][k].get('pose_reliable', True)))

    def refine_target(self, call, observation):
        return call.target
