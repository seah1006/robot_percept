"""One-shot post-skill disturbances in MuJoCo only."""
from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True)
class Perturbation:
    kind: str
    after_skill: int
    oid: str | None = None
    region: str | None = None

    def __post_init__(self):
        if self.kind not in ('drop', 'teleport') or type(self.after_skill) is not int or self.after_skill < 1:
            raise ValueError('perturbation requires drop/teleport and a positive skill number')

    def apply(self, env, obs, call, upcoming):
        import mujoco

        if self.kind == 'drop':
            pair = next(((arm, oid) for arm, oid in obs.held.items()
                         if self.oid is None or oid == self.oid), None)
            if pair is None:
                return {'applied': False, 'reason': 'no_held_object'}
            arm, oid = pair
            eq = env.model.equality(f'm2a_weld_{arm}_{oid}').id
            if not env.data.eq_active[eq]:
                return {'applied': False, 'reason': 'no_weld'}
            env.release(arm)
            env.step(ceil(.35 / env.model.opt.timestep))
            return {'applied': True, 'oid': oid, 'arm': arm}
        objects = obs.state['objects']
        available = [oid for oid in objects if oid not in obs.held.values() and oid != call.oid]
        oid = self.oid or next((step.oid for step in upcoming if step.oid in available),
                               next(iter(available), None))
        if oid not in available:
            return {'applied': False, 'reason': 'no_eligible_object'}
        current = objects[oid]['region']
        region = self.region or next((r for r in ('left_zone', 'right_zone', 'center_zone')
                                       if r != current and r in env.layout['regions']), None)
        if region == current or region not in env.layout['regions']:
            raise ValueError('teleport destination must be a different layout region')
        x0, x1, y0, y1 = env.layout['regions'][region]
        from m2a.sim.g1_manip_env import half_height
        part = env.parts[objects[oid]['part_id']]
        joint = env.model.joint(f'm2a_free_{oid}')
        q, v = int(joint.qposadr[0]), int(joint.dofadr[0])
        env.data.qpos[q:q+3] = env.to_world([(x0+x1)/2, (y0+y1)/2, half_height(part)+.002])
        env.data.qvel[v:v+6] = 0
        mujoco.mj_forward(env.model, env.data)
        return {'applied': True, 'oid': oid, 'region': region, 'prior_region': current}
