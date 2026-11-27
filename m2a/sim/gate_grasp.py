"""Reproducible G-A grasp and layout measurements (run under rp_measure.lock)."""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import numpy as np
from m2a.common import M2A, load_parts
from .g1_manip_env import ARMS, CAMERAS, G1ManipEnv, half_height
from .skills import SkillRunner, grasp_profile

PART_IDS = ('P01', 'P04', 'P06', 'P02', 'P03', 'P05')  # round4 appended P02/P03/P05 (seeds 10045..10047)
SEED = 10042


def fixture(objects=(), seed=SEED):
    return dict(schema='m2a.scene.v1', seed=seed, split='dev', level='L1', situation='standard',
                product='m2a_shelf_v1', goal_steps=[1, 2], objects=list(objects),
                render=dict(table_rgb=[.55, .45, .35], light_seed=7))


def candidates(part_id, part):
    rng = np.random.default_rng(SEED + PART_IDS.index(part_id))
    for i in range(20):
        arm = ARMS[i % 2]; sign = 1 if arm == 'left' else -1
        x = float(rng.uniform(-.155, -.095)); y = float(rng.uniform(.338, .374)) * sign
        yaw = (float(rng.uniform(-.25, .25) + math.pi/2) if part['shape'] == 'box'
               else float(rng.uniform(-math.pi, math.pi)))
        yield arm, fixture([dict(oid='o0', part_id=part_id, xyz=[x, y, half_height(part)], yaw=yaw,
                                 region=f'{arm}_zone', in_tray=None, on=None)])



def _footprint(part, yaw):
    """Half-sizes of the world-aligned enclosing box in table XY."""
    if part['shape'] == 'cylinder':
        return np.repeat(part['size'][0], 2)
    c, s = abs(math.cos(yaw)), abs(math.sin(yaw))
    return np.array([[c,s],[s,c]]) @ (np.array(part['size'][:2])/2)


def general_candidates(part_id, part, layout):
    """7/7/6 per region, no IK or success-based rejection."""
    seed = SEED + 100 + PART_IDS.index(part_id)
    rng = np.random.default_rng(seed)
    table = np.array(layout['table']['size_xy']) / 2
    discarded = 0
    for region, count in [('left_zone',7),('right_zone',7),('center_zone',6)]:
        x0, x1, y0, y1 = layout['regions'][region]
        major = math.pi/2 if y1-y0 > x1-x0 else 0.
        for i in range(count):
            arm = region.split('_')[0] if region != 'center_zone' else ARMS[i % 2]
            for _ in range(10000):
                xy = rng.uniform([x0,y0],[x1,y1]); phi = rng.uniform(-math.pi, math.pi)
                yaw = major + phi/12 if part['shape'] == 'box' else phi
                hw = _footprint(part, yaw)
                if np.any(np.abs(xy)+hw > table) or any(
                    np.all(np.abs(xy-tr['center']) < hw+np.asarray(tr['inner'])/2+tr['wall_thickness'])
                    for tr in layout['trays'].values()
                ):
                    discarded += 1
                    continue
                break
            else:
                raise RuntimeError(f'no collision-free initial samples for {part_id} in {region}')
            spec = fixture([dict(oid='o0', part_id=part_id, xyz=[*map(float,xy),half_height(part)],
                                 yaw=float(yaw), region=region, in_tray=None, on=None)], seed=seed)
            yield arm, spec, discarded


def _place_result(env, tray, gt):
    tr = env.layout['trays'][tray]; config = env.layout['judge']
    pos = np.asarray(gt['xyz']); inner = np.asarray(tr['inner'])/2 - config['tray_margin']
    return dict(inside_xy=bool(np.all(np.abs(pos[:2]-tr['center']) <= inner)),
                inside_z=bool(tr['floor_z'] <= pos[2] <= tr['floor_z'] + config['tray_z_max_above_floor']),
                settled=gt['lin_speed'] < config['settle_speed'])

def reach(env):
    env.reset(fixture())
    for arm in ARMS:
        targets = {}
        for name, (x0, x1, y0, y1) in env.layout['regions'].items():
            targets[name] = [(x,y) for x in np.linspace(x0, x1, 3) for y in np.linspace(y0, y1, 3)]
        # Round 4: trays as 3x3 points on the inner rectangle inset by .03 m (imposed), not centre only.
        for k, v in env.layout['trays'].items():
            (cx, cy), (w, h) = v['center'], np.asarray(v['inner']) / 2 - .03
            targets[k] = [(x, y) for x in np.linspace(cx-w, cx+w, 3) for y in np.linspace(cy-h, cy+h, 3)]
        for name, points in targets.items():
            for x, y in points:
                z = .065 if name in env.layout['trays'] else .025
                trials = []
                for h in np.linspace(-math.pi, math.pi, 16, endpoint=False):
                    R = env.topdown(arm, h)
                    q, low = env.solve_ik(arm, [x,y,z], R, q0=env.rest[arm], restarts=2)
                    high = None
                    if low['ok']:
                        _, high = env.solve_ik(arm, [x,y,z+.10], R, q0=q, restarts=0)
                    trials.append(dict(yaw=float(h), low=low, high=high))
                yield dict(arm=arm, target=name, xy=[x,y], z=z,
                           ok=any(t['low']['ok'] and t['high'] and t['high']['ok'] for t in trials), trials=trials)


