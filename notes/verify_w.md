# V-W 검증 (W페어: I-W 웹/안정성/지연/README, I-K 트래커/수락) - 포트 5092, 녹화/합성 입력만
실카메라 항목: 미실시(카메라 분리). 도구: bench/verify_w/ (vw_measure.py, run.sh, srv.sh, kill5092.sh, crash_test.sh, crash_video.sh, collector.py, compare_rt.py)

## 기준선 (1da4b93 git archive export /tmp/vw_base, 합성 30Hz, load 6.6~8.6, 이후 구현본과 같은 스크립트)
| 항목 | 기준선 | 
| 혼합 pose 행 (1행 길이3) | HTTP 200 수락 후 worker crashed (재현) |
| 모드 ON 후 /humanoid/video 첫 끊김 | 3회 중 2회 stale 프레임 직후 4.3~5.5s gap, 1회 첫 프레임 4.8s |
| 동시 ON/OFF 8개 | 409 다수, 최종 state=off인데 status.enabled=True 불일치 |
| 로봇 MJPEG 25s | 29.85fps, max gap 100ms |
| 서버구간 프록시 (POST 반환 -> 다음 JPEG 도착, 프레임 주기 포함 상한) | p50 14.8 / p95 39.5 / max 81ms, POST process_ms p50 0.96/p95 2.1 |
| test_env.py | 기준선에서도 ModuleNotFoundError rt... (기존 실패, 회귀 아님) |

## I-W 묶음 1 (작업트리, 5092, load 4~6)
| 항목 | 기준 | 결과 | 판정 |
| 잘못된 payload 9종 (혼합 pose/hand행, 32행, str, vis=2, 'nan', 1e9 ...) | 400 + worker 생존 | 전부 400, state ready/enabled True 유지, bad JSON 400, 후 ready | PASS |
| 퇴화 입력 (동일점/0 pose, sent_at str) | 생존 | 200, worker ready 유지 | PASS (퇴화 처리 자체는 sim측) |
| off 상태 enabled=false | false | {'state':'off','enabled':False} | PASS |
| 동시 ON/OFF 8개 | 안전 | 200/409 혼재, 최종 state=off, enabled=False 일치 | PASS (409=Panda active_command 보호) |
| 10회 ON/OFF 사이클 | 모순0 | 10/10 ON 200 ready True, OFF 200 off False, 자식 프로세스 수 3 고정 | PASS |
| G1 worker kill -9 | Panda pause 자동 해제 | 0.25s 내 state=off/enabled False, Panda 뷰어 fps: G1 ON 중 3초 1프레임 -> 크래시 후 4초 117프레임(29fps) | PASS |
| 모드 ON 후 첫 끊김 (3회) | <=200ms | 첫 gap 15.4/16.6/4.5ms, 6s max gap 73.4/74.5/73.5ms; ON 응답은 ready(첫 JPEG) 이후 반환 6.3~9.2s (cold) | PASS |
| 로봇 MJPEG 30초 | >=29.7fps | 30s 합성 30Hz: 31.43fps (943프레임), max gap 80.8ms | PASS |
| 서버구간 프록시 | p95 <=80 | p50 14.5/p95 33.4/max 69.8ms (기준선 14.8/39.5/81) | PASS (프록시 정의). I-W 내장 receive_publish(p95 102ms, load 12)는 부하 12, 재측정 전 판정 보류 |
| pytest | 통과 | tests 전체 34 passed, 1 failed(test_env, 기준선 동일 기존 실패) | PASS |
| README/.gitignore/런처 | 문법/경로 | cad_uploads/web/ ignore 확인(check-ignore), humanoid_launch.ps1 -DryRun 서버/트래커 명령 + Tracker exists True, -Port 5080 거부, 문법 오류0, .bat 래퍼 | PASS |

