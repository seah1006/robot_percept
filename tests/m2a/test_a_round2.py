import numpy as np
import pytest

from m2a.common import load_parts
from m2a.sim.g1_manip_env import G1ManipEnv, WELD_CONTACT_GRACE_S
from m2a.sim.gate_grasp import candidates, fixture
from m2a.sim.skills import MODES, SkillRunner


def test_ee_pose_and_increment(monkeypatch):
    e = G1ManipEnv(); e.reset(fixture())
    pos, quat = e.ee_pose('left')
    assert pos.shape == (3,) and quat.shape == (4,)
    assert np.isclose(np.linalg.norm(quat), 1)
    assert e.arm_q('left').shape == (7,)
    old_time = e.data.time
    out = e.apply_ee_delta('left', [.002, 0, 0], [.005, 0, 0], .4)
    assert out['ik_ok'] and out['ok'] and out['attached_oid'] is None
    assert e.data.time - old_time == pytest.approx(.1)
    with pytest.raises(ValueError):
        e.apply_ee_delta('left', [np.nan,0,0], [0,0,0], 0)
    before = e.data.ctrl.copy(); token = e.perception_pose(.1)
    assert not np.allclose(e.data.ctrl, before)
    e.restore_perception_pose(token, .1)
    assert np.allclose(e.data.ctrl, before)


def test_mode_names():
    assert set(MODES) == {'P-phys', 'P-gate', 'P-gate-strict', 'P-oracle'}
    e = G1ManipEnv()
    assert e.gate_mode == 'P-gate'
    with pytest.raises(ValueError):
        e.set_gate_mode('P-phys')
    with pytest.raises(ValueError):
        SkillRunner(e, 'P-unknown')


def test_gate_default_no_thumb_and_zero_contact_release(monkeypatch):
    e = G1ManipEnv(); arm, spec = next(candidates('P06',load_parts()['parts']['P06'])); e.reset(spec)
    e.closed[arm] = True
    fingers = {'index'}
    monkeypatch.setattr(e, 'contact_fingers', lambda *_: fingers.copy())
    monkeypatch.setattr(e, 'in_palm', lambda *_: True)
    assert not e.attach(arm, 'o0')          # one fingertip is not enough
    fingers.add('middle')
    assert e.attach(arm, 'o0')              # thumb not required
    assert e.weld_info[arm]['thumb_opposed'] is False and e.weld_info[arm]['gate_mode'] == 'P-gate'
    n = round(WELD_CONTACT_GRACE_S/e.model.opt.timestep)
    fingers.clear(); fingers.add('index'); e.step(3*n)
    assert e._held_oid(arm) == 'o0'         # one contact keeps the weld
    fingers.clear(); e.step(n-1)
    assert e._held_oid(arm) == 'o0'
    fingers.add('thumb'); e.step(); fingers.clear(); e.step(n-1)
    assert e._held_oid(arm) == 'o0'         # loss must be continuous
    e.step()
    assert e._held_oid(arm) is None
    assert e.slip_events[-1]['reason_code'] == 'GRASP_SLIP'


def test_contact_watch_tracks_minimum(monkeypatch):
    e = G1ManipEnv(); arm, spec = next(candidates('P06',load_parts()['parts']['P06'])); e.reset(spec)
    fingers = {'index', 'middle', 'thumb'}
    monkeypatch.setattr(e, 'contact_fingers', lambda *_: fingers.copy())
    e.watch_contacts(arm, 'o0'); e.step(2); fingers.discard('thumb'); e.step(2); fingers.add('thumb'); e.step(2)
    assert e.unwatch_contacts(arm) == 2 and e.unwatch_contacts(arm) is None


def test_gate_thumb_and_contiguous_release(monkeypatch):
    e = G1ManipEnv(); e.set_gate_mode('P-gate-strict')
    arm, spec = next(candidates('P06',load_parts()['parts']['P06'])); e.reset(spec)
    e.closed[arm] = True
    fingers = {'index', 'middle'}
    monkeypatch.setattr(e, 'contact_fingers', lambda *_: fingers.copy())
    monkeypatch.setattr(e, 'in_palm', lambda *_: True)
    assert not e.attach(arm, 'o0')
    fingers.add('thumb')
    assert e.attach(arm, 'o0')
    n = round(WELD_CONTACT_GRACE_S/e.model.opt.timestep)
    fingers.clear(); fingers.add('index'); e.step(n-1)
    assert e._held_oid(arm) == 'o0'
    fingers.add('middle'); e.step(); fingers.remove('middle'); e.step(n-1)
    assert e._held_oid(arm) == 'o0'
    e.step()
    assert e._held_oid(arm) is None
    assert e.slip_events[-1]['reason_code'] == 'GRASP_SLIP'


def test_predicted_pose_selects_contacted_oid():
    e = G1ManipEnv(); parts = load_parts()['parts']; arm, spec = next(candidates('P06',parts['P06'])); e.reset(spec)
    obj = spec['objects'][0]
    runner = SkillRunner(e, 'P-gate')
    pose = dict(xyz=obj['xyz'], yaw=obj['yaw'], size=parts['P06']['size'], part_id='P06')
    result = runner.run('grasp_lift',arm,'not_a_gt_oid',obj_pose_T=pose)
    assert result['ok'] and result['grasped_oid'] == 'o0'
    assert isinstance(runner.events['thumb_opposed'], bool)
    assert isinstance(runner.events['min_contacts_during_lift'], int)


def test_strict_runner_sets_env_rule():
    e = G1ManipEnv(); parts = load_parts()['parts']; arm, spec = next(candidates('P06',parts['P06'])); e.reset(spec)
    runner = SkillRunner(e, 'P-gate-strict')
    result = runner.run('grasp_lift', arm, 'o0')
    assert e.gate_mode == 'P-gate-strict'
    assert set(result) == {'ok', 'reason_code', 'internal_done', 't_ms'}
    if result['ok']:
        assert runner.events['thumb_opposed'] is True
