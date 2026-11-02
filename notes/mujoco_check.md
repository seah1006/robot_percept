# MuJoCo 확인 결과 (0단계, S2) - 2026-10-26

## 환경
- WSL2 Ubuntu 24.04, RTX 2080 SUPER (driver 610.88), uv venv `~/work/robot_percept/.venvs/mj` (Python 3.12)
- mujoco 3.17.0, numpy 2.5.4, opencv-python-headless 5.0.0, imageio, PyOpenGL
- 로봇: `assets/mujoco_menagerie/franka_emika_panda` (git clone --depth 1)
- apt 추가: libosmesa6, libglfw3, libglew2.2, mesa-utils

## 씬 (`sim_test/scene_panda.xml`)
- `panda_mod.xml` = menagerie panda.xml + 절대 meshdir + keyframe 제거(씬에서 물체 free joint 포함해 다시 정의) + 손목 카메라 `wrist`
- 테이블(상판 z=0.30, 0.5x0.8m), 빨간 박스 물체 `obj` (5x6x8cm, free joint, 0.15kg)
- 고정 RGB-D 카메라 `rgbd`: pos (1.35, 0, 0.95) -> (0.55, 0, 0.30) 응시, fovy 58
- `<map znear=0.01 zfar=50>`, extent 1.2 -> near 0.012m / far 60m
- 생성: `build_scene.py`

## 렌더링 백엔드 (N=60, update_scene+render 포함)

| 변형 | GL renderer | 640x480 rgb | 640x480 depth | 640x480 rgb+depth | 1280x720 rgb | 1280x720 rgb+depth | depth 오차 vs mj_ray |
|---|---|---|---|---|---|---|---|
| `MUJOCO_GL=egl` (기본) | **llvmpipe (CPU)** | 3.7 | 49 | 2.5 | 2.3 | 2.6 | 0.0004mm (정확) |
| `egl` + `GALLIUM_DRIVER=d3d12` | **D3D12 (RTX 2080 SUPER)** | 23.1 | 81 | 18.3 | 22.6 | 16.9 | median 1.2mm (물체 0.7mm) |
| 위 + 그림자 off | D3D12 | 40.6 | 58 | 23.5 | 35.2 | 19.3 | 동일 |
| 위 + 그림자/반사 off | D3D12 | 46.2 | 45 | 30.6 | 50.7 | 21.5 | 동일 |
| `egl` + `GALLIUM_DRIVER=llvmpipe` | llvmpipe | 3.9 | 47 | 3.2 | 2.1 | 1.5 | 정확 |
| `osmesa` | llvmpipe | 3.3 | 39 | 3.1 | 3.2 | 2.2 | 정확 (context 생성 8.3s) |
| `glfw` (DISPLAY=:0, WSLg) | llvmpipe | 3.2 | 41 | 3.6 | 2.7 | 2.0 | 정확 |

- 주의: WSL에서 `MUJOCO_GL=egl`만 쓰면 **CPU(llvmpipe)** 로 떨어진다. GPU를 쓰려면 `GALLIUM_DRIVER=d3d12` 필수.
- d3d12 depth 특성 (llvmpipe 정답 대비, 경계 제외):
  - 거리 1.2m 이내 median 0.78mm / p95 1.3mm, 물체 표면 median 0.70mm / p95 1.16mm, 2m 이상 median 5.5mm / p95 13.9mm
  - 오차 ~ z^2 비례 (깊이버퍼 정밀도 한계로 추정) + 세로 방향 0.5px 래스터 오프셋 (llvmpipe 를 y -0.5px 이동하면 median 0.40mm)
  - znear/zfar 를 (0.06m, 4.8m), (0.12m, 3.6m)로 바꿔도 p95 개선이 작음 (9.7 -> 8.6 -> 5.5mm)
  - 깊이 경계 픽셀은 래스터 차이로 큰 이상값 발생 (최대 2.1m) -> 경계 마스킹 필요

## 카메라 / 정답 (640x480, OpenCV 규약)
- `mujoco.Renderer` depth 출력은 이미 **미터 단위 planar z** (near=znear*extent, far=zfar*extent 로 선형화). 추가 변환 불필요.
- K: fx = fy = 0.5*H/tan(fovy/2) = 432.971, cx = 319.5, cy = 239.5
- 외부 파라미터: `R_cv = cam_xmat.reshape(3,3) @ diag(1,-1,-1)`, `t = cam_xpos` -> T_world_cam
  - T_world_cam = [[0, 0.6306, -0.7761, 1.35], [1, 0, 0, 0], [0, -0.7761, -0.6306, 0.95]]
- 물체 GT: pos (0.55, 0.05, 0.3399), T_cam_obj = inv(T_world_cam) @ T_world_obj (FoundationPose 출력과 같은 형식)
- 저장: `results/<variant>/{rgb.png, rgb_1280x720.png, wrist_rgb_1280x720.png, depth_m.npy, depth_color.png, obj_mask.png, camera.json, gt_pose.json}`
- 검증:
  - GT 중심 투영 (341.03, 226.17)이 segmentation 물체 마스크 위에 있음, 마스크 중심 (341.37, 225.94)과 0.4px 차이
  - 중심 픽셀 depth 역투영 vs mj_ray 표면점: llvmpipe 0.00008mm, d3d12 0.67mm
  - 중심 픽셀 역투영점 vs GT 중심: 31mm (앞면 표면점이므로 정상, 박스 반폭 수준), 보이는 표면 centroid vs GT 21mm

## 물리 / 관절 제어 (`physics_test.py`)
- timestep 0.002, nq 16 (panda 9 + 물체 7), nu 8 (관절 7 + 그리퍼)
- 목표 [0.3, -0.3, 0.2, -2.2, 0.1, 2.0, 0.6] -> 0.6s 에 오차 < 0.01rad, 3s 후 최대 오차 6.5mrad (joint2/4 가 중력으로 처짐; 내장 PD servo, 중력보상 없음)
- 그리퍼 ctrl 0 -> finger 0.0 (닫힘 확인), 물체는 테이블 위 정지 (z=0.3399)
- 물리 속도 31,500 step/s (실시간의 63배, 렌더링 제외)

## 권장
- 실시간 웹 스트리밍/일반 개발: `source ~/work/robot_percept/sim_test/gl_env.sh`
  (`MUJOCO_GL=egl`, `GALLIUM_DRIVER=d3d12`, `MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA`)
  - 그림자/반사 끄면 rgb+depth 640x480 ~30fps, 1280x720 ~21fps
- 정밀 depth 가 필요한 오프라인 평가(FoundationPose 오차 측정): 같은 씬을 `GALLIUM_DRIVER=llvmpipe`로 렌더(정확하지만 rgb ~3fps), 또는 d3d12 depth 오차(1m 에서 ~1mm)를 감안
- 정밀 관절 추종: `qfrc_bias` 기반 중력보상 추가 또는 actuator 게인 조정
- glfw/osmesa 는 이점 없음 (둘 다 llvmpipe)
