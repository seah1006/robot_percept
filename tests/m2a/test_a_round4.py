import copy
import itertools
import math

import numpy as np
import pytest

from m2a.common import load_layout, load_parts
from m2a.sim.g1_manip_env import G1ManipEnv
from m2a.sim.gate_grasp import candidates, fixture
from m2a.sim.skill_bench import all_trials, judge_place, make_trial
from m2a.sim.skills import SkillRunner


def _corners(layout):
    for x, X, y, Y in layout['regions'].values():
        for a, b in itertools.product((x, X), (y, Y)):
            yield a, b, 0.
            yield a, b, .06
    for tr in layout['trays'].values():
        (cx, cy), (a, b) = tr['center'], np.asarray(tr['inner']) / 2 + tr['wall_thickness']
        for sx, sy in itertools.product((-1, 1), (-1, 1)):
            yield cx + sx*a, cy + sy*b, tr['floor_z'] + tr['wall_h']


def test_head_camera_sees_all_zones_and_trays():
    env = G1ManipEnv(); env.reset(fixture())
    try:
        K = env.camera_K('head'); T = np.linalg.inv(env.T_table_cam('head'))
        for p in _corners(env.layout):
            c = T[:3, :3] @ p + T[:3, 3]
            u, v = (K @ c)[:2] / c[2]
            assert c[2] > 0 and 10 <= u <= 629 and 10 <= v <= 469, (p, u, v)
    finally:
        env.close()


def test_plate_place_yaws_follow_tray_axis():
    env = G1ManipEnv(); env.reset(fixture())
    sk = SkillRunner(env, 'P-gate')
    part = load_parts()['parts']['P01']
    for yaw0 in (0.3, math.pi/2, -2.0):
        for delta in sk._place_yaws('P01', part, yaw0, tray=True):
            final = (yaw0 + delta) % math.pi
            assert min(final, math.pi - final) <= .4 + 1e-9
    deltas = sk._place_yaws('P06', load_parts()['parts']['P06'], 0., tray=True)
    assert deltas[0] == 0 and len(deltas) == 12
    env.close()


def test_bench_trials_are_deterministic_and_reachable():
    a = make_trial('P02', 'tray', 'T1', 3, 1); b = make_trial('P02', 'tray', 'T1', 3, 1)
    assert a == b and a['source_name'] != 'T1' and len(a['spec']['objects']) == 4
    trials = all_trials(1, parts=['P01'], clutters=[0])
    assert len(trials) == 16 and all(t['arm'] in ('left', 'right') for t in trials)


def test_transport_place_rejects_tray_outside_reach_table_and_places_inside():
    part = load_parts()['parts']['P06']
    arm, spec = next(iter(candidates('P06', part)))
    layout = copy.deepcopy(load_layout()); layout['reach'][arm] = [z for z in layout['reach'][arm] if z != 'T3']
    env = G1ManipEnv(layout); env.reset(spec)
    try:
        sk = SkillRunner(env, 'P-gate')
        assert sk.run('grasp_lift', arm, 'o0')['ok']
        r = sk.run('transport_place', arm, 'o0', 'T3')
        assert r['reason_code'] == 'IK_FAIL' and sk.events['place_reject'] == 'reach_table'
        r = sk.run('transport_place', arm, 'o0', 'T1')
        assert set(r) >= {'ok', 'reason_code', 'internal_done', 't_ms'} and r['ok'], sk.events
        env.step(math.ceil(1.5/env.model.opt.timestep))
        assert all(judge_place(env, 'o0', 'T1').values())
    finally:
        env.close()
