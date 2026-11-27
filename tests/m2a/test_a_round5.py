import numpy as np
from m2a.common import load_layout
from m2a.scene.generator import generate
from m2a.scene._geometry import obb, overlaps, tray_box
from m2a.sim.g1_manip_env import G1ManipEnv
from m2a.sim.skills import SkillRunner


def test_r5_tray_outer_walls_disjoint():
    layout = load_layout()
    trays = list(layout['trays'].values())
    for i, a in enumerate(trays):
        assert a['inner'] == [.24, .14]
        for b in trays[i+1:]:
            assert not overlaps(tray_box(a), tray_box(b))
        for x0, x1, y0, y1 in layout['regions'].values():
            rect = obb(((x0+x1)/2,(y0+y1)/2), (x1-x0,y1-y0))
            assert not overlaps(tray_box(a), rect)


def test_r5_reach_pregrasp_perception_roundtrip():
    env = G1ManipEnv()
    try:
        env.reset(generate(10000, 'L2', 'standard', 'dev'))
        assert SkillRunner(env, 'P-gate').run('reach_pregrasp', 'left', 'o0')['ok']
        token = env.perception_pose()
        assert env.ee_pose('left')[0][2] < -.14
        env.restore_perception_pose(token)
        np.testing.assert_allclose(env.arm_q('left'), token['left'], atol=.04)
    finally:
        env.close()