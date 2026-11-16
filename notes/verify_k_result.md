# V-K 판정 (2026-11-16, 대상: 3차 묶음 blob app 78235f3c / sim_worker 7fc93bbf / cell_db c70e7c33 / cell_executor 4555b779 / tests df9c5ac0)

판정: **NEEDS WORK** (핵심 안전 경로 직접 재현 PASS, 계약 미완 항목 남음). 모든 수치는 [시뮬GT] 타이밍·상태이며 인식 성공 주장 아님. 원자료 bench/verify_k/out/*.json, 스크립트 bench/verify_k/vk_live.py·run.sh·restart_kill.sh (측정 락 안, 5096).

| # | 항목 | 결과 |
|-|-|-|
| 기준선 | 기존 웹 6파일 | 31 passed / 종료 3.495s / 잔존 0 |
| 1 | 만료 deadline·epoch 불일치 명령 | arm_qpos 변화 0, 둘 다 이동 없이 거부. cid(32hex)별 결과 독립. 단 stale epoch가 STALE_EPOCH가 아닌 status=stopped로 보고(계약 4.2 불일치) |
| 1 | wait 타임아웃 후 늦은 명령 | long/late 둘 다 stopped, 지연 실행 없음 |
| 2 | 동기 pick 중 stop(N=40, 현 코드) | physics 35건 p50 1.18 / p95 10.33 / max 12.86 ms (상한 100). 전부 status=stopped, held=null |
| 2 | IK 경계 | 도달불가 목표 N=20: 전 건 ik.after/ik.before에서 정지, max 41.9ms. 최초(1차) 실행 1건 491ms였으나 2차 checkpoint 이후 재현 안 됨. 단 solve_ik 1600반복 최악(~385ms) 구간을 의도적으로 맞추지는 못함 → IK p95는 N 부족(IK 5건 p95 152.7ms) |
| 2 | 그리퍼 열지 않음·held 보존 | 이 스크립트는 gripper 폭을 직접 못 읽음(status 키 없음). I-K 3차 window 지표(폭 delta 0.0449mm)는 내 직접 재현 아님 |
| 3 | /tasks 입력검증·owner 배제 | 잘못된 payload 4종 400, 동시 2번째 task 409, owner 중 /teleop 409. needs_help도 owner 유지(deadline 300s까지 teleop/legacy 차단, cancel로 해제) |
| 3 | latch 복구 | estop 202 → /robot/place·/tasks 409 → reset-stop 확인 누락/오 ack/오 version 각 409 → 1s 후 200(epoch 3→4, latch false) → 이후 /robot/place 202, 재호출 409. 레거시 영구 잠김 회귀(1차) 해소 |
| 4 | SQLite | 단일 writer 스레드. kill -9 후 재기동: needs_help → aborted/server_restart 확인, 잔존 프로세스 0. 한계: 계약의 commands/events/cell 테이블 없음(tasks 1개), 종료마다 synthetic stop-* 행 추가 |
| 5 | 종료 | I-K 보고 1.0s·3.57s, 내 기준선 3.5s, kill -9 후 3s 내 자식 0 |
| 6 | 호환 | 전체 pytest 375 passed 96.4s(락 안, 잔존 0). sim/ik.py diff 0, web/cell_state.py diff 0 |
| 7 | GT 표기 | 기본 perceive 없음 → needs_help(MODEL_UNAVAILABLE), gt_assist=false. SimGTAdapter는 badge [시뮬GT]·gt_assist=True(코드 확인만, 실행 미재현) |

## 남은 문제
1. stale epoch ACK 코드(STALE_EPOCH) 미구현 (stopped로 보고).
2. POST /tasks에 Idempotency-Key, confirm 엔드포인트, schema_version 검증 없음. cancel은 version CAS 없음.
3. DB: commands/events 테이블, event_seq 없음. synthetic stop task 오염.
4. IK 최악 구간(solve_ik 1600반복) 정지 지연 p95 미확정(N 부족), 회사 PC 재측정 별도.
5. humanoid 동시 요청 409 실서버 미재현(teleop만), held_object 시 /tasks 409·status_ws type=cell은 I-K 자체 테스트만, 나는 미재현.
6. 기본 서버에서 /tasks는 perceive 주입 없이는 항상 needs_help (실사용 불가, 의도된 상태).

---
# 4차 재판정 (blob app 42e09ed9 / sim_worker 6ccc1af7 / cell_db bf691399 / cell_executor c5bcc8a1 / tests fd1d5237)
판정: **CONDITIONAL PASS (K 실행부 안전 경로 한정)**, 전체 K 완료 아님. 직접 재현(락 안, 5096, [시뮬GT]):
- stale epoch는 status=stale_epoch/STALE_EPOCH, 이동 0. 만료는 DEADLINE_EXCEEDED, arm_qpos 불변. 타임아웃 후 늦은 명령도 STALE_EPOCH.
- /tasks: key 없음 400, schema_version 2 400, 잘못된 body 4종 400, held 주입 409(slot 주입, 물리 grasp 아님), 동일 key 재전송 202+같은 task_id, 같은 key 다른 body 409, owner 중 새 key 409, teleop 409, humanoid/mode 409, cancel 잘못된 version 409 후 올바른 version 202, 재 cancel 200, WS type=cell(event_seq 포함) 수신.
- estop 후 reset-stop: 확인 누락/오 ack/오 version 409, 정상 200(epoch 3->4), 이후 /robot/place 202.
- stop 지연(sync pick N=40): physics 35건 p95 9.3ms(max 19.3), IK 경계 5건 max 126ms. 도달불가 IK N=20 max 36.4ms. 전부 stopped.
- 최악 solve_ik(1600반복) 독립 재측정 N=30(vk_ik_worst.py, 요청 1~250ms 랜덤): p50 229 / p95 400.1 / max 441.7ms. I-K(요청을 solve 직후 고정) p95 479.9/max 483.7. 상한 500 여유 얇음.
- solve_ik는 private MjData, caller data 비수정, env.step 미호출. 실측에서 qpos 변화 0.0 rad, sim time 변화 0.0 s(N=30) -> 팔 안 움직임, 이 지연은 계획 지연(안전 위험 낮음).
- kill -9 후 재기동: aborted/server_restart, 종료 시 synthetic 행 추가 없음, 잔존 0.
- 전체 pytest 387 passed 93.1s(락 안, 1회), 잔존 0. sim/ik.py diff 0, sim/grasp.py는 승인 범위(+9/-1).
다음 라운드: DB 정규화(steps/cell/commands), watchdog 실서버, restart 후 latch, 접촉 기반 held 검증, 회사 PC IK 재측정, non-executing cancel이 stop_latched=true를 남기는 동작(계약 4.6-5와 다름).
