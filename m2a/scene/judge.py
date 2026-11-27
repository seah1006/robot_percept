"""GT-only physical outcome evaluation. Independent of planning and skills."""
from collections import Counter, defaultdict
from math import isfinite
from numbers import Real
from m2a.common import load_parts
from ._geometry import geometric_tray


def _strict_order(order, members, events):
    """Only final contributing objects matter; repicks use the last final-tray event."""
    groups = [[(oid, tray) for tray in group for oid in members[tray]] for group in order]
    groups = [group for group in groups if group]
    if len(groups) <= 1:
        return None
    if events is None:
        return 'step_order_unverified'
    stamps = {}
    latest_by_oid = {}
    for event in events:
        if not isinstance(event, dict) or not {'oid', 'tray', 't_ms'} <= event.keys():
            return 'invalid_step_events'
        oid, tray, stamp = event['oid'], event['tray'], event['t_ms']
        if (not isinstance(oid, str) or not isinstance(tray, str) or
                isinstance(stamp, bool) or not isinstance(stamp, Real) or not isfinite(stamp) or stamp < 0):
            return 'invalid_step_events'
        stamps[oid, tray] = max(stamp, stamps.get((oid, tray), -1))
        latest_by_oid[oid] = max(stamp, latest_by_oid.get(oid, -1))
    for group in groups:
        for oid, tray in group:
            if oid in latest_by_oid and stamps.get((oid, tray)) != latest_by_oid[oid]:
                return 'step_order_unverified'
    previous = None
    for group in groups:
        # With a complete log, an object with no insertion was already present.
        times = [stamps.get(key, -1) for key in group]
        if previous is not None and (previous > min(times) or previous == min(times) >= 0):
            return 'step_order_violation'
        previous = max(times)
    return None


def judge(gt_objects, goal, layout, reported_missing=None, internal_done=None, events=None):
    """Judge against the original goal; inventory shortage is independent of placement.

    All original objects must be in GT, including fallen objects. Events, when supplied,
    must be a complete success-insertion log: [{oid, tray, t_ms}, ...].
    """
    parts = load_parts(goal.get('product', 'm2a_shelf_v1'))['parts']
    unavailable = set(goal.get('unusable_trays', []))
    excluded = set(goal.get('excluded_parts', []))
    trays = {tid: Counter(goal['trays'].get(tid, {})) for tid in layout['trays']}
    unknown = goal['trays'].keys() - trays.keys()
    violations = [f'unknown_tray:{tid}' for tid in sorted(unknown)]
    inventory = Counter(obj['part_id'] for obj in gt_objects.values())
    need = sum(trays.values(), Counter())
    missing = need - inventory
    if dict(missing) != (reported_missing if reported_missing is not None else {}):
        violations.append('missing_report_mismatch')

    measured = defaultdict(Counter)
    members = defaultdict(list)
    settle = layout['judge']['settle_speed']
    for oid, obj in gt_objects.items():
        xyz, pid, speed = obj['xyz'], obj['part_id'], obj['lin_speed']
        if not all(isfinite(value) for value in (*xyz, speed)) or speed < 0:
            violations.append(f'invalid_gt:{oid}')
            continue
        if xyz[2] < 0:
            violations.append(f'fallen:{oid}')
        tid = geometric_tray(xyz, layout)
        if tid is None:
            continue
        if tid in unavailable:
            violations.append(f'unusable_tray:{tid}:{oid}')
        if pid in excluded:
            violations.append(f'excluded_part:{tid}:{oid}')
        if not parts.get(pid, {}).get('bom', False):
            violations.append(f'non_bom_in_tray:{tid}:{oid}')
        if speed >= settle:
            violations.append(f'unsettled:{tid}:{oid}')
            continue
        measured[tid][pid] += 1
        members[tid].append(oid)

    # Assign shared inventory to the right trays first, then spare stock in goal step order.
    effective = {tid: trays[tid] & measured[tid] for tid in trays}
    pool = inventory - sum(effective.values(), Counter())
    ordered = dict.fromkeys([tid for group in goal.get('step_order', []) for tid in group if tid in trays]
                            + list(trays))
    for tid in ordered:
        fill = (trays[tid] - effective[tid]) & pool
        effective[tid] += fill
        pool -= fill

    per_tray = {}
    progress_count = 0
    for tid, expected in effective.items():
        actual = measured[tid]
        matched = sum((actual & expected).values())
        progress_count += matched
        ok = actual == expected and not (tid in unavailable and actual)
        if actual != expected:
            violations.append(f'tray_counts:{tid}')
        per_tray[tid] = dict(expected=dict(expected), requested=dict(trays[tid]), actual=dict(actual), ok=ok)

    success = not violations
    order_problem = _strict_order(goal.get('step_order', []), members, events) if success else None
    strict_violations = [order_problem] if order_problem else []
    denom = sum(sum(counter.values()) for counter in effective.values())
    return dict(success=success, strict_success=success and not order_problem,
                avg_progress=progress_count / denom if denom else 1.,
                false_completion=bool(internal_done and not success), per_tray=per_tray,
                violations=violations, strict_violations=strict_violations)
