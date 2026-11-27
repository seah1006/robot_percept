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


---

# 작업자 E (3라운드): 실제 O3 연결 · B1c · 재현 스크립트

기준: worktree `~/work/rp_m2a_e3`, 브랜치 `m2a/ws-e-3`, 베이스 main 182469d, 커밋 없음. 표기: O0 = GT 인식, O3 = 시뮬 렌더 예측 인식(실사 근거 아님), P-gate = GT 보조 weld 파지 근사. 모든 배치는 **스킬 A4 중간판(main 182469d 포함 bd3e123) 조건**이며 A4 최종 병합 전이다. dev seed 10000~10059만 사용. 원자료: `m2a/notes/wse_runs/<run-id>/{result.json,config.json,repro.txt}`, 표: `m2a/notes/wse_tables/*_a4mid3.md`.

## 1. 변경 파일 (소유 경로만)
- 신규: `m2a/run/o3_perception.py`(IdTracker, O3Perception), `m2a/run/embed_server.py`(DINOv2-S 별도 CPU 프로세스), `m2a/run/analyze.py`(표·층 귀속·쌍체 부트스트랩), `m2a/run/diag_missing.py`, `m2a/run/repro_batch.sh`, `tests/m2a/test_e_o3.py`, `m2a/notes/wse_tables/`.
- 수정: `m2a/run/episode.py`(B1c, MISID 기록, fail_code 접기, 키프레임 정책), `m2a/run/perception.py`(Observation.meta, `held_from_env`), `m2a/run/batch.py`(`--perception {O0,fake-O3,O3-depth,O3-knn}`, `--skill-label`, 집계에 misid/원 reason 추가), `tests/m2a/test_e_run.py`(키프레임 수 단언 1줄), `m2a/notes/wse_pytest.txt`.

## 2. O3 연결과 지속 oid
- `O3Perception`(= `m2a.percept.o3.O3.perceive(env)`, 워커당 O3 1개 재사용)이 키프레임마다 `perception_pose` 훅 아래에서 헤드 RGB-D를 예측해 기호 상태를 만든다. 구성은 G 권장대로 **깊이 plateau + DINOv2-S kNN**(`O3-knn`; 갤러리 `~/m2a_data/percept/train_dinov2_gallery.npz`는 train 전용). DINOv2는 `robot_percept_rocm` env의 **별도 프로세스, device=cpu**(GPU 미사용, OMP 2스레드)로 돌려 EGL 렌더와 분리했다(`embed_server.py`). `O3-depth`(임베더 없음)도 선택 가능(Top-1 72.4% vs kNN 79.3%, wsg_report).
- **지속 id(`IdTracker`, 임계는 임의 지정)**: ① part_id 일치 + xy ≤ 3 cm를 헝가리안(scipy)으로 재연결 → 안정 id q0,q1.. ② 계획이 방금 옮긴 물체(성공한 place/put-aside 직후)는 같은 part_id의 미매칭 예측에 거리 무관 재연결 ③ 그 외 미매칭 트랙(연속 3회까지)도 같은 part_id면 거리 무관 재연결(외부 이동 대비; 다른 part_id는 절대 안 이음 = 분류가 뒤집히면 disappeared+appeared) ④ 들고 있는 물체는 동결: 잡을 때 의도한 안정 id를 유지하고, 손(ee) 9 cm 안 예측은 제거. 트레이 안 물체는 일반 예측과 동일하게 추적(in_tray 술어).
- 계획·스킬에는 안정 id와 `obj_pose_T`만 간다(`pose_only`, 스킬엔 oid=None). GT는 ① 손 보유 여부 센서 대용(GT 보조) ② 평가 전용 `Observation.meta`(안정 id↔GT 매칭 3 cm 헝가리안, missed_gt/false_pos/wrong_part)에만 쓴다.
- **MISID 기록**: grasp_lift 성공 시 `grasped_oid`(GT, 평가 전용) ≠ 의도한 안정 id의 GT 매칭이면 `episodes.jsonl`의 `misid=true`, 에피소드 `percept.misid/misid_events`. 에피소드 fail_code는 "첫 이상 사건이 MISID"이고 실패일 때 MISID.
- 추가한 완화책(원인은 5절): 모든 post_skill 읽기를 키프레임으로(양손 열림·비었을 때만 perception_pose, 아니면 제자리), pose 시간 1.6 s(임의 지정), 팔 자기모델 마스크(팔이 파킹 위치에서 5 cm 넘게 벗어난 동안 팔·손 링크 xy 8 cm 안 예측 삭제), 팔 뒤에 가려진 트랙은 18 cm 안이면 직전 상태 이월(`meta.occluded_carried`).

