import math

import pytest

from m2a.sim import skill_bench
from m2a.sim.g1_manip_env import G1ManipEnv
from m2a.sim.skills import SkillRunner


@pytest.mark.parametrize('predicted', [False, True])
def test_explicit_approach_is_independent_of_cylinder_yaw(predicted):
    trial = next(t for t in skill_bench.all_trials(1) if t['part_id'] == 'P04'
                 and t['source'] == 'left_zone' and t['clutter'] == 0)
    e = G1ManipEnv()
    try:
        e.reset(trial['spec'])
        sk = SkillRunner(e, 'P-gate')
        pose = dict(e.get_gt_objects()['o0'], size=[.008, .06]) if predicted else None
        assert sk.run('reach_pregrasp', trial['arm'], 'o0', obj_pose_T=pose, approach=.2)['ok']
        assert sk.events['approach_yaw'] == pytest.approx(.2)
        with pytest.raises(ValueError):
            sk.run('reach_pregrasp', trial['arm'], 'o0', approach=math.nan)
    finally:
        e.close()