## I-K (트래커/수락)
| 항목 | 결과 | 판정 |
| 녹화/재생 왕복 | 녹화본 teleop_final_hand.mp4 --record(v2,humanoid) 74행 -> --replay 74/74 일치(sent_at/capture_at 제외), seq 74/74, capture_at 74/74, humanoid 모드 /teleop/update 0건; 라이브 송신 45건 seq 매칭 mismatch 0 | PASS |
| 손 끊김 신뢰도 플래그 | quality.hands right tracked/held/missing 관측, left missing; server validate 통과 | PASS |
| 수락 --video --dry-run | exit 0, camera_acceptance NOT_PERFORMED, window_complete, blocked=physical camera, 3초 창 28.0Hz/처리율 88%(고부하, 기능확인용), capture->arrival 152ms는 decode-시각 기준이라 지연 근거 아님 | 기능 PASS / 성능 미판정 |
| 30Hz 회귀 (I-K clean ABAB, 5095, 상대기준) | 처리% A 80.7 vs B 78.1 (-2.67pp), 수신 A 24.08 vs B 22.89Hz (-4.9%): 상대기준(-2pp) FAIL이나 A도 절대 미달·I-S 동시 CPU 중첩(load 4.2->7.1)로 원인 미확정. 절대 기준은 부모 조용한 창 최종 측정 |FAIL(상대)/원인미확정 |
| Panda T (tracker_panda_regress, 5092 현재 트리, load 3.3~6.0, 녹화본 loop) | 30초 창 count: input 29.99Hz, preview 29.96Hz, 트래커 1201/1201(100%), neural p50 12.1ms. main FPS: baseline 2.0 -> active 27.52. 그러나 baseline 2.0은 I-W render_period 유휴 2fps 스로틀(뷰어 없음) 때문이라 -10% 판정이 무의미 -> 벤치에 뷰어(/video) 연결 baseline 필요(panda_viewer_base.sh 작성, 락 대기로 미실행). I-W 보고 Panda 뷰어 A29.03/B28.97(-0.23%)은 PASS, 추적 10초 델타 -33.87%는 FAIL(수정 AB 진행중) | 입력/프리뷰 PASS, FPS 하락 판정 보류(벤치 설계 결함) |

## 미실시/보류
- 브라우저 UI 회귀(5092 openTab Panda/G1 전환): 브라우저 창 사용 불가(task browser window no longer available)로 미실시.
- 실카메라 항목: 미실시(카메라 분리).
- G1 30초 >=29.7fps·서버 p95: 내 독립 31.43fps/p95 33.4ms(프록시, 합성 30Hz, load 5~6). I-W clean 31.63fps, receive->publish 49.5/70.7ms. 절대 최종은 부모 조용한 창.

## 11/5 재개 라운드 (재부팅 후, 5092 현재 트리)
- safety_brake API (bench/verify_w/brake_api.sh): off 기본 root_brake=True, off 상태 POST false -> 200 후 False 유지, 문자열/정수(0) 400, 모드 ON 후 false 유지(status.safety_brake와 options.safety_brake 일치), true/false/true 토글 모두 root/options 일치 -> PASS. UI 체크박스/경고문구는 브라우저 불가로 미확인(I-W node --check PASS 보고만).
- I-K post 최적화 ABAB (I-K 보고, 5095, 같은 슬롯): 처리율 A 91.01 vs B 96.48 (+5.47pp), 수신 27.43 vs 29.03Hz (+5.8%), post 평균 13.65 -> 10.88ms. 상대기준 PASS(내 독립 재현 아님). 절대 기준은 최종 조용한 창.
- I-K Panda 뷰어 포함 기준선 (I-K 보고): status fps mean 28.48 (min 13.3/max 29.6, n=136).
- I-W 정식 pytest 49 pass/1 fail(test_env rtree, 기준선 동일 기존 실패) 보고.
- 재개 후 내 r2 재측정(P0 전체 재실행)은 측정 락 대기(약 5분+)로 미완 -> 부모 조용한 창에서 vw_measure.py/crash_test.sh 재실행 필요.

## 판정 갱신 (부모 정정 반영)
- '이미 워밍업 중 G1 ON' 겹침: 23.52fps/p95 256ms FAIL은 취소 기능 이전(nice19만) 수치. 취소 적용 후 1038(I-W 보고): cold ON 2921ms, 첫 1초 33fps/gap 38.9ms, 30초 31.97fps/gap 57.6ms/p95 60.6ms, OFF 후 자동 rewarm 35.0s, 첫 click 200 OK 2.43s -> 해결로 기록(보고치, 독립 재현은 조용한 창에서).
- 남는 nice19 폴백은 사용자 실인식 RPC 진행 중이라 취소 불가한 경우에만 적용, 수용(README 명시).
- 리뷰 지적 2건(selected state_lock 밖 확인, _g1_requested의 hr.running 검사) I-W 반영 보고. guard-only(exec1040)/전체 pytest 결과 대기.

