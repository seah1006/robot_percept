"""O3 adapters provide symbolic state and grasp observations without exposing GT."""
from dataclasses import dataclass, field
from typing import Protocol

from m2a.scene.symbolic import symbolic_from_gt


@dataclass
class Observation:
    state: dict
    held: dict = field(default_factory=dict)  # arm -> oid
    poses: dict = field(default_factory=dict)  # predicted oid -> {xyz, yaw, size}


class Perception(Protocol):
    def observe(self, env, layout, parts) -> Observation: ...
    def refine_target(self, call, observation): ...
    pose_only: bool  # True for predictive adapters; O0 keeps the §7 call


class OraclePerception:
    pose_only = False
    def observe(self, env, layout, parts):
        gt = env.get_gt_objects()
        held = {arm: oid for arm in ('left', 'right') for oid in gt
                if env.data.eq_active[env.model.equality(f'm2a_weld_{arm}_{oid}').id]
                or (env.closed[arm] and env.in_palm(arm, oid) and env.contact_fingers(arm, oid))}
        return Observation(symbolic_from_gt(gt, layout, parts), held)

    def refine_target(self, call, observation):
        return call.target  # O0 skills already read current GT poses.


class NoisyGTPerception:
    """Fake O3 for testing: GT + Gaussian noise (sigma values are 임의 지정), predicted oids != GT oids.

    Predicted oids are 'p0', 'p1', ... in a per-episode shuffled order. Held state is read from the
    simulator (gripper-state sensing stand-in, GT 보조). Never passes GT oids to skills."""
    pose_only = True

    def __init__(self, sigma_xy=0.004, sigma_yaw=0.05, seed=0, drop_prob=0.0):
        import numpy as np
        self.rng, self.sxy, self.syaw, self.drop = np.random.default_rng(seed), sigma_xy, sigma_yaw, drop_prob
        self.gt_of = {}  # predicted oid -> GT oid, evaluation/debug only
        self._ids = {}  # GT oid -> predicted oid; fixed per episode (tracker-like id persistence, 가정)

    def observe(self, env, layout, parts):
        gt = env.get_gt_objects()
        oracle = OraclePerception().observe(env, layout, parts)
        if not self._ids or set(self._ids) != set(gt):
            order = list(gt)
            self.rng.shuffle(order)
            self._ids = {oid: f'p{i}' for i, oid in enumerate(order)}
        noisy, poses, self.gt_of, pred_of = {}, {}, {}, {}
        for oid in gt:
            if self.rng.random() < self.drop:
                continue  # PERCEPT_MISS simulation
            g, part = gt[oid], parts['parts'][gt[oid]['part_id']] if 'parts' in parts else parts[gt[oid]['part_id']]
            xyz = [float(v) for v in g['xyz']]
            xyz[0] += float(self.rng.normal(0, self.sxy)); xyz[1] += float(self.rng.normal(0, self.sxy))
            yaw = float(g['yaw'] + self.rng.normal(0, self.syaw))
            pid = self._ids[oid]
            noisy[pid] = {**g, 'xyz': xyz, 'yaw': yaw}
            pred_of[oid], self.gt_of[pid] = pid, oid
            size = list(part['size'])
            poses[pid] = dict(xyz=xyz, yaw=yaw, size=size, part_id=g['part_id'], shape=part['shape'])
        state = symbolic_from_gt(noisy, layout, parts)
        held = {arm: pred_of[o] for arm, o in oracle.held.items() if o in pred_of}
        return Observation(state, held, poses)

    def refine_target(self, call, observation):
        return call.target