import json
from copy import deepcopy

import pytest

from m2a.common import load_layout
from m2a.run.batch import RunLog, main, wilson
from m2a.run.dispatcher import Dispatcher, skill_calls
from m2a.run.episode import FAIL_CODES, run_episode
from m2a.run.perception import Observation
from m2a.scene.symbolic import symbolic


class FakeEnv:
    def __init__(self):
        self.layout = load_layout()

    def reset(self, spec):
        self.state = symbolic(spec, self.layout)
        self.gt = {o['oid']: {**o, 'lin_speed': 0} for o in spec['objects']}
        self.held = {}

    def get_gt_objects(self):
        return deepcopy(self.gt)


class FakePerception:
    def observe(self, env, layout, parts):
        return Observation(env.state, env.held)

    def refine_target(self, call, observation):
        return call.target


class FakeRunner:
    failure = None
    ghost = False

    def __init__(self, env, grasp_mode):
        self.env = env

    def run(self, skill, arm, oid, target):
        e = self.env
        reason = self.failure
        if not reason and skill == 'grasp_lift':
            e.held[arm] = oid
        elif not reason and skill in ('transport_place', 'put_aside'):
            e.held.pop(arm)
            if not self.ghost and skill == 'transport_place':
                e.state['objects'][oid].update(region=None, in_tray=target, on=None)
                e.gt[oid]['xyz'] = [*e.layout['trays'][target]['center'], .03]
            elif not self.ghost:
                e.state['objects'][oid].update(region=target, in_tray=None, on=None)
        return dict(ok=not reason, internal_done=not reason, reason_code=reason, t_ms=1)


def _run(config, **kw):
    return run_episode(10000, 'dev', 'L0', 'standard', config, env=FakeEnv(),
                       perception=FakePerception(), runner_factory=kw.pop('runner_factory', FakeRunner), **kw)


@pytest.mark.parametrize('action,target,oid', [
    (['pick', 'left', 'p', 'left_zone'], 'left_zone', 'p'),
    (['pick-from-top', 'left', 'upper', 'lower', 'left_zone'], 'left_zone', 'upper'),
    (['pick-from-tray', 'left', 'p', 'T1'], 'T1', 'p'),
])
def test_pick_mapping(action, target, oid):
    assert [(c.skill, c.arm, c.oid, c.target) for c in skill_calls(action)] == [
        ('reach_pregrasp', 'left', oid, target), ('grasp_lift', 'left', oid, target)]


def test_place_and_handover():
    runner = FakeRunner(FakeEnv(), 'P-gate')
    dispatch = Dispatcher(runner)
    call, = skill_calls(['handover', 'left', 'right', 'o1'])
    assert dispatch.execute(call, lambda: 12)['reason_code'] == 'HANDOVER_UNSUPPORTED'
    assert not dispatch.events
    assert skill_calls(['place', 'right', 'p', 'T1'])[0].skill == 'transport_place'
    assert skill_calls(['put-aside', 'right', 'p', 'center_zone'])[0].skill == 'put_aside'


def test_events_and_schema(tmp_path):
    ep = _run('B4')
    assert ep['judge']['success']
    assert ep['events'] and all(set(e) == {'oid', 'tray', 't_ms'} for e in ep['events'])
    book = RunLog(tmp_path/'run', {'split': 'dev'})
    book.append(ep)
    book.finish()
    rows = [json.loads(line) for line in (book.root/'episodes.jsonl').read_text().splitlines()]
    assert len(rows) == ep['num_skills'] == 3
    assert [r['skill_no'] for r in rows] == [1, 2, 3]
    assert all(r['fail_code'] is None or r['fail_code'] in FAIL_CODES for r in rows)
    assert all('skill_ms' in r and 't_ms' in r and 'episode_id' in r for r in rows)
    assert len((book.root/'plan.jsonl').read_text().splitlines()) == 1
    assert (book.root/'scene_graph.jsonl').stat().st_size > 0
    assert (book.root/'timing.jsonl').stat().st_size > 0
    assert json.loads((book.root/'result.json').read_text())['complete']
    assert wilson(12, 12)[1] == pytest.approx(1)


