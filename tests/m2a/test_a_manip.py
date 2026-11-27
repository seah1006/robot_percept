import math
import mujoco
import numpy as np
import pytest

from m2a.common import load_layout
from m2a.sim.g1_manip_env import FIXTURE_BIT, HAND_BIT, OBJECT_BIT, G1ManipEnv
from m2a.sim.gate_grasp import fixture
from m2a.sim.skills import SkillRunner


@pytest.fixture(scope='module')
def env():
    e = G1ManipEnv()
    e.reset(fixture([dict(oid='o0', part_id='P01', xyz=[-.12,.34,.0125], yaw=.5,
                          region='left_zone', in_tray=None, on=None)]))
    yield e
    e.close()


def test_model(env):
    m = env.model
    assert not (m.opt.disableflags & int(mujoco.mjtDisableBit.mjDSBL_CONTACT))
    assert m.njnt == 29  # 14 arm + 14 finger + 1 free object; waist/legs rigid
    assert set(m.camera(i).name for i in range(m.ncam)) >= {'head', 'front', 'wrist_l', 'wrist_r'}
    for tray in ('T1', 'T2', 'T3'):
        assert all(m.geom(tray + tail).id >= 0 for tail in ('_floor','_x1','_x-1','_y1','_y-1'))


def test_contact_masks(env):
    m = env.model
    def accepts(a, b):
        return (m.geom_contype[a] & m.geom_conaffinity[b]) or (m.geom_contype[b] & m.geom_conaffinity[a])
    hand, other = (next(iter(env.arm_geom[a])) for a in ('left', 'right'))
    obj = env.object_geoms['o0']; table = m.geom('m2a_table').id; floor = m.geom('floor').id
    assert [m.geom_contype[x] for x in (hand,obj,table,floor)] == [HAND_BIT,OBJECT_BIT,FIXTURE_BIT,0]
    assert accepts(hand,obj) and accepts(hand,table) and accepts(obj,table)
    assert not accepts(hand,other) and not accepts(obj,floor)
    assert all(m.geom_contype[i] == 0 for i in range(m.ngeom)
               if m.body(m.geom_bodyid[i]).name.startswith(('torso','pelvis')))


def test_gt_and_real_grip_pose(env):
    gt = env.get_gt_objects()['o0']
    assert set(gt) == {'part_id','xyz','yaw','lin_speed'}
    np.testing.assert_allclose(gt['xyz'], [-.12,.34,.0125], atol=1e-8)
    assert gt['yaw'] == pytest.approx(.5) and gt['lin_speed'] == pytest.approx(0.)
    xyz = [-.12,.34,.08]
    q, res = env.solve_ik('left', xyz, env.topdown('left'))
    assert res['ok']
    ik = env.ik['left']; d = ik.fk(env.data.qpos, q)
    np.testing.assert_allclose(env.to_table(d.site('left_grip').xpos), xyz, atol=.0025)


def test_weld_requires_contact_and_release(env):
    assert not env.attach('left','o0')
    assert not np.any(env.data.eq_active)
    assert env.attach('left','o0',oracle=True)
    assert np.any(env.data.eq_active)
    env.release('left')
    assert not np.any(env.data.eq_active)


def test_skill_shape(env):
    r = SkillRunner(env).run('transport_place','left','o0','T1')
    assert set(r) == {'ok','reason_code','internal_done','t_ms'}
    assert (r['ok'], r['reason_code'], r['internal_done']) == (False,'GRASP_SLIP',False)
    assert type(r['t_ms']) is int and r['t_ms'] >= 0


def test_p04_uses_index_before_thumb_and_keeps_middle_open():
    from m2a.sim.skills import grasp_profile, hand_command
    p04 = grasp_profile('P04'); generic = grasp_profile('P01')
    assert p04['name'] == 'index_thumb_pinch'
    assert generic['name'] == grasp_profile('P06')['name'] == 'three_finger'
    early = hand_command(p04, .4, 1)
    np.testing.assert_allclose(early[:3], p04['open'][:3])
    assert early[3] < 0 and early[4] < 0
    np.testing.assert_allclose(hand_command(p04, 1, 1)[5:], 0)
    np.testing.assert_allclose(hand_command(p04, .8, -1), -hand_command(p04, .8, 1))


def test_camera_parameters(env):
    from m2a.sim.g1_manip_env import CAMERAS
    for camera, (width, height) in CAMERAS.items():
        K = env.camera_K(camera)
        assert K.shape == (3,3) and K[0,0] == K[1,1] > 0
        np.testing.assert_allclose(K[:2,2], [(width-1)/2,(height-1)/2])
        T = env.T_world_cam(camera)
        np.testing.assert_allclose(T, env.T_world_table @ env.T_table_cam(camera), atol=1e-9)
        np.testing.assert_allclose(T[:3,:3] @ T[:3,:3].T, np.eye(3), atol=1e-8)
        assert np.linalg.det(T[:3,:3]) == pytest.approx(1.)


def test_general_sampling_is_stratified_and_deterministic(env):
    from collections import Counter
    from m2a.sim.gate_grasp import PART_IDS, general_candidates
    for part_id in PART_IDS:
        samples = list(general_candidates(part_id, env.parts[part_id], env.layout))
        assert samples == list(general_candidates(part_id, env.parts[part_id], env.layout))
        assert Counter(spec['objects'][0]['region'] for _,spec,_ in samples) == {
            'left_zone':7, 'right_zone':7, 'center_zone':6,
        }
        for arm, spec, _ in samples:
            obj = spec['objects'][0]; x, y, _ = obj['xyz']
            x0,x1,y0,y1 = env.layout['regions'][obj['region']]
            assert x0 <= x <= x1 and y0 <= y <= y1
            assert arm in ('left','right')
