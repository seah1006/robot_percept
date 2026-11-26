# V-GA 검증 계획 (M2A 관문 G-A, 독립 검증자 Claude)

작성 2026-11-26 (1단계). 대상: GA1 `sim/g1_grasp_env.py` (Codex, CuO9awWQVjnj3yBX), GA2 `tools/m2a_grasp_gate.py` (Codex, lX6lyUIKwIBH6tsv).
명세: `notes/m2a/TASK-GA.md`, `TASK-GA1.md`, `TASK-GA2.md`. 저장소 파일 수정·커밋 없음.

## 0. 원칙
- **검증 PASS ≠ 관문 통과**. 검증은 "결과가 명세대로, 재현 가능하게, 정직하게 나왔는가"를 본다. 12/20 통과 여부는 결과값일 뿐.
- **독립성**: 내 판정은 `tools.m2a_grasp_gate.judge`를 쓰지 않는다. GA2의 `run_trial`은 *동작 시퀀스*(같은 seed 재현)와 *GA2 주장값* 획득용으로만 호출하고, 판정은 `mujoco.mj_step`을 패치해 **매 물리 스텝(500Hz)** `env.model/env.data`에서 직접 읽은 정답 상태(물체 xpos, `right_palm_site`, `data.contact`)로 `vlib.judge_gt`가 따로 내린다. `env.state()`·weld 플래그는 판정에 쓰지 않고, 오히려 내 GT와 대조해 state() 자체의 정확성을 검사한다.
- 측정 락: 모든 CPU 배치·pytest는 `flock -w 900 /tmp/rp_measure.lock` 안, 1회 보유 < 5분 (`timeout 290~295`). GA2와 락 공유하므로 짧게 쪼갬.

