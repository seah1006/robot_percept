
## I-K 1차 묶음 (2026-11-16, 미완/NEEDS WORK)
- 파일: web/app.py, web/sim_worker.py, sim/control.py(checkpoint 훅만), 신규 web/cell_db.py, web/cell_executor.py, tests/test_cell_exec_r5.py. 커밋 0.
- 구현: Runtime cid별 결과 저장(manager dict), epoch/deadline envelope, timeout→CellState.expire→stop. mp.Event/Value 별도 stop 슬롯; dequeue/physics/IK before·after checkpoint 및 현재 arm q hold. stop 경로 open_gripper/detach 0.
- DB: 단일 SQLite 쓰기 스레드, commit ACK, boot_id, 재시작 미완 aborted. executor 단일 스레드·주입식 인식. 기본 MODEL_UNAVAILABLE→needs_help. SimGTAdapter는 [시뮬GT]/gt_assist=True 배지 명시 injection만.
- 테스트: flock -w 60 /tmp/rp_measure.lock -c 'python -m pytest tests/test_cell_exec_r5.py -q' → 2 passed 0.20s. py_compile 5개 PASS. 전체 웹 회귀는 V-K 담당.
- 검증자: xRf7q6DPD6eqjpVM. 부모: 1NIgF2z2BvfBSkOh.
### 재개 우선순위 (필수, 현재 운영 사용 금지)
1. reset-stop 실제 q_hold/velocity/gripper 증거 수집 및 복구(현재 False 고정 fail-closed 409). idle estop ACK 부재도 보강.
2. worker running ACK를 cid별 저장하고 CellState.tick 주기 구동; 2s ACK timeout 정책 구현. timeout 후 expire의 outstanding terminal ACK 처리·지연 결과 수렴 검증.
3. stop 시 held_object 불확실성 유지/복구: pick 중 물리 grasp 이후 held_object 미반영 가능. cancel latch 정책 확정(현재 stop Event 유지). owner epoch 동기화 재검증.
4. realtime status_ws cell 별도 schedule/builder 추가. HTTP arbiter 외 WebSocket tracker 직접 accept_update 경로 소유권 차단.
5. stop physics/IK p95 회사 PC 락 내 측정(미측정), 동기 pick 종료<=5s 및 기존 웹 회귀 V-K 재현.
6. G1 연결 요청 수신: backend.call('ground',schema_version=1,frame=FrameMeta.to_dict(),rgb=bytes,queries=[{query_id,canonical_class,phrase}],deadline=monotonic...,owner_epoch=...). segment_box/capabilities 제공. 결과 error 확인; app/perception_lock→RPC 순서. pose 계획기 미완으로 app 연결 보류.
7. DB close race, DB 실패시 fail-closed latch, executor 오류시 safe stop, immutable task snapshot 보강. db 저장소 경로는 RP_CELL_DB 또는 ROOT/cell_runtime.sqlite3.

