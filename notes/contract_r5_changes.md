# contract_r5 변경 노트 (v1 → v1.1)

작성: D-CT(Claude, 설계 대행). 배경: I-CT(Codex) 사용량 한도로 정지(목 11-12 약 13:50 KST 복귀 예정). 사용자 규칙상 Claude는 설계 문서만 대신하고 Codex 확인을 받는다. 코드(.py)·커밋 없음. v1 원본 백업은 부모 세션 tmp(contract_r5_v1_backup.md)에만 있다.

## 1. V-CT 지적 반영 위치
| 지적 | 반영 절 | 요지 |
|-|-|-|
| C1 ACK timeout 후 큐 잔존 명령의 epoch 증가 주체(app.py:158) | 4.2 | 증가 주체는 ControlArbiter 하나. expire(cid)가 공유 슬롯 epoch+1을 먼저 게시 후 DB commit. worker는 dispatch 직전 STALE_EPOCH 거부. 자동 재시도 없음 |
| C2 자동 open/home 적용 범위, place/home 취소 시 held_object | 4.4 | 금지는 정지 경로에만. 정상 경로 pick 실패 open은 checkpoint 뒤 허용(접촉 남으면 open 안 함), 셀 home은 별도 명령. 정지 시점별 그리퍼·held_object 표 |
| C3 track_loop·select_at이 셀 선택을 덮지 않는 규칙 | 3.1 | 셀 전용 슬롯·cell_generation, 셀 owner 중 track_loop 미실행·select_at/reacquire 409 |
| C4 IK 내부 checkpoint 없을 때 정지 지연 상한 | 4.3 | 호출 경계 checkpoint 필수, IK 구간 ≤500 ms(실측 최대 385 ms), physics 구간 ≤100 ms(render 미측정, 구현 시 확정) |
| C5 cancel/estop/이중 cancel/stopping 중 deadline | 4.6 | 먼저 commit된 요청이 terminal 사유, estop 셀 효과는 항상, 이중 cancel 202 no-op, stopping 중엔 stop_ack_timeout 3 s만 |
| C6 reset-stop 합격 조건 | 4.7 | q 허용오차 0.02 rad·qvel ≤0.05 rad/s(0.5 s), 그리퍼 폭 ≤2 mm, held_object 재판정+사람 ack, GT 변위는 진단만, 단일 transaction |

## 2. 그 외 변경
- 4.9 현재 근거 표: 6행 → 30행, 파일:라인(HEAD 2859663 직접 확인).
- 2.3 G0 반영: device 판정을 torch 빌드 기준(hip→rocm)으로, rocm은 peak_mb 기록. capabilities에 device_name·torch_version·accel_version·models.*.loaded 추가. perceiving deadline 180 단일 → cold 180 / warm 30.
- 1장 오류 코드 3개 추가(STALE_EPOCH, OWNER_CONFLICT, RECOVERY_CHECK_FAILED). 6장 SQLite cell에 held_object·q_hold_json, /status.cell에 held_object.
- 5.3·7장 사용자 확정: N≥100+Wilson CI, 녹화 위치 오차 '측정 불가'(null), W2 실촬영 회사 PC.

## 3. 측정 원자료 (D-CT, 4.3 근거)
- 11-10, 집 PC, robot_percept env(수정 없음), mustard 장면, `flock /tmp/rp_measure.lock` 안, loadavg 0.67, 스크립트는 저장소 밖(부모 tmp ik_measure.txt, stdin 실행).
- timestep 0.002. solve_ik 도달 불가(x=2.0 m): 338.7/342.8/383.2/369.7/385.2 ms. 도달 가능(ee −5 cm): p50 1.02 ms, max 2.38 ms(N=20). choose_grasp(mustard): 8.4/8.0/8.7 ms. Controller._step(hook 없음): p50 0.038 ms, max 0.156 ms(N=200).
- 한계: N 작음, 집 PC 한 대, render_hook 시간 미포함. 회사 PC 재측정 필요.

