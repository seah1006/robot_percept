# V-GA 검증 리포트: M2A 관문 G-A (G1 + Dex3 집기)

검증자 V-GA (Claude), 2026-11-26 14:05~14:20 KST. 대상은 worktree `/home/user/work/m2a_g1`의 미커밋 파일 `sim/g1_grasp_env.py`(GA1, mtime 13:51), `tools/m2a_grasp_gate.py`(GA2, mtime 13:59:03), `bench/m2a_ga/evaluation_v1/*`(14:00~14:04)이다. 계획서: `m2a_verify_plan.md`. 저장소 파일은 수정·커밋하지 않았다.

## 최종 판정: **조건부 PASS**

구현은 명세를 지키고 결과는 재현된다. 독립 재판정은 6개 조합 120회 중 5개 조합(100회)에서 GA2와 완전히 일치했다. 남은 1개 조합 **gate/board는 판정 기준에 따라 결과가 크게 달라진다**: 명세 3조건 기준 11/20, GA2 기준 2/20. 아래 조건을 붙여야 결과를 사용할 수 있다.
1. gate/board는 두 열(명세 3조건 11/20, GA2 2/20)을 함께 보고하고, 어느 기준을 채택할지 메인이 결정한다. 어느 쪽이든 12/20 가설선에는 못 미친다(11/20은 1개 차).
2. gate 성공은 weld 근사라는 점을 명시해야 한다. gate/board 성공 사례는 weld가 손가락 끝에 붙여 들고 가는 형태다(아래 V1).
3. `ga2_changes.md`가 갱신되지 않았다(튜닝·평가 이력이 없음). 메타데이터로는 실행한 코드 버전을 특정할 수 없다.

## 1. 관문 결과: 독립 재판정 vs GA2

모드·물체마다 판정 seed 1000~1019 전체 20개를 다시 돌렸다. 동결 파라미터 sha256 e7cf2599…dac7, GA2 `run_trial` 시퀀스를 사용했다. 내 판정은 매 물리 스텝(500Hz) MuJoCo 정답 상태로 내렸다.

| 모드 | 물체 | **명세 3조건 (V-GA)** | Wilson 95% | **GA2 판정** | bench raw | 불일치 seed |
|---|---|---|---|---|---|---|
| phys | board | 1/20 | 0.009–0.236 | 1/20 | 1/20 | 없음 |
| phys | dowel | 0/20 | 0.000–0.161 | 0/20 | 0/20 | 없음 |
| phys | block | **13/20** | 0.433–0.819 | 13/20 | 13/20 | 없음 |
| gate | board | **11/20** | 0.342–0.742 | **2/20** | 2/20 | 1000, 1001, 1003, 1006, 1008, 1009, 1012, 1016, 1019 |
| gate | dowel | 0/20 | 0.000–0.161 | 0/20 | 0/20 | 없음 |
| gate | block | **13/20** | 0.433–0.819 | 13/20 | 13/20 | 없음 |

- 12/20 가설선을 넘는 조합은 phys/block과 gate/block 둘이다. block은 phys와 gate의 성공 seed가 같아서 weld가 더한 것이 없다. dowel은 두 모드 모두 0/20으로, 엄지가 dowel에 닿지 않아 들어 올리지 못했다.
- 재실행한 GA2 행은 bench `raw.jsonl`과 120/120 동일했다(벽시계 시간 제외). bench의 앞 3개 seed는 `render=True`로 프레임을 저장한 실행이었는데도 같았으므로, 렌더링은 결과에 영향이 없다.
- `ik_fail`은 조합마다 1~2회(1005, 1017 등)이고 양쪽 판정이 같다.

