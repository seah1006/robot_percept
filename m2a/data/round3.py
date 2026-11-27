"""Round 3: sample main's scripted P-gate controller at 10 Hz."""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
from time import perf_counter
import numpy as np
from .auto_demo import l0_case, prepare
from .recorder import DT, observation, write_npz

TASKS = dict(P06='pick up the bracket', P03='pick up the short board',
             P05='pick up the cam lock', P04='pick up the dowel')


def case_for(seed, split, side='right'):
    from m2a.scene.generator import scene_digest
    spec, oid, arm, _ = l0_case(seed, split)
    if arm != side:
        return None
    target = next(o for o in spec['objects'] if o['oid'] == oid)
    if target['part_id'] not in TASKS:
        return None
    rng = np.random.default_rng(np.random.SeedSequence([seed, 731]))
    other = [o for o in spec['objects'] if o['oid'] != oid]
    n = int(rng.integers(3))
    kept = sorted(rng.choice(len(other), size=min(n, len(other)), replace=False))
    spec['objects'] = [target, *(other[i] for i in kept)]
    return spec, oid, arm, scene_digest(spec), target['part_id']


def dev_cases(part):
    """Native right-arm cases first; use deterministic L0 goal override if needed."""
    from m2a.scene.generator import generate, scene_digest, _place
    from m2a.common import load_layout, load_parts, load_steps
    natives = []
    for seed in range(10000,10200):
        try: case = case_for(seed,'dev')
        except ValueError: continue
        if case is not None and case[4] == part:
            natives.append(case[0]['seed'])
            yield case
    layout = load_layout()
    for seed in range(10000,10200):
        if seed in natives: continue
        try: spec = generate(seed,'L0','standard','dev')
        except ValueError: continue
        parts = load_parts(spec['product'])['parts']
        tray = next(s['tray'] for s in load_steps(spec['product'])['steps'] if part in s['parts'])
        rng = np.random.default_rng(np.random.SeedSequence([seed, 733]))
        n = int(rng.integers(3))
        choices = [p for p in parts if p != part]
        items = [dict(oid='o0',part_id=part,target=tray)] + [dict(oid=f'o{i+1}',part_id=str(pid))
                  for i,pid in enumerate(rng.choice(choices,n))]
        try: objects = _place(items,parts,layout,rng)
        except ValueError: continue
        target = objects[0]
        if target['region'] == 'left_zone' or (target['region'] != 'right_zone' and target['xyz'][1]>=0):
            continue
        spec['objects'] = objects
        goal=spec['expected']['goal']
        goal.update(trays={tray:{part:1}}, step_order=[[tray]], source_text=TASKS[part])
        spec['goal_steps'] = [step['step'] for step in load_steps(spec['product'])['steps'] if step['tray']==tray]
        yield spec, 'o0', 'right', scene_digest(spec), part


