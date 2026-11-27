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


---

# 3라운드 (2026-11-27, 작업자 A3: 이전 A 작업자 중단분 이어받음)

모든 P-gate 수치는 **P-gate(GT 보조 weld 파지 근사)** 이며 실물 마찰 파지 성능이 아니다. 원자료는 모두 `m2a/notes/wsa_gate_raw/`.

## 변경 파일
- `m2a/sim/g1_manip_env.py`: `GATE_RULES`, `env.gate_mode`(기본 `P-gate`), `set_gate_mode`, `weld_info[arm]`(oid, fingers, thumb_opposed, gate_mode, sim_time), `watch_contacts/unwatch_contacts`(매 물리 스텝 최소 손끝 접촉 수). attach/해제 규칙을 모드별로 분리. (메인이 befadaf로 중간 병합)
- `m2a/sim/skills.py`: `MODES=('P-phys','P-gate','P-gate-strict','P-oracle')`, `run()` 때 env 규칙 설정, `events.thumb_opposed`, `events.min_contacts_during_lift`, `events.approach_yaw`. befadaf 이후 미병합분: 중앙 판재(P01~P03) 접근 yaw 우선순위, 트레이 접근 충돌 검사를 벽만으로 한정.
- `m2a/sim/gate_grasp.py`: `--mode P-gate-strict`, `--tag`(기본 round3), 행에 `thumb_opposed`, `min_contacts_during_lift`, `min_contacts_during_hold`.
- `m2a/config/layout.json`: center_zone `[-0.22,-0.14,-0.12,0.12] → [-0.235,-0.155,-0.12,0.12]`(아래 결정). **계획·생성기에 영향 있으니 메인이 C에 알림 필요.**
- `tests/m2a/test_a_round2.py`: 모드 이름, P-gate 기본 규칙(엄지 불필요, 접촉 1개면 유지, 0개 200ms 연속이면 해제), 접촉 감시 최소값, strict 규칙, strict 러너 반환 키 테스트.
- 측정·진단 스크립트: `m2a/notes/wsa_round3_measure.py`(center/tray/top/clutter, `--mode`, `--center` 후보 덮어쓰기), `wsa_round3_center_diag.py`(P01 중앙 heading 스윕), `wsa_round3_tray_diag.py`(트레이 접근 차단 geom).
- API 시그니처·반환 키는 바꾸지 않았다(추가 필드·메서드만).

## 모드 정의
|모드|weld 조건|해제 조건|용도|
|---|---|---|---|
|`P-gate`(기본)|손 닫힘 + 서로 다른 손끝 ≥2곳 접촉(엄지 무관) + 물체 중심이 손바닥 영역 안|weld 중 손끝 접촉 **0개가 200 ms 연속** → release + GRASP_SLIP. 손 열면 해제|기획서 정의, E·F 사용|
|`P-gate-strict`|위 + 엄지 포함|접촉 **≤1개가 200 ms 연속** → release + GRASP_SLIP|대향 파지 엄격판(비교군)|
|`P-phys`|weld 없음(순수 마찰)|-|비교군|
|`P-oracle`|접촉 무관 weld|-|디버그 전용|
- 200 ms, 손끝 2곳, 손바닥 영역 경계는 임의 지정(이전 라운드 값 유지). `thumb_opposed` = weld 순간 엄지 접촉 여부(P-phys는 닫힘 직후 엄지 접촉 여부). `min_contacts_during_lift` = 들어 올리는 10 cm 구간 매 스텝 최소 손끝 접촉 수.
- env 규칙은 env 단위 상태다. 같은 env에서 strict 러너를 쓴 뒤 `apply_ee_delta`를 쓰면 strict 규칙이 남는다(기본으로 돌리려면 `env.set_gate_mode('P-gate')`).

## 공식 게이트 (gate_grasp.py, 기존 seed 10042/10043/10044, 좌우 10회씩, 같은 초기 자세)
|부품|모드|성공|Wilson 95% CI|weld 시 엄지 대향|성공 중 lift 최소 접촉(횟수)|실패|원자료|
|---|---|---:|---:|---:|---|---|---|
|P01|P-gate|18/20|69.9–97.2%|13/20 weld (성공 중 13/18)|0:5, 1:13|GRASP_SLIP(lift) 2|`gate_round3_P01_P-gate_00-20.jsonl`|
|P01|P-gate-strict|0/20|0.0–16.1%|13/13 weld|-|GRASP_SLIP closure 7, lift 13|`gate_round3_P01_P-gate-strict_00-20.jsonl`|
|P04|P-gate|17/20|64.0–94.8%|17/17 weld|1:16, 2:1|GRASP_SLIP(closure) 3|`gate_round3_P04_P-gate_00-20.jsonl`|
|P04|P-gate-strict|1/20|0.9–23.6%|17/17 weld|2:1|GRASP_SLIP lift 16, closure 3|`gate_round3_P04_P-gate-strict_00-20.jsonl`|
|P06|P-gate|20/20|83.9–100.0%|20/20 weld|3:20|없음|`gate_round3_P06_P-gate_00-20.jsonl`|
|P06|P-gate-strict|20/20|83.9–100.0%|20/20 weld|3:20|없음|`gate_round3_P06_P-gate-strict_00-20.jsonl`|
- strict 결과는 이전 작업자가 보고한 중간값(0/20, 1/20, 20/20, `gate_round2_*`)과 같다.
- 해석: P01 P-gate 성공 18회 중 5회는 들어 올리는 동안 손끝 접촉이 잠깐 0개가 됐다(200 ms 미만이라 유지). P04 성공 17회 중 16회는 lift 중 접촉이 1개까지 떨어졌다. 즉 P-gate 성공 상당수는 엄지 대향 마찰로 버티는 파지가 아니고, weld가 붙잡고 있는 상태다. P06만 엄지 포함 3접촉을 끝까지 유지했다.