### gate/board 불일치 9건 분석 (명세 3조건 성공, GA2 `no_contact`)
- 9건 모두 유지 2.0초 동안 최소 들림 0.0539~0.0552m(≥0.05), 테이블 접촉 0회, 손바닥 기준 drift ≤0.00032m였다. 1001샘플, 500Hz로 측정했다.
- weld가 켜진 시각은 t≈8.49~8.51s다. 시퀀스 타이밍상 닫기는 6~7s, 안정화는 7~8s, **들기는 8~9s**이므로 들기 도중에 켜졌다. 켜진 순간 정답 접촉은 엄지+검지+중지(또는 엄지+중지)였다.
- 따라서 GA2가 설명한 "20ms 샘플링이 짧은 2손가락 접촉을 놓쳤다"는 원인은 정확하지 않다. 닫기·안정화 구간에서는 엄지+검지/중지 동시 접촉이 2ms 해상도로도 성립하지 않았다(성립했다면 그때 weld가 켜졌어야 한다). 접촉은 들기 중에 처음 생겼다. GA2 judge는 정의대로 동작했고, 쟁점은 그 정의가 명세 성공 정의보다 엄격하다는 점이다.
- 명세(TASK-GA.md)의 성공은 유지 구간 3조건뿐이다. `no_contact` 코드 설명은 "닫았는데 손가락 접촉 2개 미만"이지만, 3조건을 만족한 시행을 실패로 바꾸는 규칙은 명세에 없다. 그래서 내 판단으로는 **명세 3조건 열(11/20)이 계약에 맞는 해석**이다. 다만 "닫기 시점 파지"를 요구하는 GA2 해석도 실제 파지 의미로는 근거가 있다. 메인이 결정할 사안이다.

