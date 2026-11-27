# 작업자 A: G1 부품 키팅 및 게이트 G-A

## 변경 파일
- `m2a/sim/{__init__,g1_manip_env,skills,gate_grasp}.py`: 환경, 스킬, 게이트/도달표/캡처 러너
- `m2a/config/layout.json`: 테이블, 영역, 트레이, 팔별 도달표
- `tests/m2a/test_a_manip.py`: 모델·비트 필터·GT/IK·게이트 조건·반환 스키마 검증. `tests/m2a/__init__.py` 삭제는 메인이 먼저 반영한 181659a와 동일한 조치.
- `m2a/notes/{wsa_report.md,wsa_gate_raw/,img_a/}`: 본 보고서, 원자료, 캡처
- `python -m pytest tests/m2a -q`: 8 passed, 1 warning (Dash pytest 플러그인 경고). 커밋 없음.

## 레이아웃 및 도달표
- 좌표는 m. 값은 임의 지정. 월드 테이블 중심 `(0.34,0,0.90)` 및 `top_z_world=0.90` (초기 `null`), 회전은 단위행렬. 초기 후보 `(0.47,0,0.82)`에서는 원거리 x에서 손바닥 하향 IK가 거의 실패.
- 트레이 공통 x `.10 → -.01`, y `+.16/0/-.16` 유지. 내부 `(.24,.13)` 유지, 바닥 `.004`, 벽 두께 `.006`, 벽 높이 `.03`.
- left `[-.20,.20,.26,.48] → [-.20,-.05,.24,.46]`; right `[-.20,.20,-.48,-.26] → [-.20,-.05,-.46,-.24]`; center `[-.22,-.04,-.24,.24] → [-.22,-.14,-.12,.12]`. 먼저 팔 도달을 위해 x를 줄였고, 측면 y는 P01이 들어가도록 확장했으며, center x 끝은 트레이 외벽과 겹치지 않도록 조정.
- 영역 면적 왼쪽·오른쪽 각각 `.0330`, 중앙 `.0192`, 합 `.0852 m²`. P01 `.20×.06`은 세 영역 모두 yaw=π/2로 단품 완전 수납 가능(회전 자유도·다수 배치는 제한; L2 실패하면 생성기의 제약 배치 확인 후 축척 변경 검토). 축척을 길이 방향으로만 줄이면 파지 폭은 보존되나 접촉·관성은 달라지므로 게이트 재측정 필요.
- 도달표는 그립 사이트 하향 자세로 영역 3×3 점 및 각 트레이 중심을 측정. 각 점은 저점 `.025`(트레이 `.065`) 및 10 cm 위에서 같은 yaw로 IK 위치 2.5mm·회전 2.5° 이내에 드는 후보가 하나 이상이면 성공(16개 yaw, 임의 지정). 이는 정적 IK로 경로 충돌 및 부품별 자세까지 보장하지 않음.

|팔|목표|수렴 점|
|---|---|---:|
|left|left_zone|9/9|
|left|right_zone|3/9|
|left|center_zone|9/9|
|left|T1|1/1|
|left|T2|1/1|
|left|T3|1/1|
|right|left_zone|3/9|
|right|right_zone|9/9|
|right|center_zone|9/9|
|right|T1|1/1|
|right|T2|1/1|
|right|T3|1/1|
영역은 과반수(5/9)이고 트레이는 중심 1/1이면 기호 `reach`에 포함(임의 지정). 원자료: `m2a/notes/wsa_gate_raw/reach.jsonl`.