## 1. 스크립트 (WSL `/tmp/m2a_verify/`)
WSL이 13:49에 재시작되며 `/tmp`가 비워진 것을 확인함. 원본은 Windows 세션 tmp `...\tmp\m2a_verify_src\`에 두고 `sync.ps1`로 `/tmp/m2a_verify`에 LF로 복사 후 실행.

| 파일 | 역할 |
|---|---|
| `common.sh` | REPO/PY/gl_env/PYTHONPATH(리터럴), `LOCK=flock -w 900 /tmp/rp_measure.lock` |
| `vlib.py` | geom 분류, 비트 감사, `GTRecorder`(mj_step 패치 + API 이벤트 로그 + state() 대조), `judge_gt`, `gate_edges`, `wilson`, 사후 렌더(`render_qpos`, 정면/측면 + 물체 근접 자유카메라 2개), 팔–테이블 거리(`mj_geomDistance`) |
| `v_static.sh` | 동결 파일 diff, 소유 범위, 타 worktree, 중력보상/비트/weld 코드 grep, 튜닝·판정 시드 흔적, bench 파일 mtime |
| `v_model.py` (`run_model.sh`) | A 임포트 부작용, B API·state 키/타입, C 접촉 비트, D 물체 사양·opt, E 중력보상 물체 미적용(qfrc/xfrc=0 + 5cm 낙하 시험), F reset 결정성·배치 범위(seed 0~199), G gate 음성 시험 |
| `v_trials.py` (`run_trials.sh <tag> <modes> <objs> <seeds> [--ga2-raw ...] [--frames N] [--release]`) | GA2 시퀀스 재실행 + 독립 재판정 + GA2 주장/bench raw 대조 + gate 엣지 감사 + 관통·발산 + 팔–테이블 거리 + 프레임 + weld 해제 시험 |
| `v_repro.py A.jsonl B.jsonl` | 같은 seed 두 번 실행의 GT 다이제스트·GA2 행(벽시계 제외) 비트 동일성 |
| `v_jsonl.py <bench_dir...>` | raw.jsonl 일관성(성공⇔코드, 성공행 임계값), summary 집계·Wilson 재계산, 메타(commit/dirty/params/mujoco/seeds), oracle 제외, 판정 seed=1000~1019 정확 일치 |
| `run_tests.sh` | 소유 테스트 2개 + `tests/test_humanoid.py`를 각각 락 안에서 실행, 벽시계 측정 |

## 2. 체크리스트 (ID / 방법 / 통과 기준)
| ID | 항목 | 방법 | 기준 |
|---|---|---|---|
| S1 | 기존 파일 동작 불변 | `git diff --stat b80d817 -- sim/humanoid_env.py sim/humanoid_ik.py sim/humanoid_teleop.py web/` + 작업트리/untracked | 출력 비어 있음 |
| S2 | 런타임 부작용 | v_model A: G1GraspEnv import·생성 전후 `build_g1_xml()` 해시, `REST`, `HumanoidEnv` disableflags(접촉 OFF)·크기 | 완전 동일 |
| S3 | 소유 범위 | v_static: 변경 경로가 소유 파일/notes/bench/m2a_ga 안 | 밖 0개, 타 worktree 미수정(기존 M 상태와 비교) |
| M1 | API 계약 | inspect.signature, state() 키·타입·길이, 잘못된 obj 거부 | 계약과 일치 (추가 헬퍼는 허용) |
| M2 | 접촉 전역 ON + 몸통 자기충돌 OFF | `mjDSBL_CONTACT` 미설정, 손 외 로봇 geom 전부 (0,0), 비트 호환 쌍이 손–물체/손–테이블/물체–테이블(+바닥)뿐 | 예상 밖 쌍 0, 시행 중 비손 로봇 접촉 0 |
| M3 | 중력보상 물체 미적용 | 물체 DOF `qfrc_applied`=0, `xfrc_applied`=0; 1초 정착 z 불변; 5cm 들어 올려 놓으면 자유낙하(min vz≈-0.98) 후 테이블 복귀 | 모두 충족 |
| M4 | 물체 사양 | geom 종류·크기·질량, dowel 눕힘(geom 축 수평) | 계약 일치 |
| M5 | 배치·결정성 | seed 0~199 xy 범위 ≤6cm, yaw 범위 ≤60°, 같은 seed 반복/새 env 동일 | 충족 |
| G1 | gate weld 조건 | (a) reset·손 닫고 허공·반쯤 연 손 누르기에서 weld 0 (b) 시행 중 weld 상승 엣지마다 내 GT 접촉에서 엄지+(검지|중지) 성립 여부, 손바닥 좌표계 물체 위치 기록 (c) phys에서 weld 0 (d) `--release`: set_hand(0) 후 다음 스텝에 해제, 물체 낙하 | 위반 엣지 0, phys weld 0, 해제 확인. 손바닥 영역 정의 타당성은 판단 항목 |
| J1 | 독립 재판정 일치 | 판정 seed 중 모드(phys,gate)×물체(3)당 ≥5개(1000~1004, 락 여유 시 20개 전부) 재실행, `judge_gt` vs GA2 행 vs bench raw | 성공/실패 불일치 0 (코드 우선순위 차이는 근거와 함께 기록) |
| J2 | state() 정확성 | state() 호출 시점마다 내 GT와 obj_pos/palm_pos/table 접촉/손가락 집합/관통/weld 비교 | 불일치 0 |
| J3 | 판정 입력 품질 | 유지 구간 샘플 ≥50Hz, 2.0s, 시작 z 정의(object_rest_pose) | 충족 |
| R1 | 재현성 | 같은 seed 별도 프로세스 2회 → GT 다이제스트·GA2 행 동일; 재실행 vs bench raw 동일; render=True(프레임 저장) 여부와 무관 | 비트 동일 |
| T1 | 튜닝/판정 시드 분리 | ga2_changes 튜닝 이력, `bench/m2a_ga/tuning/*.jsonl`의 seed 범위, 판정 run mtime vs 파라미터 변경 시점, 판정 run의 metadata.seeds | 튜닝 seed ⊂ 0~99, 판정 run 이후 파라미터 변경 없음 |
| P1 | 관통·발산 | 시행 전체 손–물체 최대 관통, 손–테이블 관통, NaN, 최대 qvel, 물체 속도; 팔(비트 0)–테이블 기하 거리 | 손–물체 ≤0.01m, 발산 0, 팔–테이블 관통 시 기록 |
| V1 | 렌더 육안 | GA2 `--save-frames` PNG + 내 사후 렌더(유지 시작/끝, 정면·측면·근접 2각) | 물체가 손 안, 공중 부양/관통/테이블 침투 없음, weld 근사 표시 |
| X1 | 테스트 | `run_tests.sh`: test_g1_grasp_env(<60s), test_m2a_grasp_gate(<30s), test_humanoid | 전부 통과, 시간 기준 충족 |
| X2 | 리포트 정직성 | summary/notes: gate=weld 근사 표기, oracle 제외, Wilson 재계산 일치, commit/dirty/mujoco/params/seeds 기록 | 충족 |

## 3. 1단계 시험 실행 결과 (스크립트 디버그 겸, 현 시점 코드)
- S1 PASS(diff 비어 있음), S3 PASS(소유 범위 밖 변경 0).
- v_model: A·B·C·E·F(board/block)·G 전부 PASS. 접촉 비트 손(1,6)/테이블(2,5)/물체(4,3), 비손 로봇 활성 geom 0, 바닥 (0,0). 낙하 시험 min vz -0.981(자유낙하 기대 -0.990), 정착 관통 ~1e-5 m. dowel 2건 FAIL은 **내 스크립트 결함**(body 축으로 봄, GA1은 geom만 회전) → geom 축으로 수정 후 재실행: **21/21 PASS** (dowel geom 축 z=1e-16 수평, yaw 범위 59.3°).
- v_trials 디버그(board/dowel seed 5, 튜닝 전 기본 파라미터): GA2 `no_contact` = 내 판정 실패, 일치. state() 불일치 0, 500Hz 1001샘플/2.0s, 팔–테이블 최소 거리 +6mm(right_wrist_pitch_link), 손–테이블 관통 3.3mm.

## 4. GA1 정적 검토 메모 (2단계 판단 대상)
1. 중력보상: `qfrc_applied[robot_dofs]=qfrc_bias`, 물체 6 DOF는 0 — 명세 준수.
2. gate 조건 코드: closure≥0.3 AND 같은 손 엄지+(검지|중지) 실제 접촉(dist≤0) AND `_inside_palm` → weld ON, 현재 상대 자세 저장(스냅 없음), closure<0.3에서 해제. 명세 준수.
3. **손바닥 영역이 넓음**: 로컬 x∈[-0.015,0.12], 닫힘축∈[-0.015,0.10], |z|≤0.06 m. 손가락 끝까지 포함하는 박스라 "손바닥 영역" 해석이 관대함 → 엣지별 물체 위치로 실제 활성 지점 확인 후 판단(조건부 사유 후보).
4. weld는 활성 후 손가락 접촉이 사라져도 손을 열 때까지 유지(명세 "손 열면 해제"와 부합). gate 성공이 "유지 중 접촉 0"인 경우가 있는지 기록, 근사임을 리포트에 명시해야 함.
5. 바닥 (0,0): 테이블 밖으로 떨어진 물체는 바닥을 통과 → z 기준으로만 실패 처리. `obj_table_contact`의 floor 검사는 사실상 무효(경미).
6. 팔·손목 geom (0,0) → 테이블을 접촉 없이 관통 가능. `mj_geomDistance`로 측정.
7. weld `torquescale=.06`, `solref=.01`: 회전이 느슨함. 판정은 위치 drift만 보므로 기울어짐은 프레임으로 확인.
8. reset: 0.25s 정착 후 `d.time=0`, 정착 위치를 rest pose로 사용(GA2 initial_z와 동일 확인).

## 5. GA2 관찰 메모
- `run_trial`: reset→(옵션 경유점)→pregrasp→보간 하강→0.5s 닫기→1.0s 들기→2.0s 유지(sample_dt 0.02). 유지 trace = 들기 끝 state + 유지 100샘플. 내 유지 구간 = 시행 마지막 2.0s(동일 구간).
- no_contact 규칙 변경 통보: 닫기 구간 중 한 snapshot의 최대 distinct finger 수. 시간 합집합 금지. → 코드 확인.
- `bench/m2a_ga/tuning/sweep*.jsonl` 생성 중 → 2단계에서 seed 범위 감사.
- GA2 통보(평가 진행 중): `bench/m2a_ga/evaluation_v1`, `frozen_params_v1.json` sha256 e7cf2599...dac7. 중간 phys board 1, dowel 0, block 13 /20, gate board 2/20.
- **2단계 우선 확인 사항**: GA2가 직접 인정한 사례(gate board seed 1000)는 유지 3조건을 만족했는데 20ms 샘플링에서 2손가락 접촉을 놓쳐 `no_contact`로 실패 처리됐다. TASK-GA.md 성공 정의는 유지 구간 3조건뿐이므로, 이는 성공을 과소 집계하는 판정 결함 후보. 내 judge_gt는 들어 올리지 못한 경우에만 no_contact를 매기므로 이 seed에서 불일치가 나올 것으로 예상 → 같은 유형 전수 확인(raw에서 code=no_contact인데 max_lift≥0.05·drift≤0.03인 행) 후 GA2·부모에게 통보. 확인할 것: frozen params hash와 판정 run metadata 일치, 평가 시작 이후 params/judge 수정 여부(mtime·hash).

## 6. 2단계 절차 ("검증 시작" 수신 후)
1. `sync.ps1` → `v_static.sh` (락 불필요).
2. `run_model.sh` (락, ~40s).
3. `run_tests.sh` (테스트별 락).
4. `run_trials.sh J1 phys,gate board,dowel,block 1000-1004 --ga2-raw 'bench/m2a_ga/*/raw.jsonl' --frames 2 --release` (락, 30시행 ≈ 1분). 락 여유 시 1005-1019 추가(모드별 분할).
5. `run_trials.sh J1b ... 1000-1004` 재실행 → `v_repro.py out/J1/v_trials.jsonl out/J1b/v_trials.jsonl`. 프레임 저장 run과 비저장 run 비교 포함.
6. `v_jsonl.py bench/m2a_ga/<판정 run 디렉터리>` + 튜닝 jsonl seed 감사.
7. 프레임 육안(GA2 PNG + 내 PNG, read_file로 확인).
8. 결함 → 해당 구현자에게 message_agent(재현 명령·seed·수치 포함), 부모에게 요약. 산출물은 Windows tmp로 백업.
9. `m2a_verify_report.md`: 체크리스트별 결과, 독립 재판정 표, 결함/조건, 최종 판정.

## 7. 최종 판정 기준
- **PASS**: S·M·G·J·R·T·X 전부 충족, P/V에서 결과를 뒤집는 문제 없음.
- **조건부**: 결과 숫자는 신뢰 가능하나 해석/근사 표기/경미한 명세 해석 차이(예: 손바닥 영역 관대, 바닥 비충돌, 코드 우선순위 차이) 등 조건 명시 필요.
- **FAIL**: 동결 파일 변경, 물체 중력보상, 독립 재판정 성공/실패 불일치, 재현 불가, 판정 seed로 튜닝, gate weld가 조건 미충족에서 활성, 테스트 실패 중 하나라도.
