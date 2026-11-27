"""Reproducible, simulator-independent scene generation."""
from collections import Counter
from hashlib import sha256
from itertools import combinations
import json
from math import pi
from numbers import Integral

import numpy as np
from m2a.common import load_layout, load_parts, load_steps
from ._geometry import contains, corners, floor_z, inset, obb, overlaps, size_xyz, tray_box, tray_rect

SPLITS = {'train': (0, 4999), 'dev': (10000, 10199), 'test': (90000, 90099)}
LEVELS = ('L0', 'L1', 'L2')
SITUATIONS = ('standard', 'missing', 'pretray', 'stacked', 'reach')
PRODUCT = 'm2a_shelf_v1'
GAP = .004  # 임의 지정
STACK_MARGIN = .002  # 임의 지정: required clearance from each support edge
PACKING_RETRIES = 192  # 임의 지정
PLACEMENT_TRIALS = 180  # 임의 지정


def validate_seed(seed, split, final_test=False):
    if isinstance(seed, bool) or not isinstance(seed, Integral):
        raise ValueError('seed must be an integer')
    if split not in SPLITS or not SPLITS[split][0] <= seed <= SPLITS[split][1]:
        raise ValueError(f'seed {seed} does not belong to split {split!r}')
    if split == 'test' and final_test is not True:
        raise ValueError('test seeds require final_test=True')


def scene_digest(spec):
    return sha256(json.dumps(spec, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                             allow_nan=False).encode('utf-8')).hexdigest()


def _goal_items(level, situation, steps, parts, rng):
    if level == 'L0':
        step = steps[int(rng.integers(len(steps)))]
        return [(step['tray'], str(rng.choice([pid for pid in step['parts'] if situation != 'stacked' or parts[pid]['shape'] == 'box'])))]
    groups = list(combinations(steps, 2))
    groups += [(step,) for step in steps] if level == 'L1' else [tuple(steps)]
    lo, hi = ((5 if situation == 'missing' else 4), 6) if level == 'L1' else (6, 9)
    groups = [group for group in groups if sum(sum(step['parts'].values()) for step in group) >= lo]
    group = groups[int(rng.integers(len(groups)))]
    slots = [(step['tray'], pid) for step in group for pid in step['parts']]
    pool = [(step['tray'], pid) for step in group for pid, count in step['parts'].items()
            for _ in range(count - 1)]
    quantity = int(rng.integers(max(lo, len(slots)), min(hi, len(slots)+len(pool))+1))
    slots.extend(pool[int(i)] for i in rng.permutation(len(pool))[:quantity-len(slots)])
    return slots


def _can_stack(base, top):
    # Both objects are centered on the same xy and use the same yaw.
    return base['shape'] == 'box' and all(
        a >= b + 2 * STACK_MARGIN for a, b in zip(size_xyz(base)[:2], size_xyz(top)[:2]))