## D3 중앙 영역 (center_zone) 결정
측정: `wsa_round3_measure center`, seed 10170+부품, 부품·팔별 20회, P01 yaw=영역 장축±15°(생성기 규칙), P04/P06 yaw 균일. 물체가 영역 안에 완전히 들어가는 자세만 추출. "집기" = grasp_lift 성공. 같은 실행에서 put_aside로 center_zone에 다시 놓는 것(2 s 후 영역 안·정지·바닥 높이 ±5 mm)도 기록.

|조건|P01 L/R 집기|P04 L/R 집기|P06 L/R 집기|원자료|
|---|---|---|---|---|
|round2(strict, 원래 영역)|0/20, 0/20 (closure에서 weld 실패)|집기+치우기 0/40|집기+치우기 12/40|`round2_center.jsonl`|
|P-gate, 원래 영역, heading 수정 전|0/20, 0/20 (weld는 되나 lift 중 접촉 0 → SLIP)|14/20, 15/20|17/20, 17/20|`round3_center_P-gate_*`|
|P-gate, 원래 영역, P01 heading 수정 후|18/20, 17/20|(위와 같음)|(위와 같음)|`round3b_center_P-gate_P01_*`|
|**P-gate, 영역 x −0.015 이동(채택)**|**20/20, 18/20**|**19/20, 20/20**|**20/20, 16/20**|`round3c_center_P-gate_*`|
- 채택안 양팔 합계: P01 38/40(83.5–98.6%), P04 39/40(87.1–99.6%), P06 36/40(76.9–96.0%). 팔별 최저는 P06 right 16/20(80%, CI 58.4–91.9%, 실패 4회 모두 pregrasp TIMEOUT)로 기준 ≥80%를 겨우 채운다. 그래서 `reach_exclude`는 넣지 않았다.
- P01 원인과 수정: heading 스윕(`round3_center_diag_P01.jsonl`, 4샘플×양팔×8 오프셋) 결과, 기본 접근(판재 폭 가로지르기, yaw+π/2)은 중앙에서 전부 IK_FAIL이었다. 판재 길이 방향(yaw+0)은 weld 후 lift 중 접촉이 0이 돼 전부 SLIP. 대각(왼팔 yaw+3π/4, 오른팔 yaw+π/8~π/4)은 대부분 성공했다. 기존 코드는 관절 거리가 가장 작은 heading을 골라 길이 방향을 자주 택했다. 그래서 중앙 판재에 한해 "폭 방향 > 대각 > 길이 방향" 우선순위를 줬다(가중 100, 임의 지정).
- 영역 이동 근거: 원래 영역에서 P04 실패가 영역의 먼 쪽(x ≥ −0.165)에 몰렸다(left 해당 4회 중 3 실패, right 5회 중 4 실패). 크기 .08×.24는 유지했다. x 폭을 줄이면 P01(폭 .06, ±15°)이 들어가지 않는다. 새 영역 x 끝 −0.155는 트레이 외벽 x=−0.136과 0.019 m, 테이블 끝 −0.25와 0.015 m 떨어져 있어 겹치지 않는다. 이동량 0.015 m는 임의 지정이고 후보는 이것 하나만 측정했다.
- 남은 문제: 중앙 P01 weld는 항상 index+middle이었다(엄지 대향 0/38). put_aside로 중앙에 다시 놓기는 P01에서 COLLISION(빈 자리 없음)이 잦다(이동 후 left 11/20, right 5/20). 들어 올린 뒤 판재 yaw가 바뀌어 폭 .08 영역에 발자국이 안 들어가는 것으로 추정한다. P04는 원래 영역에서 집기 성공 29회 중 24회가 놓은 뒤 높이 판정에서 탈락했다(쓰러짐 추정). `layout.reach` 표(`reach.jsonl`)는 영역 이동 후 재측정하지 않았다.

