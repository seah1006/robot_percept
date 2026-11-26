"""Fast checks of the G1 contact scene, control, and attachment contract."""
import mujoco
import numpy as np
import pytest

from sim.g1_grasp_env import G1GraspEnv, HAND, OBJECTS, TABLE_TOP, pregrasp_pose


@pytest.mark.parametrize('obj', OBJECTS)
def test_seeded_settling_and_uncompensated_object(obj):
    env = G1GraspEnv(obj)
    try:
        a = env.reset(17)
        assert env.reset(23)['obj_pos'][:2].tolist() != a['obj_pos'][:2].tolist()
        b = env.reset(17)
        np.testing.assert_array_equal(a['obj_pos'], b['obj_pos'])
        np.testing.assert_array_equal(a['obj_quat'], b['obj_quat'])
        np.testing.assert_array_equal(b['obj_pos'], env.object_rest_pose()[0])
        assert b['t'] == 0.
        m, d = env.model, env.data
        v = int(m.joint('grasp_object_joint').dofadr[0])
        assert m.body_mass[m.body('grasp_object').id] == pytest.approx(OBJECTS[obj][2])
        s = env.step(1.)
        assert s['finite'] and s['obj_table_contact']
        assert s['obj_pos'][2] == pytest.approx(TABLE_TOP + OBJECTS[obj][3], abs=.001)
        assert s['obj_pos'][2] == pytest.approx(b['obj_pos'][2], abs=.0001)
        assert s['max_penetration'] == 0.0
        assert np.max(np.abs(d.qfrc_applied[v:v + 6])) == 0.
        assert abs(d.qfrc_bias[v + 2]) > .1
    finally:
        env.close()


def test_collision_masks_exclude_body_and_self_contact():
    env = G1GraspEnv()
    try:
        m, d = env.model, env.data
        assert not (m.opt.disableflags & mujoco.mjtDisableBit.mjDSBL_CONTACT)
        assert sum(m.jnt_type == mujoco.mjtJoint.mjJNT_FREE) == 1
        table = m.geom('grasp_table').id
        active = np.flatnonzero(m.geom_contype)
        for g in active:
            name = m.body(m.geom_bodyid[g]).name
            assert g == table or name == 'grasp_object' or '_hand_' in name or '_wrist_yaw_' in name
        hands = np.flatnonzero(m.geom_contype == 1)
        assert len(hands) == 16
        assert np.all((m.geom_contype[hands] & m.geom_conaffinity[hands]) == 0)
        assert all(not ((m.geom_contype[g] | m.geom_conaffinity[g]) == 0 and table in c.geom)
                   for c in d.contact[:d.ncon] for g in c.geom)
    finally:
        env.close()


def test_hand_synergy_and_no_attachment_without_contact():
    env = G1GraspEnv(mode='gate')
    try:
        m, d = env.model, env.data
        ids = [m.joint(f'{side}_hand_{j}_joint').id for side in ('left', 'right') for j in HAND]
        qadr = m.jnt_qposadr[ids]
        lo, hi = m.jnt_range[ids].T
        opened = d.qpos[qadr].copy()
        for side in ('left', 'right'):
            env.set_hand(1, side)
        s = env.step(.9)
        shut = d.qpos[qadr].copy()
        assert s['finite'] and not s['weld_active'] and not s['finger_contacts']
        assert np.all(np.abs(shut - opened) > .02)
        assert np.all(shut >= lo - .004) and np.all(shut <= hi + .004)
        for side in ('right', 'left'):
            env.set_hand(0, side)
        env.step(.9)
        np.testing.assert_allclose(d.qpos[qadr], opened, atol=.003)
    finally:
        env.close()


def test_top_approach_and_unreachable_rejected():
    env = G1GraspEnv(seed=0)
    try:
        p, q = env.object_rest_pose()
        yaw = 2 * np.arctan2(q[3], q[0])
        target, quat = pregrasp_pose(p, yaw, .16)
        clearance = target.copy()
        clearance[0] = .13
        assert env.set_arm_target(clearance, quat)
        assert not env.set_arm_target([9., 9., 9.], quat)
        np.testing.assert_allclose(env.step(2.)['palm_pos'], clearance, atol=.006)
        assert env.set_arm_target(target, quat)
        np.testing.assert_allclose(env.step(2.)['palm_pos'], target, atol=.014)
    finally:
        env.close()


def test_oracle_weld_preserves_pose_and_open_releases():
    env = G1GraspEnv(mode='oracle')
    try:
        env.set_hand(1.)
        s = env.step(0.)
        assert s['weld_active']
        mujoco.mj_forward(env.model, env.data)
        eq_rows = env.data.efc_type == mujoco.mjtConstraint.mjCNSTR_EQUALITY
        assert np.count_nonzero(eq_rows) == 6
        np.testing.assert_allclose(env.data.efc_pos[eq_rows], 0., atol=1e-10)
        env.set_hand(.29)
        assert not env.state()['weld_active']
        env.set_hand(1.)
        assert env.step(0.)['weld_active']
        assert not env.reset(0)['weld_active']
    finally:
        env.close()
