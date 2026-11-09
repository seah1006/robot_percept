# V-T 검증 (동작 따라하기, 라운드 1) - 포트 5090, 녹화/합성 입력만 사용
verdict: FAIL (라운드 1) - 안전/게이팅/히스테리시스/스모크 PASS, 실시간성(추종 지연, 명령률) FAIL
## 측정 (스크립트 bench/verify_t/*.py, 합성 30Hz 입력, 시스템 load avg ~16 공유 환경)
- 입력 수신률 27~30Hz (서버 /teleop/status hz 29~33). 그러나 로봇 갱신(tick)은 sim 루프(render 포함) 속도에 묶임: /status 프레임 8~9Hz.
- 추종 지연: teleop_target 대비 TCP 최적 지연 1.4s (탐색 상한 도달), RMS 45mm(원) / 73mm(사각, 지연 보정 후); 지연 0 일 때 86~107mm.
- 기대 경로(스케일 매핑) 대비 RMS 46mm(원) / 88mm(사각) (최적 지연 1.45s).
- 관절속도 (status 샘플 기준) 최대 0.68~0.79 rad/s (한도 .65에 근접/약간 초과, 샘플 시간 오차), 한 틱 최대 dq 0.040~0.042rad -> IK 점프 없음.
- 원인: tick 이 sim 루프당 1회, dt=min(.04, 경과) 로 cap -> 루프 < 25Hz 면 시뮬 시간이 벽시계보다 느리게 진행(로봇이 느려짐).
## 안전 PASS
- 손 소실(detected=false): 4.5mm 이후 정지, 이후 0mm 이동. 패킷 중단(stale .3s): 정지(0.8s 내 10mm 이후 0).
- 작업공간 클램프: 극단 입력 시 target [.25,.35,.85] / [.70,-.35,.36] 로 클램프.
- 핀치 히스테리시스: <.28 닫힘, .28~.42 유지, >.42 열림 (12단계 확인).
- 잘못된 입력(-1,2,'a') 400. reset 시 teleop 자동 OFF. OFF 후 /click + pick(mustard 잡음)+place(err 0.8mm, upright 1.0) 정상.
- --replay 61 updates 10.1s 정상 재생, 타겟 이동 확인.
## UI
- 따라하기 모드 패널 펼침/상태/미리보기 표시, JS 에러 0. 단 좌하단 고정 패널이 집기/놓기 버튼을 가림 (screenshot ui_teleop.png).
## 기존 기능
- pytest tests/test_smoke.py: 2 passed. /click OK. FPS 회귀: 공유 부하로 측정 불가 (렌더 11~12 FPS 텔레옵 중 vs 부하 타 프로세스).
## 라운드 2 (재시작 후, 같은 합성 입력)
- verdict: FAIL (추종 속도). status 프레임 11~13Hz, 입력 30Hz 수신.
- 관절속도 최대 0.30~0.31 rad/s (이전 .68~.79) -> 속도 한도 OK, IK 점프 없음(단일 틱 dq .02~.03).
- 그러나 지연 >=1.45s(탐색 상한), 원 RMS 56mm, 사각 RMS 81~99mm.
- 스텝 응답(타겟 +0.14m y 점프): TCP가 약 22 mm/s 등속 램프로만 이동 (5s 후 0.104m). 설계상 오차 클립 .03m*게인4 = 최대 ~120mm/s 여야 함 -> 실제 5배 느림. sim 시간이 벽시계보다 느리거나(RTF<1) 서보 게이팅/게인 문제.

## 라운드 3 (command 적분 수정 후) - FAIL (안정성)
- 스텝 응답 개선: +0.14m 점프를 ~0.7s에 도달, 오버슈트 ~8% (0.151), 정착 0.140. (이전 22mm/s 램프 해결)
- 하지만 사각 경로 10s: 상태 샘플 기준 관절속도 최대 2.58 rad/s, 한 샘플 dq 0.27 rad (한도 .65), RMS 124mm(최적 지연 .25s) -> 불안정/점프.
- 이어서 worker crash: state=crashed, ValueError: Arm target outside joint limits at sim/teleop.py:17 `self.env.set_arm_target(self.env.arm_qpos())` (측정 q가 한계를 살짝 벗어나면 hold 호출이 예외). 서버 sim_time 12.9 에서 정지. rtf 0.95, servo_ticks 805.
- 요청: hold/target 은 clip(q, limits) 후 전달, 예외는 worker 를 죽이지 않도록 teleop.tick try/except -> teleop_enabled=False; command 적분은 측정 q 와 괴리(windup) 제한 (|command-q|<=0.1rad), 속도 .65 rad/s 보장 테스트 추가.