## 3. B1c (폐루프 IK)
각 pick(reach_pregrasp) 직전에 키프레임 재인식(`pre_pick`) → 대상 안정 id의 obj_pose_T를 갱신해 reach와 이어지는 grasp_lift에 사용. 다른 스킬은 재인식하지 않는다(이전 구현은 모든 스킬 전에 재인식했음 → 지시대로 pick 직전만). **O0에서는 스킬이 현재 GT 자세를 직접 읽으므로 B1c = B1**: L0 20장면에서 둘 다 14/20·progress 0.700·동일 fail_code(`e3-b1c-o0-a4mid3`), 단위 테스트로도 스킬 호출열 동일 확인.

## 4. fail_code 접기 규칙 (P2)
계약 §13 목록에 COLLISION이 없다. 규칙: **COLLISION → IK_FAIL**(충돌 없는 실행 가능한 운동을 못 만든 스킬 실패), 그 밖의 미지 코드 → PLAN_VIOLATION. 스킬 원 코드는 `episodes.jsonl`의 `reason_code`와 에피소드 결과 `raw_reason_code`(마지막 실패 스킬)에 그대로 남고, 배치 집계에 `raw_reason_codes`가 있다. (예: O3 dev60에서 마지막 실패 스킬이 COLLISION인 에피소드는 B1 2 / B1c 1 / B4 6건이고, 에피소드 fail_code가 스킬 실패 기원이면 IK_FAIL로 집계된다.)

## 5. 스모크: O3(knn) + B1/B1c/B4, L0 standard 20장면 (`e3-smoke-o3knn-a4mid3`)
| 구성 | 성공 (Wilson 95% CI) | 엄격 | progress | 거짓 완료 | MISID | fail_code(원인 층) |
|---|---|---:|---:|---:|---|---|
| B1 | 4/20 [8.1, 41.6%] | 4 | 0.200 | 10 | 1 | FALSE_COMPLETION 10, GRASP_SLIP 5, IK_FAIL 1 (인식 10 / 스킬 6) |
| B1c | 7/20 [18.1, 56.7%] | 7 | 0.350 | 10 | 1 | FALSE_COMPLETION 10, GRASP_SLIP 2, IK_FAIL 1 (인식 10 / 스킬 3) |
| B4 | 4/20 [8.1, 41.6%] | 4 | 0.200 | 9 | 1 | FALSE_COMPLETION 9, MISID 1, GRASP_SLIP 5, IK_FAIL 1 |
쌍체(같은 20장면, 부트스트랩 10000회 95% CI, 임의 지정): B1c−B1 성공 +0.150 [0.000, +0.300], B4−B1 0.000 [0, 0].
- 인식 분포(초기 관측, 20장면 GT 60개): GT 미검출 32(헤드 화각 밖이 대부분 추정), 거짓 양성 11, 맞게 매칭됐지만 part_id 오분류 5. **PERCEPT_MISS가 에피소드 코드로 남은 건 0**(B4 중 신규 appeared/disappeared 오탐은 중간 진단에서 제거됨, 5절 아래).
- **FALSE_COMPLETION 10/20의 정체**: 스킬 0회, "필요 부품이 없다"고 보고(`missing_report_mismatch`). 목표 부품이 GT로는 있는데 인식이 놓쳐(미검출 7, 오분류 3; `m2a/run/diag_missing.py`, 대부분 |y|≈0.30~0.43 영역 가장자리) 계획기가 부재로 판단한 것이다. 판정기 정의상 FALSE_COMPLETION이지만 원인 층은 **인식**(analyze의 "실패 층" 열).

