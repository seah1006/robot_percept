"""E round 3: stable-id tracking over predictions, B1c re-perception count, COLLISION fold, MISID record."""
import random

import pytest

from m2a.run.episode import run_episode
from m2a.run.o3_perception import IdTracker
from m2a.run.perception import Observation
from test_e_run import FakeEnv, FakePerception, FakeRunner


def pred(part, x, y):
    return dict(part_id=part, xyz=[x, y, .01], yaw=0.)


def test_ids_survive_shuffled_local_ids():
    t = IdTracker()
    scene = [pred('P01', .1, .1), pred('P02', .2, .1), pred('P01', .3, .2)]
    first = t.update({f'p{i}': v for i, v in enumerate(scene)})
    order = [2, 0, 1]
    moved = [pred(scene[i]['part_id'], scene[i]['xyz'][0]+.004, scene[i]['xyz'][1]-.003) for i in order]
    second = t.update({f'p{j}': v for j, v in enumerate(moved)})
    assert {second[f'p{j}'] for j in range(3)} == set(first.values())
    assert [second[f'p{j}'] for j in range(3)] == [first[f'p{i}'] for i in order]  # same physical object, same id


def test_same_part_swap_within_threshold_uses_distance():
    t = IdTracker(link_xy=.03)
    a = t.update({'p0': pred('P01', .10, .10), 'p1': pred('P01', .20, .10)})
    b = t.update({'p0': pred('P01', .201, .10), 'p1': pred('P01', .099, .10)})
    assert b['p0'] == a['p1'] and b['p1'] == a['p0']


def test_placed_object_relinks_after_plan_move_and_flip_is_new_id():
    t = IdTracker()
    a = t.update({'p0': pred('P01', .1, .1), 'p1': pred('P02', .2, .1)})
    sid = a['p0']
    t.update({'p1': pred('P02', .2, .1)}, frozen={sid})  # held: not predicted, id kept frozen
    t.note_moved(sid)
    b = t.update({'p0': pred('P02', .2, .1), 'p1': pred('P01', .55, -.2)})  # P01 now far away (tray)
    assert b['p1'] == sid and b['p0'] == a['p1']
    c = t.update({'p0': pred('P03', .2, .1), 'p1': pred('P01', .55, -.2)})  # classification flip: not linked
    assert c['p0'] not in a.values() and c['p1'] == sid
    assert t.tracks[a['p1']]['missing'] == 1


def test_disappeared_object_is_not_resurrected_with_new_id_later():
    t = IdTracker(max_missing=1)
    a = t.update({'p0': pred('P01', .1, .1)})
    t.update({})
    again = t.update({'p0': pred('P01', .1, .1)})
    assert again['p0'] == a['p0']
    t.update({}); t.update({}); t.update({})
    far = t.update({'p0': pred('P01', .4, .1)})
    assert far['p0'] != a['p0']  # missed longer than max_missing: forgotten


class CountingPredict(FakePerception):
    pose_only = True

    def __init__(self, shuffle=True):
        self.calls, self.shuffle = 0, shuffle

    def observe(self, env, layout, parts):
        self.calls += 1
        names = list(env.state['objects'])
        if self.shuffle:
            random.Random(self.calls).shuffle(names)
        ids = {oid: f'q{i}' for i, oid in enumerate(names)}
        return Observation({'objects': {ids[o]: v for o, v in env.state['objects'].items()}, 'reach': env.state['reach']},
                           {a: ids[o] for a, o in env.held.items()},
                           {ids[o]: dict(xyz=env.gt[o]['xyz'], yaw=0, size=[.03]*3) for o in names},
                           dict(gt_of={ids[o]: o for o in names}))


class PoseRunner(FakeRunner):
    wrong = False

    def run(self, skill, arm, oid, target, *, obj_pose_T):
        if skill in ('reach_pregrasp', 'grasp_lift'):
            real = next(o for o, v in self.env.gt.items() if v['xyz'] == obj_pose_T['xyz'])
        else:
            real = self.env.held[arm]
        result = super().run(skill, arm, real, target)
        if skill == 'grasp_lift':
            result['grasped_oid'] = 'ghost' if self.wrong else real
        return result