## 2. 체크리스트 결과
| ID | 항목 | 결과 | 근거 |
|---|---|---|---|
| S1 | 기존 파일 동작 불변 | PASS | `git diff --stat b80d817 -- sim/humanoid_env.py sim/humanoid_ik.py sim/humanoid_teleop.py web/` 비어 있음. 작업트리·스테이지 diff와 untracked 모두 0 |
| S2 | 런타임 부작용 | PASS | G1GraspEnv import·생성 전후로 `build_g1_xml()` 해시, `REST`, HumanoidEnv disableflags=16(접촉 OFF), nbody 49 / ngeom 106 / nu 43 / dt 0.002가 동일 |
| S3 | 소유 범위 | PASS | 변경 경로가 모두 소유 파일, notes/m2a, bench/m2a_ga 안에 있음. 다른 worktree의 M 상태는 이전부터 있던 것(이번 작업 무관) |
| M1 | API 계약 | PASS | 시그니처 9개 일치, state() 키 10개·타입·길이 일치, 잘못된 obj는 ValueError. `pregrasp_pose` 헬퍼 제공 |
| M2 | 접촉 ON + 몸통 자기충돌 OFF | PASS | disableflags=0. 비트는 손 (1,6), 테이블 (2,5), 물체 (4,3). 손 외 로봇 geom 64개와 바닥은 전부 (0,0). 비트가 맞는 쌍은 손–물체, 손–테이블, 물체–테이블뿐. 120회 동안 비손 로봇 접촉 0 |
| M3 | 중력보상 물체 미적용 | PASS | 코드: `qfrc_applied[robot_dofs]=qfrc_bias`, 물체 6 DOF는 0. 120회 동안 물체 qfrc/xfrc 최대 0.0. 1초 정착 z 변화 <1e-10. 5cm 띄우기 시험에서 최소 vz -0.981(자유낙하 기대 -0.990) 후 테이블로 복귀(3개 물체 모두) |
| M4 | 물체 사양 | PASS | board 박스 반치수 .06/.025/.0125, 0.08kg. dowel 원기둥 r .012, 반길이 .04, 0.02kg, geom 축 z성분 1e-16(눕힘). block 반치수 .02, 0.05kg |
| M5 | 배치·결정성 | PASS | seed 0~199에서 xy 범위 0.0596/0.0598m, yaw −29.9°~29.4°. 같은 seed 반복과 새 env 모두 비트 동일 |
| G1 | gate weld 조건 | PASS (판단 메모 있음) | weld 켜짐 24회 모두 켜진 순간 정답 접촉이 엄지+(검지 또는 중지)였음(위반 0). phys에서 weld 0. reset, 허공에서 손 닫기, 반쯤 연 손으로 누르기 모두 weld 0. 해제 시험 24/24에서 `set_hand(0)` 직후 weld가 꺼지고 물체가 0.057~0.070m 낙하 |
| J1 | 독립 재판정 일치 | 5/6 조합 일치 | 위 표 참조. gate/board 9건 불일치는 판정 정의 차이(1절) |
| J2 | state() 정확성 | PASS | state() 호출마다 내 정답값과 대조: obj_pos, palm_pos, 테이블 접촉, 손가락 집합, 관통, weld 불일치 0 |
| J3 | 판정 입력 | PASS | 유지 2.0s, 내 측정 500Hz(GA2 trace는 50Hz), 시작 z는 `object_rest_pose`(reset 끝 값과 동일) |
| R1 | 재현성 | PASS | 별도 프로세스 재실행(gate/board, phys/board seed 1000~1004): 정답 trace 다이제스트와 GA2 행 10/10 비트 동일. 재실행 vs bench 120/120 동일 |
| T1 | 튜닝/판정 seed 분리 | PASS (문서 미흡) | `tuning/sweep*.jsonl` seed 0~2, `validation_*.jsonl` seed 0~99, 판정 run 메타 seeds는 정확히 1000~1019. 수정 시각 순서: 툴 13:59:03 < 동결 파라미터 13:59:23 < 첫 판정 14:00:11. 판정 이후 툴·env·파라미터 변경 없음. 6개 run의 파라미터 모두 동결본과 같음. 단 `ga2_changes.md`에는 여전히 "No tuning yet"으로 적혀 있음 |
| P1 | 관통·발산 | PASS | 손–물체 최대 관통 0.0041m(≤0.01), 손–테이블 최대 0.0049m, 비유한값 0. 팔(비트 0)–테이블 최소 거리 +0.042m(right_wrist_pitch_link)로 숨은 관통 없음 |
| V1 | 렌더 육안 | 확인 (메모) | GA2 PNG와 내 사후 렌더(정면, 측면, 근접 2각). block은 엄지와 손가락 사이에 감싸 쥐어 그럴듯함. **gate/board 성공 사례(예: 1001)는 보드가 손가락 끝 한 점에 매달린 모습으로, weld가 접착하듯 들고 감**(유지 시작 시 정답 접촉은 엄지 1개). phys/board 실패 프레임에서는 보드가 공중에서 낙하 중 |
| X1 | 테스트 | PASS | 측정 락 안에서: `tests/test_g1_grasp_env.py` 7 passed(3.1s, 기준 <60s), `tests/test_m2a_grasp_gate.py` 19 passed(0.08s, 기준 <30s), `tests/test_humanoid.py` 62 passed(25.3s) |
| X2 | 리포트 정직성 | 조건부 | summary에 "gate = contact-triggered weld approximation; oracle excluded" 표기, 6개 run 모두 Wilson 재계산 일치, mujoco 3.17.0과 seeds 기록. 단 `git_commit=b80d817, dirty=True`라 실행 코드를 특정할 수 없음(툴·env 파일 해시 권장). `ga2_changes.md` 미갱신 |