## 6. 본 배치 (dev 10000~10059, 스킬 A4 중간판)
### O0 (`e3-main-o0-a4mid3`, 상황 5종 × 12장면, L1 48 / L2 12)
| 구성 | 성공 | 엄격 | progress | 거짓 완료 | fail_code | 평균 s |
|---|---|---:|---:|---:|---|---:|
| B0-script | 4/60 [2.6, 15.9%] | 4 | 0.237 | 2 | IK_FAIL 27, GRASP_SLIP 26, FALSE_COMPLETION 2, TIMEOUT 1 | 1.7 |
| B1 | 2/60 [0.9, 11.4%] | 2 | 0.178 | 1 | IK_FAIL 30, GRASP_SLIP 27, FALSE_COMPLETION 1 | 1.9 |
| B4 | 1/60 [0.3, 8.9%] | 1 | 0.157 | 0 | GRASP_SLIP 28, IK_FAIL 26, PLAN_VIOLATION 5 | 3.0 |
(합계는 상황별 12장면 표를 더한 값이며 `analyze`를 `--by` 없이 실행해도 같다. 상황별 표(15칸)는 `m2a/notes/wse_tables/main_o0_a4mid3.md`.) 쌍체 B4−B1(60장면): 성공 −0.017 [−0.050, 0.000], progress −0.021 [−0.058, 0.000]. **스킬 층(GRASP_SLIP·IK_FAIL) 실패가 100%**라 구성 비교는 여전히 불가능하다.

### O3-knn (`e3-main-o3knn-a4mid3`)
세 구성 모두 **0/60 [0.0, 6.0%]**(엄격 0), progress B1 0.073 / B1c 0.081 / B4 0.059(상황별 표: `main_o3knn_a4mid3.md`). 거짓 완료 B1 3 / B1c 5 / B4 2, fail_code 합: B1 GRASP_SLIP 45·IK_FAIL 12·FALSE_COMPLETION 3, B1c GRASP_SLIP 40·IK_FAIL 10·PERCEPT_MISS 5·FALSE_COMPLETION 5, B4 GRASP_SLIP 35·IK_FAIL 7·PERCEPT_MISS 11·PLAN_VIOLATION 5·FALSE_COMPLETION 2. 마지막 실패 스킬의 원 reason_code 기준 COLLISION은 B1 2 / B1c 1 / B4 6건(에피소드 fail_code는 접힘 규칙대로 IK_FAIL 또는 다른 코드). 쌍체: B1c−B1 성공 0.000 [0,0], progress +0.008 [−0.015, +0.031]; B4−B1 성공 0.000, progress −0.014 [−0.033, +0.003]. 평균 에피소드 시간 5.3~11.4 s(O0의 3~5배; 인식 키프레임당 CPU DINOv2 포함).
- 인식(B1 60장면, GT 317개): 초기 미검출 95(30%), 거짓 양성 19, 매칭된 것 중 오분류 50(약 22%), MISID 집기는 구성 합 2건(B1 0 / B1c 1 / B4 1).

### L0 교란 (O0, `e3-l0pert-o0-a4mid3`, 20장면 alternate drop/teleport)
B1 7/20 [18.1, 56.7%] progress 0.400 vs **B4 11/20 [34.2, 74.2%] progress 0.550**; 쌍체 B4−B1 성공 +0.200 [−0.050, +0.450](CI가 0을 포함 → 방향성). 같은 장면·교란 없는 O0 B1(L0 20장면)은 14/20.