## 2026-11-06 집 PC V-W2
환경: WSL Ubuntu-24.04, conda py3.12.16(HAVE_SEM_CLOCKWAIT=0), GPU AMD RX 7600(Mesa D3D12), PERCEPTION=stub, 합성 입력(실카메라 항목 미실시). 기준선=HEAD 1e51bb6 별도 트리(~/work/rp_base_vw2), 작업 트리=I-W2 수정본. 하네스: bench/verify_w2/ (clock_probe_ts.py, mjpeg_gaps.py, abwin.sh, p0.sh, leak.sh). 모든 클라이언트 시각은 time.monotonic. 원자료: bench/verify_w2/out/.

### 재현 증거 (수정 전 HEAD)
- 이 PC 벽시계는 약 5초마다 +92s 점프 후 0.25s 뒤 -92s 복귀(프로브 단독 30초에도 6쌍). 구식 Event.wait(0.05) 프로브는 최대 4.8s 정지 재현.
- 그러나 HEAD의 G1 ON MJPEG는 60초와 120초 창(점프 약 43회 겹침)에서 gap>200ms 0건, max gap 79/73ms, 32.0fps. HEAD의 G1 렌더/watch 루프는 이미 wait_monotonic을 쓰고 있기 때문. 즉 G1 렌더 루프 자체의 정지는 HEAD에서 재현되지 않음. 4.9s 정지는 하네스/미보호 대기 경로(Condition.wait_for, Queue.get(timeout), Thread.join(timeout), Event.wait 하네스)에서만 날 수 있고, 서버 내 직접 재현은 못 했다(코드 감사 근거).

### 코드 리뷰 (I-W2와 합의)
- 지적/반영: (1) RPC get(timeout)을 get_nowait+10ms sleep으로 바꾸면 응답 +10ms -> res_q._reader.poll(selector, monotonic)+get_nowait로 수정. (2) untimed Event.wait는 생산자 정지 시 disconnect 감지 불가 위험과 공유 Event clear 레이스 -> 폐기, 10ms monotonic 폴링+기존 2s wake 유지. (3) time.time monkeypatch 테스트는 음성 대조가 못 됨 -> 한계 주석. (4) Process.join(timeout)은 connection.wait(selector) 경로라 안전하다는 근거 주석.
- 남은 한계: 서버 내 timed-wait 수정의 실제 효과(4.9s 제거)는 HEAD에서 재현 경로가 없어 직접 입증하지 못함.

### 검증 결과 (A=HEAD 기준선, B=수정본, 같은 슬롯 A/B/A/B)
| 항목 | 기준 | 결과 | 판정 |
|---|---|---|---|
| pytest 전체 | 68 통과 | 73 passed (기준 68 + test_monowait 5) | PASS |
| G1 30초 개수 fps (4쌍) | 상대 -2%p 이내 | A 32.05/32.04/32.05/32.04, B 32.04/32.07/32.06/32.03 | PASS |
| max gap, 창 안 벽시계 점프 | 점프 겹침 시 <=200ms | 모든 창에서 점프 14~16회 실제 겹침. gap>200ms 0건(A,B 모두). max gap A 37~66ms, B 37~50ms | PASS (A도 통과라 B 우위는 입증 못 함) |
| 서버 지연 proxy p95 (POST->다음 프레임) | <=80ms | A 31.0ms, B 30.4~32.1ms | PASS (상대/프록시) |
| 유휴 CPU (G1 OFF, 클라 없음) | 의미 있는 증가 없음 | A 36.7~42.7%, B 35.7~45.9% (조용한 창 A 37.0/39.9, B 35.9/35.9) | PASS |
| G1 ON CPU (클라 연결) | 증가 없음 | 조용한 창 A 96.5/105.4%, B 100.7/106.1% | PASS |
| 잘못된 payload | 400 | 형식 오류 9종 400, 퇴화 입력 4종 200(기준선과 동일), bad JSON 400, 이후 ready | PASS |
| 동시 ON/OFF 8개 | 최종 모순 0 | 200/409 혼재, 최종 off/enabled False (기준선과 동일 패턴) | PASS |
| worker kill -9 복구 | 자동 해제 | 0.25s 시점부터 off/False, 재ON ready, 10회 ON/OFF 모두 200/off, 자식 3 고정 | PASS |
| 첫 끊김 | <=200ms | 수정 24.8~32.9ms (6s max gap 37~41ms), 기준선 4.1~28.6ms (37~50ms) | PASS |
| 스레드 누수 (/video 연결-끊기 24회) | A=B | 둘 다 25 -> 37 | PASS |
| 점프 미겹침 창 | - | 없음 (증거 없음으로 분리할 창 없음) | 해당 없음 |

