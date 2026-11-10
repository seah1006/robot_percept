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
