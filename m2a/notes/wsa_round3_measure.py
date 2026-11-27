"""Round-3 scene measurements with an explicit grasp mode (run under rp_measure.lock).

python -m m2a.notes.wsa_round3_measure center --mode P-gate --part P01 --arm left
python -m m2a.notes.wsa_round3_measure tray|top|clutter --mode P-gate
Same seeds/sampling as wsa_round2_measure (center 10170+i, scenes 10050+i, pick rng 10188).
"""
import argparse
from collections import Counter
import json
from math import pi
from pathlib import Path
import numpy as np
from m2a.common import load_parts
from m2a.scene._geometry import corners, contains, obb, size_xyz
from m2a.scene.generator import generate
from m2a.sim.g1_manip_env import ARMS, G1ManipEnv, half_height
from m2a.sim.gate_grasp import PART_IDS, fixture
from m2a.sim.skills import SkillRunner

MODE = 'P-gate'


def run_skill(env, spec, arm, oid, place=False, reset=True):
    if reset:
        env.reset(spec)
    runner = SkillRunner(env, MODE)
    result = runner.run('grasp_lift', arm, oid)
    lifted = env.get_gt_objects()[oid]
    events = dict(runner.events)
    put = runner.run('put_aside', arm, oid) if result['ok'] and place else None
    if place:
        env.step(round(2/env.model.opt.timestep))
    final = env.get_gt_objects()[oid]
    keep = bool(put and put['ok'] and final['lin_speed'] < .02 and contains(env.layout['regions']['center_zone'], final['xyz'])
                and abs(final['xyz'][2]-half_height(env.parts[final['part_id']])) < .005)
    return dict(mode=MODE, arm=arm, oid=oid, grasp=result, place=put, lifted=lifted, final=final,
                pick_ok=result['ok'], ok=keep if place else result['ok'], events=events,
                thumb_opposed=events.get('thumb_opposed'), min_contacts_during_lift=events.get('min_contacts_during_lift'),
                slips=env.slip_events)


def center(env, parts_sel, arms_sel):
    parts = load_parts()['parts']
    rect = env.layout['regions']['center_zone']
    x, X, y, Y = rect
    major = pi/2 if Y-y > X-x else 0.
    for part_i, pid in enumerate(PART_IDS):
        part = parts[pid]; size = size_xyz(part)
        rng = np.random.default_rng(10170+part_i)
        for arm in ARMS:
            for i in range(20):
                for _ in range(3000):
                    yaw = float(rng.uniform(-pi/12, pi/12) + major) if pid in ('P01', 'P02', 'P03') else float(rng.uniform(-pi, pi))
                    xy = [float(rng.uniform(x, X)), float(rng.uniform(y, Y))]
                    if all(contains(rect, z) for z in corners(obb(xy, size, yaw))):
                        break
                else:
                    raise ValueError(f'no geometrically admissible position for {pid}')
                if pid not in parts_sel or arm not in arms_sel:
                    continue
                spec = fixture([dict(oid='o0', part_id=pid, xyz=[*xy, half_height(part)], yaw=yaw, region='center_zone',
                                     in_tray=None, on=None)], seed=10170+part_i)
                yield dict(spec=spec, part_id=pid, trial=i, center_zone=rect, **run_skill(env, spec, arm, 'o0', place=True))


def scenes(env, job):
    rng = np.random.default_rng(10188)
    n = 30 if job == 'clutter' else 10
    situation = {'clutter': 'standard', 'tray': 'pretray', 'top': 'stacked'}[job]
    for i in range(n):
        seed = 10050+i
        try:
            spec = generate(seed, 'L1', situation, 'dev', layout=env.layout)
        except ValueError as err:
            yield dict(seed=seed, ok=False, generate_error=str(err)); continue
        below = {o['on'] for o in spec['objects'] if o['on'] is not None}
        opts = [o for o in spec['objects'] if (o['oid'] not in below if job == 'clutter' else
                                               o['in_tray'] is not None if job == 'tray' else o['on'] is not None)]
        obj = opts[int(rng.integers(len(opts)))]; oid = obj['oid']
        region = obj['region'] or obj['in_tray']
        arm = {'left_zone': 'left', 'right_zone': 'right', 'T1': 'left', 'T3': 'right'}.get(region, ARMS[i % 2])
        env.reset(spec); env.step(round(.5/env.model.opt.timestep))
        yield dict(spec=spec, part_id=obj['part_id'], seed=seed, source=region, **run_skill(env, spec, arm, oid, reset=False))


def main():
    global MODE
    p = argparse.ArgumentParser()
    p.add_argument('job', choices=('center', 'clutter', 'tray', 'top'))
    p.add_argument('--mode', default='P-gate', choices=('P-gate', 'P-gate-strict', 'P-phys'))
    p.add_argument('--part', action='append'); p.add_argument('--arm', action='append')
    p.add_argument('--tag', default='round3')
    p.add_argument('--center', type=float, nargs=4, help='override center_zone [x0 x1 y0 y1] (candidate test)')
    a = p.parse_args(); MODE = a.mode
    env = G1ManipEnv()
    if a.center:
        env.layout['regions']['center_zone'] = list(a.center)
    if a.job == 'center':
        rows = center(env, a.part or PART_IDS, a.arm or ARMS)
        suffix = '_'.join([*(a.part or ['all']), *(a.arm or ['both'])])
    else:
        rows = scenes(env, a.job); suffix = ''
    dest = Path('m2a/notes/wsa_gate_raw')/f"{a.tag}_{a.job}_{MODE}{'_' + suffix if suffix else ''}.jsonl"
    counts = Counter()
    with dest.open('w', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False)+'\n'); f.flush(); counts[bool(row['ok'])] += 1
    print(dest, dict(counts))
    env.close()


if __name__ == '__main__':
    main()