## 7. 층별 실패 분석
- **스킬 층(A)**: 본 배치 실패의 압도적 다수. O0 dev60 3구성 모두 GRASP_SLIP+IK_FAIL이 사실상 전부, O3 dev60도 B1에서 에피소드 60 중 57이 첫 이상 사건이 스킬 실패. 부품 4~6개 전부를 맞춰야 하는 L1/L2 목표에서는 부품당 성공률이 낮아 합이 0%가 된다(스킬 단독 L0 14/20 → 곱셈 효과는 추정).
- **인식 층(G)**: L0 O3의 실패 중 절반(10/20)이 위 "부재 오보고"(미검출·오분류)이고 O3에서만 생김. 헤드 화각(A4 수정 중)과 판재 가장자리 잘림이 원인으로 추정. MISID 집기는 드묾(2/…).
- **계획 층(B)**: 계획·검증 자체의 실패는 B4의 PLAN_VIOLATION(O0 5, O3 5)뿐이며 대부분 B4 가지치기 후 도달 불가 판정(`reach` 상황). 계획기 오류는 아님.
- **디스패처/관측 층(E)**: O3에서 PERCEPT_MISS 오탐이 크게 두 갈래였음(아래), 완화 후 B4 PERCEPT_MISS 11/60·B1c 5/60이 남음(잔여는 스킬 후 팔이 못 빠진 상태의 오검출·미검출로 추정).

### 진단: 스킬 후 perception_pose가 팔을 시야 밖으로 못 옮김 (A4/sim 요청)
재현 `tmp` 스크립트 요지: dev 10000 L2, 왼팔 reach_pregrasp 후 `env.perception_pose(secs)`가 secs 0.6/1.6/3.0 모두 ctrl은 파킹값인데 관절 q는 목표와 ~0.5 rad 어긋난 채 정지(손 z≈0.06, 헤드 영상에 손이 보임). 초기 키프레임(팔이 이미 파킹)에서는 정상. 그 결과 중간 실행(`e3-main-o3knn-a4mid`, a4mid2)에서 B4 PERCEPT_MISS가 상황당 4~9/12였고 대부분 팔·손이 phantom 물체(`region None`/트레이 위)로 appeared. 이 라운드의 마스크·이월은 우회책이다. **요청(A4/메인): perception_pose 복귀 신뢰성(충돌/정지 원인) 확인.** 원자료 비교: `e3-main-o3knn-a4mid`(완화 전) → `-a4mid2`(post_skill 키프레임) → `-a4mid3`(마스크·이월 포함 최종).

## 8. 재현 (`m2a/run/repro_batch.sh`)
```
source ~/miniforge3/etc/profile.d/conda.sh && conda activate robot_percept && source /home/my/work/robot_percept/sim_test/gl_env.sh
cd ~/work/rp_m2a_e3 && WORKERS=4 bash m2a/run/repro_batch.sh all a4mid3 "A4 중간판"   # 단계: smoke|main-o0|main-o3|l0pert|b1c-o0|tables|all
```
각 단계는 `runs/<id>/repro.txt`에 커밋 해시·dirty 파일 수·정확한 명령을 쓰고 `m2a/notes/wse_runs/<id>/`로 result.json·config.json·repro.txt를 복사한다. 표는 `python -m m2a.run.analyze --label X --by situation --pairs B4:B1 B1c:B1 --runs <dirs>`. 보고 표 ↔ run-id: 5절 `e3-smoke-o3knn-a4mid3`, 6절 `e3-main-o0-a4mid3`·`e3-main-o3knn-a4mid3`·`e3-l0pert-o0-a4mid3`, 3절 `e3-b1c-o0-a4mid3`. 임의 지정 옵션: workers 4, nice 10, 락 없음, seed 10000~10059(및 L0는 10000~10019). **주의**: 현재 변경은 커밋 전이라 repro.txt의 commit은 베이스 182469d + `dirty_files` 수로 읽어야 하며, 메인이 커밋하면 같은 명령이 그 해시에서 재현된다. 중간 진단 실행(`e3-t-*`, `e3-smoke-o3knn*`, `-a4mid`, `-a4mid2`)은 코드 변경 전·중 실행분이라 보고 표에는 쓰지 않았다(O0는 결정적이라 a4mid/2/3 결과 동일).