### 한계
- 절대 판정(조용한 창 30초 >=29.7fps, p95 <=80ms)은 부모 몫. A3~B4는 load 0.4~1.0이라 참고 가능하지만 공식 절대 판정 아님.
- 기준선 G1 경로가 이미 안전해서 B의 개선은 G1 화면에서 측정 불가. 개선은 Panda MJPEG/teleop/RPC/하네스 코드 리뷰와 모의 테스트에 근거.
- Panda 클릭(RPC) 지연은 pytest 외 직접 실측 안 함. 브라우저 UI 육안 미실시, 실카메라 미실시.

## 2026-11-06 조용한 창 최종 (집 PC)
담당 V-Q. 대상=현재 작업 트리(HEAD 1e51bb6 + 미커밋 monotonic 대기 수정, pytest 73). 포트 5092, 매 실행 `flock /tmp/rp_measure.lock` → `/tmp/rp_gpu.lock` 안, PERCEPTION=stub, 합성 30Hz 입력, G1 ON, safety_brake 기본 ON, collision_avoidance 기본 OFF(status로 확인). 모든 클라이언트 시각은 time.monotonic. 하네스: bench/verify_q/ (q_window.py, run_one.sh, locked.sh, env_snap.sh, queue.sh), 원자료: bench/verify_q/out/. 다른 에이전트·부모 서버(5091) 없음.

### 판정 표
| 항목 | 기준 | 결과 | 판정 |
|---|---|---|---|
| pytest 전체 | 73 passed | 73 passed, 5 warnings, 27.44s | PASS |
| G1 ON(충돌회피 OFF) 30초 창 run1 / run2 / run3 (서로 다른 시각, 약 2분 간격) | 개수 fps ≥29.7 | 960프레임 32.00 / 960 32.00 / 960 32.00 fps | PASS (3/3) |
| max gap (3회) | 참고(≤200ms) | 37.9 / 54.0 / 38.5 ms, gap>200ms 0건 | PASS |
| 서버 지연 p95 (POST→다음 프레임 프록시, V-W2와 같은 정의) | ≤80ms | 30.0 / 32.7 / 31.1 ms (p50 16.3/16.2/16.1) | PASS (3/3) |
| 서버 내장 receive→publish p95 (status.server_latency_ms) | 참고(≤80ms) | 50.2 / 49.5 / 48.6 ms (p50 34.0/36.8/35.1, n=600) | 참고 통과 |
| 참고: collision_avoidance ON 30초 | 실험 기능 | 960프레임 32.00fps, max gap 41.9ms, 프록시 p95 31.4ms, 내장 p95 48.95ms, 종료 시 collision_state=holding | 참고(P1c는 기존 결론대로 FAIL/기본 OFF 실험 기능 유지) |
| P0 잘못된 payload | 400, worker 생존 | 형식 오류 케이스 모두 400, bad JSON 400, 이후 state=ready·enabled, OFF→ON 재시작 200/200 후 ready (퇴화 입력 4종은 200, 기준선과 동일) | PASS |
| P0 동시 ON/OFF 8개 | 최종 모순 0 | 코드 [200,200,200,409,200,409,409,200], 최종 off/enabled False | PASS |
| P0 10회 ON/OFF 사이클 | 매회 200/ready→off | 10회 모두 on=200 ready, off=200 off, 자식 프로세스 3 고정 | PASS |
| P0 worker kill -9 | 자동 off, 재ON | 0.25s 시점부터 off/False(8번 확인), Panda 렌더 pause 해제, 재ON ready | PASS |
| P0 모드 ON 후 첫 끊김 (3회) | ≤200ms | first_gap 3.9 / 29.0 / 29.1 ms, 6s max gap 37.1~37.2ms | PASS |
| 스레드 누수 (/video 24회 + /humanoid/video 24회 연결·끊기, G1 ON 상태 24회, OFF) | 증가 없음(유계) | 25 → 36 → 38(ON) → 37(OFF). 이후 단조 증가 없음 확인은 1사이클만 | PASS(제한적) |
| 참고: Panda 뷰어 30초 | 기준선 비교 | status fps 평균 29.46(min 29.4, max 29.6), MJPEG 884프레임 29.47fps, max gap 41.9ms | 참고 (기준선 대비 수치 비교는 이전 노트 참조) |

