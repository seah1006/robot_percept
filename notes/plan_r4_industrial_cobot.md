# r4 계획서 v3: 유일 산업용·협동로봇 추가와 기구학 데이터 시각화

> **2026-11-09 방향 변경:** 이 계획은 r5 "자연어 지시 기반 범용 피킹 셀"(notes/plan_r5_grounded_picking_cell.md)의 5단계 티칭·디버깅 탭으로 흡수·축소됨. 단독 진행하지 않음.


작성 2026-11-09 부모(1NIgF2z2BvfBSkOh). v3는 검토자 R4-C(Claude Sonnet, 사용자·교육 관점)·R4-O(Claude Opus, 구현 관점) 합의안 반영(notes/plan_r4_review_c.md, notes/plan_r4_review_o.md). Codex 검토(R4-X)는 사용량 한도로 미실시 → 리셋 후 2차 확인 예정.
근거: notes/yuil_specs.md(카탈로그 치수·사양), notes/TEAM_R3.md(작업 규칙).

## 1. 목표
웹에서 **산업용 다관절**과 **협동로봇**을 골라 기구학 데이터(DH, 변환 행렬, 특이점, IK, 작업 영역)를 직관적으로 보고 비교한다. 초보자도 따라올 수 있는 순서로 보여주고, 교수님 앞 3분 시연과 면접 설명에 바로 쓸 수 있게 한다.

## 2. 결정 사항
- MuJoCo 생태계 유지, Isaac Sim 미사용(최소 RTX 4080·16GB VRAM, WSL2 미지원, NVIDIA 전용).
- 로봇(가반하중 12kg): **유일 YMX-1210(산업용)**, **유일 YBL-A612(협동)**. 검증 기준 모델 **UR5e**(Menagerie)는 메뉴에 '검증 기준 모델'로 표기해 노출.
- 12kg로 맞췄지만 작업 반경이 달라(1420 vs 1324mm) 완전히 같은 조건은 아님을 화면에 명시.

## 3. 치수 해석 (R4-O 검산)
- **YMX(확정)**: 1210·2510·14200·9200·9200L에서 H=A+C+√(D²+E²), G=H−A, I=G−A, J=B+C+D, L=J+K가 정확히 성립 → a1=A, 설치면→J2=B, a2=C, a3=D(J3 위 오프셋), d4=E, d6=F. (YMX-5200 행은 I·L 불일치 → 카탈로그 오타 추정)
  - **최대 반경 1420mm는 손목 중심 기준**(플랜지 기준이면 약 1533mm). 화면·합격 기준에 기준점 명시.
- **YBL(부분 확정)**: D=d5는 4모델 모두 G=B+C+D로 확정. E·F 중 d4(측면 오프셋)/d6(플랜지) 배정은 치수표만으론 결정 불가 → 기본 **O-1: d4=F, d6=E**('추정' 표기), 대안 O-2(d4=E, d6=F)를 문서에 병기. 카탈로그 정면도로 확인되면 확정.
- J1~J5 각도 한계·속도·질량은 카탈로그 미기재 → 가정값. 작업영역 치수(YMX K·M, YBL H~L)로 J2·J3 한계를 역추정.

## 4. 값 표기 원칙 (정직성)
값마다 출처 배지 3종: `카탈로그 p.NN`(사실) / `치수표 해석`(추정 포함) / `가정값`(다른 색, "카탈로그 미기재"). 화면·README 상시 문구: "유일로보틱스 카탈로그 치수 기반 근사 모델 · 비제휴·비공식 · 공식 CAD 아님 · 성능·안전 보증 아님". 상표는 제품 식별용으로만, 로고·카탈로그 그림·PDF는 저장소 미포함.

## 5. 구조 (단순화)
- **서버 렌더 없음**: 3D는 브라우저 three.js가 그린다(기존 vendor 사용). 서버는 Flask 안의 numpy `ArmRuntime`(DH·FK·IK·특이점)만 수행 → GL 의존 없음, 집 AMD PC에서도 동작. MuJoCo 오프스크린 렌더 워커는 v2.
- 데이터: FK/IK 요청은 POST 응답으로 즉시, 상태는 `/status/ws`에 'arm' 빌더 추가(10Hz, 약 2.1KB/회, 직렬화 ~0.6ms).
- 모델 정의: `tools/yuil_mjcf.py`가 치수로 DH 표·MJCF를 생성(`assets/yuil/`), MJCF는 FK 교차검증·향후 MuJoCo 렌더용.
- 기구학: `sim/arm_kinematics.py`(DH, Aᵢ·T0i, 자코비안, σmin·조작성, 특이점 판정, **해석해 IK(최대 8해) 우선 + DLS 수치해 보조**). sim/humanoid_ik.py는 G1 전용이라 공식만 참고해 새로 작성.
- 화면: `web/static/arm.js`·`arm.css`. 로봇 선택 `<select>`는 `web/static/humanoid.js`가 만들고 있어 최소 패치 필요.