## 4. I-CT 확인 필요(제안 값)
- warm deadline 30 s, stop_ack_timeout 3 s, accepted ACK 2 s, IK ≤500 ms/physics ≤100 ms 상한.
- 셀 home을 별도 명령으로 분리하는 것(4.4)과 legacy place 내부 home 유지.
- 신규 오류 코드 3개와 SQLite 컬럼 추가(interfaces.py·schema 테스트 영향).
- solve_ik 내부 콜백 추가 여부(sim/ik.py 변경 필요 시 별도 승인).

## 재검토 기록
- 재검토 1 (V-CT): C1~C6 반영 확인, 신규 V1~V4 지적 → 반영: V1 4.6-4(SIGTERM 2 s→SIGKILL 2 s, 총 7 s, 종료 실패 시 task aborted(worker_unkillable)+셀 owner=recovery, 서버 재시작만 복구), V2 4.6-5(owner draining, RPC lock 대기 5 s 상한 후 perception worker 자기 PID 종료), V3 4.7(arbiter outstanding 집합으로 drain 확인, 재생성 worker 초기 qpos를 q_hold로, DB 영구 실패 시 서버 재시작만), V4 4.4(held_object 있으면 POST /tasks 409, 사람 정리만).
- 재검토 2 (V-CT): V1~V4 반영 확인, 문서 판정 PASS(설계 문서 한정). 코드·테스트·pytest·뮤테이션은 미실시(Codex 복귀 후). 남은 이견 없음.

## 재개 지점
- 문서: notes/contract_r5.md v1.1 작성 완료, V-CT 재검토 루프 결과는 아래 "재검토 기록"에 추가.
- **Codex(I-CT)가 할 일(목 11-12 약 13:50 이후)**: ① v1.1 확인·이견 표시(4절 목록) ② perception/interfaces.py: FrameMeta/Frame/Detection/MaskResult/Localization/CameraModel/Command/Ack DTO, 오류 코드 14종, schema_version=1, stdlib만 ③ 상태 머신(순수 로직, 가짜 시계 주입): 4.5 전이·deadline, 4.6 우선순위·멱등, 4.2 expire/epoch, 4.7 reset-stop 검사, 4.8 재시작 ④ tests/test_contracts_r5.py: DTO roundtrip, unflip(center/edge), 전이·timeout·restart, 4.6 조합 7종, 3.1 셀 owner 중 track_loop/select_at 차단, 4.3 가짜 느린 IK 지연 상한 ⑤ 측정 락 안 전체 pytest(기준 104 passed).
- 운영 코드(web/app.py, sim_worker.py, perception_stub.py, realtime.py)는 이번 범위에서 미변경.

## 2026-11-16 I-CT 구현 확인
- v1.1 제안 warm 30s / stop_ack 3s / accepted ACK 2s 수용. IK 500ms / physics 100ms는 잠정 계약 상한만 수용, 회사 실측·실 worker 중단 보증 아님.
- 셀 home 별도 명령, legacy home 유지, 추가 오류3종 및 SQLite held_object/q_hold_json 수용. 오류는 기존11+추가3=총14종(추가17종 아님).
- solve_ik 내부 콜백은 이번 운영코드 미변경 경계상 추가하지 않음. 실제 호출경계 체크포인트/지연 측정은 후속 K 통합 범위. v1.1 설계 이견 없음, v1.2 변경 없음.
- 신규 perception/interfaces.py: stdlib 불변 DTO/14오류/schema1/공개 Frame 메타전용·IPC bytes, 반열린 box/RLE/유한값 검증.
- 신규 web/cell_state.py: 가짜 시계 주입, 상태/deadline/owner/draining/epoch/cid별 ACK/DB commit gate/stop latch/restart/watchdog 순수 정책. OS kill·DB durable 저장·운영 결선은 후속 통합 책임.
- 신규 tests/test_contracts_r5.py: 명시 전이표9x9, 직렬화, 경계값, 요청 순서/ACK/늦은결과/재시작 반례.

