# V-CT 검증 노트: r5 계약 (P0-2·5·6·7·8)

판정(현재): NEEDS WORK (22:10 KST: contract_r5.md만 존재, interfaces.py/상태머신/tests 미작성 -> 전체 pytest·뮤테이션 미실시)

## A. 현재 코드 사실 (직접 확인, HEAD 2859663)
- web/sim_worker.py:123 stop_event는 바깥 while 첫 줄에서만 검사. 명령 실행(139~176) 동안 불가.
- sim_worker.py:172 status["last_command"] 단일 슬롯 덮어쓰기. app.py:158~164 Runtime.wait가 last_command.id==cid만 폴링, timeout은 실행 취소 아님("command timeout" 반환 후 큐 명령 늦게 실행 가능).
- app.py:~150 Runtime.send: cid=uuid, command_q.put, epoch/deadline/owner 없음.
- sim/control.py:72 Controller._step -> step_hook. sim_worker.py:18 _step_hook는 render+sleep만. solve_ik 호출은 control.py:110(move_cartesian 루프), 260, 301, 304 및 sim/grasp.py:129~151: 이 구간은 hook 미호출 -> IK 경계 checkpoint 별도 필요.
- sim_worker.py:156~157 pick 실패 시 open_gripper 자동 호출(취소 시 그리퍼 열지 말라는 R5-X와 충돌 가능), place 후 return_home 자동(취소 후 자동 home 금지 대상).
- 소유권 검사 현황: app.py:118(tracking paused 판정), 207, 375, teleop.py:33이 phase/held_object/active_command만 봄. queued/perceiving/planning 구간 무방비.
- GT identity: app.py:300~306 select_at이 SAM mask vs seg 겹침으로 이름 선택(GT 누출), non-fp는 estimate_pose(perception_stub.py:8~11, gt_pose + rng(7) 고정 시드 jitter .0015). track_loop(app.py:~130)도 non-fp에서 동일.
- track_loop는 rt.selected/generation 기준 자동 갱신 -> 셀 선택을 덮을 수 있음(owner/generation 검사 필요).
- 트래커 tools/teleop_tracker_win.py:303,374 cv2.flip(frame,1)->640x360, 418~438 오버레이(cv2.line/circle) 후 446 imencode q65 -> 448 pending. web/teleop.py:7 preview={jpeg,seq}만, capture_at 없음, 53~57 accept_preview에서 seq만 증가.
- web/realtime.py:74 next dict, 112 builders dict가 robot/teleop/humanoid 고정, sent()가 name별 분기.
- sim/grasp.py:11 TOP_MAX_H=0.07 (<= vs < 경계는 코드 확인 필요).

## B. R5-X P0 대조표 (contract_r5.md 15146B, 21:59 기준)
| 항목 | 계약 위치 | 판정 |
|-|-|-|
| P0-2 DTO(프레임id·촬영/수신·mirror·보정id·좌표계·오류코드) | 1장 | 반영 (소유 G/W2/K 경계 포함) |
| P0-5 GT identity 분리·고정 클래스 사전·인스턴스 선택 | 3장 | 반영. 단 track_loop/selected 덮임 규칙 누락 (C3) |
| P0-6 단일 executor·epoch·cid 결과·FIFO 밖 stop·checkpoint·ACK 전 owner | 4장 | 대부분 반영. 늦은 실행 시 epoch 증가 주체(C1), 자동 open/home 구분(C2), IK 내부 checkpoint 한계(C4) 미비 |
| P0-7 stop latch·failed·deadline·restart·DB commit ACK·단일 프로세스 | 4,6장 | 반영. 정지/취소/deadline 우선순위(C5), reset-stop 검증 조건(C6) 미비 |
| P0-8 unflip·오버레이·수신시각·불변 캡처·트윈 batch·보정 절차 | 5장 | 반영 |
라인 인용 검증: app.py 283/299-309/337/156-164/371-379, sim_worker 123/145-178 모두 실제 코드와 일치.

