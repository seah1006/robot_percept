"""Measure actual head arm occlusion with paired arm-hidden segmentation renders."""
import json
import numpy as np
import mujoco as mj
from m2a.common import M2A
from m2a.scene.generator import generate
from m2a.sim.g1_manip_env import ARMS, G1ManipEnv
from m2a.sim.skills import SkillRunner


def legacy_park(env):
    dt = env.model.opt.timestep
    initial = {a: env.data.ctrl[env.arm_act[a]].copy() for a in ARMS}
    target = {a: np.array([.32, .18*s, 0, .22, 0, 0, 0]) for a,s in zip(ARMS,(1,-1))}
    n = round(.6/dt)
    for i in range(0,n,4):
        end = min(i+4,n)
        f = end/n
        for a in ARMS:
            env.data.ctrl[env.arm_act[a]] = initial[a] + f*f*(3-2*f)*(target[a]-initial[a])
        env.step(end-i)


def occlusion(env):
    m = env.model
    body_names = [m.body(int(b)).name for b in m.geom_bodyid]
    robot_arm = [g for g,b in enumerate(body_names) if b and b.startswith(ARMS)
                 and any(k in b for k in ('shoulder','elbow','wrist','_hand_'))]
    visible_arms = [g for g in robot_arm if m.geom_group[g] <= 2]
    old_groups = m.geom_group[visible_arms].copy()
    m.geom_group[visible_arms] = 5
    try:
        with mj.Renderer(m, 480, 640) as r:
            r.enable_segmentation_rendering()
            opts = mj.MjvOption()
            opts.geomgroup[5] = 1
            r.update_scene(env.data, camera='head', scene_option=opts)
            seg = r.render()[...,0].copy()
            opts.geomgroup[5] = 0
            r.update_scene(env.data, camera='head', scene_option=opts)
            clean = r.render()[...,0]
            arm_mask = np.isin(seg, visible_arms)
            obj_mask = np.isin(clean, tuple(env.object_geoms.values()))
            return int(np.count_nonzero(arm_mask & obj_mask))
    finally:
        m.geom_group[visible_arms] = old_groups


def main():
    out = M2A/'notes/wsa_gate_raw/round5_perception_return.jsonl'
    with out.open('w') as f:
        for seed in range(10000,10012):
            spec = generate(seed,'L2','standard','dev')
            for arm, sign in zip(ARMS, (1,-1)):
                candidates = [o for o in spec['objects'] if (o['xyz'][1]*sign > 0 or o['region'] == 'center_zone')]
                for obj in (candidates if seed == 10000 else candidates[:1]):
                    oid = obj['oid']
                    for version in ('old','new'):
                        e = G1ManipEnv()
                        try:
                            e.reset(spec)
                            sk = SkillRunner(e, 'P-gate')
                            reach = sk.run('reach_pregrasp',arm,oid)
                            if not reach['ok']:
                                continue
                            before = occlusion(e)
                            try:
                                if version == 'old':
                                    legacy_park(e)
                                else:
                                    token = e.perception_pose()
                                after = occlusion(e)
                                err = max(np.max(abs(e.arm_q(a)-e.data.ctrl[e.arm_act[a]])) for a in ARMS)
                                restore_error = None
                                if version == 'new':
                                    e.restore_perception_pose(token)
                                    restore_error = max(np.max(abs(e.arm_q(a)-token[a])) for a in ARMS)
                                row = dict(before=before, after=after, q_error=float(err), restore_q_error=restore_error)
                            except RuntimeError as exc:
                                row = dict(error=str(exc))
                            f.write(json.dumps(dict(seed=seed, arm=arm, oid=oid, version=version, **row))+'\n')
                            f.flush()
                        finally:
                            e.close()

if __name__ == '__main__':
    main()