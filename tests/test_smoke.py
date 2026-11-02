"""기본 스모크 테스트: import, SimEnv 생성/렌더, grasp 계획, 웹 앱 생성 없이 모듈 로드"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("MUJOCO_GL", "egl")

def test_imports():
    import sim.env, sim.control, sim.grasp, sim.ik, eval.pose_metrics  # noqa
    import web.app, web.sim_worker, perception.fp_runner  # noqa

def test_env_render_and_grasp():
    import numpy as np
    from sim.env import SimEnv
    from sim.grasp import choose_grasp
    env = SimEnv(objects=("mustard",), seed=3)
    env.reset(seed=3, randomize=True)
    out = env.render_rgbd()
    assert out["rgb"].shape == (480, 640, 3) and out["depth"].dtype == np.float32
    assert env.object_mask("mustard").sum() > 200
    plan = choose_grasp(env.model, env.data, env.T_world_obj("mustard"), env.registry["mustard"].bounds)
    assert plan["mode"] in ("top", "side", "top-cap")
    env.close()
