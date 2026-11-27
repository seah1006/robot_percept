# 작업자 E (2라운드): 디스패처 · 에피소드 러너 · 배치 평가

기준: m2a/ws-e-2, `m2a/main` 9abfc63 병합 후(파지 모드 분리). 커밋 없음. 모든 수치 원자료는 `runs/<run_id>/result.json`(에피소드별 행 + 집계)과 `episodes|plan|scene_graph|timing.jsonl`.
표기: P-gate = GT 보조 weld 파지 근사, O0 = GT 인식. **center_zone 보정 전**(A 진행 중) 결과다. 아래 어디에도 성능 주장 없음.

## 1. 변경 파일 (소유 경로만)
- `m2a/run/{dispatcher,episode,perception,perturb,batch}.py`, `tests/m2a/test_e_run.py`, `m2a/notes/wse_pytest.txt`, 본 보고서.
- 이번 라운드에서 추가/수정한 것
  1. batch: `--grasp-mode P-gate-strict`, `--no-prune`(B4 ablation), `--fake-o3`, config.json에 평가 라벨 기록.
  2. B4 **reach 가지치기**: IK_FAIL/COLLISION(전 스킬), GRASP_SLIP(집기 스킬)이 난 (팔, 위치)를 다음 계획의 `state['reach']`에서 제거해 다른 팔로 재계획. 같은 (실패 코드, 물체) 2회 연속이면 사람 호출 종료(계약 §13) 유지. (임의 설계)
  3. B4 복구 put-aside 순서: center_zone → 그 팔 쪽 영역(`{arm}_zone`) (임의 지정). 이전엔 center만 써서 recovery 29회 중 COLLISION 20·IK_FAIL 8로 막혔다(`runs/m2a-e2-prune-*`).
  4. 실패한 스킬 뒤 0.6 s 정착(`SETTLE_S`, 임의 지정) 후 관측. 놓다 실패(GRASP_SLIP)했지만 물체가 트레이 위에 떨어져 있던 경우를 정착 전에 "완료"로 오판 → FALSE_COMPLETION이던 L0 2건(`runs/m2a-e3-l0`, 10013·10015 B4)이 해소됨(10015 재실행 success).
  5. 스킬은 실패했지만 정착 후 물체가 목표 트레이 안에 관측되면 events에 `{oid,tray,t_ms}` 추가(없으면 judge가 pretray로 간주).
  6. 에피소드 fail_code: 재계획이 계획 불가로 끝나도 원인 스킬 코드를 유지(이전엔 PLAN_VIOLATION으로 덮음). 성공한 에피소드는 fail_code=None.
  7. `NoisyGTPerception`(fake O3): GT에 σ_xy 4 mm, σ_yaw 0.05 rad(임의 지정) 노이즈, 예측 oid `p0..`(에피소드 내 고정, 가정), 손 보유는 시뮬 값 사용(GT 보조), `pose_only=True` → 스킬에는 oid=None+obj_pose_T만 전달. 키프레임(초기·재계획 전) `perception_pose`/`restore` 훅, 손이 닫혀 있으면(RuntimeError) 그 자리 관측으로 폴백(scene_graph.jsonl `posed`).

## 2. 실행 명령
```
source ~/miniforge3/etc/profile.d/conda.sh && conda activate robot_percept && source /home/my/work/robot_percept/sim_test/gl_env.sh
export PYTHONPATH=.
flock -w 900 /tmp/rp_measure.lock timeout 290 python -m m2a.run.batch --workers 6 --start 10000 --end 10009 --run-id <id>   # 10장면씩 6회 = 60장면
  옵션: --grasp-mode {P-gate,P-gate-strict,P-phys,P-oracle} --perturb {drop,teleport,alternate} --level L0 --situations standard --fake-o3 --no-prune
python -m pytest tests/m2a -q   # 136 passed (m2a/notes/wse_pytest.txt), test_e_*: 18 passed
```
60장면 배분: 상황 5종 각 12장면(seed%5), 레벨은 L1 48 / L2 12(임의 지정). seed는 dev 10000~10059만 사용.

## 3. 본 배치 (dev 10000~10059, O0, P-gate=GT 보조 weld 근사, center_zone 보정 전)
원자료 `runs/m2a-e4-main-{10000,10010,...,10050}`. (e2/e3 계열은 코드 변경 전·중 실행분이라 최종은 e4 사용; 결과 형태는 동일.)

