"""Opt-in B4r retry policy. B4's original global reach-pruning remains unchanged."""
from math import hypot, pi

RETRY_LIMIT = 2  # 임의 지정, per object, excluding its initial attempt
RETRY_R = 6  # 임의 지정, default replans for L1/L2 B4r
MOVE_XY = .01  # 임의 지정, m
RETRY_CODES = ('GRASP_SLIP', 'IK_FAIL')
PICKS = ('pick', 'pick-from-tray', 'pick-from-top')


def retry_plan(plan, state, goal, layout, prior, verify):
    """Change only the failed object's first verified pick/place pair, if reachable."""
    actions = plan['actions']
    oid, failed_arm = prior['oid'], prior['arm']
    start = next((i for i, a in enumerate(actions) if a[0] in PICKS and a[2] == oid), None)
    if start is None:
        return plan, None
    end = next((i for i in range(start+1, len(actions))
                if actions[i][0] in ('place', 'put-aside') and actions[i][2] == oid), None)
    fresh = prior['fresh_pose']
    old = prior['old_pose']
    moved = bool(fresh and old and hypot(*(a-b for a, b in zip(fresh['xyz'][:2], old['xyz'][:2]))) >= MOVE_XY)
    other = 'right' if failed_arm == 'left' else 'left'
    strategy = 'fresh_position' if moved else 'fresh_pose'
    approach = None
    if actions[start][1] == other:
        strategy = 'alternate_arm'
    elif (prior['attempt'] == RETRY_LIMIT or not prior.get('supports_approach')) and end == start+1 and actions[end][1] == failed_arm:
        altered = list(actions)
        for i in (start, end):
            altered[i] = [actions[i][0], other, *actions[i][2:]]
        candidate = dict(plan, actions=altered)
        if verify(state, goal, candidate, layout)['ok']:
            plan, strategy = candidate, 'alternate_arm'
    if strategy == 'fresh_pose' and prior.get('supports_approach') and prior.get('approach_yaw') is not None:
        approach = (prior['approach_yaw'] + (pi if prior['attempt'] == 1 else -pi/2)) % (2*pi)
        strategy = 'opposite_approach'
    return plan, dict(oid=oid, strategy=strategy, moved=moved, attempt=prior['attempt'], approach=approach)