## 9. 테스트
`python -m pytest tests/m2a -q` → **160 passed, 1 skipped**(`m2a/notes/wse_pytest.txt`), test_e_*: 30 passed. 새 테스트 `tests/m2a/test_e_o3.py`: 가짜 인식으로 id 재연결(섞인 로컬 id, 같은 part 교환, 이동 후 재연결, 분류 뒤집힘=새 id, max_missing), B1c의 pick당 재인식 호출 수(`pre_pick` = pick 수, B1은 0), O0에서 B1c = B1, MISID 기록, COLLISION→IK_FAIL 접기와 원 reason 유지, 실제 O3(depth)+시뮬 통합.

## 10. 남은 문제 · 요청
1. **A4 최종 병합 알림 후 6번(본 배치 최종)을 `repro_batch.sh all <새 TAG> "A4 최종판"`으로 재실행**해야 한다(지금 표는 중간판). 약 20분.
2. A4/sim: 스킬 후 `perception_pose`가 팔을 못 치우는 문제, 헤드 화각(좌우 가장자리 물체 미검출 30%).
3. G: 오분류 22%(P01/P02 등)와 가장자리 잘림 → 부재 오보고. 플래너 쪽에서 "미검출 vs 정말 없음"을 구분하는 재관측(wrist 카메라/헤드 이동) 정책이 필요하다.
4. B4가 O3에서 오히려 progress가 낮음(−0.014~−0.058): 잔여 PERCEPT_MISS 재계획 비용으로 추정, 미검증.
5. test seed 미사용, 계약·타 소유 경로 수정 없음.

## 11. 면접 설명 (3줄)
- 무엇: 헤드 RGB-D 예측 인식을 계획 루프에 연결하되, 키프레임마다 바뀌는 예측 id를 part_id+위치 헝가리안 매칭으로 안정 id에 묶고, 스킬엔 자세(obj_pose_T)만 전달, 평가용으로만 GT 매칭해 MISID를 센다.
- 왜: B4의 불일치 감지가 oid 기준이라 id가 흔들리면 매 관측이 오탐 재계획이 된다(2라운드에서 MISID 9/10 실측).
- 대안 대비: 트래커 없이 인식기에 id 안정성을 요구하는 방식보다 어댑터에 두는 편이 인식기와 분리돼 간단하지만, 임계(3 cm 등)가 임의 지정이고 가림·분류 뒤집힘에서 새 id가 생기는 한계가 있다.
---

# 작업자 E (4라운드): G3 O3 연결, 부재 재관측, 판재 배정, B4r

기준: `~/work/rp_m2a_e4` (`m2a/ws-e-4`, A5/G3 `5e34255`에서 시작, A6 API 병합 `ada408b`로 fast-forward), 커밋 없음. **O3=시뮬 렌더 예측 인식(무질감)**, **P-gate(GT 보조 weld 파지 근사)**. dev만 실행, 봉인 test seed 미사용.

## 변경 파일

- `m2a/run/o3_config.py`, `embed_server.py`, `batch.py`: G3 head-v2 train-only 갤러리와 `DinoSmall(crop_size=112)`를 중앙 설정으로 연결. NPZ에 카메라 버전 필드가 없어 G3 파일 SHA-256을 고정하고 train seed 0–199 및 crop 112도 확인한다. 다른 내용의 파일은 fail-closed. 재생성한 별도 갤러리의 변경은 검증 및 지문 갱신이 필요하다. 배치 config에 갤러리 경로·버전·해시·crop을 기록한다.
- `o3_policy.py`, `o3_perception.py`, `perception.py`, `episode.py`: 재관측 및 후보 보존, 판재 배정과 전후 비교용 로그. GT 매칭은 판정/로그에만 쓰고 후보·배정은 RGB-D 예측만 사용한다.
- `retry.py`, `dispatcher.py`, `episode.py`, `batch.py`: B4와 별개인 B4r. `e4_analyze.py`, `repro_batch.sh`: 통계 및 원자료 보존. `tests/m2a/test_e_round4.py`: 정책 회귀 테스트.