## 6. 화면 — MVP 우선순위
| 순서 | 기능 | 비고 |
|-|-|-|
| 1 | 3D 뷰(관절 좌표축·이름), DH 표(파라미터 툴팁), 변환 행렬 A1~A6·T01…T06 | FK 슬라이더 |
| 2 | **Aᵢ 누적 스텝퍼**: 관절을 하나씩 선택하면 Aᵢ가 T에 곱해지며 좌표계가 쌓이는 과정 표시(브라우저 계산) | 교육 핵심 |
| 3 | 특이점 경고(σmin/해석 det, 히스테리시스) + 손목 특이점 시각화 | 시연 핵심 |
| 4 | IK(숫자 입력, 해 8개 중 선택·전환, 반복별 오차) | |
| 5 | 두 로봇 비교: 카탈로그 사양, 작업영역 단면, 조작성 분포 히스토그램(오프라인 사전계산 JSON), J6 속도비 420:180°/s | |
| 6 | 자코비안 히트맵 | 후순위 |
| v2 | 같은 경로 소요시간, 3D 목표 드래그, CSV 내보내기, 그래프, 작업영역 점구름, 서버 MuJoCo 렌더 | |

**시연 프리셋 4개**(JSON 고정, pytest 회귀): ① 홈 자세 ② 손목 특이점(θ5→0) ③ 팔 완전 신장 ④ 같은 목표로 두 로봇 IK 비교.

## 7. 단계
| 단계 | 내용 | 공유 파일 |
|-|-|-|
| B0 | 범용 DH·FK 모듈 + UR5e 검증(치수 해석과 무관, A와 병행) | 없음 |
| A | YMX·YBL 치수 확정(대안 O-1/O-2), 가정값 문서화, MJCF 생성 | 없음 |
| B | 자코비안·특이점·해석해/수치해 IK, 프리셋, 단위 테스트, **payload 계약 고정** | 없음 |
| C | ArmRuntime + `/arm/*` API + `/status/ws` 'arm' | web/app.py, web/realtime.py |
| D | 화면 MVP 1~5 (B의 계약으로 목업부터 병행) | web/static/humanoid.js(select), index.html |
| E | 독립 검증, README, 한계 문서 | |
예상: A 0.5일, B0+B 1~1.5일, C 0.5일, D 1.5~2일, E 1일(약 5일).

## 8. 합격 기준 (검증자가 직접 재현한 원자료로만 PASS)
- **작업영역 재현**: 관절 한계 포함 FK 몬테카를로로 카탈로그 작업영역 치수(YMX I·J·L, YBL H·K) ±2%. (같은 치수로 만든 모델의 최대 반경 비교는 항상 통과하므로 기준에서 제외, 참고값으로만 손목 중심 1420/1324 확인)
- **FK 정확도**: 생성 DH vs 생성 MJCF ≤1µm·≤1e-6rad(1000자세, 생성기 회귀 검사). UR5e는 MJCF에서 추출한 DH와 ≤1µm, 제조사 공개 DH와의 차이는 별도 보고(≤1mm, Menagerie 모델 차이 최대 약 0.7mm·베이스 180° 회전 반영).
- **자코비안**: 수치미분 대비 상대오차 ≤1e-6.
- **IK**: 목표는 무작위 관절각의 FK로 생성, 성공 = 위치 ≤0.1mm·자세 ≤1e-3rad. 해석해 성공 100%·p95 ≤1ms, 해석해 8개 전부 FK 역검증; 수치해 ≥98%·p95 ≤10ms, 수치해가 해석해 중 하나와 일치; 해 선택 결정론, 직선 경로에서 분기 점프 없음.
- **특이점**: 정답은 해석 det 인수 또는 σmin; 특이 자세 100% 경고, 일반 자세 오경고 ≤1%(히스테리시스 밴드 ε1~2ε1 제외).
- **안전·입력**: 관절 한계 위반 0, 범위 밖·잘못된 입력 400, origin 검사, 단순 형상 자기충돌·바닥 '경고'(회피 아님).
- **체감**: 슬라이더→행렬 갱신 브라우저 측정 p95 ≤100ms, HTTP 왕복 p95 ≤100ms, 브라우저 렌더 ≥29.7fps(30초 창), 1280×720 스크린샷 체크리스트(한 화면 구성, 근사·비제휴 문구 상시 노출, 가정값 배지), 프리셋 4개 재현.
- **회귀**: 전체 pytest 통과, 기존 Panda·G1 기능 회귀 없음.