def _items(level, situation, slots, parts, layout, rng):
    items = [{'part_id': pid, 'target': tray} for tray, pid in slots]
    missing = {}
    if situation == 'missing':
        counts = Counter(pid for _, pid in slots)
        eligible = [i for i, obj in enumerate(items) if level != 'L2' or
                    obj['part_id'] not in ('P01', 'P02') or counts[obj['part_id']] > 1]
        missing[items.pop(int(rng.choice(eligible)))['part_id']] = 1
    if situation == 'pretray':
        i = int(rng.integers(len(items)))
        correct = items[i]
        correct['in_tray'] = correct['target']
        if level == 'L0':
            wrong = {'part_id': correct['part_id']}
            items.append(wrong)
        else:
            wrong = items[int(rng.choice([j for j in range(len(items)) if j != i]))]
        designated = {tid for tid, pid in slots if pid == wrong['part_id']}
        wrong['in_tray'] = str(rng.choice([tid for tid in layout['trays'] if tid not in designated and tid != correct['in_tray']]))
    if level == 'L0':
        n = int(rng.integers(1, 4)) - (situation == 'pretray')
        options = [pid for pid in parts if pid != slots[0][1]]
        if situation == 'stacked':
            # Guarantee a compatible distractor without changing the L0 goal or total count.
            supports = [pid for pid in options if _can_stack(parts[slots[0][1]], parts[pid])]
            if not supports:
                raise ValueError('No compatible stacked distractor for L0 goal')
            items.append({'part_id': str(rng.choice(supports))})
            n -= 1
        items.extend({'part_id': str(rng.choice(options))} for _ in range(n))
    if level == 'L2':
        for pid in ('P01', 'P02', 'D01'):
            if not any(obj['part_id'] == pid for obj in items):
                items.append({'part_id': pid})
    for i, item in enumerate(items):
        item['oid'] = f'o{i}'
    if situation == 'stacked':
        # Consider every pair; reject overhang and cylinder supports before sampling.
        pairs = [(base, top) for base in items if 'target' in base for top in items
                 if base is not top and _can_stack(parts[base['part_id']], parts[top['part_id']])]
        if not pairs:
            raise ValueError('No compatible stacked pair in selected inventory')
        base, top = pairs[int(rng.integers(len(pairs)))]
        top['on'] = base['oid']
    reach_case = None
    if situation == 'reach':
        obj = items[int(rng.integers(len(slots)))]
        target_y = layout['trays'][obj['target']]['center'][1]
        arms = {}
        for arm, reachable in layout['reach'].items():
            others = {zone for name, regions in layout['reach'].items() if name != arm for zone in regions}
            arms[arm] = [zone for zone in layout['regions'] if zone in reachable and zone not in others]
        if not all(arms.values()) or len(arms) != 2:
            raise ValueError('reach situation requires arm-exclusive zones on both sides')
        distance = lambda zone: abs(sum(layout['regions'][zone][2:])/2 - target_y)
        nominal = min(arms, key=lambda arm: min(map(distance, arms[arm])))
        opposite = next(arm for arm in arms if arm != nominal)
        obj['fixed_region'] = min(arms[opposite], key=distance)
        reach_case = {'oid': obj['oid'], 'nominal_arm': nominal, 'required_pick_arm': opposite}
    return items, missing, reach_case
def _place(items, parts, layout, rng):
    zones, trays = layout['regions'], layout['trays']
    exclusive = [zone for zone in zones if sum(zone in reach for reach in layout['reach'].values()) == 1]
    loose_regions = exclusive or list(zones)
    tray_boxes = [tray_box(tray) for tray in trays.values()]
    hx, hy = (side/2 for side in layout['table']['size_xy'])
    table_rect = (-hx, hx, -hy, hy)
    tops = {obj['on']: obj for obj in items if 'on' in obj}
    dims = {obj['oid']: size_xyz(parts[obj['part_id']]) for obj in items}
    def area(obj):
        return max(dims[oid][0]*dims[oid][1] for oid in (obj['oid'], tops.get(obj['oid'], obj)['oid']))
    base_items = sorted((obj for obj in items if 'on' not in obj), key=lambda obj: (
        'in_tray' not in obj, 'fixed_region' not in obj, -area(obj)))
    for attempt in range(PACKING_RETRIES):
        dense = attempt >= 8  # 임의 지정: prefer squarer yaw and boundary slots only on retries
        candidates = list(zones) if dense else loose_regions
        occupied, placed = [], {}
        for obj in base_items:
            tid = obj.get('in_tray')
            top = tops.get(obj['oid'])
            following = [obj, top] if top else [obj]
            yaw_max = pi/12 if any(member['part_id'] in ('P01', 'P02', 'P03')
                                   for member in following) else pi
            for trial in range(PLACEMENT_TRIALS):
                region = None if tid else obj.get('fixed_region') or str(rng.choice(candidates))
                rect = tray_rect(trays[tid]) if tid else zones[region]
                x, X, y, Y = rect
                heading = pi/2 if yaw_max < pi and Y-y > X-x else 0.
                limit = min(yaw_max, pi/120) if dense and trial % 4 else yaw_max
                yaw = heading + float(rng.uniform(-limit, limit))
                vertices = [corner for member in following
                            for corner in corners(obb((0., 0.), dims[member['oid']], yaw))]
                rx, ry = max(abs(x) for x, _ in vertices), max(abs(y) for _, y in vertices)
                x0, x1, y0, y1 = x+rx+GAP/2, X-rx-GAP/2, y+ry+GAP/2, Y-ry-GAP/2
                if tid:
                    jx, jX, jy, jY = inset(rect, layout['judge']['tray_margin'])
                    x0, x1, y0, y1 = max(x0, jx), min(x1, jX), max(y0, jy), min(y1, jY)
                if x0 > x1 or y0 > y1:
                    continue
                xy = [float(rng.uniform(x0, x1)), float(rng.uniform(y0, y1))]
                if dense and trial % 4:
                    # Keep room for adjacent pieces by sampling region extremes.
                    edge = rng.integers(4)
                    xy[1] = y1 if edge % 2 else y0
                    if edge < 2:
                        xy[0] = x0 if rng.integers(2) else x1
                boxes = [obb(xy, dims[member['oid']], yaw) for member in following]
                if (any(not contains(table_rect, c) for box in boxes for c in corners(box))
                        or any(overlaps(a, b, GAP) for a in boxes for b in occupied)
                        or (not tid and any(overlaps(a, b, GAP) for a in boxes for b in tray_boxes))):
                    continue
                occupied.extend(boxes)
                z = floor_z(trays[tid]) if tid else 0.
                for member in following:
                    oid = member['oid']
                    height = dims[oid][2]
                    placed[oid] = dict(oid=oid, part_id=member['part_id'], xyz=[*xy, z+height/2],
                        yaw=yaw, region=region, in_tray=tid, on=member.get('on'))
                    z += height
                break
            else:
                break
        else:
            return [placed[obj['oid']] for obj in items]
    raise ValueError(f"S0 packing exhausted for {obj['oid']} ({obj['part_id']}); "
                     f"{PACKING_RETRIES} retries; check layout dimensions and reach")