## 라운드 4 - 동작/안전 PASS (새 서버 5090)
- 스텝: +0.14m 를 ~1.2s 에 정착, 오버슈트 없음(0.1399). rtf 1.0, servo_ticks 증가, error None.
- 원 경로: 최적 지연 0.4s, RMS 5.0mm(기대 경로) / 5.4mm(target). 사각: 지연 0.5~0.6s, RMS 36~43mm (코너 둥글림).
- 관절속도(프레임 타임스탬프 기준): p50 .26-.29, p95 .55, max .63-.68 rad/s (샘플링 오차 포함, 한도 근처). 한 샘플 dq<=.11rad. 크래시 없음.
- 손 소실: 0.2mm 이후 정지. stale: 1mm 후 정지. 핀치 히스테리시스 OK. 잘못된 값 400. 작업공간 클램프 OK (x .25~.70, z .36~.85, y +-.35 도달/수렴). reset 시 teleop OFF. OFF 후 click+pick(mustard)+place err .8mm OK.
- 남은 항목: 라운드5 UI(나란히 비교 레이아웃, 방향 일치, 프리뷰 fps), 실제 손 영상 replay, 메인 FPS 회귀.

## 라운드 5 (UI 나란히 비교) - 판정: 조건부 PASS (UI/방향/안전 PASS, FPS 회귀·프리뷰 fps FAIL/미달)
- 레이아웃: 켜기 -> 좌 '내 카메라·손 추적'(스켈레톤, 초록 작업공간 박스) | 중간 배지(손 없음/Hz/전송 ms/집게/카메라 FPS) | 우 로봇 시뮬레이션(동일 크기). 420px 폭에서 위/아래 스택 OK. 끄기 -> #video-wrap 원위치, 이후 물체 클릭 선택/포커스 뷰 정상, 켠 상태에서도 포커스 패널 유지. JS 오류 0.
- 방향: 합성 입력 x+.15 -> TCP 이미지 u +51px(오른쪽), y-.15(손 위) -> v -50px(위). 일치.
- 손 있는 jsonl replay(teleop_round2_async.jsonl): 입력 11->20Hz, detected True, 집게 닫힘/열림 반영, 목표 이동. mp4 재처리는 스켈레톤이 그려진 영상이라 손 미검출(0 hands) -> 영상 입력 경로는 jsonl 로 검증.
- 프리뷰: status preview_hz 11~14Hz (목표 >=15 미달, 공유 부하 하 측정), tracker 영상 처리 13~19Hz.
- 메인 FPS(브라우저 닫고 /status fps 평균, 공유 부하 노이즈 큼): OFF 14.3/17.0, ON idle 19.0/12.5, ON +30Hz 입력 10.6/9.0 -> 입력 스트리밍 시 -26%/-47% (목표 <10% 미달). 서보 틱(50Hz, 야코비안)·status 직렬화 비용 의심. 요청: tick 비용 프로파일/ status 갱신 분리.
- 서버 5090이 가끔 외부 요인으로 종료됨(원인 불명, 로그 에러 없음).
- 스크린샷: tmp/vt/ui_on_focus.png, ui_on_hand.png, ui_mobile.png (얼굴 포함 녹화 프레임 - 공유 주의).

