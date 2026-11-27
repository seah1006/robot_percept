"""Skill-level bench: one pick -> place cycle per trial, fixed seeds, per-stage failure codes.

P-gate here is the GT-assisted weld grasp approximation (not friction grasping).
Grid (all imposed values): parts P01..P06 x source {left_zone, right_zone, center_zone, tray}
x destination {T1, T2, T3, put_aside->center_zone} x clutter {0, 3} x reps.
Usage: python -m m2a.sim.skill_bench --tag base --reps 2 --workers 6
"""
from __future__ import annotations
import argparse
import json
import math
import os
import time
from collections import Counter, defaultdict
from multiprocessing import Pool
import numpy as np
from m2a.common import M2A, load_layout, load_parts
from m2a.scene._geometry import contains, corners, inset, obb, overlaps, size_xyz, tray_box, tray_rect
from .g1_manip_env import ARMS, G1ManipEnv

PARTS = ('P01', 'P02', 'P03', 'P04', 'P05', 'P06')
SOURCES = ('left_zone', 'right_zone', 'center_zone', 'tray')
DESTS = ('T1', 'T2', 'T3', 'put_aside')
CLUTTER = (0, 3)
PLATES = ('P01', 'P02', 'P03')
NEIGHBOURS = ('P01', 'P02', 'P03', 'P04', 'P05', 'P06', 'D01')
GAP = .006           # imposed minimum gap between sampled objects
SETTLE_S = 1.5       # imposed settle time before the independent GT check
BASE_SEED = 20400    # imposed; bench seeds are outside generator split ranges on purpose
STAGES = ('reach_pregrasp', 'grasp_lift', 'place', 'judge')


def _fixture(objects, seed):
    return dict(schema='m2a.scene.v1', seed=seed, split='dev', level='L0', situation='standard',
                product='m2a_shelf_v1', goal_steps=[1], objects=objects,
                render=dict(table_rgb=[.55, .45, .35], light_seed=7))


def _sample(rng, part_id, part, rect, occupied, layout, in_tray):
    """Generator-like pose sampling (plates near the long axis, others free yaw)."""
    hx, hy = np.asarray(layout['table']['size_xy']) / 2
    trays = [tray_box(t) for t in layout['trays'].values()]
    size = size_xyz(part); x, X, y, Y = rect
    if in_tray:
        x, X, y, Y = inset(rect, layout['judge']['tray_margin'])
    for trial in range(400):
        plate = part_id in PLATES
        limit = (math.pi/12 if plate else math.pi) * (1 if trial < 200 else .25)
        heading = math.pi/2 if plate and (Y-y) > (X-x) else 0.
        yaw = heading + float(rng.uniform(-limit, limit))
        vs = corners(obb((0., 0.), size, yaw))
        rx, ry = max(abs(a) for a, _ in vs), max(abs(b) for _, b in vs)
        x0, x1, y0, y1 = x+rx+GAP/2, X-rx-GAP/2, y+ry+GAP/2, Y-ry-GAP/2
        if x0 > x1 or y0 > y1:
            continue
        xy = (float(rng.uniform(x0, x1)), float(rng.uniform(y0, y1)))
        box = obb(xy, size, yaw)
        if any(not (-hx <= cx <= hx and -hy <= cy <= hy) for cx, cy in corners(box)):
            continue
        if any(overlaps(box, o, GAP) for o in occupied):
            continue
        if not in_tray and any(overlaps(box, t, GAP) for t in trays):
            continue
        return xy, yaw, box
    return None


def _arm_for(source_name, dest, layout, idx):
    reach = layout['reach']
    side = {'left_zone': 'left', 'right_zone': 'right', 'T1': 'left', 'T3': 'right'}.get(source_name)
    target = 'center_zone' if dest == 'put_aside' else dest
    order = [side] if side else [ARMS[idx % 2], ARMS[(idx+1) % 2]]
    if side:
        order.append('right' if side == 'left' else 'left')
    for arm in order:
        if source_name in reach[arm] and target in reach[arm]:
            return arm
    return None