## 재개 지점 (11-16 I-CT)
- 측정락 계약 pytest 실행 exec1005. 전체 pytest는 다음 측정락 슬롯에서 실행 필요.
- V-CT CPKC6flRVgtXDk80에 API/파일/수용값 전달. 독립 검증·뮤테이션 회신 반영 필요.
- 운영 공유 4파일 미변경, 커밋 없음. SQLite/프로세스 실제 통합 PASS로 보고하지 말 것.
- V-CT 1차 독립 144 check: 140 PASS/4 FAIL(F1 restart 복구, F2 종료확인 watchdog 복구, F3 estop→cancel no-op, F4 이중 estop). 4건 수정 + begin_rpc API + 회귀 테스트 저장, 재검증 대기.
- 전체 pytest exec1007 시작(측정락 내부), 출력 /tmp/rp_ct_full_pytest.log. 계약 pytest exec1005도 락 대기. 다음 구현자는 두 exec poll 및 V-CT 재검증 회신 반영. 현 테스트 수/회귀0 아직 미확정.

## 재개 지점 (11-16 부모 요청 재개: pytest 분류)
- exec1005 완료: tests/test_contracts_r5.py **115 passed, 0.16s**, 수정 후 blob(state 33d1c3ba, tests 64efe19a) 일치.
- exec1007 기존 전체 실행 완료: **16 failed, 267 passed, 92.98s**. 실패 전부 SA 신규 tests/test_cell_scene_r5.py::test_settled line43(max_speed<0.01), seed 100000/100009/100016/100017/100020/100023/100025/100026/100027/100031/100032/100037/100039/100040/100042/100048. 관측 max_speed 0.016~0.336 m/s. CT 신규115 실패0, 기존 테스트 실패0. 원자료 /tmp/rp_ct_full_pytest.log.
- export PYTHONPATH=$PWD가 Windows cwd로 확장된 사실은 있으나 위 실패는 실제 settling assertion이며 import 실패가 아님. 후속 명령은 PYTHONPATH=. 또는 repo 절대경로 권장.
- TEAM_R5 12:22 규칙 확인: 구현자 전체 pytest 추가 금지. 전체 새 투입 없음. V-CT에게 분류 결과 전달 완료.
- 수정본 계약만 측정락 재실행 exec1009 대기 중, 로그 /tmp/rp_ct_contract_retest.log. 이 exec poll 후 숫자 기록하고 V-CT에 전달 필요.

### 재개 결과 확정
- exec1009 종료: 수정본 계약 테스트만 측정락 재실행 **115 passed, 1 warning, 0.11s**. 원자료 /tmp/rp_ct_contract_retest.log. V-CT CPKC6flRVgtXDk80에 전달 완료.
- exec1005/1007/1009 모두 종료. 구현자 전체 pytest 신규 투입 없음. 남은 것은 V-CT 독립 검증 최종 판정/뮤테이션 및 SA settling 수정 뒤 검증자 묶음 확정이다.

## 11-16 V-CT 2차 및 비중복 Gemini 후보 처리
- 독립 149/149 PASS. V-CT 지적 mutation 생존19개에 단독 가드 반례 추가: epoch/deadline/inflight/commit/stopping/estop epoch/cancel event 멱등/terminal409/CAS/후보 세대·epoch/복구 각 조건/라치/watchdog/held/store full.
- 보강1 측정락 결과(exec1019): **148 passed, 0.28s**. /tmp/rp_ct_guard_tests.log. /tmp/rp_ct_guard_mutation.log: 36개 중 비동치 **34/34 pytest KILL**, 동치2(outstanding release/settle, commit가드에 마스킹)는 검증자도 제외 판정.
- G1 확인·수정: deadlines.perceiving_warm 기본30, 유한 양수 검증 및 override 테스트. cold override와 warm override는 별도 키.
- G2 확인·수정: CameraModel.validate_frame은 FrameMeta뿐 아니라 Frame.meta도 지원. 일치/보정id 불일치/크기 불일치 양 타입 반례 추가.
- G3 확인·수정: 이미 terminal ACK 받은 cid 또는 terminal task에서 expire no-op. 정상 경로 submit은 executing에서만 허용되고 outstanding 중 executing 이탈 불가하므로 비executing outstanding expire는 정상 API로 도달 불가. 완료 cid expire epoch/event 변조는 실제 결함으로 수정. 비executing 상태에 인위적으로 commands/outstanding을 주입하는 전제까지 API 계약으로 허용하지 않음.
- G4 확인·테스트: executing 180s 직전/경계→state와 owner 유지/stopping, settle 후 aborted 고정.
- G5 부분수용: submit 거부에 ContractError(ValueError).code 추가(OWNER_CONFLICT/STALE_EPOCH/DEADLINE_EXCEEDED). 순수 can_start/legacy_allowed는 bool 정책 질의, reset_stop은 (HTTP status,실패항목) 모델 API이므로 실제 HTTP Error DTO/RECOVERY_CHECK_FAILED 연결은 이번 금지된 운영 결선 범위에서 하지 않음. 오류코드 enum 자체는14종 고정. OS kill/실제 복구 수치도 caller 사실검증 책임이며 통합 PASS 아님.
- 추가 실제 결함: cancel_requested=True→watchdog aborted 뒤 재cancel이202로 빠지는 순서 문제를 terminal409 우선검사로 수정·회귀 추가.
- 계약 notes/contract_r5.md 머리말 v1.2 갱신, 4절 제안값 전부 확정(값 변경 없음). IK500ms/physics100ms는 잠정, 회사 PC 통합 재측정 필요. I-CT/V-CT 합의.