## 2026-11-06 집 PC 트래커 절대 판정 (스톡 영상)
- 구성: 서버 master 7f96fec (worktree ~/work/rp_master, PERCEPTION=stub, G1 ON, 포트 **5094**: Windows→5092 중계에 CLOSE_WAIT 약 60개가 쌓여 막혀 있어 5094 사용, WSL 내부 5092는 정상). 트래커 tools/teleop_tracker_win.py(저장소 497b6fb 이후 최신본, SHA256 9378ABC5…80AF, Windows 사본과 동일) / Windows Python 3.12.10, mediapipe 1.2.2 / `--mode humanoid --video stock_person_720p30.mp4 --loop-video --seconds 30`, transport http/ws 교차 6창(http,ws,http,ws,http,ws), 한 번 실행 3분 55초(이중 락, 21:33:56~21:37:42, 포트 5094).
- **입력은 회사 녹화본이 아니라 Pexels 무료 영상 2개를 1280x720 30fps로 재인코딩한 스톡 영상**(443프레임, 14.8초, 프레임 복제 없음, 사전 검출률 손 91%/자세 100%). 사람 얼굴·손 동작이 회사 녹화본과 다르다. **실카메라 항목은 미실시**(카메라 장치 없음).
- 동시 부하: G1 렌더, 서버 쪽 MJPEG(/humanoid/video, /teleop/preview.mjpg) 시청 2, /status/ws push 구독 1. 창 직전 load1 0.60~0.96, openclaw CPU 0.4~0.6%. 창 안 벽시계 점프 12~14회(기존 환경 특성, G1 gap>200ms 0). 원자료: bench/verify_t2/out/t2/*.json, out/t2_windows_raw/(트래커 metrics·stdout·stderr), out/t2.env, out/t2.server.log, out/t2_summary.md. 스크립트 bench/verify_t2/{locked_t2.sh,run_t2.sh,t2_win.py,win_run.ps1,summ_t2.py}.
- 서버 수신 Hz 정의: /humanoid/status input_count가 처음 증가한 시각~마지막 값에 처음 도달한 시각(0.25초 샘플링)의 증가분/시간. 시작 쪽 경계 때문에 실제보다 약 0.1~0.2Hz 낮게 나올 수 있다(보수적).

| 지표 | w1_http | w2_ws | w3_http | w4_ws | w5_http | w6_ws | 차이 ws-http 평균 | 95% CI (창 3쌍 부트스트랩) | 판정 |
|-|-|-|-|-|-|-|-|-|-|
| 처리율(ratio) | 100.000 | 100.000 | 100.000 | 100.000 | 100.000 | 100.000 | +0.000 | [+0.000, +0.000] | 차이 입증 안 됨(0 포함) |
| 트래커 hz | 30.017 | 30.017 | 30.016 | 30.015 | 30.014 | 30.019 | +0.001 | [-0.001, +0.005] | 차이 입증 안 됨(0 포함) |
| 손 검출률% | 90.566 | 90.566 | 90.566 | 90.566 | 90.566 | 90.566 | +0.000 | [+0.000, +0.000] | 차이 입증 안 됨(0 포함) |
| 자세 검출률% | 100.000 | 100.000 | 100.000 | 100.000 | 100.000 | 100.000 | +0.000 | [+0.000, +0.000] | 차이 입증 안 됨(0 포함) |
| neural p50 | 23.619 | 23.938 | 24.028 | 26.404 | 24.444 | 24.019 | +0.756 | [-0.425, +2.376] | 차이 입증 안 됨(0 포함) |
| neural p95 | 26.928 | 27.178 | 27.383 | 29.833 | 28.178 | 27.727 | +0.750 | [-0.451, +2.450] | 차이 입증 안 됨(0 포함) |
| post_ms p50 | 4.303 | 1.551 | 4.503 | 1.707 | 4.837 | 1.574 | -2.937 | [-3.262, -2.752] | 0 불포함 |
| post_ms p95 | 22.178 | 2.289 | 22.709 | 2.434 | 21.295 | 2.271 | -19.730 | [-20.276, -19.024] | 0 불포함 |
| preview 전송수 | 901 | 901 | 901 | 901 | 901 | 901 | +0.000 | [+0.000, +0.000] | 차이 입증 안 됨(0 포함) |
| 네트워크 오류 | 0 | 0 | 0 | 0 | 0 | 0 | +0.000 | [+0.000, +0.000] | 차이 입증 안 됨(0 포함) |
| sent_updates | 901 | 900 | 901 | 901 | 901 | 900 | -0.667 | [-1.000, +0.000] | 차이 입증 안 됨(0 포함) |
| source_frames_due | 901 | 901 | 901 | 901 | 901 | 901 | +0.000 | [+0.000, +0.000] | 차이 입증 안 됨(0 포함) |
| updates | 901 | 901 | 901 | 901 | 901 | 901 | +0.000 | [+0.000, +0.000] | 차이 입증 안 됨(0 포함) |
| 서버 수신Hz | 29.896 | 29.981 | 29.784 | 29.886 | 29.975 | 29.950 | +0.054 | [-0.025, +0.102] | 차이 입증 안 됨(0 포함) |
| G1 fps | 31.993 | 31.998 | 31.980 | 31.999 | 32.023 | 32.001 | +0.001 | [-0.022, +0.019] | 차이 입증 안 됨(0 포함) |
| G1 max gap | 47.700 | 41.400 | 63.000 | 41.900 | 43.300 | 39.000 | -10.567 | [-21.100, -4.300] | 0 불포함 |
| 서버 CPU main% | 16.000 | 13.500 | 16.300 | 14.700 | 16.500 | 13.600 | -2.333 | [-2.900, -1.600] | 0 불포함 |
| 서버 CPU tree% | 75.100 | 73.300 | 76.300 | 79.600 | 77.700 | 73.100 | -1.033 | [-4.600, +3.300] | 차이 입증 안 됨(0 포함) |
| Win 트래커 CPU %전체 | 0 | 0 | 0 | 0 | 0 | 0 | +0.000 | [+0.000, +0.000] | 차이 입증 안 됨(0 포함) |
| Win 트래커 CPU %1코어 | 0 | 0 | 0 | 0 | 0.100 | 0.100 | +0.000 | [+0.000, +0.000] | 차이 입증 안 됨(0 포함) |
| Win 시스템 CPU 평균% | 66.900 | 70.400 | 69.900 | 82.300 | 74.400 | 70.200 | +3.900 | [-4.200, +12.400] | 차이 입증 안 됨(0 포함) |

### 절대 기준 판정 (6창 모두, 창 3쌍은 같은 슬롯 교차)
| 항목 | 기준 | 결과 | 판정 |
|---|---|---|---|
| processed_input_ratio | ≥99% | 6창 모두 100.0% (updates 901 / source_frames_due 901, unprocessed 0) | PASS 6/6 |
| 트래커 hz | ≥29.7 | 30.014~30.019 | PASS 6/6 |
| 서버 수신 Hz | ≥29.7 | http 29.896/29.784/29.975, ws 29.981/29.886/29.950 (최소 29.784, 여유 0.08Hz) | PASS 6/6 (여유 작음) |
| 네트워크 오류 / preview 전송 | 0 / 참고 | 오류 0, preview 901/901 전부 | PASS |
| 손/자세 검출률 | 참고 | 손 90.6%, 자세 100% (스톡 영상 사전 91%/100%와 일치) | 참고 |
| neural p50/p95 | 참고 | 23.6~26.4 / 26.9~29.8 ms (hand+pose 병렬, 프레임 주기 33.3ms 안) | 참고 |
| G1 fps | 참고(≥29.7) | 31.98~32.02, gap>200ms 0 (max gap 39~63ms) | PASS |
| 서버 CPU main/tree | 참고 | 13.5~16.5% / 73~80% (tree=worker 포함, 100%=1코어) | 참고 |

### http vs ws (차이 = ws − http, 부트스트랩 95% CI, 창 3쌍, n이 작아 CI는 거칠다)
- post_ms p50: http 4.3~4.8ms → ws 1.55~1.71ms (차이 −2.94, CI [−3.26, −2.75], 0 불포함). post_ms p95: http 21.3~22.7ms → ws 2.27~2.43ms (차이 −19.7, CI [−20.3, −19.0], 0 불포함). 세 쌍 모두 같은 방향.
- 서버 CPU main: 차이 −2.3%p (CI [−2.9, −1.6], 0 불포함). F 라운드(−약 11%p, 같은 서버 구성 단 G1+push) 보다 작다.
- G1 max gap: 차이 −10.6ms (CI [−21.1, −4.3]) 이나 http w3의 63ms 한 건이 크게 기여, 참고로만 본다(gap>200ms는 양쪽 0).
- **차이 입증 안 됨(CI가 0 포함)**: 처리율, 트래커 hz, 서버 수신 Hz(+0.054, CI [−0.025, +0.102]), G1 fps, neural 시간, 서버 CPU tree, Windows 시스템 CPU(+3.9%p, CI [−4.2, +12.4]). 즉 처리율·수신Hz 측면에서 ws가 더 낫다고 주장할 수 없다(둘 다 PASS). ws의 이점은 **전송 지연(post_ms)과 서버 main CPU**에 한정.
- 한계: Windows 트래커 프로세스 CPU%는 Start-Process 핸들 문제로 0으로 기록돼 **무효(N/A)**. 대신 Windows 시스템 전체 CPU 평균 67~82%(12코어, 다른 Windows 프로세스 포함)만 참고로 기록. GPU 사용률 N/A(AMD, nvidia-smi 없음). 스톡 영상 14.8초 반복(loop)이라 장면 반복, 실카메라 아님. 3쌍 6창 연속(약 35초 간격)이라 서로 다른 날/부하 조건은 아님. 소프트웨어 렌더/MediaPipe 가속 설정은 기본값.

### 의견 (결정은 부모)
- 트래커 절대 판정(처리율 ≥99%, 수신 ≥29.7Hz): 스톡 영상 기준 PASS. 단 실카메라·회사 녹화본은 미실시이므로 "스톡 영상 한정 PASS".
- ws를 기본으로 바꿀 근거: 처리율/수신Hz 개선은 입증 안 됨. 근거가 되는 것은 post_ms p95 약 20ms→2.3ms, 서버 main CPU −2.3%p로 지연·서버 부하 이득뿐이고 오류·회귀는 0건. 전환하려면 "처리율 개선"이 아니라 "전송 지연·서버 부하 감소" 명목이어야 하며, 기본값 전환은 되돌리기 쉬운 변경(--transport http 폴백 유지)이라 위험은 낮다. 장시간(수 분~수십 분) ws 안정성(재연결, 누수)은 이번에 미측정이라 전환 전 확인 권장.
- 정리: 측정 종료 후 서버·worker 0, 5094/5092 리스너 0, Windows python 프로세스 0 확인. worktree ~/work/rp_master 유지, 커밋 없음.


## 2026-11-06 ws 장시간·기본값 전환 (V-J)
기본 판정 **NEEDS WORK**. 직접 잰 항목만 PASS. 스크립트 bench/verify_j/, 원자료 bench/verify_j/out/{long,recon,adopt}/ + Windows C:\Users\my\rp_tracker\out_vj\{long,recon,adopt}\ (트래커 metrics·stdout).

### 구성
- 서버 master 7f96fec(worktree ~/work/rp_master), PERCEPTION=stub, 포트 5094, G1 ON(humanoid mode on, /humanoid/video 시청 1 + status 0.25초 샘플). V-T 때의 MJPEG 시청 2·/status/ws push 구독 1은 이번엔 생략(부하가 약간 낮음). 트래커는 Windows 사본(sam_camera, SHA256 9378ABC5…) 그대로, 스톡 영상 --loop-video --mode humanoid --transport ws, PowerShell 환경변수 정리.
- 조용한 창: 다른 에이전트 작업 없음 가정(I-J에게 중단 요청). 세그먼트 직전 load1 0.66~1.21, openclaw CPU 합 1.6~9.9%(세그먼트1 직전 45%는 기동 직후). 이중 락, 한 번 5분 이내(트래커 285초). 벽시계 점프는 이 PC 특성(status.csv 벽시계 열에서 수십~90초 점프 관찰, 판정엔 monotonic만 사용).

### 1) 장시간 (서버 1회 기동 약 22분, 트래커 285초 세그먼트 4개)
| 세그먼트 | 처리율 | 트래커 Hz | 서버 수신 Hz(monotonic) | post p50/p95 ms | 네트워크 오류 | 재연결 |
|-|-|-|-|-|-|-|
| 1 | 100.000% (8551/8551) | 30.001 | 29.977 | 1.67/2.49 | 0 | 0(오류 0이라 재연결 경로 미발동) |
| 2 | 100.000% | 30.000 | 30.001 | 1.62/2.31 | 0 | 0 |
| 3 | 100.000% | 30.000 | 29.983 | 1.64/2.34 | 0 | 0 |
| 4 | 100.000% | 30.000 | 29.958 | 1.66/2.40 | 0 | 0 |
- 서버(1분 간격 20점): G1 fps 첫 1분 30.67(기동 직후), 이후 31.86~32.01 안정. main 스레드 28~31(기울기 -0.015/분), fd 29~33, tree 스레드 157~160, fd 121~125, 프로세스 6 고정. RSS main 79→82MB(+0.17MB/분), tree 1315→1318MB(+0.17MB/분). 누수 판정: 세그먼트 1 vs 4에서 처리율·post p95·Hz 차이 없음(post p95 2.49→2.40), 스레드·fd 증가 없음, RSS 22분간 +3MB(약 0.2%)로 누수 징후 없음. 단 22분이라 시간 단위 누수는 미확인.
- 트래커 재연결 수는 트래커가 집계하지 않음(metrics에 필드 없음). 오류 0이므로 재연결 없었다고 추정(간접).
- 판정: 20분급 ws 안정성 **PASS**(스톡 영상, 22분 한정). 원자료 out/long/{summary.txt,mon/,env.txt}.

### 2) 서버 SIGTERM 후 10초 뒤 재기동 (3회, 트래커 100초, 22초 시점 종료)
| 회차 | 서버 종료 소요 | 마지막 처리→재기동 후 첫 응답 | 첫 응답→첫 입력 증가 | 총 처리 중단 | 트래커 network_errors | sent_updates/3001 |
|-|-|-|-|-|-|-|
| r1 | 1.23s | 12.78s | 0.26s | 13.04s | 9 | 2649 |
| r2 | 1.23s | 13.07s | 0.77s | 13.84s | 9 | 2630 |
| r3 | 1.23s | 13.06s | 0.78s | 13.84s | 10 | 2624 |
- 트래커는 종료되지 않고 자동 재연결해 서버 기동 직후(0.3~0.8초) 처리 재개. 트래커 처리율은 3001/3001(100%, 송신만 끊김 동안 손실, 큐잉·재전송 없음). 오류 형태: stdout `upload_error: "timed out"`(3건만 출력, 총 9~10건 카운트). 서버 정상 종료(SIGTERM)는 1.2초, 잔존 worker 0(마스터 서버).
- **발견: 서버 재기동 후 humanoid mode가 off로 돌아가 G1 상태 state=off**(트래커가 mode를 켜지 않음). 입력은 계속 수용되지만 G1 렌더는 재개 안 됨. 기본 ws 전환과 무관한 기존 동작이나 재기동 시 UI/스크립트가 mode를 다시 켜야 함.
- 한계: monitor 가 재기동 서버에 mode를 다시 켜지 않는 설정(once)으로 측정. 3회 모두 같은 조건. 판정: 재연결 **PASS**(3/3).
- 정리: 원자료 out/recon/{summary.txt,env.txt,mon_r*/}.