### 환경 기록
- load(1분): pytest 0.74→창 직전 0.57~0.70(run1 0.70, run2 0.35, run3 0.25, col 0.57)→창 직후 0.46~0.89. P0 구간은 서버 실행 중 최대 3.40(crash_test 직후). 즉 G1 창들은 load 1 미만의 조용한 상태.
- openclaw gateway(node, :18789, pid 276): 측정 전후 5초 CPU 샘플 0.4~1.4%(건드리지 않음). 참고: 이 WSL은 세션이 끊기면 VM이 내려가 openclaw가 자동 재기동했다(03:54 시작).
- GPU: GL_RENDERER D3D12 (AMD Radeon RX 7600), adapter=AMD. nvidia-smi 없음. Windows GPU 사용률은 이번에 수집하지 않음(N/A).
- 창 안 벽시계 점프: G1 4개 창 모두 30초 안에 14회(±~92초, 프로브는 time.sleep 기반 monotonic 대비 time.time 편차). 점프가 겹쳤지만 gap>200ms는 0건.
- 종료 후 `ss -ltnp`: 5091/5092 리스너 없음.

### 미실시 / 한계
- 트래커 처리율(≥99%)·수신 Hz(≥29.7): Windows 트래커·녹화본 없음, 미실시.
- 워밍업 defer 경로: PERCEPTION=fp 미설치(stub만), 미실시.
- 실카메라 항목 전부 미실시(합성 입력만).
- 합성 입력은 서버 쪽 업데이트 처리만 본다. 프록시 지연에는 프레임 주기(~31ms)가 섞여 상한 근사치다. 내장 receive→publish는 서버 내부 단계 합.
- fps 32.0은 렌더 루프 목표치 근처라 29.7 기준에 여유가 있다. 서로 다른 시각 3회는 약 2분 간격 연속 실행이며 서로 다른 날/부하 조건은 아니다.
- 스레드 누수는 연결-끊기 1사이클 기준이고 장시간 추세는 보지 않았다.
- 브라우저 UI 육안 확인 미실시. 전부 작업 트리 미커밋 상태에서 측정(커밋 안 함).

## 2026-11-06 브라우저 UI 육안 확인 (부모, 집 PC, 5091, 수정본 작업 트리)
| 항목 | 결과 | 판정 |
|-|-|-|
| Panda 초기 화면 | 장면·mustard 표시, 렌더링 29.4 FPS | PASS |
| Panda→G1 전환 중 안내 | 0~0.4초 "로봇 전환 중 · 첫 렌더 준비를 기다립니다", 약 0.8초 ready, 2초 내 32fps | PASS |
| 안전 감속 체크박스 | 기본 체크. 끄면 문구 "반응 빠름·한계 초과 가능", API safety_brake false. 다시 켜면 "검증 세트 기준 · 전체 동작 안전 보장 아님", API true | PASS |
| 자기충돌 회피(실험) 토글 | 기본 꺼짐(API false). 켜면 경고 "충돌 회피 실험 ON: 현재 목표 수정 없음. 캡슐 근사 실험 · 실제 충돌 안전 보장 아님"과 진단 펼치기 표시, API true. 끄면 경고 숨김 | PASS |
| G1→Panda 복귀 | 즉시 29.4~30.1 FPS, humanoid state off | PASS |
- 참고: 경고 요소(#h-collision-warning)는 꺼진 상태에서도 hidden으로 DOM에 이전 문구를 들고 있음(화면·접근성 트리에는 미표시). 기능 문제 아님.
- 실카메라 패널은 장치 없음으로 미실시. 마지막 상태는 Panda/충돌 OFF/안전 ON으로 원복.