## 재개 지점 (보강2)
- exec1020: 최종 자기 계약 테스트만 측정락 실행, /tmp/rp_ct_final_contract.log. 전체 신규 실행 없음.
- V-CT에 mutation34/34 결과 및 G1~G5 수정 전달. warm/deadline/terminal cancel 변경으로 검증자 mutation 치환패턴 갱신+run_mut 재검증 요청 완료.
- 최종 hash는 exec1020 끝에 출력. 운영 공유파일·커밋 없음. 완료 판정은 최종 계약테스트 및 V-CT 회신 대기.

### 보강2 실행 완료
- exec1020 종료: **161 passed, 1 warning, 0.27s**, 측정락 자기 계약테스트만. /tmp/rp_ct_final_contract.log.
- blob: interfaces82253db8ead018577f9175c31b8de6389e0f2c5a / state ad16b0a059845344e0ea266132ded68468cfa690 / tests4e19548562e63026aadb0ab54329c04e0e12057a / contract d8a2efcdf9fff89df61e10b7ac12d2f6f3456933. V-CT에 전달, 최종 패턴 리베이스 mutation 재검증 대기.

## 11-16 V-CT 3차 및 마지막 테스트 보강
- V-CT 보고: 독립166/166 PASS, 전체323 passed/0 failed(SA 포함), 계약161 passed, 운영파일 diff0. 최신 mutation48개 중 동치3 제외45: 독립45/45, 구현자pytest42/45.
- 생존3가드(begin_rpc inactive, watchdog 종료확인 시 outstanding/commit 정리, unknown deadline key)에 반례4case만 추가. state/interfaces 미변경.
- exec1022 측정락 자기테스트 **165 passed, 1 warning, 0.28s**, 로그 /tmp/rp_ct_last_guards.log. tests blob80dc097c09f735cb2dd8302e48c60ba227dfcb00.
- V-CT 최신 mutation 재검증/PASS 요청 완료. 구현자 전체 신규 실행없음. 재개: V-CT 최종 PASS 회신 기록 및 부모 전달만 남음.

## 최종 마감 (11-16 I-CT)
- V-CT notes/verify_contract_r5.md K절 최종 **PASS** 확인: 독립166/166, 계약165 passed, 비동치 mutation45/45 양쪽 KILL(48개 중 동치3 제외), 운영·공유 diff0.
- 전체323 passed/0 failed는 마지막 테스트4case 추가 전 검증자 실행이며, 이후 state/interfaces 불변. 최신 전체327 PASS로 외삽 보고하지 않음.
- 계약 v1.2 갱신 이미 완료. 최종 소유 변경5파일: notes/contract_r5.md, notes/contract_r5_changes.md, perception/interfaces.py, web/cell_state.py, tests/test_contracts_r5.py. 커밋 없음.
- 재개 지점: CT 순수 DTO/정책 구현 완료. 후속 K에서 실제 worker 중단·DB durable ACK·프로세스 종료·회사 IK/physics 상한 재측정 통합 검증 필요.
