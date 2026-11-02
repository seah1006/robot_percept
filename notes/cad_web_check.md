# Phase 0 / S4: 웹 + CAD 파트 검증 (교수님 MD의 `flask pyrealsense2 trimesh opencv-python "cadquery>=2.6"`)

검증일: 2026-10-26, WSL2 Ubuntu 24.04, Python 3.12.3

## 1. 설치 (격리 venv)
- 위치: `~/work/robot_percept/.venvs/cad` (uv venv, conda env와 분리, 약 1.9GB)
- 설치: `uv pip install flask pyrealsense2 trimesh "cadquery>=2.6" numpy scipy networkx rtree coacd fast-simplification manifold3d mujoco`
- 전체 고정 목록: `notes/cad_venv_freeze.txt`

| 패키지 | 버전 |
|---|---|
| cadquery | 2.8.0 |
| cadquery-ocp (OCCT) | 7.9.3.1.1 |
| vtk | 9.6.2 (cadquery-ocp 의존) |
| numba / llvmlite | 0.68.0 / 0.50.0 (cadquery 의존, `numpy<2.6,>=1.22`) |
| numpy | 2.5.4 (venv 최신) |
| scipy | 1.18.1 |
| trimesh | 5.2.0 |
| flask / werkzeug | 3.1.3 / 3.1.9 |
| pyrealsense2 | 2.59.1.11053 (`rs.context()` 장치 0개, 정상) |
| coacd | 1.0.14 (볼록 분해, 선택) |
| mujoco | 3.17.0 (충돌 메쉬 로드 확인용, 선택) |

### numpy 충돌 여부
- cadquery/OCP 휠은 numpy 2.x와 호환. 제약은 numba의 `numpy<2.6`.
- 메인 env의 numpy 2.5.3으로 고정해도 같은 세트가 해결됨 (`uv pip install --dry-run ... "numpy==2.5.3"` 성공, 다운그레이드 1개만 발생).
- 같은 env에 함께 넣을 때 동작하는 세트: `numpy==2.5.3 cadquery==2.8.0 cadquery-ocp==7.9.3.1.1 trimesh==5.2.0 flask==3.1.3 pyrealsense2==2.59.1.11053` (numpy는 2.6 미만 유지).
- 단, cadquery-ocp + vtk가 1GB 이상이라 FoundationPose env와는 분리(이 venv) 권장. 변환 결과(OBJ)만 공유하면 됨.

## 2. `tools/stp_to_mesh.py`
STEP(.stp/.step) -> 미터 단위 메쉬
```bash
source ~/work/robot_percept/.venvs/cad/bin/activate
python tools/stp_to_mesh.py part.step -o out_dir [--unit mm|cm|m|in|ft] [--center none|bbox|centroid] [--collision none|hull|decimate|coacd|all] [--tol 1e-4]
```
출력 (모두 m 단위):
- `<name>.obj` : FoundationPose / MuJoCo visual mesh
- `<name>.stl` : 같은 메쉬 binary STL
- `<name>_collision_hull.obj` : 볼록 껍질 1개
- `<name>_collision_decimate.obj` : CAD 재테셀레이션 저해상도 버전 (tol x10, 각도 0.6)
- `<name>_collision_coacd_NN.obj` : 볼록 분해 조각 (오목한 물체용, 최대 16개)
- `<name>.json` : 헤더 단위, 적용 스케일, extents, bounds, center offset, 삼각형 수, watertight, 부피

단위 처리:
- STEP 헤더의 길이 단위(`FileUnits`)를 읽어 기록하고, OCCT 리더의 system length unit을 m로 설정해 바로 m 좌표를 얻음.
- 주의(OCCT 7.9): `SetSystemLengthUnit(1000)`은 `ReadFile()` 다음에 호출해야 적용됨. 먼저 호출하면 mm로 리셋됨(실험으로 확인).
- `--unit` 은 헤더가 틀린 파일용: 원본 숫자를 지정 단위로 재해석.
- `--center bbox`(기본): bbox 중심을 원점으로 이동, 적용한 offset을 json에 기록 (원래 CAD 좌표 = 메쉬 좌표 - offset).