@pytest.mark.parametrize('config,limit,replans,termination', [
    ('B1', 3, 0, 'IK_FAIL'), ('B4', 0, 0, 'replan_limit'), ('B4', 3, 1, 'human_required'),
])
def test_failure_replanning(config, limit, replans, termination):
    class Failed(FakeRunner):
        failure = 'IK_FAIL'
    ep = _run(config, R=limit, runner_factory=Failed)
    assert ep['replans'] == replans
    assert ep['termination'] == termination
    assert not ep['events']
    assert not ep['internal_done']


def test_b4_bounded_goal_impossible(monkeypatch):
    from m2a.run import episode
    monkeypatch.setattr(episode.planner, 'plan', lambda *a, **kw: dict(ok=False, actions=[], missing={},
                                                                    plan_ms=0, reason='goal_unsat'))
    ep = _run('B4', R=3)
    assert ep['replans'] == 3 and ep['termination'] == 'replan_limit'
    assert all(r['trigger']['type'] == 'goal_impossible' for r in ep['logs']['plan'][1:])


def test_handover_replan_disables_action(monkeypatch):
    from m2a.run import episode
    flags = []
    real_plan = episode.planner.plan

    def plan(state, goal, layout, *, allow_handover):
        flags.append(allow_handover)
        if allow_handover:
            return dict(ok=True, actions=[['handover', 'left', 'right', next(iter(state['objects']))]],
                        missing={}, plan_ms=0, reason=None)
        return real_plan(state, goal, layout, allow_handover=allow_handover)

    monkeypatch.setattr(episode.planner, 'plan', plan)
    monkeypatch.setattr(episode.verifier, 'verify', lambda *a: {'ok': True})
    ep = _run('B4')
    assert flags == [True, False]
    assert ep['judge']['success']
    assert ep['logs']['episodes'][0]['reason_code'] == 'HANDOVER_UNSUPPORTED'


def test_false_completion_and_mismatch():
    class Ghost(FakeRunner):
        ghost = True
    one = _run('B1', runner_factory=Ghost)
    assert one['judge']['false_completion'] and one['fail_code'] == 'FALSE_COMPLETION'
    four = _run('B4', runner_factory=Ghost)
    assert not four['internal_done'] and four['termination'] == 'human_required'
    assert four['logs']['plan'][1]['trigger']['type'] == 'unexpected_effect'


def test_cli_rejects_sealed_seed(tmp_path):
    with pytest.raises(SystemExit):
        main(['--start', '90000', '--end', '90000', '--runs-dir', str(tmp_path)])
    assert not list(tmp_path.iterdir())


def test_sim_smoke():
    pytest.importorskip('mujoco')
    ep = run_episode(10000, 'dev', 'L0', 'standard', 'B1')
    assert ep['logs']['plan'][0]['plan']['ok']
    assert ep['logs']['plan'][0]['verification']['ok']
    assert ep['num_skills'] >= 1
    assert isinstance(ep['judge']['success'], bool)
    assert ep['episode_ms'] > 0


