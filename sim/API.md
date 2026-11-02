# sim 패키지 인터페이스 계약 (Phase 1)

경로: /home/user/work/robot_percept/sim/  (python 패키지 `sim`, 실행 시 PYTHONPATH=/home/user/work/robot_percept)
Python: /home/user/work/robot_percept/.venvs/mj/bin/python (나중에 conda env robot_percept 에도 설치 예정)
렌더링: source /home/user/work/robot_percept/sim_test/gl_env.sh

## 소유권
| 파일 | 담당 |
|---|---|
| sim/__init__.py, sim/env.py, sim/scene_builder.py, sim/objects.py, assets/objects/ | P1-A (env) |
| sim/control.py, sim/ik.py, tests/test_control.py | P1-B (control) |
| sim/export_fp.py, eval/pose_metrics.py, data/sim_scenes/ | P1-C (export/eval) |
P1-B, P1-C 는 env.py 가 준비되기 전에는 sim_test/scene_panda.xml 로 직접 개발하고, 완성되면 SimEnv 로 갈아탄다.

## 좌표 / 단위 규약
- 단위: m, rad. 자세는 4x4 homogeneous numpy float64.
- T_a_b = b 좌표계를 a 좌표계로 표현 (p_a = T_a_b @ p_b).
- 카메라: OpenCV 규약 (x 오른쪽, y 아래, z 앞). T_world_cam: R = cam_xmat @ diag(1,-1,-1), t = cam_xpos.
- FoundationPose 출력 = T_cam_obj (메쉬 원점 기준). GT 도 같은 메쉬 원점 기준이어야 함.
- depth: float32 미터 (planar z), 유효하지 않은 값 0.

## SimEnv API (sim/env.py)
```python
class SimEnv:
    def __init__(self, objects=("mustard",), width=640, height=480, cam="front",
                 shadows=False, reflections=False, seed=0): ...
    model, data                              # mujoco.MjModel / MjData
    def reset(self, seed=None, randomize=True) -> None   # 물체를 테이블 위 랜덤 위치/yaw 로, 로봇 home 자세, 안정될 때까지 settle
    def step(self, n=1) -> None              # 중력보상(qfrc_bias) 포함 물리 n step
    def render_rgbd(self, cam=None) -> dict  # {"rgb": HxWx3 uint8, "depth": HxW float32 m, "seg": HxW int32 (객체 id, 배경 -1)}
    def object_mask(self, name, cam=None) -> HxW bool
    def camera_K(self, cam=None) -> 3x3
    def T_world_cam(self, cam=None) -> 4x4
    def T_world_obj(self, name) -> 4x4      # 메쉬 원점 기준
    def T_cam_obj(self, name, cam=None) -> 4x4
    def object_mesh_path(self, name) -> str  # FoundationPose 에 줄 OBJ (미터)
    def arm_qpos(self) -> (7,)
    def set_arm_target(self, q7) -> None     # position actuator 목표
    def set_gripper(self, width_m) -> None   # 0 ~ 0.08
    def ee_pose(self) -> 4x4                 # T_world_ee (그리퍼 TCP)
    def add_object_from_mesh(self, name, visual_obj, collision_objs, mass=0.1, rgba=None) -> None  # 다음 reset 때 반영 (모델 재컴파일)
```