def run_batch(env, part_id, mode, start, end, job='gate'):
    part = load_parts()['parts'][part_id]
    stream = (general_candidates(part_id, part, env.layout) if job == 'general' else
              ((arm,spec,0) for arm,spec in candidates(part_id, part)))
    for i, (arm, spec, discarded) in enumerate(stream):
        if not start <= i < end:
            continue
        if job == 'l0':
            spec['level'] = 'L0'
        env.reset(spec); skills = SkillRunner(env, mode)
        result = skills.run('grasp_lift', arm, 'o0')
        after_lift = env.get_gt_objects()['o0']
        row = dict(trial=i, seed=(spec['seed'] if job=='general' else SEED+PART_IDS.index(part_id)),
                   mode=mode, part_id=part_id, arm=arm, profile=grasp_profile(part_id)['name'],
                   spec=spec, skill=result, events=skills.events, after_lift=after_lift, initial_pose_rejections=discarded,
                   thumb_opposed=skills.events.get('thumb_opposed'),
                   min_contacts_during_lift=skills.events.get('min_contacts_during_lift'))
        if job == 'l0':
            tray = 'T1' if arm == 'left' else 'T3'
            place = skills.run('transport_place', arm, 'o0', tray) if result['ok'] else None
            env.step(math.ceil(2/env.model.opt.timestep))
            final = env.get_gt_objects()['o0']; check = _place_result(env, tray, final)
            ok = bool(result['ok'] and place['ok'] and all(check.values()))
            stage = None if ok else 'grasp' if not result['ok'] else 'transport_place' if not place['ok'] else 'judge'
            reason = (None if ok else result['reason_code'] if stage=='grasp' else
                      place['reason_code'] if stage=='transport_place' else
                      '+'.join(k for k,v in check.items() if not v))
            row.update(tray=tray, place_skill=place, judge=check, failure_stage=stage)
        else:
            env.watch_contacts(arm, 'o0')
            env.step(math.ceil(2/env.model.opt.timestep))
            row['min_contacts_during_hold'] = env.unwatch_contacts(arm)
            final = env.get_gt_objects()['o0']; attached = skills.is_attached(arm, 'o0')
            ok = result['ok'] and final['xyz'][2] >= .07 and attached
            reason = None if ok else result['reason_code'] or 'GRASP_SLIP'
            row.update(attached=attached)
        yield dict(**row, final=final, ok=ok, reason=reason, sim_time=float(env.data.time),
                   slip_events=env.slip_events.copy())


def capture(env, directory):
    from PIL import Image
    directory.mkdir(parents=True, exist_ok=True)
    for j, p in enumerate(PART_IDS):
        arm, spec = next(iter(candidates(p, load_parts()['parts'][p])))
        env.reset(spec); skills = SkillRunner(env, 'P-gate')
        if j == 0:
            for cam in CAMERAS:
                Image.fromarray(env.render(cam)[0]).save(directory/f'{cam}.png')
        result = skills.run('grasp_lift', arm, 'o0')
        print(p, result, skills.events)
        for cam in ('front', 'wrist_l'):
            Image.fromarray(env.render(cam)[0]).save(directory/f'{p}_{cam}.png')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('job', choices=('reach', 'gate', 'general', 'l0', 'capture'))
    p.add_argument('--part', choices=PART_IDS)
    p.add_argument('--mode', choices=('P-phys', 'P-gate', 'P-gate-strict'))
    p.add_argument('--tag', default='round3', help='output file prefix tag')
    p.add_argument('--start', type=int, default=0)
    p.add_argument('--end', type=int)
    args = p.parse_args()
    env = G1ManipEnv()
    out = M2A/'notes'/'wsa_gate_raw'; out.mkdir(parents=True, exist_ok=True)
    try:
        if args.job == 'capture':
            capture(env, M2A/'notes'/'img_a'); return
        if args.job == 'reach':
            name = 'reach' if args.tag == 'round3' else f'reach_{args.tag}'; rows = reach(env)
        else:
            limit = 10 if args.job == 'l0' else 20
            end = args.end if args.end is not None else limit
            if not args.part or not args.mode or not 0 <= args.start < end <= limit:
                p.error(f'{args.job} requires --part and --mode and 0 <= start < end <= {limit}')
            name = f'{args.job}_{args.tag}_{args.part}_{args.mode}_{args.start:02d}-{end:02d}'
            rows = run_batch(env, args.part, args.mode, args.start, end, args.job)
        with (out/f'{name}.jsonl').open('w', encoding='utf-8') as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False)+'\n'); f.flush()
    finally:
        env.close()


if __name__ == '__main__':
    main()
