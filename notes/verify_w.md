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