### 4) I-J 기본값 전환 직접 확인 (tools/teleop_tracker_win.py SHA256 67112f60…02dd, vj_new 사본으로 실행, 30초 스톡 영상)
| 케이스 | 서버 | 플래그 | transport(실사용) | fallback | updates | post p95 ms | 오류 |
|-|-|-|-|-|-|-|-|
| A | master 7f96fec | 없음 | **ws** | false | 901/901 | 2.18 | 0 |
| C | master 7f96fec | --transport http | http | false | 901/901 | 23.15 | 0 |
| B | cc37144 (ws 없음) | 없음 | http | **true** | 901/901 | 21.93 | 0, 경고 1회 |
| D | cc37144 | --transport http | http | false | 901/901 | 23.33 | 0 |
- (a) PASS, (b) PASS(자동 폴백, 404 경고 1회 후 정상 처리), (c) PASS(기존 http와 같은 post p95 21~23ms, ws 객체 미생성 확인은 metrics에 ws_roundtrip 항목 없음으로 확인).
- 지적: ① 폴백 경고에 ws_error로 404 HTML 전문이 한 줄에 출력됨(길이 제한 권장). ② 첫 WS 성공 전 일시 실패(예: 서버 기동 직후)로도 세션 전체가 HTTP 고정되며 이후 WS 재시도 없음(의도된 설계이나 사용자에게 경고 문구만으로 알림). ③ 단일 FallbackTransport가 여러 스레드에서 공유되나 WS 경로는 control_sender 단일 스레드라 현재 문제 없음.
- 정리: cc37144 구 서버는 SIGTERM 후 worker 6개가 고아로 남음(구 버그, H 라운드에서 수정된 것). 수동 종료함. 종료 후 리스너 0, 잔존 worker 0, Windows python 0.
- 미실시: 전체 pytest 회귀(아래 별도), 실카메라, 1시간 이상.
- 전체 pytest(I-J 수정 작업 트리, V-J 직접 실행): 93 passed, 5 warnings, 44.6초, 실패 0. 실행 후 리스너·worker 0.
- **최종 판정(V-J)**: 기본값 ws 전환 — 장시간(22분)·재연결 3회·(a)(b)(c) 직접 확인 모두 PASS이므로 전환 자체는 진행 가능. 단 전체는 스톡 영상·22분 한정이라 문서 판정은 "조건부 PASS(스톡 영상 한정), 지적 ①②는 NEEDS WORK 소항목". 커밋 없음.
- **재확인(I-J 수정 2판, tools/teleop_tracker_win.py SHA256 18ec32de…)**: 같은 4케이스 재실행(out/adopt/, 이전은 out/adopt_v1/). A ws(p95 2.44ms, 901/901, 오류 0), C http(21.4ms), B cc37144 → http 폴백, 경고 1회 "WebSocket is unsupported... Restart the tracker to retry WS." ws_error는 200자로 잘림, 901/901, D http(22.3ms). 지적 ①②는 해소(②: 404/미설치는 세션 고정 + 재시작 안내, 일시 실패는 30초 재시도). 일시 실패 후 30초 재시도·WS 복귀는 단위 테스트로만 있고 V-J 실측은 안 함. 재시도 시 WS 연결 시도가 최대 약 0.6초 update 스레드를 막을 수 있음(미측정). cc37144 구 서버 worker 잔존은 수동 종료.


