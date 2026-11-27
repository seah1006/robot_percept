"""Run from repo root via python -m m2a.notes.wsa_round2_measure <job>, under rp_measure.lock."""
import argparse
from collections import Counter
from itertools import combinations
import json
from math import pi
from pathlib import Path
import numpy as np
from m2a.scene._geometry import corners, contains, footprints_overlap, obb, size_xyz
from m2a.scene.generator import generate
from m2a.sim.g1_manip_env import ARMS, G1ManipEnv, half_height
from m2a.sim.gate_grasp import PART_IDS, fixture
from m2a.sim.skills import SkillRunner


def run_skill(env, spec, arm, oid, place=False, reset=True):
    if reset:
        env.reset(spec)
    runner = SkillRunner(env, 'P-gate')
    result = runner.run('grasp_lift', arm, oid)
    lifted = env.get_gt_objects()[oid]
    put = runner.run('put_aside', arm, oid) if result['ok'] and place else None
    if place:
        env.step(round(2/env.model.opt.timestep))
    final = env.get_gt_objects()[oid]
    keep = bool(put and put['ok'] and final['lin_speed'] < .02 and contains(env.layout['regions']['center_zone'], final['xyz']) and abs(final['xyz'][2]-half_height(env.parts[final['part_id']])) < .005)
    return dict(arm=arm, oid=oid, grasp=result, place=put, lifted=lifted, final=final,
                ok=keep if place else result['ok'], events=runner.events, slips=env.slip_events)


def center(env):
    from m2a.common import load_parts
    parts = load_parts()['parts']
    rect = env.layout['regions']['center_zone']
    x, X, y, Y = rect
    for part_i, pid in enumerate(PART_IDS):
        part = parts[pid]; size = size_xyz(part)
        rng = np.random.default_rng(10170+part_i)
        for arm in ARMS:
            for i in range(20):
                for _ in range(3000):
                    yaw = float(rng.uniform(-pi/12, pi/12) + pi/2) if pid == 'P01' else float(rng.uniform(-pi, pi))
                    xy = [float(rng.uniform(x, X)), float(rng.uniform(y, Y))]
                    if all(contains(rect, z) for z in corners(obb(xy,size,yaw))):
                        break
                else:
                    raise ValueError(f'no geometrically admissible position for {pid}')
                spec = fixture([dict(oid='o0', part_id=pid, xyz=[*xy, half_height(part)], yaw=yaw, region='center_zone',in_tray=None,on=None)], seed=10170+part_i)
                yield dict(spec=spec, part_id=pid, trial=i, **run_skill(env,spec,arm,'o0',place=True))


def settle(env):
    for i in range(50):
        level = 'L1' if i%2==0 else 'L2'
        situation = ('standard','missing','pretray','stacked','reach')[(i//2)%5]
        seed = 10000+i
        try:
            spec = generate(seed, level, situation, 'dev', layout=env.layout)
        except ValueError as err:
            yield dict(seed=seed, level=level, situation=situation, ok=False, generate_error=str(err)); continue
        env.reset(spec); env.step(round(5/env.model.opt.timestep)); gt = env.get_gt_objects()
        overlaps = []; shifted = []
        for obj in spec['objects']:
            g = gt[obj['oid']]
            if abs(g['xyz'][2]-obj['xyz'][2]) > .005 or g['lin_speed'] >= .02:
                shifted.append(obj['oid'])
        for a,b in combinations(gt,2):
            g,h = gt[a],gt[b]
            p,q = env.parts[g['part_id']],env.parts[h['part_id']]
            if abs(g['xyz'][2]-h['xyz'][2]) < half_height(p)+half_height(q)-.002 and footprints_overlap(
                    obb(g['xyz'],size_xyz(p),g['yaw']),obb(h['xyz'],size_xyz(q),h['yaw']),p['shape']=='cylinder',q['shape']=='cylinder'):
                overlaps.append([a,b])
        yield dict(seed=seed, level=level,situation=situation, ok=not shifted and not overlaps,
                   spec=spec, final=gt, overlaps=overlaps, shifted_or_fast=shifted)


def scenes(env, job):
    rng = np.random.default_rng(10188)
    n = 30 if job=='clutter' else 10
    situation = {'clutter':'standard','tray':'pretray','top':'stacked'}[job]
    for i in range(n):
        seed = 10050+i
        try:
            spec = generate(seed,'L1',situation,'dev',layout=env.layout)
        except ValueError as err:
            yield dict(seed=seed, ok=False, generate_error=str(err)); continue
        below = {o['on'] for o in spec['objects'] if o['on'] is not None}
        opts = [o for o in spec['objects'] if (o['oid'] not in below if job=='clutter' else o['in_tray'] is not None if job=='tray' else o['on'] is not None)]
        obj = opts[int(rng.integers(len(opts)))]; oid = obj['oid']
        region = obj['region'] or obj['in_tray']
        arm = {'left_zone':'left','right_zone':'right','T1':'left','T3':'right'}.get(region,ARMS[i%2])
        env.reset(spec); env.step(round(.5/env.model.opt.timestep))
        yield dict(spec=spec, part_id=obj['part_id'], seed=seed, source=region,
                   **run_skill(env,spec,arm,oid,reset=False))


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('job', choices=('center','settle','clutter','tray','top')); args=parser.parse_args()
    env = G1ManipEnv(); fns = {'center':center,'settle':settle}
    rows = fns[args.job](env) if args.job in fns else scenes(env,args.job)
    dest = Path('m2a/notes/wsa_gate_raw')/f'round2_{args.job}.jsonl'
    with dest.open('w',encoding='utf-8') as f:
        counts = Counter()
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False)+'\n'); f.flush(); counts[bool(row['ok'])]+=1
        print(args.job, counts)
    env.close()

if __name__=='__main__':
    main()