## 9. 팀·파일
| 역할 | 모델 | 포트 | 소유 |
|-|-|-|-|
| 구현 I-A | Codex | 5096 | tools/yuil_mjcf.py, assets/yuil/, sim/arm_kinematics.py, web/arm*.py, web/static/arm.*, tests/test_arm.py, notes/arm_changes.md |
| 검증 V-A | Claude | 5097 | bench/verify_a/, notes/verify_a.md |
공유 파일(web/app.py, web/realtime.py, web/static/humanoid.js, index.html)은 P1c(S 페어)와 순서 조율: **B0·A·B는 즉시 병행, C·D의 공유 파일 수정은 P1c 다음 동결(c6) 이후**에 한 번에 최소 패치. 측정 규칙은 notes/TEAM_R3.md.

## 10. 위험
| 위험 | 대응 |
|-|-|
| YBL E·F 배정 오류 | 대안 O-1/O-2 문서화·'추정' 표기, 정면도 확인 시 확정 |
| 근사 모델을 실제 제품으로 오해 | 상시 문구·출처 배지 |
| 상표·저작권 | 식별용 표기만, 로고·그림·PDF 미포함, 최소 인용+출처 |
| 공유 파일 충돌 | 위 순서 규칙, 한 번에 한 구현자 |
| 패널 과다로 체감 저하 | MVP 순서, 숨긴 패널 갱신 중지, 무거운 통계는 오프라인 사전계산 |

## 11. 사용자 확인 필요
1. 로봇 조합 YMX-1210 + YBL-A612 유지? (검토자 권장: 유지)
2. YBL E·F 배정: 카탈로그 정면도로 확인 가능하면 알려주기(없으면 O-1 '추정'으로 진행)
3. 진행 순서: B0·A·B는 r3와 병행, 화면 연결은 P1c 다음 동결 이후 — 괜찮은지
4. 유일로보틱스 STEP(CAD) 문의 여부(받기 전에는 실제 외형 사용 안 함)

## 12. [대기] Codex 2차 검토 (착수 전 필수)
상태: **미실시**. 2026-11-09 R4-X(Codex gpt-6.1-sol)가 사용량 한도로 시작하지 못해, 구현 관점 검토를 R4-O(Claude Opus)가 대신함. 구현(I-A)을 Codex가 맡으므로 착수 전에 Codex의 2차 검토를 받는다.
- 결과 파일: notes/plan_r4_review_x.md (Codex만 작성)
- 통과 조건: Codex가 v3를 '구현 가능'으로 판정하거나, 지적이 v4에 반영되고 R4-C/R4-O(또는 새 Claude 검토자)와 이견이 정리될 것.
- Codex 검토자에게 줄 지시문:
```
너는 robot_percept r4 계획서 2차 검토자 R4-X(Codex, 구현자 관점)다. 한국어. 읽기 전용(코드·서버·카메라 실행 금지, 가벼운 git/grep/파일 읽기·짧은 python 계산만). 쓰기는 notes/plan_r4_review_x.md 하나만. 사용자 5080 서버 금지.
읽을 것: notes/plan_r4_industrial_cobot.md(v3, 검토 대상), notes/plan_r4_review_c.md, notes/plan_r4_review_o.md(1차 합의), notes/yuil_specs.md, notes/TEAM_R3.md, notes/HANDOFF_R3.md, 참고 코드 web/app.py, web/realtime.py, web/static/humanoid.js, web/templates/index.html, sim/humanoid_ik.py, assets/mujoco_menagerie/universal_robots_ur5e/.
확인할 것: (1) 1차 합의의 치수 해석(YMX 5모델 관계식, YBL D=d5, E/F 대안 O-1/O-2)과 UR5e MJCF-DH 차이(최대 0.7mm·베이스 180°)를 직접 재계산, (2) 구조(three.js 렌더 + Flask numpy ArmRuntime + /status/ws 'arm' 10Hz)의 구현 난이도·누락(three.js 로봇 형상 생성 방식, payload 계약, 해석해 IK 8해 구현), (3) 합격 기준이 구현자 입장에서 측정 가능한지와 소요(약 5일) 현실성, (4) 공유 파일(app.py, realtime.py, humanoid.js, index.html) 패치 범위와 P1c와의 순서, (5) 빠진 것·과한 것.
1차 검토자와 이견이 있으면 해당 근거를 명시하고, 가능하면 Claude 검토자(부모가 task id 전달)와 message_agent로 1회 이상 왕복해 해소. 최종: notes/plan_r4_review_x.md에 판정(구현 가능/수정 필요)·항목별 지적·수정안, 최종 응답은 요약 30줄 이내.
```