def test_o3_predicted_oid_never_sent_to_skill():
    class PoseEnv(FakeEnv):
        keyframes = 0

        def perception_pose(self):
            self.keyframes += 1
            return self.keyframes

        def restore_perception_pose(self, token):
            assert token == self.keyframes

    class Predict(FakePerception):
        pose_only = True

        def observe(self, env, layout, parts):
            objects = env.state['objects']
            return Observation({'objects': {f'p_{oid}': v for oid, v in objects.items()},
                                'reach': env.state['reach']},
                               {arm: f'p_{oid}' for arm, oid in env.held.items()},
                               {f'p_{oid}': {'xyz': env.gt[oid]['xyz'], 'yaw': 0, 'size': [.03]*3}
                                for oid in objects})

    class PoseRunner(FakeRunner):
        def run(self, skill, arm, oid, target, *, obj_pose_T):
            assert oid is None
            if skill in ('reach_pregrasp', 'grasp_lift'):
                real = next(o for o, value in self.env.gt.items() if value['xyz'] == obj_pose_T['xyz'])
            else:
                assert obj_pose_T is None
                real = self.env.held[arm]
            result = super().run(skill, arm, real, target)
            if skill == 'grasp_lift':
                result['grasped_oid'] = real
            return result

    env = PoseEnv()
    ep = run_episode(10000, 'dev', 'L0', 'standard', 'B1c', env=env,
                     perception=Predict(), runner_factory=PoseRunner)
    # initial + one pre-pick re-read (B1c) + one keyframe read per post-skill observation (round 3)
    posed = [r for r in ep['logs']['scene_graph'] if r['posed']]
    assert env.keyframes == len(posed) >= 2 and posed[0]['stage'] == 'initial'
    assert ep['judge']['success'] and ep['judge']['strict_success']
    assert ep['events'][0]['oid'] in env.gt
    grasp = ep['logs']['episodes'][1]
    assert grasp['oid'].startswith('p_') and grasp['grasped_oid'] == ep['events'][0]['oid']


@pytest.mark.parametrize('config, expected', [('B1', 0), ('B4', 1)])
def test_teleport_mismatch_replanning(config, expected):
    class Teleport:
        kind, after_skill = 'teleport', 1

        def apply(self, env, obs, call, upcoming):
            new_zone = 'left_zone' if obs.state['objects'][call.oid]['region'] == 'right_zone' else 'right_zone'
            env.state['objects'][call.oid].update(region=new_zone, in_tray=None, on=None)
            return {'applied': True, 'oid': call.oid, 'region': new_zone}

    ep = _run(config, perturb=Teleport())
    assert ep['perturbation']['applied']
    assert ep['replans'] == expected
    assert ep['logs']['episodes'][0]['mismatch']
    if expected:
        assert ep['logs']['plan'][1]['trigger']['type'] == 'unexpected_effect'
        assert ep['logs']['plan'][0]['plan']['actions'][0][1] != ep['logs']['plan'][1]['plan']['actions'][0][1]


def test_b4_prunes_failed_arm_location(monkeypatch):
    from m2a.run import episode
    seen = []
    real = episode.planner.plan

    def spy(state, goal, layout, **kw):
        seen.append({arm: list(v) for arm, v in state['reach'].items()})
        return real(state, goal, layout, **kw)
    monkeypatch.setattr(episode.planner, 'plan', spy)

    class FirstFails(FakeRunner):
        def run(self, skill, arm, oid, target):
            self.failure = 'IK_FAIL' if skill == 'reach_pregrasp' else None
            return super().run(skill, arm, oid, target)
    ep = _run('B4', R=3, runner_factory=FirstFails)
    first = ep['logs']['episodes'][0]
    assert len(seen) >= 2 and first['target'] in seen[0][first['arm']]
    assert first['target'] not in seen[1][first['arm']]  # failed (arm, location) pruned from reach
    ep = _run('B4', R=3, runner_factory=FirstFails, prune_reach=False)
    assert ep['replans'] <= 1  # without pruning the same plan repeats and the loop stops

def test_sim_noisy_o3_uses_pose_path_not_gt_oid():
    pytest.importorskip('mujoco')
    from m2a.run.perception import NoisyGTPerception
    perc = NoisyGTPerception(sigma_xy=0.003, sigma_yaw=0.03, seed=1)
    ep = run_episode(10000, 'dev', 'L0', 'standard', 'B1', perception=perc, grasp_mode='P-gate')
    assert ep['observation'] == 'NoisyGTPerception'
    rows = ep['logs']['episodes']
    assert rows and all(r['oid'].startswith('p') for r in rows)  # predicted oids, never GT oids
    assert any(r['grasped_oid'] for r in rows if r['skill'] == 'grasp_lift' and r['ok']) or not any(
        r['ok'] for r in rows if r['skill'] == 'grasp_lift')
    assert all(e['oid'].startswith('o') for e in ep['events'])  # events use judge-side GT ids