## 부재 및 P01/P02 정책

1. 계획 직전 목표 수량보다 현재 기호 인벤토리가 부족하면 `perception_pose` 키프레임을 한 번 더 요청한다. 여전히 부족하고 `uncertain` 예측의 Top-3에 부족한 타입이 있으면 해당 안정 oid/타입을 확인 목록에 남겨 한 번 더 관측한다(최대 2회, 임의 지정). 후보를 발견 목록으로 승격시키지는 않는다. 마지막 관측에서 계속 부족하면 기존 플래너가 `missing`을 결정한다. 파킹을 시도할 수 없거나 훅이 실패하면 제자리 관측으로 폴백하며 `scene_graph.jsonl`의 `posed`로 구별한다.
2. 장면 내에서 Top-1이 P01/P02인 예측의 윗면 관측 장축을 정렬한다. 전체 BOM이 허용하는 최대 수량(설명서 P01 2·P02 2) 내에서 짧은 쪽을 P02, 긴 쪽을 P01로 배정한다. 일부만 검출되면 관측 수량을 가능한 유지하고, 1개뿐이거나 BOM 초과 또는 경계 길이 동률이면 원래 라벨을 유지한다(보수 정책, 임의 지정). 원본 그래프/Top-3/예측 자세는 보존하고 어댑터 기호 단계에서만 배정한다. L1 효과는 B1의 초기 동일 프레임에서 위치 매칭된 GT P01/P02에 대한 배정 전/후 정답 수와 혼동쌍을 비교한다. 미검출 물체는 이 비교의 분모 밖이다.
3. 재관측 전/후는 동일 장면 B1에서 재관측만 끈 배치(`--no-reobserve-missing`)를 대조군으로 둔다. 판재 배정은 두 조건 모두 동일하게 활성화. 거짓 완료는 judge, 잘못된 missing은 `missing_report_mismatch`. `PERCEPT_MISS`는 실행 이벤트 분류 수, `MISID`는 잘못 집은 물체(평가 GT 기준) 수를 별도 집계하고 최종 `fail_code`와 혼동하지 않는다.

## B4r (재시도 허용)

- 기존 B4(R=3)를 바꾸지 않았다. B4r은 GRASP_SLIP/IK_FAIL로 실패한 물체를 재관측하고, 물체당 최대 2회·dev L1/L2 R=6(둘 다 임의 지정). 이동(1 cm 이상, 임의 지정) 시 갱신 위치를 사용한다. 다른 팔로 바꾼 pick/place 묶음은 전체 계획 검증을 통과한 경우만 허용한다. B4의 전역 reach 차단은 B4r에는 적용하지 않는다.
- A6에서 직전 실제 접근각을 읽을 수 있으면 같은 팔 첫 재시도에서 그 각의 반대(π), 두 번째에서 대체 팔이 불가하면 직전 각에서 −π/2(임의 지정). 물체 yaw 값은 바꾸지 않는다. 명시 접근각을 O0은 reach에만 주어 GT oid 경로를 보존하고, O3는 lift에서 재계획하므로 두 스킬에 준다. A5처럼 API가 없는 경우 갱신 위치·검증된 대체 팔만 쓴다. 재시도 상한 소진 시 사람 호출로 종료한다.
- A5 호환 비교(접근각 지정 없음)는 B1 2/60, B4 3/60, B4r 3/60. B4r−B4 성공 Δ 0.000 [0.000, 0.000], 평균 진행 +0.027 [+0.004, +0.057]. 원자료 `m2a/notes/wse_runs/{e3-main-o0,e4-retry-o0}-a5final/result.json`, 상세 [A5 호환 표](wse_tables/e4_a5final.md). 접근각을 명시한 A6 수치로 인용하면 안 된다.