## pick-from-tray / pick-from-top / 주변 물체 (P-gate, 10/10/30회, seed 10050+i, round2와 같은 물체 선택 rng)
|시험|round2(strict, 수정 전)|round3(P-gate, 수정 후)|Wilson 95%|round3 실패 유형|원자료|
|---|---:|---:|---:|---|---|
|트레이 안 집기|0/10 (pregrasp COLLISION 8)|2/10|5.7–51.0%|TIMEOUT(pregrasp, T2) 3, GRASP_SLIP lift 3(판재, index+middle weld), closure 2|`round3_tray_P-gate.jsonl`|
|적층 위 집기|1/10|4/10|16.8–68.7%|GRASP_SLIP lift 5(P05 캠락, 엄지 포함 3접촉 weld 뒤), closure 1|`round3_top_P-gate.jsonl`|
|주변 물체 있을 때 집기|3/30|17/30|39.2–72.6%|GRASP_SLIP lift 10, closure 2, IK_FAIL 1|`round3_clutter_P-gate.jsonl`|
- 트레이 보정: 진단(`wsa_round3_tray_diag.py`) 결과, 접근을 막은 원인은 손을 연 운동학 미리보기에서 엄지 끝이 트레이 바닥·테이블을 24~32 mm 파고드는 것이었다. 테이블 집기에서도 같은 일이 생기고 접촉 물리로 해결되므로, 미리보기 충돌 검사를 트레이 벽(`T*_x±`, `T*_y±`)으로만 한정했다. 이후 COLLISION 0회. 접근 높이 후보(+.012/+.024 m)는 이전 작업자 코드를 유지했다.
- 부품별: 트레이 P04 1/2, P03 1/1, P01 0/2, P02 0/3, P05 0/2. 적층 위 P04 4/5, P05 0/5. 주변 물체 P01 5/6, P02 4/7, P03 1/1, P04 5/10, P05 1/3, P06 1/3.
- round2는 strict 규칙으로 측정했으므로 모드 차이와 수정 효과가 섞여 있다. 수정 효과로 확인된 것은 트레이 COLLISION 제거뿐이다. 나머지 향상은 주로 규칙 완화 때문으로 추정한다.

## 다물체 정착·가림률 (기존 원자료, 재측정 안 함)
정착(`round2_settle.jsonl`): 생성기 dev seed 10000~10049, L1/L2 각 25, 상황 5종 각 10. 5 s 물리 후 높이 변화 >5 mm, 속도 ≥.02 m/s, 서로 파고듦 중 하나라도 있으면 실패.

|상황|장면|물체 수|실패 장면|
|---|---:|---:|---:|
|standard|10|68|0|
|missing|10|58|0|
|pretray|10|63|0|
|stacked|10|63|0|
|reach|10|65|0|
|합계|50|317(트레이 안 20, 적층 10 포함)|0 (50/50 통과)|

가림률(`round2_visibility.jsonl`): seed 10080~10103, 24장면 152물체. 헤드 카메라 세그멘테이션 픽셀 수를 perception_pose 전후로 비교.

|상황|물체|0픽셀 전→후|50픽셀 미만 전→후(임의 기준)|
|---|---:|---|---|
|standard|40|5→5|11→11|
|missing|36|3→3|4→4|
|pretray|24|1→1|2→2|
|stacked|24|2→2|3→3|
|reach|28|2→2|5→5|
|합계|152|13→13 (8.6%)|25→25 (16.4%)|
- perception_pose는 가림률을 바꾸지 않았다. 기본 자세에서 이미 팔이 헤드 시야를 가리지 않기 때문이다. 0픽셀 13개는 모두 측면 영역의 바깥쪽(|y|≈.36~.45)이다. 그중 5개의 중심을 헤드 카메라에 투영해 보니 5개 모두 이미지 밖(u<0 또는 u>640)이었다. 즉 가림이 아니라 **헤드 화각 밖**이다(나머지 8개는 같은 위치대라 같은 이유로 추정). 인식(G)에 측면 영역 바깥 끝이 헤드에 안 보인다고 알려야 한다. 전후 0.8 s 동안 물체 6개가 5 mm 넘게 움직였다(최대 31 mm, seed 10081 o6). 팔 동작이 아니라 초기 정착 때문으로 추정한다.

## 테스트
`python -m pytest tests/m2a -q` → 116 passed, 1 warning(Dash 플러그인 경고).

## 남은 문제
- P-gate 성공을 마찰 파지로 읽으면 안 된다. P01 엄지 대향 weld는 게이트 13/20, 중앙 0/38이다. P01·P04는 lift 중 접촉이 0~1개까지 떨어진다. strict 기준으로는 P01 0/20, P04 1/20이다.
- 트레이 안 집기 2/10: T2(가운데 트레이) 접근에서 TIMEOUT(손목 관절 추종 오차 ~1 rad, 원인 미확인). 트레이 안 판재는 길이 방향·대각 접근 모두 lift 중 SLIP.
- 적층 위 P05(캠락) 0/5: 엄지 포함 3접촉 weld 뒤 lift 중 SLIP.
- 중앙 치우기 배치: P01은 빈 자리 탐색 실패(COLLISION), P04는 놓은 뒤 쓰러짐(추정).
- 중앙 판재 heading 우선순위는 P01로만 측정했다. P02/P03 중앙은 측정하지 않았다.
- center_zone 이동 후 `layout.reach` 표를 재측정하지 않았다. 계획층과 생성기(C)에 영역 변경을 반영해야 한다.
- 팔 링크 충돌 off(V-A D4)는 그대로 남아 있다.