기타 확인 사항:
- trimesh `simplify_quadric_decimation` / fast-simplification은 CAD 테셀레이션을 전혀 줄이지 못함(2284 -> 2284). 그래서 decimate는 CAD 원본을 거친 공차로 다시 테셀레이션하는 방식으로 구현. 재테셀레이션 전 `BRepTools.Clean_s` 필요(안 하면 기존 촘촘한 메쉬 유지).
- cadquery `exporters.export` 는 `write.step.unit` 설정을 무시함. 단위 지정 STEP 저장은 `STEPControl_Writer` 직접 사용(`tools/make_samples.py`). 인치는 `"INCH"` (`"IN"`은 거부됨).

## 3. 변환 테스트 (`cad_uploads/samples/` -> `cad_uploads/converted/`)
| 샘플 | 헤더 단위 | extents [m] | 삼각형 | watertight | hull / decimate / coacd |
|---|---|---|---|---|---|
| box_fillet_50x30x20mm (R3 필렛) | millimetre | 0.05 x 0.03 x 0.02 | 1148 | True | 1148 / 380 / 1 |
| box_fillet_metre_header | metre | 0.05 x 0.03 x 0.02 | 1148 | True | 1148 / 380 / 1 |
| box_fillet_cm_header | centimetre | 0.05 x 0.03 x 0.02 | 1148 | True | 1148 / 380 / 1 |
| box_fillet_inch_header | INCH | 0.05 x 0.03 x 0.02 | 1148 | True | 1148 / 380 / 1 |
| cup_d70_h60mm (윗면 개방, 벽 3mm) | millimetre | 0.07 x 0.07 x 0.06 | 2284 | True | 1164 / 724 / 16 |
| box 2x1.2x0.8 "mm" (인치 숫자) | millimetre | 0.002 x 0.0012 x 0.0008 | | | |
| 같은 파일 `--unit in` | millimetre -> in | 0.0508 x 0.03048 x 0.02032 | | | |

- 부피 검증: 필렛 박스 2.9845e-5 m^3 (50x30x20=3.0e-5에서 필렛 모서리만큼 감소, 정상).
- OBJ 재로드(trimesh.load): extents 0.07 x 0.07 x 0.06, watertight 유지.
- MuJoCo 3.17 로드 테스트: 컵 visual + coacd 16조각 collision을 freejoint로 바닥에 떨어뜨림 -> 정지 z = 0.0299 m (높이 절반 0.03, 원점 중심화 확인).

## 4. Flask 스모크 테스트 (`tools/cad_server.py`, 포트 5050)
- `GET /health` -> `{"ok": true}`
- `POST /upload` (multipart `file`, 선택 form `unit`, `center`, `collision`) -> `cad_uploads/<이름>_<id>/`에 저장 + 변환 + JSON
- `GET /files/<job>/<file>` -> 변환 파일 다운로드

curl 결과:
- mm 박스: ok, extents [0.05, 0.03, 0.02], 1148 tris, watertight, 변환 0.34 s
- INCH 헤더 박스 + collision=coacd: ok, header_unit INCH, extents [0.05, 0.03, 0.02], 0.39 s
- 단위 오기 박스 + unit=in: ok, extents [0.0508, 0.03048, 0.02032]
- .txt 업로드: HTTP 400 `unsupported extension`
- 변환 OBJ 다운로드: HTTP 200, 73,938 bytes

## 5. 다음 단계 메모
- FoundationPose: 변환 OBJ는 텍스처가 없음 -> trimesh 기본 회색 vertex color로 렌더됨. 시뮬 물체도 같은 단색으로 만들면 일관됨. 실물 연동 시 색/텍스처 지정 필요.
- MuJoCo: visual은 `<name>.obj`, collision은 coacd 조각(오목 물체) 또는 hull(볼록 물체). 질량은 json의 volume x 밀도로 계산 가능.
- 웹 통합 시 `/upload` 응답의 `files`, `extents_m` 을 시뮬 장면 생성기와 FoundationPose mesh 경로로 넘기면 됨.