def generate(seed, level, situation, split, final_test=False, layout=None):
    """Build a contract v1 scene using a supplied layout dict or the default config."""
    validate_seed(seed, split, final_test)
    if level not in LEVELS or situation not in SITUATIONS:
        raise ValueError(f'unknown level/situation: {level!r}/{situation!r}')
    seed = int(seed)
    rng, positioning, render_rng = map(np.random.default_rng, np.random.SeedSequence(seed).spawn(3))
    layout = load_layout() if layout is None else layout
    parts = load_parts(PRODUCT)['parts']
    steps = load_steps(PRODUCT)['steps']
    slots = _goal_items(level, situation, steps, parts, rng)
    # Packed geometry may favor another valid stack pair/candidate inventory.
    for attempt in range(4 if situation == 'stacked' else 1):  # 임의 지정
        if attempt:
            slots = _goal_items(level, situation, steps, parts, rng)
        try:
            items, missing, reach_case = _items(level, situation, slots, parts, layout, rng)
            objects = _place(items, parts, layout, positioning)
        except ValueError as error:
            last_error = error
        else:
            break
    else:
        raise last_error
    trays = {step['tray']: dict(counts) for step in steps
             if (counts := Counter(pid for tid, pid in slots if tid == step['tray']))}
    goal_steps = [step['step'] for step in steps if step['tray'] in trays]
    goal = dict(schema='m2a.goal.v1', trays=trays, allowed_arms=['left', 'right'], unusable_trays=[],
                step_order=[[tid] for tid in trays], excluded_parts=[],
                source_text='장면 기본 목표: ' + ', '.join(f'{step}단계' for step in goal_steps))
    color = render_rng.uniform([.48, .38, .28], [.62, .52, .42]).tolist()
    expected = {'goal': goal, 'missing': missing}
    if reach_case is not None:
        expected['reach'] = reach_case
    return dict(schema='m2a.scene.v1', seed=seed, split=split, level=level, situation=situation,
                product=PRODUCT, goal_steps=goal_steps, objects=objects,
                render={'table_rgb': color, 'light_seed': int(render_rng.integers(2**31))},
                expected=expected)
