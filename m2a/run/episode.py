"""Monitored kitting episode with serializable observations and skill logs."""
from collections import Counter, deque
from copy import deepcopy
from math import ceil
from time import perf_counter

from m2a.common import load_layout, load_parts
from m2a.plan import b0_script, parser_ko, planner, verifier
from m2a.scene.generator import generate
from m2a.scene.judge import judge

from .dispatcher import Dispatcher, skill_calls
from .o3_policy import confirm_absence
from .perception import OraclePerception
from .perturb import Perturbation
from .retry import RETRY_CODES, RETRY_LIMIT, retry_plan

SETTLE_S = 0.6  # 임의 지정: settle time after a failed skill before observing
CONFIGS = ('B0-script', 'B1', 'B1c', 'B4', 'B4r')
FAIL_CODES = frozenset(('PERCEPT_MISS', 'MISID', 'PLAN_VIOLATION', 'IK_FAIL', 'GRASP_SLIP',
                        'FALSE_COMPLETION', 'LANG_MISPARSE', 'TIMEOUT'))
# The contract list (CONTRACT §13) has no COLLISION. Fold rule (E round 3): COLLISION -> IK_FAIL (the skill could not
# produce a feasible collision-free motion); any other unknown skill code -> PLAN_VIOLATION. The raw skill code is
# kept separately as `reason_code` (episodes.jsonl) and `raw_reason_code` (episode result).
FOLD = {'COLLISION': 'IK_FAIL'}
PERCEPTION_POSE_S = 1.6  # 임의 지정: 0.6 s default left the arm mid-motion in view after a far pose (arm seen as objects)


def _secs_kw(env):
    import inspect
    try:
        return {'secs': PERCEPTION_POSE_S} if 'secs' in inspect.signature(env.perception_pose).parameters else {}
    except (TypeError, ValueError):
        return {}


def _delta(before, after, call, ok):
    def predicates(obs):
        return {oid: tuple(obj[k] for k in ('part_id', 'region', 'in_tray', 'on'))
                for oid, obj in obs.state['objects'].items()}
    expected, actual = predicates(before), predicates(after)
    held = dict(before.held)
    oid = call.oid
    if ok and oid in expected:
        part = expected[oid][0]
        if call.skill == 'grasp_lift':
            held[call.arm] = oid
        elif call.skill in ('transport_place', 'put_aside'):
            held.pop(call.arm, None)
            expected[oid] = ((part, call.target, None, None) if call.skill == 'put_aside'
                             else (part, None, call.target, None))
    for view, hands in ((expected, held), (actual, after.held)):
        for obj in hands.values():
            if obj in view:
                view[obj] = (view[obj][0], None, None, None)
    appeared, disappeared = sorted(actual.keys()-expected.keys()), sorted(expected.keys()-actual.keys())
    changed = {o: {'expected': expected[o], 'observed': actual[o]} for o in sorted(expected.keys() & actual.keys())
               if expected[o] != actual[o]}
    if appeared or disappeared or changed or held != after.held:
        return dict(appeared=appeared, disappeared=disappeared, changed=changed,
                    expected_held=held, observed_held=after.held)
    return None


def run_episode(seed, split, level, situation, config, instr=None, arm_mode='auto',
                grasp_mode='P-gate', R=3, perturb=None, *, perception=None, env=None,
                runner_factory=None, layout=None, prune_reach=True):
    if config not in CONFIGS or arm_mode not in ('auto', 'left', 'right'):
        raise ValueError('invalid config or arm_mode')
    if type(R) is not int or R < 0:
        raise ValueError('R must be a nonnegative integer')
    if isinstance(perturb, dict):
        perturb = Perturbation(**perturb)
    layout = load_layout() if layout is None else layout
    perception = OraclePerception() if perception is None else perception
    owns_env = env is None
    if owns_env:
        from m2a.sim.g1_manip_env import G1ManipEnv
        env = G1ManipEnv(layout)
    if runner_factory is None:
        from m2a.sim.skills import SkillRunner
        runner_factory = SkillRunner
    try:
        return _run(seed, split, level, situation, config, instr, arm_mode, grasp_mode, R,
                    perturb, perception, env, runner_factory, layout, prune_reach)
    finally:
        if owns_env:
            env.close()