def scripted(env, case, record=False, minimum_rise=None, grasp_mode='P-gate', render_images=True):
    import mujoco as mj
    from scipy.spatial.transform import Rotation
    from .recorder import STATE
    from m2a.sim.skills import SkillRunner
    from m2a.sim.grasp_profiles import grasp_profile, hand_command
    spec, oid, arm, _, pid = case
    prepare(env, spec, arm)
    env.set_gate_mode(grasp_mode)
    runner = SkillRunner(env, grasp_mode=grasp_mode)
    start = perf_counter()
    initial_z = env.get_gt_objects()[oid]['xyz'][2]
    rows, lost, next_t, prev = [], 0, env.data.time, 0.
    max_rise = 0.
    step = env.step
    if record:
        model, data = env.model, env.data
        scratch = mj.MjData(model)
        qadr = env.ik[arm].qadr
        grip_site = model.site(f'{arm}_grip').id
        table_R = env.T_world_table[:3,:3].T
        profile = grasp_profile(pid)
        sign = 1 if arm == 'left' else -1
        grid = np.linspace(0, 1, 401)
        commands = np.stack([hand_command(profile, g, sign) for g in grid])
        commands[0] = sign * np.asarray(profile['open'])

        def tick(n=1):
            nonlocal next_t, prev, lost, max_rise
            # Split only at observation boundaries; do not change held controls.
            dt = model.opt.timestep
            while n:
                if data.time >= next_t - dt / 2:
                    p, quat = env.ee_pose(arm)
                    if render_images:
                        obs, missing = observation(env, arm, oid, prev)
                    else:
                        obs,missing={STATE:np.r_[p,quat,prev,env.arm_q(arm)]},0
                    scratch.qpos[:] = data.qpos
                    scratch.qpos[qadr] = data.ctrl[env.arm_act[arm]]
                    mj.mj_kinematics(model, scratch)
                    goal = env.to_table(scratch.site_xpos[grip_site])
                    rot = Rotation.from_matrix(table_R @ scratch.site_xmat[grip_site].reshape(3,3))
                    dr = (rot * Rotation.from_quat(quat, scalar_first=True).inv()).as_rotvec()
                    grip = float(grid[np.argmin(np.sum((commands-data.ctrl[env.hand_act[arm]])**2, axis=1))])
                    if env.closed[arm]: grip = max(grip, .85)
                    rows.append(dict(obs, action=np.asarray([*(goal-p), *dr, grip], np.float32)))
                    lost += missing
                    prev = grip
                    next_t += DT
                count = min(n, max(1, round((next_t-data.time)/dt)))
                step(count)
                n -= count
                max_rise = max(max_rise, env.to_table(data.xpos[env.object_bodies[oid]])[2]-initial_z)
        env.step = tick
    try:
        result = runner.run('grasp_lift', arm, oid)
        if result['ok']:
            # Match the old hold duration, using the current scripted skill's lift.
            if minimum_rise is None:
                env.step(round(2./env.model.opt.timestep))
            else:
                held_ticks = 0
                for _ in range(20):
                    env.step(round(DT/env.model.opt.timestep))
                    rise = env.get_gt_objects()[oid]['xyz'][2]-initial_z
                    held_ticks = held_ticks+1 if rise >= minimum_rise and env._held_oid(arm)==oid else 0
                if held_ticks < 20:
                    result.update(ok=False, reason_code='LIFT_SHORT', internal_done=False)
            if env._held_oid(arm) != oid:
                result.update(ok=False, reason_code='GRASP_SLIP', internal_done=False)
    finally:
        if record:
            del env.step
    rise = env.get_gt_objects()[oid]['xyz'][2] - initial_z
    return rows, dict(result, final_rise_m=rise, max_rise_m=max(max_rise, rise),
                      attached=env._held_oid(arm) == oid, mask_lost_frames=lost if record else None,
                      ticks=len(rows) if record else None, seconds=perf_counter()-start,
                      events=runner.events)


def main():
    from m2a.sim.g1_manip_env import G1ManipEnv
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output', type=Path)
    p.add_argument('--part', required=True, choices=TASKS)
    p.add_argument('--grasp-mode',required=True,choices=('P-gate','P-gate-strict'))
    p.add_argument('--count', type=int, default=100)
    p.add_argument('--commit', default=None)
    p.add_argument('--start', type=int, default=0)
    p.add_argument('--end', type=int, default=4999)
    a = p.parse_args()
    if not 0 <= a.start <= a.end <= 4999 or a.count < 1: p.error('invalid train range/count')
    commit = a.commit or subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip()
    a.output.mkdir(parents=True, exist_ok=True)
    env = G1ManipEnv()
    counts = Counter()
    try:
        with (a.output/f'attempts_{a.part}_{a.start}_{a.end}.jsonl').open('x', buffering=1) as log:
            for seed in range(a.start, a.end+1):
                try: case = case_for(seed, 'train')
                except ValueError: continue
                if case is None or case[4] != a.part: continue
                spec, oid, arm, digest, pid = case
                _, result = scripted(env, case, grasp_mode=a.grasp_mode)
                if result['ok']:
                    rows, result = scripted(env, case, record=True, grasp_mode=a.grasp_mode)
                    if result['ok']:
                        write_npz(a.output/f'{seed:05}.npz', rows, seed=seed, part=pid, mode=a.grasp_mode,
                                  arm=arm, task=TASKS[pid], provenance=dict(commit=commit, scene_digest=digest,
                                  distractors=len(spec['objects'])-1, grasp_mode_name=a.grasp_mode, action_encoding='ee_delta_table_v1'))
                counts[result['reason_code']] += 1
                print(json.dumps(dict(result, seed=seed, arm=arm, oid=oid, part=pid, task=TASKS[pid],
                                      commit=commit, scene_digest=digest, distractors=len(spec['objects'])-1,
                                      grasp_mode=a.grasp_mode, source=0)), file=log)
                if counts[None] >= a.count: break
    finally:
        env.close()
    print(a.part, counts, flush=True)


if __name__ == '__main__':
    main()