## 게이트 G-A
GT 보조 스크립트로 단품 배치. 원래 부품 치수 유지. 시드 P01/P04/P06 = 10042/10043/10044, 좌우 교대로 10회씩, 모드 간 동일 자세. 측면 영역 부분집합에서 x∈[-.155,-.095], |y|∈[.338,.374], 판재·브래킷 yaw=π/2±.25 rad, 다월 yaw=[-π,π] 균일(모두 임의 지정). 전체 영역 또는 임의 전방위 yaw를 대표하지 않음. 목표는 10 cm 상승 및 2초 유지 후 중심 z≥7 cm이고 여전히 손에 붙음. 12/20이 부품별 통과선(가설). 보유 여부: weld 활성+손 영역 내, 또는 물리 모드에서 손 영역 내 유효 손끝 접촉. P-gate 순간에는 별도 끝마디 2개 이상을 요구. Dex1 평행 그리퍼는 이 Menagerie G1 디렉터리에 모델이 없어 제외. P-oracle은 테스트/디버그 전용.

|부품|모드|성공|Wilson 95% CI|실패 유형|원자료 (`m2a/notes/wsa_gate_raw/`) |
|---|---|---:|---:|---|---|
|P01|P-phys|0/20|0.0%–16.1%|GRASP_SLIP 20|`P01_P-phys_00-20.jsonl`|
|P01|P-gate|20/20|83.9%–100.0%|없음|`P01_P-gate_00-20.jsonl`|
|P04|P-phys|0/20|0.0%–16.1%|GRASP_SLIP 20|`P04_P-phys_00-20.jsonl`|
|P04|P-gate|0/20|0.0%–16.1%|GRASP_SLIP 20|`P04_P-gate_00-20.jsonl`|
|P06|P-phys|20/20|83.9%–100.0%|없음|`P06_P-phys_00-20.jsonl`|
|P06|P-gate|20/20|83.9%–100.0%|없음|`P06_P-gate_00-20.jsonl`|

## 모드 추천과 남은 문제
메인 결정으로 P-gate를 주력 모드로 추천(검증된 P01/P06 데모용). 기준 프로파일에서는 P04가 미통과했으며(정식 핀치 재측정은 아래 참조),, P-gate 성공률을 실물 마찰 파지 성능으로 해석하지 않는다. P-phys는 비교군으로 유지한다.
- 스킬은 GT를 보조로 쓰고 관절 보간으로 움직인다. `transport_place`/`put_aside`에는 대상 중심에 놓는 구현이 있으나, 빽빽한 트레이의 빈 슬롯 탐색·이송 경유점·복수 부품 배치는 이번 게이트 미검증.
- 계약 요청: `trays[*].floor_z`, `wall_thickness`; 기호 reach는 집계표이며 실행 전 개별 부품 좌표·yaw에 대해 재확인. `render(cam)`은 `(RGB uint8, depth float32 m)`, 선언 순서 RGB→depth. 선택적 목표 좌표를 스킬 디스패처가 넘기는 규약은 2주차에 합의 필요.

## PNG

`m2a/notes/img_a/P01_front.png`, `m2a/notes/img_a/P01_wrist_l.png`, `m2a/notes/img_a/P04_front.png`, `m2a/notes/img_a/P04_wrist_l.png`, `m2a/notes/img_a/P06_front.png`, `m2a/notes/img_a/P06_wrist_l.png`, `m2a/notes/img_a/front.png`, `m2a/notes/img_a/head.png`, `m2a/notes/img_a/wrist_l.png`, `m2a/notes/img_a/wrist_r.png`

육안 확인: 헤드에는 세 트레이가 보인다. 조정 후 손목 영상에서 P01은 손끝에 판재가 걸리고, P06은 손끝 사이에 부품이 놓인 것을 확인했다. P04는 손에 남지 않았다.

## P04 후속 진단
진단은 `m2a/notes/wsa_p04_diagnostic.py`로 재현. 동일 시드·유지 판정·20회 단위. 확대 가설은 런타임에만 적용하여 `parts.json`은 수정하지 않았다.

