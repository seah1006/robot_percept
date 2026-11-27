"""Naive baseline: identify parts but ignore placement, stacking and reach."""
from collections import Counter, defaultdict
from time import perf_counter

from m2a.common import load_steps


def plan(symbolic_state, goal, layout, *, product='m2a_shelf_v1'):
    start = perf_counter()
    by_part = defaultdict(list)
    objects = symbolic_state['objects']
    for oid in sorted(objects):
        by_part[objects[oid]['part_id']].append(oid)
    requested = goal['trays']
    excluded = set(goal.get('excluded_parts', ()))
    order = list(dict.fromkeys([s['tray'] for s in load_steps(product)['steps']] + sorted(requested)))
    actions, missing = [], Counter()
    for tray in order:
        for part, count in requested.get(tray, {}).items():
            if part in excluded:
                continue
            for _ in range(count):
                if not by_part[part]:
                    missing[part] += 1
                    continue
                oid = by_part[part].pop(0)
                obj = objects[oid]
                xyz = obj.get('xyz')
                region = obj.get('region')
                if xyz is not None:
                    y = xyz[1]
                elif region in layout['regions']:
                    bounds = layout['regions'][region]
                    y = (bounds[2] + bounds[3]) / 2
                elif obj.get('in_tray') in layout['trays']:
                    # Estimate y only; still issue a blind tabletop pick.
                    y = layout['trays'][obj['in_tray']]['center'][1]
                else:
                    y = 0
                arm = 'left' if y > 0 else 'right'
                actions.extend([['pick', arm, oid, region or 'center_zone'], ['place', arm, oid, tray]])
    return dict(schema='m2a.plan.v1', planner='b0_script', ok=True, actions=actions,
                missing=dict(missing), reason=None, plan_ms=round((perf_counter() - start) * 1000, 3))