## 3. 결함·지적 사항
### GA2 (`tools/m2a_grasp_gate.py`, 노트)
- **D1 [주요, 판정 정의]** 명세 3조건을 만족해도 닫기·안정화 구간의 동시 접촉 손가락이 2개 미만이면 `no_contact`로 실패 처리한다. gate/board에서 9건, 성공 집계로 2/20 대 11/20의 차이가 난다. 원인 설명("20ms 샘플링 누락")도 부정확하다: 실제로는 들기 중(t≈8.5s)에 처음 접촉했다. 두 열 병기 또는 기준 결정이 필요하다.
- **D2 [경미, 코드 분류]** phys/board 10건은 들림이 최대 0.031~0.085m까지 갔다가 떨어졌는데(실제로는 `slip`) 우선순위 때문에 `no_contact`로 기록됐다. 성공 판정과는 무관하지만 실패 분포가 오해를 낳는다. 내 판정 코드도 같은 우선순위라, 실패 코드는 참고용으로만 봐야 한다.
- **D3 [문서]** `ga2_changes.md`가 FakeEnv 단계에 머물러 있다. 빠진 내용: 튜닝 이력(sweep, validation seed 0~99, 7/100), 동결 파라미터와 해시, 평가 명령, 결과표, D1 쟁점.
- **D4 [경미, 메타]** 메타데이터의 commit은 b80d817인데 dirty=True다. 툴·env 파일의 sha256을 같이 기록하면 결과와 코드의 대응이 확실해진다.

### GA1 (`sim/g1_grasp_env.py`)
- **E1 [경미]** 바닥이 (0,0)이라 테이블에서 밀려난 물체가 끝없이 자유낙하한다. 28회에서 z가 −20~−328m까지 내려갔다. 성공 판정은 z 기준으로 실패 처리되므로 결과는 바뀌지 않는다. 다만 `obj_table_contact`의 바닥 검사는 사실상 작동하지 않고 낙하 프레임도 부자연스럽다. 바닥에 물체 비트를 주는 것을 권장한다.
- **E2 [판단]** gate 손바닥 영역(로컬 x −0.015~0.12, 닫힘축 −0.015~0.10, |z|≤0.06)이 관대하다. 실제 weld 켜짐 지점은 닫힘축 0.067~0.093m, 손바닥 사이트까지 거리 최대 0.115m였다. 또 weld는 켜진 뒤 접촉이 사라져도 손을 열 때까지 유지되어, 손가락 끝 접착처럼 들고 가는 결과가 나온다(V1). 명세 문구("조건일 때만 활성, 손 열면 해제")를 어기지는 않지만, 근사의 강도를 결과 해석에 명시해야 한다. 개선 선택지: 유지 중 접촉 지속 요구(끊기면 해제), 또는 영역 축소.

## 4. 재현 방법
1. 원본 스크립트: `...\tmp\m2a_verify_src\`. `sync.ps1`로 `/tmp/m2a_verify`에 복사한 뒤 아래를 실행한다.
   - 정적 점검: `wsl -d Ubuntu-24.04 -- bash /tmp/m2a_verify/v_static.sh`
   - 모델 점검(락): `run_model.sh`
   - 테스트(락): `run_tests.sh`
   - 재판정(락): `run_trials.sh F_gate_board gate board 1000-1019 --params bench/m2a_ga/frozen_params_v1.json --ga2-raw 'bench/m2a_ga/evaluation_v1/*/raw.jsonl' --frames 2 --release`
   - 집계: `run_agg.sh`
2. 출력: `...\tmp\vout\` (`F_*/v_trials.jsonl`, `agg.txt`, `detail.txt`, `jsonl_audit.txt`, PNG).
3. 환경 메모: WSL 배포판이 유휴 상태에서 자동 종료되면서 tmpfs `/tmp`가 두 번 비워졌다(13:49, 14:07). 그래서 출력은 Windows 세션 tmp에 두었다. GA2의 `/tmp` 스크립트가 사라진 것도 같은 원인으로 보인다.
4. gate_block 실행: 부모 요청 명령과 동일한 명령을 GA2의 `/tmp/m2a_ga2_evaluate.sh`가 14:03:36~14:04 실행해 이미 완료했다(20행). `raw.jsonl`이 있으면 CLI가 거부하므로 다시 실행하지 않았다. 내 재실행 결과와 이 bench 결과는 20/20 동일하다.