| 구성 | 성공 (Wilson 95% CI) | 엄격 | avg_progress | 거짓 완료 | fail_code | 평균 에피소드 ms |
|---|---|---|---|---|---|---|
| B0-script | 0/60 [0, 6.0%] | 0 | 0.131 | 0 | GRASP_SLIP 33, IK_FAIL 21, PLAN_VIOLATION 6 | 1.1~1.8 s |
| B1 | 0/60 [0, 6.0%] | 0 | 0.084 | 0 | GRASP_SLIP 49, IK_FAIL 9, PLAN_VIOLATION 2 | 1.4~2.1 s |
| B4 | 0/60 [0, 6.0%] | 0 | 0.087 | 0 | GRASP_SLIP 41, PLAN_VIOLATION 13, IK_FAIL 6 | 1.6~2.7 s (평균 재계획 1.3~1.8) |

상황별(각 0/12, CI [0, 24%])은 모든 구성에서 0이고 progress만 다르다: pretray 0.25(B0/B1/B4 모두), stacked 0.17/0.07/0.08, 나머지 ≤0.11. 상황×구성 15칸 전체는 `result.json`의 `aggregate`에 있다.
**결론: L1/L2 전체 목표(부품 4~6개)에서는 세 구성 모두 0이고 구성 간 비교가 불가능하다.** 원인은 아래 4절(스킬 층).

### L0 (부품 1~2개, standard) — 파이프라인이 닿는 곳
| 조건 | B1 | B4 | 원자료 |
|---|---|---|---|
| O0, P-gate, 20장면 | 6/20 [15, 52%] | 6/20 [15, 52%] (거짓 완료 1) | `runs/m2a-e6-l0-o0` |
| O0, P-oracle(DEBUG 성능 아님), 20장면 | 9/20 [26, 66%] | 9/20 (거짓 완료 2) | `runs/m2a-e5-l0-oracle` |
| fake-O3(GT+노이즈), P-gate, 20장면 | 8/20 [22, 61%] | 8/20 [22, 61%] | `runs/m2a-e6-l0-fako3` |

## 4. P-oracle 디버그 검증 (DEBUG: P-oracle, 성능 아님) dev 10000~10019
`runs/m2a-e4-debug-{10000,10010}` (20장면 × 3구성):

| 구성 | 성공 | 엄격 | progress | fail_code |
|---|---|---|---|---|
| B0-script | 1/20 | 1 | 0.173 | IK_FAIL 12, GRASP_SLIP 3, PLAN_VIOLATION 4 |
| B1 | 1/20 | 1 | 0.187 | IK_FAIL 16, PLAN_VIOLATION 2, GRASP_SLIP 1 |
| B4 | 0/20 | 0 | 0.103 | IK_FAIL 10, PLAN_VIOLATION 9, GRASP_SLIP 1 |

**기대(B1·B4 거의 성공)와 다르다.** 층별 원인(원자료: `runs/m2a-e2-debug-*`·`m2a-e2-main-*` B1 에피소드 스킬 집계):
- 계획층: 계획·검증기는 200/200 viable, 오류 없음(plan.jsonl `verification.ok`). 문제 아님.
- 디스패처층: 매핑·events·재계획은 단위 테스트와 L0에서 정상. 문제 아님(수정 4~6은 B4 보강).
- **스킬 IK층(A 영역)**: P-oracle에서 집기는 거의 성공(grasp_lift 약 42/43)이지만 `transport_place`가 IK_FAIL 약 14/38 (left→T1 6/13 실패, left→T2 4/8, right→T1·T2도 실패; 기호 reach는 영역 집계라 개별 자세 IK를 못 보장 = 계약 §7). 이송 자세가 집을 때 고정한 손목 R을 그대로 써서 트레이 위치에 안 닿는 것으로 **추정**. 또 `reach_pregrasp` P04 IK_FAIL 2, 트레이에서 P01 COLLISION 1.
- 놓기 판정층(C): 정착·판정 불일치는 L0 FALSE_COMPLETION 케이스 외 관찰 없음(수정 4로 해소).
- 부품 6개가 모두 성공해야 하는 목표에서 부품당 성공이 약 50~60%면 전체 성공률은 수% 이하가 된다(산수, 추정).
- B4가 B1보다 낮은 것(0/20 vs 1/20)은 CI가 전부 겹치는 노이즈이며, 같은 IK_FAIL을 만난 B4가 복구로 물체를 center/옆 영역에 옮겨 놓다 상태를 흩뜨리는 비용도 있다(추정).
- P-gate(60장면) 실패는 GRASP_SLIP이 압도적: grasp_lift GRASP_SLIP이 P02 7/15(left_zone), P04 7/11, **P05 5/5와 5/5(양팔)**, center_zone P01/P02 0/2씩. A가 검증한 부품은 P01/P04/P06뿐이다(`m2a-e2-main-*` B1).

## 5. 교란 (a) 낙하 (b) 순간이동, 10장면 alternate(짝수 seed=drop, 홀수=teleport)
전체 목표(L1/L2, dev 10000~10009) B1 vs B4는 둘 다 0/10(progress 0.045)이라 구분 불가(`runs/m2a-e4-pert-{gate,oracle}`). 그래서 **L0 20장면**으로 비교:

| 조건 | B1 | B4 | 원자료 |
|---|---|---|---|
| P-oracle(DEBUG), L0 20장면 | 5/20 [11, 47%] progress 0.25 | **9/20** [26, 66%] progress 0.45 | `runs/m2a-e5-l0pert-oracle` |
| P-gate, L0 20장면 | 3/20 [5, 36%] progress 0.15 | **7/20** [18, 57%] progress 0.35 | `runs/m2a-e5-l0pert-gate` |

B4가 두 조건 모두 +4건. CI는 겹치므로(n=20) 방향성 증거이지 유의 결과는 아니다. 같은 장면에서 교란 없는 O0 기준 B1은 6/20(P-gate), 9/20(P-oracle)이라 B4(교란 시 7/20, 9/20)는 거의 기준선까지 회복한 셈이다. 낙하는 events 등록이 안 된 채 B4가 mismatch(held 불일치)로 재계획·재집기, 순간이동은 영역 변경 mismatch로 재계획(`plan.jsonl`의 `trigger`).

## 6. O3 경로 (fake O3, G의 `m2a.percept.o3` 미병합)
- `Perception` 프로토콜(`observe/refine_target/pose_only`). O3 모드(`pose_only=True`)에서는 예측 oid를 스킬에 보내지 않고 `oid=None, obj_pose_T`만 전달(테스트 `test_o3_predicted_oid_never_sent_to_skill`, sim 테스트 `test_sim_noisy_o3_uses_pose_path_not_gt_oid`). place는 oid=None(팔이 든 물체). 판정용 events는 평가측 `grasped_oid`로 GT oid 기록(평가 전용, 스킬 입력 아님).
- 결과: L0 fake-O3 B1/B4 각 8/20 (위 표). L1/L2 10장면은 `runs/m2a-e6-fako3` B1 0/10, B4 0/10 (progress 0.12/0.095).
- **G에게 요청**: 예측 oid가 관측 간 안정적이어야 한다(B4 mismatch 판정이 oid 기준). 불안정하면 매 관측이 MISID/appeared로 오판됨을 실측(`runs/m2a-e4-fako3`: 예측 id를 매번 섞었을 때 B4 MISID 9/10). 안정 ID가 어렵다면 위치 매칭 기반 id 부여를 어댑터 쪽에 넣어 달라.

## 7. 로그 스키마 점검
`runs/<id>/{config.json, episodes.jsonl, plan.jsonl, scene_graph.jsonl, timing.jsonl, result.json}` 존재·내용 확인(테스트 `test_events_and_schema`). fail_code는 계약 8종 집합 안(`FAIL_CODES` 검증). config.json에 jobs, commit, layout sha, 평가 라벨.

## 8. 요청 · 남은 문제
- **A**: (1) `transport_place`/`put_aside` IK_FAIL(특히 left→T1, T2) — 집을 때의 손목 R 고정이 원인인지 확인하고 이송 자세 재탐색 허용. (2) P02/P05 파지 프로파일(P-gate에서 P05 0/10). (3) center_zone 보정, 복구 put-aside의 `_empty_slot` None→COLLISION 처리.
- **B**: 영역 `reach`가 개별 자세 IK보다 낙관적이다. 최소한 트레이 reach를 팔별 실측으로 보수화하면 B4 가지치기가 덜 필요함.
- **C**: 판정의 `unsettled`는 정착 시간 의존. 현재 러너가 0.6 s 정착 후 관측하는 것과 맞는지 확인.
- **G**: 예측 oid 안정성(6절), O3 어댑터의 held 정보 출처.
- 열린 일: 본 배치 L1/L2 0/60이라 B0/B1/B4 구성 비교는 A의 스킬 개선 후 재실행 필요(같은 명령, 약 10분). 교란 비교는 L0(n=20)뿐이라 CI가 넓다. `P-gate-strict`와의 비교, B1c 구성 배치, test seed는 실행하지 않음.

## 9. 면접 설명 (3줄)
- 무엇: PDDL 계획의 각 액션을 스킬 호출로 풀어 실행하고, 매 스킬 뒤 관측과 기대 효과를 비교해 실패·이탈이면 B4가 상태를 다시 읽어 재계획하는 폐루프 러너와 배치 평가기.
- 왜: 계획이 맞아도 실행이 어긋나므로, 이탈을 감지·복구하는 층(관측 비교, 재계획 상한 R=3, 같은 실패 반복 시 종료)이 있어야 성공 지표가 의미를 가진다.
- 대안 대비: 스크립트 재생(B0)·무감시(B1)보다 복구가 가능하지만(L0 교란 +4건) 시간이 1.2~2배 들고, 스킬 층이 약하면 전체 성공률은 이 층에서 막힌다(본 배치 0/60이 그 증거).