## I-K 2차 묶음 (재개, 2026-11-16)
- 자체 웹 회귀: 지정 기존6파일 31 + 신규4 = 35 passed, 21.78s, 측정 락 내. 원자료 bench/k/ik_web_regression.log. grasp checkpoint=None을 git HEAD 원본 choose_grasp 결과와 ndarray 비트 동일 비교 PASS; checkpoint before/after 개수 동일 PASS. WS update owner 차단/별도 cell schedule 테스트 PASS.
- 실제 spawned worker 동기 pick stop [시뮬GT]/GT=True, physics N20 p95=14.65533085ms (<100), IK N20 p95=5.17509455ms (<500), 실패0. load 2.3457/1.3413/1.0688. 원자료 bench/k/stop_measure.json, 재현 bench/k/stop_measure.py. 측정 후 GPU 상태 RTX2080SUPER util18%, 948MiB(동일 시각 샘플 아님).
- 5096 서버 shutdown: 3.57s, 잔존 worker0, port free. bench/k/ik_shutdown.log. 5080 사용0.
- 추가: idle stop ACK, accepted/running cid ACK, Runtime.wait 2s accepted 정책과 CellState.tick 구동, needs_help 대기 tick, stopped pick/place→held_object_uncertain(True)/새 task409, fixed stop baseline q_hold/폭/ctrl/접촉 관측, /cell/estop·reset-stop alias, WS cell builder 및 update arbiter.
- 부모 승인 소유권 예외: sim/grasp.py optional checkpoint=None 및 solve_ik 전후만. sim/ik.py 변경0.
### reset-stop 409 유지의 구체적 근거와 다음 구현 (부모 합의)
1. recovery_observation의 max_arm_velocity는 순간 샘플뿐이다. elapsed>=0.5만으로 합격 금지. worker physics step마다 0.5s 창(max속도·q_hold편차·폭편차·ctrl불변·접촉)을 집계해야 한다.
2. stop_baseline(q_hold/그리퍼 폭/ctrl/접촉)은 Manager 상태뿐, DB에 durable 저장되지 않는다. DB metadata 또는 cell 테이블에 boot/epoch/stop request에 묶어 commit ACK를 받은 기준값만 recovery 판정에 사용해야 한다.
3. legacy /robot/* 포함 Runtime 전역 outstanding+terminal ACK drain 집합이 없다. send시 등록, cid별 terminal 결과 수집 후 DB ACK까지 완료해야 제거. stale epoch 명령도 계속 drain.
4. 위 3개 충족시 계약4.7 각 검사 반례와 전부 통과200 테스트 후 latch clear. 현재 route q_hold_ok/velocity_ok/gripper_ok=False는 의도적 fail-closed. idle task 없는 estop도 복구 모델을 만들어야 한다.
### 남은 계약 리스크
- DB tasks만 저장(commands/events/epoch durable 미완), idempotency/confirm 미완. cancel에도 Event latch 남음(복구 구현 전 계속409). tick watchdog3s worker terminate/recreate 연결 미완. reboot 이전 중단 이력 latch 복원 미완.
- 현재 stop 측정은 빠른 mustard GT pick 경계 N20이며, 최악 fallback IK 모든 장면에 대한 상한 보장은 아님.

## I-K 3차 묶음 (2026-11-16, 테스트 락 대기)
- worker: stop epoch/request_at별 fixed baseline 유지, physics step마다 최소0.5s/250sample 슬라이딩 창 max velocity/width delta/q hold error/ctrl/contact 집계. 첫 hold 때만 qvel0, 이후 관측값을 zero로 덮지 않음.
- SQLite: metadata/commands 추가. stop baseline boot+request_at별 commit ACK, 모든 legacy 포함 send 전 sent durable 등록, terminal DBcommit 뒤 global outstanding 제거. collector는20ms.
- reset: 모든조건 통과시 CellState.reset_stop→SQLite recovery_reset+task 1transaction commit ACK→공유epoch+1/latch clear. DB실패503은 state rollback/latch유지. idle estop도 synthetic aborted task로 복구 가능.
- 반례: window시간/샘플,속도,폭,qerror,ctrl,접촉,신선도,확인,scene,heldACK,version,boot,DBdurability,outstanding 및 정상200·DB503 테스트 추가. 아직 실제 실행결과 없음(락 대기).
- 첫 wait120 테스트는 락 미획득으로 실행0. PASS 아님. 현재 exec_session_id=1047: flock-w900 단일작업에서 지정기존6+자체 tests 후 bench/k/recover_live.py(5096 HTTP estop→reset200)를 실행. 로그 bench/k/r3_combined.log의 LOCK_ACQUIRED 확인 필수. 이후 parent가 bash_interact 1047로 결과 수거 가능. 다른GPU측정 락 대기로 진행 지연.
- blob: app 78235f3c1fd11685373b09782c54ee446a5a6e7e; worker 7fc93bbf2d439ac429d5053289b9b41f2ff379a2; db c70e7c3306072c2c5865983008b1f2f8c147a5f1; executor4555b7792a9936e451adf0a01b407e9b2e9bc7e9; test df9c5ac08cf0c3fdf3c1246d4bfe38097b7a1918. V-K 전달완료.
### 3차 잔여/주의
- 실제 worker 관측이 .5s/250sample 기준에 도달하는지 live 재현 필요. 슬라이딩 창이 느린 PC에서 샘플수 부족하면 의도적으로409 유지.
- 접촉이 stopACK와 달라지면 현재 지속409: 사람 재확인 후 새 접촉 기준 revision을 durable 갱신하는 절차는 아직없음(느슨하게 통과시키지않음).
- 재시작 durable latch 복구, watchdog worker재생성, idempotency/confirm은 종전 미완 그대로. 커밋0.

### 3차 최종 결과 (위 테스트 대기 기록 갱신)
- exec1047 완료. 측정락 획득 후 지정기존6+자체: 52 passed, 23.84s, 회귀0. 원자료 bench/k/r3_combined.log.
- 실제5096 HTTP: /cell/estop202→window미충족409 4회→/cell/reset-stop200. epoch3→4, version2→3, stop_latchedfalse. window0.503543664s/251samples, max velocity4.4058e-12rad/s, gripper width delta0.0000449181m, maxhold error9.99e-15rad, ctrl/contact unchangedTrue. GT도움 없이 idle 복구판정.
- live 서버 종료1.018s. bench/k/recover_live.py. 3차 blob은 위 해시 그대로(코드추가수정0). 부모/V-K에 결과 전달.
- 다음 재개: 접촉변화후 인간 재확인 revision절차, 재시작latch복원, watchdog재생성, idempotency/confirm. 이들은 3차 범위밖 기존잔여.

## I-K 4차 묶음 (2026-11-16)
1. worker dequeue에서 epoch/deadline 선검사 RejectedCommand→status stale_epoch/expired, error_code STALE_EPOCH/DEADLINE_EXCEEDED. 미실행 reject는 held_object_uncertain을 켜지않음. 실서버 STALE_EPOCH 직접확인.
2. POST/tasks 공개입력 schema_version int1/instruction/source/Idempotency-Key 필수, GT identity/image필드 거부. key+request_hash/task/원본202응답 DB동일transaction. 같은key다른body409. 내부submit(target)은 테스트/명시 GT injection 호환. confirm candidate/frame/version CAS→planning durable 후 queue, cancelversion CAS 실패는stop/latch없이409.
3. SQLite events AUTOINCREMENT event_seq·UTC at·command/task/event payload 추가, boot/restart/state/command/metadata/reset/shutdown 이벤트. cached event_seq snapshot. shutdown은 현재 실제 nonterminal task만 aborted로마감하고 shutdown event기록; 신규 stop-* task행 생성0. idle estop의 내부stop state도 events만저장, reset시tasks행미생성. 이전DB의과거stop-*행은 삭제하지않음.
4. 최악 IK 실측: bench/k/worst_ik.py, 매호출160x10=1600회 Jacobian 카운트 전건확인, 첫Jacobian후1ms timer stop→호출뒤checkpoint. N20 p95=479.9373ms/max483.6992ms (<잠정500ms). load2.329/1.646/1.400. [시뮬GT], gt_assistFalse. sim/ik.py변경0. 외부max_iters/restarts분할은 RNG/best 보존을깨므로 동작동일분할불가; 이번실측상분할미적용. 16.3ms여유뿐이며 OS/전체장면보편상한은 주장하지않음.
5. bench/k/api_live_r4.py 실제5096: held slot주입409([시뮬GT],실제grasp성공주장아님), owner중humanoid/mode409, status/ws typecell 수신, 멱등중복202동일id/다른body409, stale_epoch+error_code확인. raw bench/k/r4_combined.log.
- 락내 회귀: 기존웹6+자체=62 passed25.44s(회귀0). confirm정상/틀린frame 테스트1개추가후 자체최종32 passed9.13s, raw bench/k/r4_self_final.log. 전체pytest실행0.
- blob app42e09ed96c1c6d4c5f99cecbaeb062e4ed2dc97d / worker6ccc1af7911420ccbff22c73f6ee726bf9b446df / dbbf69139920a19e3ea06785ca0e7e5943dabae5fe / executorc5bcc8a1c2de4257ca07afe2d203b0827fdb1402 / testsfd1d523773d0bb612667db9b0645851a96e174ff.
### 재개지점/범위밖잔여
- DB는 기존payload형tasks/commands컬럼호환 유지이며 계약6장 SQL전체정규화(steps/cell외래키/CAS SQL)까지 완성했다는 주장X. confirm은 주입perceiver candidates가 있을때만유효, 기본MODEL_UNAVAILABLE은 계속needs_help.
- 재시작latch복원/3s watchdog재생성/접촉변화후durable 인간재확인revision은 기존잔여. API DB실패503 매핑/rollback 정밀검증 및 동시epoch arbiter완전통합 후속점검필요. 커밋0.