|조건|성공|최대 동시 손끝 수(횟수)|최종 중심의 원래 손바닥 경계 밖 최대 거리|원자료|
|---|---:|---|---:|---|
|baseline|0/20|{0: 2, 1: 18}|11.5 mm|`m2a/notes/wsa_gate_raw/P04_diagnostic_baseline.jsonl`|
|pinch|17/20|{0: 3, 2: 17}|18.3 mm|`m2a/notes/wsa_gate_raw/P04_diagnostic_pinch.jsonl`|
|pinch_wider|17/20|{0: 3, 2: 17}|18.3 mm|`m2a/notes/wsa_gate_raw/P04_diagnostic_pinch_wider.jsonl`|
|pinch_large|16/20|{0: 3, 1: 1, 2: 16}|32.6 mm|`m2a/notes/wsa_gate_raw/P04_diagnostic_pinch_large.jsonl`|

기준 P04 하강 목표는 T 기준 `.105→.033 m` (임의 지정); 20회 중 18회 손끝 최대 한 곳, 2회는 손끝 접촉 없음. 손바닥 경계를 넓혀도 이 기준 궤적에서는 두 손끝 조건을 채우지 못한다. `pinch`: 검지를 먼저 닫고 중지는 열어 두며 손 프레임 오프셋을 적용했다. `pinch_wider`: 여기에 손바닥 경계만 확장했다. `pinch_large`: 원래 경계를 쓰고 반지름 `.016`, 높이 `.08`로 바꿨다. 모두 임의 지정 실험값.

## 정식 파지 프로파일 및 추가 평가

- `m2a/sim/grasp_profiles.json`: P04에만 `index_thumb_pinch`. 검지부터 닫고 중지는 열어 둔다. 엄지 닫기 지연 0.52와 손 프레임 오프셋 `[-.020, 0, -.018]` m는 진단에서 채택한 임의 지정값. 손바닥 게이트 조건과 `parts.json` 치수는 유지. P01/P06과 기타 부품은 이전 `three_finger`.
- 좁은 게이트는 앞의 20개 동일 P04 초기 자세에서 정식 프로파일을 재측정. 일반화는 각 부품 20회(좌/우/중앙에 각각 7/7/6회). 시드 10142/10143/10144. 각 영역 직사각형 전체에서 중심 xy 균일 추출한 뒤 테이블 밖 또는 트레이 외곽과 초기 물체 AABB가 겹치는 경우만 다시 추출. IK·물리 결과에 따른 재추출 없음. P01/P06 yaw는 영역 장축 ±15°, 직립 P04 yaw는 `[-π,π]`. 중앙 팔은 교대 배정.
- L0은 기존 좁은 측면 샘플의 처음 10개를 사용하고 좌→T1, 우→T3. `grasp_lift`→`transport_place` 직후 2초 정착 후 독립 GT 검사. 트레이 내부 XY 여유 `.01 m`, 중심 z `[floor_z, floor_z+.08 m]`, 선속력 `<.02 m/s`, 두 스킬 성공까지 모두 필요. yaw·시드·샘플 배분·판정 상수는 임의 지정. 스택·장애물·트레이 다중 적재는 평가하지 않음.
- 재현: 각 작업은 `flock -w 900 /tmp/rp_measure.lock timeout 295 python -m m2a.sim.gate_grasp {gate|general|l0} --part P04 --mode P-gate` 형태로 개별 실행. 원자료는 아래 파일과 `m2a/notes/wsa_gate_raw/` 참조.

|시험|부품|모드|성공|Wilson 95% CI|실패 유형 (단계)|원자료|
|---|---|---|---:|---:|---|---|
|gate|P04|P-gate|17/20|64.0%–94.8%|GRASP_SLIP 3|`gate_profiles_v1_P04_P-gate_00-20.jsonl`|
|gate|P04|P-phys|0/20|0.0%–16.1%|GRASP_SLIP 20|`gate_profiles_v1_P04_P-phys_00-20.jsonl`|
|general|P01|P-gate|13/20|43.3%–81.9%|IK_FAIL 7|`general_profiles_v1_P01_P-gate_00-20.jsonl`|
|l0|P01|P-gate|8/10|49.0%–94.3%|judge/inside_xy 2|`l0_profiles_v1_P01_P-gate_00-10.jsonl`|
|general|P04|P-gate|18/20|69.9%–97.2%|GRASP_SLIP 1, IK_FAIL 1|`general_profiles_v1_P04_P-gate_00-20.jsonl`|
|l0|P04|P-gate|8/10|49.0%–94.3%|grasp/GRASP_SLIP 2|`l0_profiles_v1_P04_P-gate_00-10.jsonl`|
|general|P06|P-gate|20/20|83.9%–100.0%|없음|`general_profiles_v1_P06_P-gate_00-20.jsonl`|
|l0|P06|P-gate|10/10|72.2%–100.0%|없음|`l0_profiles_v1_P06_P-gate_00-10.jsonl`|

