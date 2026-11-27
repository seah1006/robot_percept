"""O3-only assignment and confirmation: predictions are never changed in place."""
from collections import Counter
from math import isfinite

LONG, MEDIUM = 'P01', 'P02'
BOARDS = (LONG, MEDIUM)


def inventory_deficit(state, goal):
    need = Counter()
    for tray, parts in goal['trays'].items():
        if tray not in goal.get('unusable_trays', ()):
            need.update({k: v for k, v in parts.items() if k not in goal.get('excluded_parts', ())})
    observed = Counter(o['part_id'] for o in state['objects'].values())
    return dict(need - observed)


def confirm_absence(observation, goal, observe):
    """One keyframe for a deficit; at most two if an uncertain Top-3 candidate exists."""
    first = inventory_deficit(observation.state, goal)
    checks = []
    confirmed_candidates = {}
    if not first:
        return observation, None
    for attempt in (1, 2):  # 임의 지정
        remaining = inventory_deficit(observation.state, goal)
        if not remaining:
            break
        for oid, labels in observation.candidates.items():
            confirmed_candidates.setdefault(oid, set()).update(labels)
        candidates = {oid: sorted(labels & remaining.keys()) for oid, labels in confirmed_candidates.items()
                      if labels & remaining.keys()}
        if attempt == 2 and not candidates:
            break
        checks.append(dict(before=remaining, candidates=candidates))
        observation = observe(f'confirm_missing_{attempt}', keyframe=True)
    return observation, dict(before=first, after=inventory_deficit(observation.state, goal), checks=checks)


def assign_boards(predictions, capacity):
    """Rank top-1 P01/P02 by the observed long span, shortest first.

    A full cohort uses BOM counts. For an incomplete cohort, enforce only upper
    bounds and preserve the detected per-type counts when feasible. Do not
    force a pair out of sparse detections or reclassify other top-1 categories.
    """
    if not all(capacity.get(k, 0) > 0 for k in BOARDS):
        return {}
    cohort = []
    for oid, pred in predictions.items():
        dims = pred.get('dimensions', ())
        if pred['part_id'] in BOARDS and len(dims) >= 2:
            span = max(dims[:2])
            if isfinite(span) and span > 0:
                cohort.append((span, oid, pred['part_id']))
    cohort.sort()
    n = len(cohort)
    if n < 2 or n > sum(capacity[k] for k in BOARDS):  # 임의 지정: sparse/overfull conservative fallback
        return {}
    splits = [i for i in range(max(0, n-capacity[LONG]), min(n, capacity[MEDIUM])+1)
              if i in (0, n) or cohort[i-1][0] < cohort[i][0]]
    raw_medium = sum(part == MEDIUM for _, _, part in cohort)
    preserve_count = min(max(raw_medium, n-capacity[LONG]), capacity[MEDIUM])
    if preserve_count not in splits:
        return {}

    def labels(i):
        return [MEDIUM]*i + [LONG]*(n-i)

    return {oid: k for (_, oid, pred), k in zip(cohort, labels(preserve_count)) if k != pred}