def make_trial(part_id, source, dest, clutter, rep, layout=None, parts=None):
    layout = layout or load_layout(); parts = parts or load_parts()['parts']
    key = (PARTS.index(part_id), SOURCES.index(source), DESTS.index(dest), clutter, rep)
    seed = BASE_SEED + key[0]*1000 + key[1]*200 + key[2]*40 + key[3]*5 + key[4]
    rng = np.random.default_rng(seed)
    if source == 'tray':
        choices = [t for t in layout['trays'] if t != dest]
        source_name = str(choices[rep % len(choices)])
        rect = tray_rect(layout['trays'][source_name]); in_tray = source_name
    else:
        source_name = source; rect = layout['regions'][source]; in_tray = None
    part = parts[part_id]
    got = _sample(rng, part_id, part, rect, [], layout, in_tray)
    if got is None:
        return None
    floor = layout['trays'][in_tray]['floor_z'] if in_tray else 0.
    objects = [dict(oid='o0', part_id=part_id, xyz=[*got[0], floor + size_xyz(part)[2]/2], yaw=got[1],
                    region=None if in_tray else source_name, in_tray=in_tray, on=None)]
    occupied = [got[2]]
    # Neighbours: one in the source area, one in the destination area, rest anywhere (imposed).
    dest_name = 'center_zone' if dest == 'put_aside' else dest
    areas = [source_name, dest_name] + [None] * max(0, clutter - 2)
    for i, area in enumerate(areas[:clutter]):
        for _ in range(20):
            name = area or str(rng.choice([*layout['regions'], *layout['trays']]))
            tray = name if name in layout['trays'] else None
            r = tray_rect(layout['trays'][name]) if tray else layout['regions'][name]
            pid = str(rng.choice(NEIGHBOURS))
            g = _sample(rng, pid, parts[pid], r, occupied, layout, tray)
            if g is None:
                continue
            fz = layout['trays'][tray]['floor_z'] if tray else 0.
            objects.append(dict(oid=f'o{i+1}', part_id=pid, xyz=[*g[0], fz + size_xyz(parts[pid])[2]/2],
                                yaw=g[1], region=None if tray else name, in_tray=tray, on=None))
            occupied.append(g[2])
            break
    arm = _arm_for(source_name, dest, layout, rep + key[1])
    return dict(seed=seed, part_id=part_id, source=source, source_name=source_name, dest=dest,
                clutter=clutter, rep=rep, arm=arm, spec=_fixture(objects, seed))


def judge_place(env, oid, dest):
    gt = env.get_gt_objects()[oid]; pos = np.asarray(gt['xyz']); cfg = env.layout['judge']
    if dest == 'put_aside':
        part = env.parts[gt['part_id']]
        box = obb(pos[:2], size_xyz(part), gt['yaw'])
        rect = env.layout['regions']['center_zone']
        return dict(inside_xy=bool(contains(rect, pos[:2])),
                    footprint_inside=all(contains(inset(rect, -.005), c) for c in corners(box)),
                    upright=bool(abs(pos[2] - size_xyz(part)[2]/2) <= .005),
                    settled=gt['lin_speed'] < cfg['settle_speed'])
    tr = env.layout['trays'][dest]; inner = np.asarray(tr['inner'])/2 - cfg['tray_margin']
    return dict(inside_xy=bool(np.all(np.abs(pos[:2]-tr['center']) <= inner)),
                inside_z=bool(tr['floor_z'] <= pos[2] <= tr['floor_z'] + cfg['tray_z_max_above_floor']),
                settled=gt['lin_speed'] < cfg['settle_speed'])