### 영역별 일반화 결과
- P01: left_zone 6/7, right_zone 7/7, center_zone 0/6; 기하 조건 제외 50회.
- P04: left_zone 6/7, right_zone 7/7, center_zone 5/6; 기하 조건 제외 1회.
- P06: left_zone 7/7, right_zone 7/7, center_zone 6/6; 기하 조건 제외 6회.

좁은 공식 기준에서 P-gate 세 부품이 이제 12/20을 통과한다(P01/P06 기존 결과에 미수정 프로파일). 일반화·배치 수치는 그 기준과 별개다.

### RGB-D와 캘리브레이션 API

- `env.render(cam)` → `(rgb, depth)`. `rgb`는 `np.uint8`, 순서 RGB, `(H,W,3)`; `depth`는 `np.float32`, `(H,W)`, 카메라 광축 +z의 미터(픽셀별 유클리드 거리 아님). 헤드·전면은 `(H,W)=(480,640)`, 손목은 `(256,256)`.
- `env.camera_K(cam)` → `float64 (3,3)` 픽셀 단위 pinhole 내부행렬. `fx=fy=H/[2 tan(fovy/2)]`, `(cx,cy)=((W−1)/2,(H−1)/2)`; 정수 인덱스의 픽셀 중심 관례. 왜곡 없음.
- `env.T_world_cam(cam)` 및 `env.T_table_cam(cam)` → 각각 카메라→월드, 카메라→테이블의 `float64 (4,4)` 동차변환. 카메라 좌표축은 오른쪽 +x, 아래 +y, 전방 +z. 손목은 프레임마다 움직이므로 `render`와 같은 시뮬레이션 상태에서 읽는다. `p_T=T_table_cam·[d K⁻¹(u,v,1)ᵀ;1]`.
- `layout.json`의 `floor_z`, `wall_thickness` 유지. 기호 `reach`는 영역 수준이고 개별 자세는 `IK_FAIL`이 날 수 있다. 배치의 물리 성공은 `internal_done`이 아니라 독립 GT 판정으로 구분한다.
- 정식 P04 핀치 PNG: `m2a/notes/img_a/P04_pinch_front.png`, `m2a/notes/img_a/P04_pinch_wrist_l.png`.
- 네 카메라의 RGB/depth shape와 dtype은 EGL 실렌더로 확인했다. 정식 P04의 손목 캡처에서 물체가 검지와 엄지 사이에 있음을 육안 확인했고, 같은 프레임의 기록된 접촉도 `index`, `thumb`였다.
- 다음 병목: P01 중앙 0/6은 전부 `IK_FAIL`. 물체별 중심·yaw에 맞춘 접근 자세와 보관 위치를 별도로 검증해야 한다. L0의 P01 실패 2회는 스킬 성공 후 XY 판정에서 탈락했으므로 트레이 내판 방향과 릴리스 궤적을 개선 후보로 남긴다. 이 시험의 성공 기준은 중심과 정착이지 발자국 전체가 트레이에 들어갔다는 뜻은 아니다.
- 앞 절의 `wsa_p04_diagnostic.py`는 정식 프로파일 이전 코드를 기준으로 한 역사적 진단 스크립트다. 현재 버전 재현은 정식 `gate_grasp.py` 명령을 사용한다.
