"""Replay contract actions and independently check count/order objectives."""
from collections import Counter
from copy import deepcopy

from m2a.common import load_parts


def verify(symbolic_state, goal, candidate, layout, *, strict=True):
    state = deepcopy(symbolic_state)

    def invalid_candidate(field, **details):
        return {'ok': False, 'violations': [{'code': 'invalid_candidate', 'field': field,
                                             **details}], 'final_state': state}

    if not isinstance(candidate, dict):
        return invalid_candidate('candidate')
    if type(candidate.get('ok')) is not bool:
        return invalid_candidate('ok')
    raw_actions = candidate.get('actions')
    if not isinstance(raw_actions, (list, tuple)):
        return invalid_candidate('actions')
    reported = candidate.get('missing')
    if (not isinstance(reported, dict)
            or any(not isinstance(p, str) or type(n) is not int for p, n in reported.items())):
        return invalid_candidate('missing')
    shapes = {'pick': 4, 'pick-from-top': 5, 'pick-from-tray': 4,
              'place': 4, 'put-aside': 4, 'handover': 4}
    for idx, action in enumerate(raw_actions):
        if (not isinstance(action, (list, tuple)) or not action
                or not all(isinstance(arg, str) for arg in action)
                or shapes.get(action[0]) != len(action)):
            return invalid_candidate('actions', index=idx)

    objects = state['objects']
    reach = state.get('reach', layout.get('reach', {}))
    permitted = set(goal.get('allowed_arms', ('left', 'right'))) & {'left', 'right'}
    forbidden = set(goal.get('unusable_trays', ()))
    excluded = set(goal.get('excluded_parts', ()))
    wanted = {t: {p: n for p, n in counts.items() if p not in excluded and n}
              for t, counts in goal['trays'].items()}
    bom = {p for p, meta in load_parts()['parts'].items() if meta['bom']}
    tray_ids, regions = set(layout['trays']), set(layout['regions']) | {'center_zone'}
    violations, placements = [], []
    held = dict.fromkeys(('left', 'right'))
    requested = Counter()
    for counts in wanted.values():
        requested.update(counts)
    physical = Counter(obj['part_id'] for obj in objects.values())
    expected_missing = requested - physical

    def counts_now():
        counts = {t: Counter() for t in tray_ids}
        for obj in objects.values():
            if obj.get('in_tray') in counts:
                counts[obj['in_tray']][obj['part_id']] += 1
        return counts

    def fail(*args):
        violations.append(':'.join(str(v) for v in args))

    def stack_region(oid):
        seen = set()
        while oid in objects and oid not in seen:
            seen.add(oid)
            obj = objects[oid]
            if obj.get('on') is None:
                return obj.get('region') if obj.get('in_tray') is None else None
            oid = obj['on']
        return None

    if candidate.get('ok') is not True:
        fail('plan_not_ok')
    if reported != dict(expected_missing):
        fail('missing_report_mismatch')
    if (set(wanted) | forbidden) - tray_ids or any(wanted.get(t) for t in forbidden):
        fail('invalid_tray_goal')
    if set(goal.get('allowed_arms', ())) - {'left', 'right'}:
        fail('invalid_arm_goal')
    for idx, action in enumerate(raw_actions):
        cmd, arm, *args = action
        if arm not in permitted:
            fail(idx, 'forbidden_arm', arm)
            break
        if cmd == 'handover':
            other, oid = args
            if other == arm or other not in permitted:
                fail(idx, 'forbidden_handover', other)
                break
            if held[arm] != oid or held[other] is not None:
                fail(idx, 'handover_precondition', oid)
                break
            held[arm], held[other] = None, oid
            continue
        oid, *args = args
        if oid not in objects:
            fail(idx, 'unknown_object', oid)
            break
        obj, target = objects[oid], args[-1]
        if target not in reach.get(arm, ()):
            fail(idx, 'out_of_reach', arm, target)
            break
        if cmd.startswith('pick'):
            if held[arm] is not None or oid in held.values():
                fail(idx, 'hand_not_available', oid)
                break
            if any(o.get('on') == oid for o in objects.values()):
                fail(idx, 'not_clear', oid)
                break
            tray, support, region = obj.get('in_tray'), obj.get('on'), obj.get('region')
            if cmd == 'pick':
                located = target in regions and region == target and tray is None and support is None
            elif cmd == 'pick-from-tray':
                located = target in tray_ids and tray == target and support is None and region is None
            else:
                located = (target in regions and tray is None and support == args[0]
                           and support in objects and stack_region(oid) == target)
            if not located:
                fail(idx, 'pick_location', oid, target)
                break
            held[arm] = oid
            obj.update(region=None, in_tray=None, on=None)
        else:
            if held[arm] != oid:
                fail(idx, 'not_held', oid)
                break
            if cmd == 'place':
                part = obj['part_id']
                if target not in tray_ids or target in forbidden:
                    fail(idx, 'forbidden_tray', target)
                    break
                if part not in bom or part in excluded:
                    fail(idx, 'forbidden_part', part)
                    break
                if part not in wanted.get(target, {}):
                    fail(idx, 'wrong_tray', target, part)
                    break
                placements.append((idx, target, part, counts_now()))
                obj.update(region=None, in_tray=target, on=None)
            else:
                if target != 'center_zone':
                    fail(idx, 'not_buffer', target)
                    break
                obj.update(region=target, in_tray=None, on=None)
            held[arm] = None

    final = counts_now()
    if any(oid is not None for oid in held.values()):
        state['held'] = {a: oid for a, oid in held.items() if oid is not None}
        fail('arms_not_empty')
    filled = Counter()
    for tray, counts in sorted(final.items()):
        for part, n in counts.items():
            if tray in forbidden or part in excluded or part not in bom:
                fail('forbidden_contents', tray, part)
            if tray in wanted:
                if n > wanted[tray].get(part, 0):
                    fail('extra_contents', tray, part)
                filled[part] += min(n, wanted[tray].get(part, 0))
    if requested - filled != expected_missing:
        fail('wrong_counts')

    groups = [tuple(g) for g in goal.get('step_order', ())] if strict else []
    ordered = [t for g in groups for t in g]
    if len(set(ordered)) != len(ordered) or set(ordered) - set(wanted):
        fail('invalid_step_order')
        groups = []
    tail = tuple(sorted(set(wanted) - set(ordered)))
    if tail:
        groups.append(tail)
    priority = {p: idx for idx, p in enumerate(goal.get('priority_parts', ()))}
    group_for = {t: i for i, g in enumerate(groups) for t in g}
    # Use the actually delivered counts, not a reimplementation of oid assignment.
    completed = {t: {p: min(n, final.get(t, {}).get(p, 0)) for p, n in parts.items()}
                 for t, parts in wanted.items()}
    for idx, tray, part, before in placements:
        if tray not in group_for:
            continue
        group_idx = group_for[tray]
        earlier = [t for g in groups[:group_idx] for t in g]
        if any(before[t] != Counter(completed[t]) for t in earlier):
            fail(idx, 'step_order', tray)
        for t in groups[group_idx]:
            if any(priority.get(p, len(priority)) < priority.get(part, len(priority))
                   and before[t][p] < n for p, n in completed[t].items()):
                fail(idx, 'priority_order', part)
                break
    return {'ok': not violations, 'violations': violations, 'final_state': state}