## A6 dev 측정 및 원자료

- [A6 결과 표](wse_tables/e4_a6final.md): O0 dev60 B1/B4/B4r, O3 L0 20 및 dev60 B1/B1c/B4, 성공 Wilson 95% CI·엄격 성공·평균 진행·거짓 완료·wrong missing·fail_code·인식 사건. 성공/엄격/진행 차이는 같은 seed·level·상황으로 짝지어 10,000회 percentile 부트스트랩한 95% CI(임의 지정).
- O0/O3 병목은 `O0 성공 ∧ O3 실패`로 계산하고 역전·양쪽 성공·양쪽 실패도 표에 남긴다. A5 메인 앵커와 A6 동일 버전 앵커는 분리한다. L0 O0 B4는 교란 조건이라 무교란 O3와 직접 짝지을 수 없다. dev60의 O0 B1c는 별도 실행하지 않아 O0 B1을 대조군으로 표기한다(두 구성의 GT 자세 경로는 동일).
- 완료된 실행은 `m2a/notes/wse_runs/e4-*-a6final/{config.json,result.json,repro.txt,*.jsonl.gz}`, 진행 중인 원자료는 `runs/e4-*-a6final/`. 작업 인계 시에는 `/tmp/rp_e4_a6.log` 및 `/tmp/rp_e4_a6_driver.pid` 참고. [A6 결과 표](wse_tables/e4_a6final.md)는 순차 배치 종료 후 자동 재생성한다.

## 재현 및 검증

```bash
cd ~/work/rp_m2a_e4
export PATH="$HOME/miniforge3/envs/robot_percept/bin:$PATH"
source /home/my/work/robot_percept/sim_test/gl_env.sh
WORKERS=3 bash m2a/run/repro_batch.sh e4-all a6final A6
python -m pytest tests/m2a -q
```

산출물마다 새 TAG를 지정하거나 단계별(`e4-retry-o0`, `e4-l0`, `e4-dev`, `e4-baseline`, `e4-tables`)로 실행. 별도 TAG로 실험해도 메인의 O0 앵커는 기본 `O0_TAG=a5final`에서 읽는다. 테스트: **183 passed, 1 skipped** (기존 Dash 경고 1건). 원자료 `m2a/notes/wse_pytest_e4.txt`.

## 남은 문제

- 같은 고정 시점 재관측이 구조적 가림을 풀어주지는 않는다. 확인 목록은 불확실성을 보존하지만 추가 카메라 시점/능동 자세 선택은 하지 않는다.
- 길이 순위는 부분 가림으로 순위가 역전될 수 있다. 불확실한 판재, P03으로 잘못 분류된 판재는 이 정책으로 복구한다고 가정하지 않는다. B4r도 대체 팔 계획이 불가능하거나 실제 접근 Yaw가 나오기 전에 실패하면 새 위치/재관측만 사용할 수 있다.
- 이 결과는 무질감 시뮬, dev, GT 보조 파지 근사 범위에 한정된다.

면접에서 이렇게 설명하면 됨:
1. 목표 파트가 부족하면 바로 부재로 단정하지 않고 재관측했으며 불확실한 Top-3 후보는 끝까지 추적했습니다.
2. P01/P02는 예측 원본을 보존한 채 장면 내 길이 순서와 BOM 상한으로 계획 라벨만 정리했습니다.
3. 재시도 정책과 인식 개선을 같은 장면의 쌍체 비교로 보고, O0에서도 막히는 실행 실패와 O3에서만 잃은 성공을 분리했습니다.