## C. 상태 머신 점검 항목
1. cancel 요청 중 estop / estop 중 cancel / 이중 cancel
2. stopping 중 deadline 초과, ACK 영영 없음 -> watchdog 경로
3. ACK timeout 후 늦은 실행: epoch/deadline 검사가 worker 쪽에서 실행 전 수행되는가
4. 재시작: queued/needs_help/executing/stopping 전부 aborted(server_restart), 자동 재개 없음
5. needs_help에서 executing 직행 금지(perceiving 경유), confirm 중복/오래된 version 409
6. estop latch 중 task 수락/teleop/manual 차단, reset-stop 이후 새 epoch
7. 종결 상태 불변(terminal에서 전이 불가), failed vs cancelled vs aborted 구분
8. 모든 비종결 상태가 deadline 또는 외부 이벤트로 종결 가능(데드락 없음)
9. 순수 로직: 시계 주입(monotonic), 락 순서, 재진입

## D. 실행 로그
(전체 pytest, 뮤테이션 결과)

## 재개 지점
22:10 지적 C1~C6을 구현자(49eRW8bk3gTrLYJw)에 전달, 회신·파일 대기 중. 다음: notes/contract_r5.md, perception/interfaces.py, 상태머신 파일, tests/test_contracts_r5.py 존재 확인 후 B/C 채움 -> 측정 락 안 전체 pytest.

## E. v1.1 재검토 (문서 범위, 11-10 V-CT)
- I-CT는 Codex 한도로 11-12 13:50경까지 정지. interfaces.py/상태머신/tests/전체 pytest/뮤테이션은 Codex 복귀 후(미실시).
- C1~C6 반영 위치 확인: C1 4.2, C2 4.4, C3 3.1, C4 4.3, C5 4.6, C6 4.7. 전부 반영.
- 라인 인용 약 30곳 직접 대조 일치(app.py 106/118/123/313/318/333/366, sim_worker 141/143/154-155/163-164/20, control.py 142/260/301/304/320/392-393, ik.py 57-60, perception_stub 74-75/93-94/108, teleop 33).
- 직접 재현: solve_ik 도달불가 5회 360/323/341/333/344 ms [시뮬GT 타이밍](문서 339~385와 일치, flock 내).
- 신규 지적 V1(watchdog 종료 실패 영구 stopping), V2(비executing cancel 시 RPC 잔여 대기), V3(재생성 후 q_hold 부재·DB 영구 실패·큐 empty 근사), V4(held_object 시 place-only task 충돌) -> D-CT(XLc6VoHDsFEKDkck)에 전달, 회신 대기.
- 판정(문서): NEEDS WORK (V1 데드락 가능성). V1~V4 반영되면 문서 PASS 가능. 코드/테스트 PASS는 별개.
## 재개 지점 (갱신)
D-CT 회신 후 V1~V4 반영 확인 -> 문서 판정 확정. Codex 복귀 후: interfaces.py/상태머신/tests 대조, 측정 락 안 전체 pytest(104+신규), 뮤테이션 1~2개.

## F. 재검토2 (D-CT 205줄판)
V1(4.6-4: SIGTERM2s->SIGKILL2s, 실패 시 aborted(worker_unkillable)+recovery owner, 재시작만 복구), V2(4.6-5 draining owner, 5s 상한), V3(4.7 respawn q_hold, DB 영구실패 503, outstanding 집합), V4(4.4 held_object 시 POST /tasks 409) 모두 반영 확인. 문서 판정: PASS(설계 문서 한정). 코드/테스트/pytest/뮤테이션: 미실시, Codex 복귀 후.
## 재개 지점 (최종 갱신)
Codex(11-12 13:50경) 복귀 후 interfaces.py/상태머신/tests 대조(특히 draining/recovery owner, outstanding drain, STALE_EPOCH, 4.6 조합 테스트가 가짜 시계로 존재하는지), 측정 락 안 전체 pytest(104+신규), 뮤테이션 1~2개.