def _stage_counts(ep):
    counts = {}
    for r in ep['logs']['scene_graph']:
        counts[r['stage']] = counts.get(r['stage'], 0) + 1
    return counts


def test_b1c_reperceives_once_per_pick_and_b1_does_not():
    ep1 = run_episode(10000, 'dev', 'L0', 'standard', 'B1', env=FakeEnv(), perception=CountingPredict(),
                      runner_factory=PoseRunner)
    epc = run_episode(10000, 'dev', 'L0', 'standard', 'B1c', env=FakeEnv(), perception=CountingPredict(),
                      runner_factory=PoseRunner)
    picks = sum(r['skill'] == 'reach_pregrasp' for r in epc['logs']['episodes'])
    assert picks >= 1
    assert _stage_counts(epc).get('pre_pick') == picks
    assert 'pre_pick' not in _stage_counts(ep1)
    assert ep1['judge']['success'] and epc['judge']['success']


def test_b1c_equals_b1_with_oracle_perception():
    runs = [run_episode(10000, 'dev', 'L0', 'standard', c, env=FakeEnv(), perception=FakePerception(),
                        runner_factory=FakeRunner) for c in ('B1', 'B1c')]
    assert [r['judge']['success'] for r in runs] == [True, True]
    assert [(e['skill'], e['oid'], e['ok']) for e in runs[0]['logs']['episodes']] == \
           [(e['skill'], e['oid'], e['ok']) for e in runs[1]['logs']['episodes']]


def test_misid_is_recorded_when_grasped_gt_differs_from_intended():
    class Wrong(PoseRunner):
        wrong = True
    ep = run_episode(10000, 'dev', 'L0', 'standard', 'B1', env=FakeEnv(), perception=CountingPredict(shuffle=False),
                     runner_factory=Wrong)
    assert ep['percept']['misid'] >= 1
    event = ep['percept']['misid_events'][0]
    assert event['grasped_gt'] == 'ghost' and event['intended_gt'] is not None
    assert any(e['misid'] for e in ep['logs']['episodes'] if e['skill'] == 'grasp_lift')
    assert ep['percept']['first_bad'] == 'MISID'


@pytest.mark.parametrize('raw, folded', [('COLLISION', 'IK_FAIL'), ('IK_FAIL', 'IK_FAIL'), ('GRASP_SLIP', 'GRASP_SLIP'),
                                         ('WEIRD', 'PLAN_VIOLATION')])
def test_collision_fold_keeps_raw_reason(raw, folded):
    class Fail(FakeRunner):
        failure = raw
    ep = run_episode(10000, 'dev', 'L0', 'standard', 'B1', env=FakeEnv(), perception=FakePerception(), runner_factory=Fail)
    first = ep['logs']['episodes'][0]
    assert first['reason_code'] == raw and first['fail_code'] == folded
    assert ep['raw_reason_code'] == raw and ep['fail_code'] == folded


def test_sim_real_o3_depth_stable_ids_and_pose_only():
    pytest.importorskip('mujoco')
    from m2a.run.o3_perception import O3Perception
    ep = run_episode(10000, 'dev', 'L0', 'standard', 'B1c', perception=O3Perception())
    assert ep['observation'] == 'O3Perception'
    states = [r['state']['objects'] for r in ep['logs']['scene_graph']]
    assert all(oid.startswith(('q', 'held_')) for objs in states for oid in objs)  # stable ids, never GT o* / local p*
    assert all(e['oid'].startswith('q') for e in ep['logs']['episodes'])
    assert ep['logs']['scene_graph'][0]['eval']['gt_of']  # evaluation-only mapping recorded
    assert 'pre_pick' in {r['stage'] for r in ep['logs']['scene_graph']}
    assert set(ep['percept']) >= {'misid', 'initial_missed_gt', 'first_bad'}