def run_trial(trial, mode='P-gate'):
    from .skills import SkillRunner
    row = {k: v for k, v in trial.items() if k != 'spec'}
    row['spec'] = trial['spec']
    if trial['arm'] is None:
        return dict(row, ok=False, stage='plan_reach', reason='UNREACHABLE', excluded=True)
    env = G1ManipEnv()
    try:
        env.reset(trial['spec']); sk = SkillRunner(env, mode); arm = trial['arm']
        initial = env.get_gt_objects(); t0 = time.perf_counter(); skills = {}
        dest = trial['dest']
        steps = [('reach_pregrasp', 'reach_pregrasp', None), ('grasp_lift', 'grasp_lift', None),
                 ('place', 'put_aside' if dest == 'put_aside' else 'transport_place',
                  'center_zone' if dest == 'put_aside' else dest)]
        for stage, skill, target in steps:
            r = sk.run(skill, arm, 'o0', target)
            skills[stage] = dict(r, events={k: v for k, v in sk.events.items() if k != 'tracking_error'},
                                 tracking_error=sk.events.get('tracking_error'))
            if not r['ok']:
                env.step(math.ceil(.5/env.model.opt.timestep))
                return dict(row, ok=False, stage=stage, reason=r['reason_code'], skills=skills,
                            wall_s=time.perf_counter()-t0, final=env.get_gt_objects())
        env.step(math.ceil(SETTLE_S/env.model.opt.timestep))
        check = judge_place(env, 'o0', dest); final = env.get_gt_objects()
        moved = {o: float(np.linalg.norm(np.subtract(final[o]['xyz'], initial[o]['xyz'])))
                 for o in initial if o != 'o0'}
        ok = all(check.values())
        return dict(row, ok=ok, stage=None if ok else 'judge',
                    reason=None if ok else '+'.join(k for k, v in check.items() if not v),
                    judge=check, skills=skills, neighbour_moved_m=moved,
                    wall_s=time.perf_counter()-t0, final=final)
    except Exception as exc:  # keep the batch alive, record as harness error
        return dict(row, ok=False, stage='error', reason=repr(exc))
    finally:
        env.close()


def all_trials(reps, parts=PARTS, sources=SOURCES, dests=DESTS, clutters=CLUTTER):
    layout = load_layout(); catalog = load_parts()['parts']
    out = []
    for p in parts:
        for c in clutters:
            for s in sources:
                for d in dests:
                    for r in range(reps):
                        t = make_trial(p, s, d, c, r, layout, catalog)
                        if t is not None:
                            out.append(t)
    return out


def _worker(args):
    os.nice(10)
    return run_trial(*args)


def summarize(rows):
    table = defaultdict(lambda: dict(n=0, ok=0, fails=Counter()))
    for r in rows:
        if r.get('excluded'):
            continue
        for key in [(r['part_id'], r['clutter']), ('ALL', r['clutter']),
                    (r['part_id'], f"src:{r['source']}"), (r['part_id'], f"dst:{r['dest']}"),
                    ('ALL', f"src:{r['source']}"), ('ALL', f"dst:{r['dest']}")]:
            cell = table[key]; cell['n'] += 1; cell['ok'] += bool(r['ok'])
            if not r['ok']:
                cell['fails'][f"{r['stage']}/{r['reason']}"] += 1
    return {f'{a}|{b}': dict(n=v['n'], ok=v['ok'], fails=dict(v['fails'].most_common())) for (a, b), v in table.items()}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--tag', default='base')
    ap.add_argument('--reps', type=int, default=2)
    ap.add_argument('--workers', type=int, default=6)
    ap.add_argument('--mode', default='P-gate')
    ap.add_argument('--parts', default=','.join(PARTS))
    ap.add_argument('--sources', default=','.join(SOURCES))
    ap.add_argument('--dests', default=','.join(DESTS))
    ap.add_argument('--clutter', default='0,3')
    a = ap.parse_args()
    trials = all_trials(a.reps, a.parts.split(','), a.sources.split(','), a.dests.split(','),
                        [int(c) for c in a.clutter.split(',')])
    out = M2A/'notes'/'wsa_gate_raw'; out.mkdir(parents=True, exist_ok=True)
    path = out/f'bench_{a.tag}.jsonl'
    rows = []
    with Pool(min(6, a.workers)) as pool, path.open('w', encoding='utf-8') as f:
        for row in pool.imap_unordered(_worker, [(t, a.mode) for t in trials]):
            rows.append(row); f.write(json.dumps(row, ensure_ascii=False, default=float) + '\n'); f.flush()
    summary = summarize(rows)
    (out/f'bench_{a.tag}_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding='utf-8')
    for k in sorted(summary):
        v = summary[k]; print(f"{k:28s} {v['ok']:3d}/{v['n']:3d}  {v['fails']}")


if __name__ == '__main__':
    main()