def _run(seed, split, level, situation, config, instr, arm_mode, grasp_mode, R,
         perturb, perception, env, runner_factory, layout, prune_reach=True):
    start = perf_counter()

    def elapsed():
        return round((perf_counter()-start)*1000, 3)

    meta = dict(seed=seed, split=split, level=level, situation=situation, config=config,
                episode_id=f'{split}:{seed}:{level}:{situation}:{config}',
                observation='O0' if isinstance(perception, OraclePerception) else type(perception).__name__,
                grasp_mode=grasp_mode)
    logs = {key: [] for key in ('episodes', 'plan', 'scene_graph', 'timing')}

    def log(stream, **data):
        logs[stream].append({**meta, 't_ms': elapsed(), **data})

    spec = generate(seed, level, situation, split, layout=layout)
    parts = load_parts(spec['product'])
    env.reset(spec)
    dispatcher = Dispatcher(runner_factory(env, grasp_mode=grasp_mode))
    skill_no = 0
    last_fail = failure = missing = trigger = injected = raw_failure = None
    percept = dict(misid=0, misid_events=[], initial_missed_gt=None, initial_false_pos=None, initial_wrong_part=None,
                   percept_miss_skills=0, percept_miss_events=0, first_bad=None, absence_checks=[], initial_board_eval=[])
    pick_pose = {}  # B1c: pose captured by the re-observation right before each pick
    allow_handover = True
    blocked = set()  # (arm, location) pairs whose skill failed; B4 prunes them from the reach table
    stop, internal_done = 'completed', False

    obs = planned_obs = None
    retry_counts = Counter()
    approach_yaws = {}
    pending_retry = active_retry = None
    pose_only = getattr(perception, 'pose_only', False)

    def observe(stage, *, keyframe=False):
        began = elapsed()
        can_pose = (pose_only and keyframe and (obs is None or not obs.held)
                    and hasattr(env, 'perception_pose') and hasattr(env, 'restore_perception_pose'))
        token = None
        kw = _secs_kw(env) if can_pose else {}
        if can_pose:
            try:
                token = env.perception_pose(**kw)
            except RuntimeError:  # hands closed/occupied: observe in place instead (logged below)
                can_pose = False
        if can_pose:
            try:
                observation = deepcopy(perception.observe(env, layout, parts))
            finally:
                try:
                    env.restore_perception_pose(token, **kw)
                except RuntimeError as exc:  # no collision-free return path: arm stays parked; next skill moves it
                    log('timing', stage=f'perception_restore_failed:{stage}', skill_no=skill_no,
                        elapsed_ms=elapsed()-began, error=str(exc)[:120])
        else:
            observation = deepcopy(perception.observe(env, layout, parts))
        log('scene_graph', stage=stage, skill_no=skill_no, state=observation.state, held=observation.held,
            posed=bool(can_pose), eval=observation.meta or None)
        if stage == 'initial' and 'missed_gt' in observation.meta:
            percept.update(initial_missed_gt=observation.meta['missed_gt'], initial_false_pos=observation.meta['false_pos'],
                           initial_wrong_part=observation.meta['wrong_part'],
                           initial_board_eval=observation.meta.get('board_eval', []))
        log('timing', stage=f'perception:{stage}', skill_no=skill_no, elapsed_ms=elapsed()-began)
        return observation

    def step(action, call, upcoming, recovery=False):
        nonlocal obs, skill_no, injected, raw_failure
        skill_no += 1
        # B1c = closed-loop IK: re-perceive right before each pick (reach_pregrasp) and use that fresh pose. With O0
        # (GT perception, skills read current GT) this only adds observation calls, so it equals B1.
        refresh = config == 'B1c' and call.skill == 'reach_pregrasp'
        if refresh:
            obs = observe('pre_pick', keyframe=True)
        before = obs
        target = perception.refine_target(call, before) if config == 'B1c' else None
        pose_obs = before if refresh else planned_obs
        if refresh and pose_only:
            pick_pose[call.oid] = (before.poses.get(call.oid), before)
        if config == 'B1c' and call.skill == 'grasp_lift' and call.oid in pick_pose:
            pose, pose_obs = pick_pose[call.oid]
        else:
            pose = (pose_obs.poses.get(call.oid) if pose_only and pose_obs is not None
                    and call.skill in ('reach_pregrasp', 'grasp_lift') else None)
        approach = (active_retry['approach'] if active_retry and call.oid == active_retry['oid']
                    and (call.skill == 'reach_pregrasp' or (pose_only and call.skill == 'grasp_lift')) else None)
        result = dispatcher.execute(call, elapsed, target=target, pose_only=pose_only, obj_pose_T=pose, approach=approach)
        if call.skill == 'reach_pregrasp':
            approach_yaws[call.oid, call.arm] = result.get('approach_yaw',
                getattr(dispatcher.runner, 'events', {}).get('approach_yaw') if result['ok'] else approach)
        if hasattr(perception, 'note_skill'):
            perception.note_skill(call, result)
        misid = intended_gt = None
        if pose_only and call.skill == 'grasp_lift' and result['ok']:
            intended_gt = (pose_obs.meta.get('gt_of') or {}).get(call.oid) if pose_obs is not None else None
            misid = result.get('grasped_oid') != intended_gt
            if misid:
                percept['misid'] += 1
                percept['misid_events'].append(dict(skill_no=skill_no, oid=call.oid, intended_gt=intended_gt,
                                                    grasped_gt=result.get('grasped_oid')))
        if pose_only and result['reason_code'] == 'PERCEPT_MISS':
            percept['percept_miss_skills'] += 1
        if percept['first_bad'] is None and (misid or not result['ok']):
            percept['first_bad'] = 'MISID' if misid else 'skill:' + str(result['reason_code'])
        if not result['ok'] and hasattr(env, 'model') and hasattr(env, 'step'):
            env.step(ceil(SETTLE_S/env.model.opt.timestep))  # let a dropped/perched object settle before observing
        # Predictive perception: every post-skill read is a keyframe (arms out of the head view when both hands are
        # open and empty; otherwise observed in place). Round-3 diagnosis: in-place reads next to the hovering arm
        # produced spurious appeared/disappeared objects (PERCEPT_MISS) after reach_pregrasp.
        obs = observe('post_skill', keyframe=pose_only)
        if (not pose_only and call.skill == 'transport_place' and not result['ok']
                and obs.state['objects'].get(call.oid, {}).get('in_tray') == call.target
                and not any(ev['oid'] == call.oid and ev['tray'] == call.target for ev in dispatcher.events)):
            # Skill reported failure but the settled object is observed inside the target tray (e.g. dropped in).
            dispatcher.events.append(dict(oid=call.oid, tray=call.target, t_ms=elapsed()))
        if perturb and skill_no == perturb.after_skill:
            injected = {'kind': perturb.kind, 'after_skill': skill_no, **perturb.apply(env, obs, call, upcoming)}
            if injected['applied']:
                obs = observe('post_perturb')
        delta = _delta(before, obs, call, result['ok'])
        raw = result['reason_code']
        if not result['ok']:
            code = raw if raw in FAIL_CODES else FOLD.get(raw, 'PLAN_VIOLATION')
        elif delta:
            if delta['appeared'] or delta['disappeared']:
                code = 'PERCEPT_MISS'
            elif any(d['expected'][0] != d['observed'][0] for d in delta['changed'].values()):
                code = 'MISID'
            else:
                code = 'PLAN_VIOLATION'
        else:
            code = None
        if pose_only and code == 'PERCEPT_MISS':
            percept['percept_miss_events'] += 1
        log('episodes', skill_no=skill_no, plan_no=len(logs['plan']), action=list(action),
            skill=call.skill, arm=call.arm, oid=call.oid, target=call.target, ok=result['ok'],
            intended_gt=intended_gt, misid=misid,
            internal_done=result['internal_done'], fail_code=code, reason_code=raw, skill_ms=result['t_ms'],
            grasped_oid=result.get('grasped_oid') if pose_only else None,
            mismatch=delta, recovery=recovery,
            perturbation=injected if perturb and skill_no == perturb.after_skill else None)
        log('timing', stage='skill', skill_no=skill_no, elapsed_ms=result['t_ms'])
        if not result['ok']:
            raw_failure = raw
        return result, code, delta

    obs = observe('initial', keyframe=True)
    goal = deepcopy(spec['expected']['goal'] if instr is None else parser_ko.parse(instr, product=spec['product']))
    if goal.get('ok') is False:
        failure, stop = 'LANG_MISPARSE', goal['error']
        goal = None
    elif arm_mode != 'auto':
        goal['allowed_arms'] = [a for a in goal.get('allowed_arms', ('left', 'right')) if a == arm_mode]

    while goal is not None:
        if trigger and obs.held:
            # The planner only starts with empty hands. Use the public skill API.
            recovery_failed = False
            for arm, oid in list(obs.held.items()):
                # Recovery order (임의 지정): shared buffer first, then the arm's own side zone.
                for spot in ('center_zone', f'{arm}_zone'):
                    action = ('put-aside', arm, oid, spot)
                    result, code, _ = step(action, skill_calls(action)[0], (), recovery=True)
                    if result['ok'] or obs.held.get(arm) != oid:
                        break
                if not result['ok'] and obs.held.get(arm) == oid:
                    raw = result['reason_code']
                    failure = code or 'PLAN_VIOLATION'
                    stop = 'human_required' if (raw or failure, oid) == last_fail else 'recovery_failed'
                    recovery_failed = True
                    break
            if recovery_failed:
                break
        if getattr(perception, 'reobserve_missing', False):
            obs, check = confirm_absence(obs, goal, observe)
            if check is not None:
                percept['absence_checks'].append(check)
        if config == 'B0-script':
            planned = b0_script.plan(obs.state, goal, layout, product=spec['product'])
            if (instr is not None or arm_mode != 'auto') and any(
                a[1] not in goal['allowed_arms'] or (a[0] == 'place' and a[3] in goal['unusable_trays'])
                for a in planned['actions']):
                planned.update(ok=False, reason='instruction_constraint')
        else:
            for arm_, loc_ in blocked:
                reach_ = obs.state.get('reach', {})
                if loc_ in reach_.get(arm_, ()):
                    reach_[arm_] = [x for x in reach_[arm_] if x != loc_]
            planned = planner.plan(obs.state, goal, layout, allow_handover=allow_handover)
        active_retry = None
        if pending_retry and planned['ok']:
            pending_retry['fresh_pose'] = obs.poses.get(pending_retry['oid'])
            planned, active_retry = retry_plan(planned, obs.state, goal, layout, pending_retry, verifier.verify)
        planned_obs = obs
        audit = (verifier.verify(obs.state, goal, planned, layout)
                 if config != 'B0-script' and planned['ok'] else None)
        viable = planned['ok'] and (audit is None or audit['ok'])
        log('plan', plan_no=len(logs['plan'])+1, is_replan=trigger is not None, trigger=trigger,
            allow_handover=allow_handover, plan=planned, verification=audit, retry=active_retry,
            fail_code=None if viable else 'PLAN_VIOLATION')
        log('timing', stage='plan', plan_no=len(logs['plan']), elapsed_ms=planned['plan_ms'])
        missing = planned['missing'] if viable or missing is None else missing
        if not viable:
            failure, stop = failure or 'PLAN_VIOLATION', planned['reason'] or 'verification_failed'
            affected = stop.split(':', 1)[1] if stop.startswith(('unlocated:', 'unreachable:')) else None
            signature = (failure, affected)
            trigger = dict(type='goal_impossible', oid=affected, reason=stop, fail_code=failure)
        else:
            queue = deque((action, call) for action in planned['actions'] for call in skill_calls(action))
            trigger = None
            while queue:
                action, call = queue.popleft()
                result, code, delta = step(action, call, [item[1] for item in queue])
                if code is None or (result['ok'] and config not in ('B4', 'B4r')):
                    continue  # B1/B1c observe mismatches but do not replace the plan.
                failure = code
                raw = result['reason_code']
                if raw == 'HANDOVER_UNSUPPORTED':
                    allow_handover = False
                if not result['ok']:
                    kind = 'skill_failed'
                elif delta['appeared'] or delta['disappeared']:
                    kind = 'object_appearance_change'
                else:
                    kind = 'unexpected_effect'
                changed = sorted(set(delta['changed']) | set(delta['appeared']) | set(delta['disappeared'])) if delta else []
                affected = call.oid if not result['ok'] or not changed else changed[0]
                signature = (raw or code, affected)
                if prune_reach and config == 'B4' and not result['ok'] and call.target is not None and (
                        raw in ('IK_FAIL', 'COLLISION') or (raw == 'GRASP_SLIP' and call.skill in ('reach_pregrasp', 'grasp_lift'))):
                    blocked.add((call.arm, call.target))
                trigger = dict(type=kind, oid=affected, skill_no=skill_no, fail_code=code, reason_code=raw)
                stop = raw or kind
                break
            if trigger is None:
                internal_done = True
                failure, stop = None, 'completed'
                break
        if config not in ('B4', 'B4r'):
            break
        pending_retry = None
        retryable = (config == 'B4r' and trigger['type'] == 'skill_failed' and
                     trigger.get('reason_code') in RETRY_CODES and trigger['oid'] is not None)
        if retryable:
            oid = trigger['oid']
            if retry_counts[oid] >= RETRY_LIMIT:
                stop = 'human_required'
                break
            retry_counts[oid] += 1
            pending_retry = dict(oid=oid, arm=call.arm, attempt=retry_counts[oid],
                                 old_pose=planned_obs.poses.get(oid),
                                 supports_approach=dispatcher.supports_approach(),
                                 approach_yaw=approach_yaws.get((oid, call.arm)))
        if not retryable and signature == last_fail and signature[1] is not None:
            stop = 'human_required'
            break
        last_fail = signature
        if len(logs['plan'])-1 >= R:
            stop = 'replan_limit'
            break
        obs = observe('before_replan', keyframe=True)

    gt = env.get_gt_objects()
    judged = (judge(gt, goal, layout, reported_missing=missing, internal_done=internal_done,
                    events=dispatcher.events) if goal is not None else
              dict(success=False, strict_success=False, avg_progress=0.0, false_completion=False,
                   per_tray={}, violations=[{'code': stop}], strict_violations=[]))
    if judged['false_completion']:
        failure = 'FALSE_COMPLETION'
    elif judged['success']:
        failure = None  # a tolerated mid-episode failure (e.g. replan fixed it) is not an episode failure
    elif failure is None:
        failure = 'PLAN_VIOLATION'
    if failure and not judged['success'] and percept['first_bad'] == 'MISID' and failure not in ('FALSE_COMPLETION', 'LANG_MISPARSE'):
        failure = 'MISID'  # the first deviation was a wrong-object grasp (eval: GT-grasped != intended)
    duration = elapsed()
    if perturb and injected is None:
        injected = dict(kind=perturb.kind, after_skill=perturb.after_skill, applied=False, reason='skill_not_reached')
    log('timing', stage='episode', elapsed_ms=duration)
    return {**meta, 'goal': goal, 'judge': judged, 'events': dispatcher.events, 'fail_code': failure,
            'raw_reason_code': raw_failure, 'percept': percept,
            'retry_counts': dict(retry_counts), 'reported_missing': missing, 'termination': stop, 'internal_done': internal_done, 'episode_ms': duration,
            'replans': sum(r['is_replan'] for r in logs['plan']), 'num_skills': skill_no,
            'perturbation': injected, 'logs': logs}