## r3 회사 PC 트래커 판정 (V-T3, 2026-11-09, 포트 5092) - 기본 판정 NEEDS WORK
구성: 서버 wip/r2 작업트리 cab9e7f + 미커밋(서버 web/*.py 해시 3c3976ed..., I-K3 서버 변경 0), PERCEPTION=stub, G1 ON(humanoid) 또는 Panda(teleop mode). 트래커 FREEZE tools/teleop_tracker_win.py SHA256 c98c3db3...(TEMP\vt3 사본), Windows Python 3.12.10 mediapipe 1.2.0, `--loop-video --seconds 30`, ws/http 교차 3쌍(A: http,ws,http,ws / B: ws,http), 슬롯마다 WSL 측정 락 안에서 Windows 실행 완료까지 대기. 하네스 bench/verify_t/r3_{run.sh,chain.sh,cross.py,win_run.ps1,summ.py,rec_*,panda_base.sh,recover.py}, 원자료 bench/verify_t/out_r3/ (수치·JSON만, 영상·프레임 없음). 회사 PC 8코어, 서버 수신/preview/화면은 개수 기반(샘플 50ms, 첫 증가~마지막 값 도달), 수신 Hz는 slope 회귀(recv_hz_fit)도 병기. 실카메라 '미실시(카메라 분리)'.

### 영상별 검출률 (트래커 파이프라인 그대로: flip, 640, 더미 서버; out_r3/hand_regress/)
- 내 첫 측정(직접 detector, flip 없음)은 무효. final_hand 손 69.7%(62/89, 11/3 수치 재현, 3cf1b19 = 현재 FREEZE 동일, 회귀 아님), 자세 100%. round2_async 손 1.1%/자세 100%, compact 손 0%/자세 100%(179f), round2 손 30.8%(26f).
- 판정 영상(I-K3 합의): 주 final_hand(손+자세), 부 round2_compact(자세 전용). test_fast(1280x720)는 이번 미측정.

### 1) 절대 판정 (30초 창, 개수 기반, 창 A 4개 + B 2개)
| 영상 | 전송 | 처리율 | 수신Hz | preview fps | G1 fps | post p95 ms | 비고 |
|-|-|-|-|-|-|-|-|
| compact (cp, 조용, load1 0.9~1.5) | http 3창 | 100/100/100 | 30.02~30.04 | 30.00~30.04 | 31.9~32.0 | 22.4/26.7/17.6 | 6/6창 모두 기준 충족 |
| compact | ws 3창 | 100 x3 | 29.99~30.03 | 29.96~30.06 | 31.9~32.0 | 3.6~3.7 | |
| final_hand fh(최초, load 1.5~2.8) | http | 98.89/99.78 | 29.68/29.81 | 29.68/29.84 | 31.3/31.7 | 23.5/21.8 | w1 기준 미달 |
| final_hand fh | ws | 100/100 | 29.74/29.76 | 29.80/29.76 | 31.0/32.0 | 6.6/4.1 | |
| final_hand fh2 (락 밖 pytest -q 100% CPU 동시 → 오염) | http | 94.7/95.0/95.9 | 28.5~28.7 | 28.5~28.7 | 30.5~31.6 | 21.6~27.6 | |
| final_hand fh2 | ws | 99.0/99.0/100 | 29.72~30.06 | 29.71~30.06 | 31.7 | 5.3~6.1 | |
- fh B(ws 92.7%, http 88.3%)는 원인 불명의 외부 부하로 폐기(Windows 시스템 CPU 81~87%, neural p95 49~51ms). fh3 재측정은 부모의 '사용자 실카메라 테스트' 공지로 중단(미완).
- 해석: 손 검출 영상(neural p95 36~43ms > 프레임 33ms)에서는 http가 99% 미달 경향, ws는 99~100%로 경계. 자세 전용 compact는 양쪽 충족. final_hand의 '조용한 슬롯 6창 판정'은 미완.
- ws-http 차이(compact, 3쌍 부트스트랩 95% CI): post p95 -18.6ms [-23.0,-14.0], 서버 main CPU -6.0%p [-6.7,-5.6], tree CPU -10.9%p, 처리율·수신Hz·preview·G1 fps·neural 차이 입증 안 됨(0 포함). fh2는 오염 슬롯이라 참고.
- 서버 main CPU: 이 PC http 25~33%, ws 17~27% (집 PC 13~17%보다 높음).

### 2) WS 일시 실패 후 ≤30초 복귀 (독립 프록시 r3_recover.py, 프록시 시계 + 트래커 QPC + 서버 로그 3중 확인; out_r3/rec2/)
- A(연결 후 차단): 프록시가 WS 파이프 절단(t=25.0)+업그레이드 503 차단 25~35s. 트래커 http_fallback(24.47s), ws_connected(54.5s), 프록시 'passed' 55.1s → **복구 후 20.1초**(≤30 충족). 차단 중 서버 입력은 HTTP로 초당 25~30건 유지, 트래커 network_errors 0, ws_failures 1, ws_connections 2. 서버 로그 /tracker/ws 101 건수 3(A 2 + B 1)으로 연결 횟수 일치.
- B(첫 연결 거부 0~30s): fallback 6.98s, ws_connected 37.0s → **복구 후 7.6초**. network_errors 0, 처리율 100%.
- 한계: 복구 지연은 30초 재시도 주기에 의해 결정되어 0~30초 범위. 차단 종료가 재시도 직후면 최악 ~30초+연결 시간(최대 0.6초)이라 경계. 최악 위상(차단 25~55.2s) 시험은 중단으로 미실시(r3_rec_one.sh 준비됨). N=각 1회.
- 판정: 2건 직접 재현 PASS, 최악 위상 미확인이므로 '조건부'.

### 4) Panda 모드 (--mode panda, final_hand, out_r3/pd_A, pd_B, pdbase)
- 6창 모두 처리율 100%, 트래커 30.01~30.02Hz, 수신 29.94~30.02Hz(fit 29.99~30.00), preview 29.98~30.04fps. Panda 화면 fps: http 29.28/29.35/29.22, ws 29.29/29.37/29.34. 트래커 없는 기준선 29.41/29.41(teleop off), 29.38/29.31(teleop on, 트래커 없음) → 트래커 부하에 의한 하락 0.1fps 이내(http/ws 차이 +0.05, CI [+0.01,+0.11] 수준). Panda 화면 ~29.3은 트래커와 무관한 기준선. 서버 main CPU http 68~70% vs ws 58~60% (-9.6%p CI [-9.8,-9.3]). Panda 모드 post 지표는 트래커 metrics에 없음(None).
- 판정: Panda 회귀 없음(기준선 대비) PASS(3cf1b19 이전 비교는 요청대로 생략).

### 3) 장시간 1h: 미실시 (부모의 사용자 카메라 테스트 공지로 시작 금지). schedule 기록 없음.
### 5) preview HTTP +3~9ms 원인 재현: I-K3 조사 결과 미수신(preview 기본 변경 없음). 이번 측정 preview post p95는 별도 계측 필드 없이 미확인.

### 정리
- 5092 리스너 0 확인, 잔존 worker 0 확인(각 run env 파일 post_listener=0 leftover=0). 중단한 fh3_A는 내가 PID 지정 종료.


### r3 후반 추가 기록 (13:06 재개 후, 13:34 부모 지시로 중지)
- 실카메라 수락(측정 락 안, 서버 5092 humanoid, 트래커 FREEZE c98c3db3, ws 기본, 30초 창 1회, 원자료 bench/verify_t/out_r3/cam4/cam4.json): 카메라 29.29fps, 처리율 98.80%(1071/1084, 미처리 13슬롯), 트래커 28.94Hz(37초 평균), 손 검출 1.3%·자세 100%(손이 거의 안 보이는 자세), 서버 수신 893건/30.13초=29.64Hz, preview 29.64Hz, 캡처→서버 도착 p50 27.9ms/p95 46.5ms(두 호스트 시계 동기 전제, 참고), 네트워크 오류 0, ws 연결 1회 폴백 0, post ws p95 3.95ms, neural p95 31.4~32.2ms. 판정: 기준(처리율 99%, 수신 29.7Hz) 근소 미달 → 실카메라 NEEDS WORK(1회, N=1). '실카메라 미실시'는 해소.
- 디버그용 실카메라 30초 1회(서버 없음, 포트 5099 더미)를 락 밖에서 실행한 실수 있음(13:12경, 측정 수치 아님, 카메라 fps 29.24, 처리율 99.35%, 손 35%).
- 무효 처리한 실행: fh3/fh4(및 cam1~cam3): WSL에서 nohup 백그라운드로 띄운 드라이버는 powershell.exe interop(accept4 failed 110)이 끊겨 트래커가 실제로는 안 돌았고 Windows 쪽 이전 metrics 파일이 재사용됨(처리율 1.0/hz 30.014 recv None 패턴). 하네스는 이제 창 시작 전 stale 파일 삭제 + \\wsl.localhost UNC 대신 로컬 복사본(TEMP\vt3\bin, r3_sync.sh)을 쓰도록 수정. 장시간/측정 드라이버는 반드시 Bash yield 라이브 세션(bash_interact)에서 실행할 것.
- 이전 유효 데이터(fh, fh2, cp, pd, pdbase, rec2)는 모두 라이브 세션 실행이며 서버 recv 값이 있는 정상 창.
- preview +3~9ms 조사(I-K3 notes/tracker_r3_changes.md): 원인 미규명(F1 Connection:close 구조비용 확정, 상대 회귀 원인은 미확정). 재현 확인은 미실시.
- 재개 지점: (1) final_hand 조용한 슬롯 6창(`bash r3_chain.sh fhN teleop_final_hand humanoid`, 라이브 세션) (2) 복구 최악 위상 `r3_rec_one.sh rec3 25 56 100` (3) 실카메라 반복 2~3회(`r3_cam_run.sh camN humanoid`, 카메라 단독 사용 확인 후) (4) 1h 장시간(락 밖, schedule 기록 후, bash_interact 세션) (5) preview 재현. 모두 bench/verify_t/ 스크립트, 포트 5092, 락 /tmp/rp_measure.lock.
- 중지 시각 13:34(KST). 5092 리스너 0, Windows 트래커·camera_acceptance 프로세스 0, 카메라 해제됨.
