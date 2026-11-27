from math import pi

import pytest

from m2a.run.dispatcher import Dispatcher, SkillCall
from m2a.run.o3_config import load_gallery
from m2a.run.o3_policy import assign_boards, confirm_absence
from m2a.run.perception import Observation
from m2a.run.retry import retry_plan


def observed(*parts, candidates=None):
    return Observation({'objects': {str(i): {'part_id': p} for i, p in enumerate(parts)}},
                       candidates=candidates or {})


def test_uncertain_candidate_carries_to_second_keyframe_without_promoting_label():
    goal = {'trays': {'T1': {'P01': 1}}}
    first = observed('P02', candidates={'q0': ['P02', 'P01', 'P03']})
    frames = iter([observed(), observed('P01')])
    stages = []

    def read(stage, *, keyframe):
        stages.append((stage, keyframe))
        return next(frames)

    final, audit = confirm_absence(first, goal, read)
    assert audit['before'] == {'P01': 1} and audit['after'] == {}
    assert audit['checks'][1]['candidates'] == {'q0': ['P01']}
    assert final.state['objects']['0']['part_id'] == 'P01'
    assert stages == [('confirm_missing_1', True), ('confirm_missing_2', True)]


def test_missing_without_uncertain_candidate_gets_one_keyframe():
    calls = []
    obs = observed('P02')
    final, audit = confirm_absence(obs, {'trays': {'T1': {'P01': 1}}},
                                  lambda stage, **_: calls.append(stage) or obs)
    assert final is obs and audit['after'] == {'P01': 1}
    assert calls == ['confirm_missing_1']
    assert confirm_absence(obs, {'trays': {'T1': {'P02': 1}}}, lambda *args: None) == (obs, None)


def test_board_rank_respects_bom_and_keeps_raw_predictions():
    def pred(p, length):
        return {'part_id': p, 'dimensions': [.05, length, .02]}
    raw = {'long': pred('P02', .18), 'short': pred('P01', .13), 'short2': pred('P02', .14),
           'long2': pred('P02', .19), 'other': pred('P03', .17)}
    cap = {'P01': 2, 'P02': 2}
    assert assign_boards(raw, cap) == {'long': 'P01', 'long2': 'P01', 'short': 'P02'}
    assert assign_boards({k: raw[k] for k in ('long', 'short')}, cap) == {'long': 'P01', 'short': 'P02'}
    assert raw['long']['part_id'] == 'P02'
    assert assign_boards({'long': raw['long']}, cap) == {}


def test_unversioned_gallery_rejected_before_parsing(tmp_path):
    old = tmp_path / 'old.npz'
    old.write_bytes(b'old')
    with pytest.raises(ValueError, match='old or unknown gallery rejected'):
        load_gallery(old)


def test_retry_prefers_verified_alternate_arm_and_does_not_mutate_plan():
    plan = {'actions': [['pick', 'left', 'o0', 'center_zone'], ['place', 'left', 'o0', 'T1']]}
    prior = {'oid': 'o0', 'arm': 'left', 'fresh_pose': None, 'old_pose': None, 'attempt': 2,
             'approach_yaw': .25, 'supports_approach': True}
    alt, decision = retry_plan(plan, {}, {}, {}, prior, lambda *args: {'ok': True})
    assert all(a[1] == 'right' for a in alt['actions']) and decision['strategy'] == 'alternate_arm'
    assert all(a[1] == 'left' for a in plan['actions'])
    _, decision = retry_plan(plan, {}, {}, {}, prior, lambda *args: {'ok': False})
    assert decision['approach'] == pytest.approx((.25-pi/2) % (2*pi))
    prior.update(attempt=1)
    _, decision = retry_plan(plan, {}, {}, {}, prior, lambda *args: {'ok': True})
    assert decision['approach'] == pytest.approx(.25+pi)
    prior.update(supports_approach=False, old_pose={'xyz': [0, 0, 0]}, fresh_pose={'xyz': [.02, 0, 0]})
    _, decision = retry_plan(plan, {}, {}, {}, prior, lambda *args: {'ok': False})
    assert decision['strategy'] == 'fresh_position' and decision['approach'] is None


def test_dispatcher_approach_does_not_turn_o0_into_pose_mode():
    class Runner:
        def run(self, skill, arm, oid, target, *, approach=None):
            assert oid == 'o0' and approach == 1.0
            return {'ok': True}

    dispatcher = Dispatcher(Runner())
    assert dispatcher.supports_approach()
    assert dispatcher.execute(SkillCall('reach_pregrasp', 'left', 'o0', 'center_zone'),
                              lambda: 0, approach=1.0)['ok']
