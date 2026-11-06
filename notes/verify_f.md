# verify_f (F 라운드 검증 기록, V-F)

## 2026-11-06 F0 기준선 (집 PC, wip/r2 cc37144, 작업 트리 dirty=5 = 로컬 전용 수정 포함)
환경: WSL Ubuntu-24.04, py3.12.16, GPU AMD RX 7600(Mesa D3D12), PERCEPTION=stub, 포트 5092, 매 실행 measure→gpu 이중 락 안, 서버 기동부터 종료까지 약 45~90초.
**입력은 합성**(tools/humanoid_synth.py 사람 랜드마크 630프레임 21초 순환 + 노이즈 JPEG 640x360 q65). 실카메라·MediaPipe 트래커 실처리·GT 보조 없음 → 트래커 실처리 절대 판정 미실시.
송신 경로: **Windows Python 3.13.7 + urllib3 2.8.0 → WSL(127.0.0.1:5092, localhost 포워딩)**. 실제 트래커와 동일하게 PoolManager(maxsize1), Timeout(total .6), retries=False, 제어/preview 스레드 분리 30Hz. 단 트래커는 Python 3.12/urllib3 버전 미확인(차이 가능).
하네스: bench/verify_f/ (sender_f.py, scen_f.py, g1_window.py=verify_q/q_window.py 복사, run_f.sh, locked_f.sh, gen_payloads.py), 원자료 bench/verify_f/out/. 이후 단계도 같은 스크립트·정의 사용 (라벨만 변경, transport 인자는 sender_f.py 5번째).
간섭 기록: I-F가 04:19~04:21 verify_f 스크립트를 잘못 실행해 그 구간 측정(g1_r1/r2, scen_r2 1차)은 폐기(out/discarded_interference/), 재측정함. scen_r1은 간섭 전(load 0.7).

### 지표 정의 (고정)
1. W1: G1 ON, Windows 송신만 30초. /humanoid/update(JSON)와 /teleop/preview(JPEG) 각 30Hz. RTT p50/p95/max(요청~응답 읽기 완료), 처리율=서버 status.input_count 증가/송신 수, 수신 Hz=그 증가/시간.
2. g1_window.py: G1 ON 30초, WSL 내부 30Hz POST, /humanoid/video 프레임 개수 fps, max gap, 프록시 p95(POST→다음 프레임), status.server_latency_ms.receive_publish p95.
3. W2 구간 서버 CPU%: 서버 프로세스(main)와 자식 트리 합(tree, worker 포함, 100%=1코어) /proc utime+stime. 유휴=G1 OFF 클라 없음 10초. W2 = G1 ON + Windows 송신 + 폴링 3(humanoid/status 10Hz, teleop/status 10Hz, /status 3Hz, http.client keepalive 시도) + MJPEG 2(/humanoid/video, /teleop/preview.mjpg).
4. W2 폴링 총 req/s와 상태 응답 p95.

### 결과 (기준선 A)
| 항목 | r1 | r2 |
|---|---|---|
| 지표1 update RTT p50/p95/max (ms) | 5.24 / 18.18 / 68.11 | 5.48 / 19.87 / 27.31 |
| preview RTT p50/p95 (ms, r1) | 5.41 / 19.21 | - |
| 처리율 / 수신 Hz (W1) | 900/900=100% / 30.0 | 100% / 30.0 |
| W2(부하 하) update RTT p50/p95 | 5.50 / 18.87 | (r2 W2는 원자료 out/F0_scen_r2.w2.json) |
| 지표2 G1 fps / max gap / gap>200 | 32.00 / 40.4ms / 0 | 32.00 / 68.6ms / 0 |
| 지표2 프록시 p95 / 내장 receive→publish p95 | 30.5 / 48.6 ms | 32.6 / 49.9 ms |
| 지표3 유휴 CPU main / tree | 1.3% / 32.3% (scen_r1) | 1.5% / 37.6% |
| 지표3 W2 CPU main / tree | 20.9% / 87.6% | 21.8% / 95.5% |
| 지표4 폴링 총 req/s | 23.75 | 23.8 |
| 지표4 응답 p95 humanoid/teleop/app status (ms) | 6.99 / 9.47 / 12.54 | 6.68 / 9.77 / 13.79 |
- 서버 p95(프록시)·fps는 기준 충족. g1 창 안 벽시계 점프 14회씩 겹쳤으나 gap>200ms 0.
- 처리율 ≥99% 목표는 이 합성 환경 기준선에서 이미 100%(회사 측정의 91~96%와 다름 → 회사 환경 차이, 이 PC에서는 처리율 개선 여지가 없음). 개선 판단은 RTT·CPU·폴링 수로 한다.
- load1: g1_r1 1.2~1.3, scen_r2 1.4→2.5, g1_r2 2.2→2.8(직전 측정 서버 잔여/openclaw 포함). 완전 조용한 창 아님 → 절대 판정 아님, A/B 같은 슬롯 상대 비교용.
- Windows GPU 사용률 미수집(N/A). 

## 2026-11-06 F2/F3 판정 진행 로그 (V-F)
- 진행: 코드 리뷰(1차 지적 5건 반영 확인: robot-push 분리, Origin 검사, route별 WS 크기 제한, status WS 상한 8, README), scen A/B 2쌍 완료(F2_A*, F2_Bhttp*, F2_Bws*), 사용량 한도로 중단 후 재개.
- 남음: 락 안 전체 pytest, G1 창 A/B/A/B, P0(HTTP/WS 잘못된 payload·동시 ON/OFF·kill -9·첫 끊김), 연결 누수, 최종 판정 표.

## 2026-11-06 F1~F3 최종 상대 판정 (V-F, 기본 NEEDS WORK)
대상: A=cc37144 별도 트리(/tmp/rp_base, HTTP+폴링), B=작업 트리(pytest 80 passed, I-F 구현). 합성 입력(실카메라·MediaPipe 없음), Windows py3.13.7+urllib3 2.8.0(+websocket-client 1.8.0, C:\Users\my\rp_vf\venv)→WSL 127.0.0.1:5092. 같은 슬롯 A/Bhttp/Bws를 4회 반복(F2_A1..4, F2_Bhttp1..4, F2_Bws1..4). Bws = WS 입력 + status/ws push 구독 1개(브라우저 탭 1개 모사), Bhttp = B 코드의 HTTP+폴링 폴백. load1 1.0~3.6(I-F/부모 작업 병행 가능성, 조용한 창 아님) → 절대 판정 아님. CI: 쌍별 차이 부트스트랩 2000회(bench/verify_f/ci_f.py, 결과 out/F2_ci.txt), n=4쌍이라 폭이 넓음.
### 판정
| 항목 | 판정 | 근거(원자료 bench/verify_f/out/) |
|---|---|---|
| 전체 pytest | PASS | F2_pytest.txt 80 passed (락 안, 29s) |
| 코드 리뷰 지적 5건(재귀·Origin·route 크기·상한·README) 반영 | PASS(코드 확인), 브라우저 실화면은 부모 | realtime.py/app.js 직접 읽음 |
| F1 keep-alive | 폐기 동의 | I-F 기록, 내가 재현 안 함 |
| F2 WS update RTT | PASS(개선 입증) | W1 p95 A 9.9~26.3 → Bws 2.0~2.5ms, 차이 -18.5 CI[-23.2,-11.3]; p50 -4.0 CI[-4.7,-3.5] |
| F2 서버 CPU(부하 W2) | PASS(개선 입증) | main 20.9~23.2 → 9.5~11.5%, 차이 -11.5 CI[-11.6,-11.3]; 트리 -12.8 CI[-14.7,-10.7] (폴링 제거분 포함, F2/F3 분리 불가) |
| F3 상태 요청 수 | 개선 입증(수치) | 23.8 req/s → push 10.8~14.0 msg/s(약 128KB/s), CI[-12.2,-9.8]. UI 동일성 미확인 |
| **F2 WS preview 전송** | **FAIL(회귀)** | Windows→WSL에서 preview RTT p50 44ms/p95 48ms(HTTP 5~6/14~26), 30초 처리 664~668/900(약 22Hz, 차이 -234 CI[-235.5,-232.8]). WSL 내부 송신은 1.8ms 정상(F2diag_wslint)이고 JPEG 10KB(F2diag_small)·TCP_NODELAY(F2diag_nodelay2)로도 동일 → 원인 미규명(Windows→WSL 경로의 바이너리 프레임 지연). update는 영향 없음. 권고: 원인 규명 전까지 preview는 HTTP로 보내거나 ws 기본 비활성 유지 |
| HTTP 폴백 회귀 | 조건부 PASS | W1 update p95 차이 +0.15 CI[-3.5,+5.0](입증 안 됨), CPU main +0.65 CI[-0.75,+1.8](안 됨), 상태 응답 p95 3종 CI가 0 포함, 처리율 100%. 단 W2 부하 update p95 +1.9ms CI[+0.6,+3.2] 소폭 증가 입증(원인 불명, 4쌍) |
| G1 fps/gap/p95 (HTTP A 4창 vs B HTTP 2창) | PASS(상대) | fps 32.00 전부, max gap -5.9 CI[-16,+1.1], proxy p95 +0.17 CI[-0.4,+0.8], 내장 p95 +0.4 CI[-1.0,+1.9] (G_A1/2, G_B1/2, F0_g1_r1/2) |
| G1 + WS 입력 2창 | PASS(상대, 소표본) | fps 32.00, gap>200 0, proxy p95 29.2/29.4(A 대비 -2.3), 내장 p95 +1.6 CI[+1.0,+2.2](소폭 증가) (F2g1_Bws1/2) |
| P0 HTTP/WS 잘못된 payload | PASS | p0_ws.py 17 route×payload + preview 5종 모두 HTTP·WS 상태코드 동일(mismatch 0), 오류 후 같은 연결 update 200, 구조 오류는 400/404 (F2_p0ws.json). 기존 vw 13종 400/200 기준선과 동일 (F2_vw.vw.json) |
| P0 크기 상한 | 부분 PASS | teleop 9030B→413(HTTP·WS), humanoid 70030B→413, JPEG 250001B→413. WS 1MB 텍스트는 서버가 연결 종료·서버 생존. **5MB 바이너리는 5초 안에 응답·종료 없음(서버 생존)** → max_message_size 효과 미확인, 보류 |
| P0 Origin | PASS | evil Origin의 /tracker/ws·/status/ws 모두 종료(rejected), 동일 Origin·무 Origin 허용 |
| P0 status ws 상한 | PASS | 10개 동시 연결 중 8개만 데이터 수신 |
| P0 동시 ON/OFF 8개, kill -9, 10회 사이클, 첫 끊김 | PASS | F2_vw: 코드 [200,200,200,409,409,200,409,200] 최종 off; F2_crash: kill 0.25s부터 off/False, 재ON ready, 10사이클 모두 200/off 자식 3 고정; 첫 끊김 24.5/33.1/8.3ms(최대 gap 37~58ms). WS 입력으로 G1 구동 중 kill 시나리오는 미실시 |
| 연결 누수 | PASS(제한적) | tracker ws 24회 + status ws 24회 + 비정상 소켓 종료 12회: 스레드 34→31→29(안정화), fd 31→28→25. 장시간 추세 미실시 |
### 한계·미실시
- 합성 입력만. 실제 트래커(MediaPipe)·실카메라·브라우저 실화면(부모 몫)·Windows GPU 미실시. 로드 1~3.6의 비조용 창이므로 절대 기준(≥29.7fps 등)은 부모의 조용한 창에서.
- WS 개선 수치는 Windows 클라이언트 urllib3 vs websocket-client 비교이며 실제 트래커의 requests 경로(panda 모드)는 비교 안 함.
- G1 B(WS) 창은 2개, A/B/A/B 순서가 완전 교차는 아님(A,B,A,B 후 Bws).
- 부수효과: Windows 쪽 격리 venv에 websocket-client==1.8.0 설치, Aside 런타임 venv(PIP_PREFIX)에도 websocket-client 1.8.0이 설치됨.

## 2026-11-06 hybrid 수정본 재판정 (V-F, 기본 NEEDS WORK → 조건부 PASS)
변경: I-F가 트래커 ws를 hybrid(JSON update=WS, raw preview=HTTP)로 바꾸고 서버 WS 메시지 상한을 6MB로 올려 app route 상한(8KB/64KB/250KB)에서 413 응답하게 함. pytest 81 passed (out/H2_pytest.txt).
**오염 기록(중요):** 이전 측정(F2_*, G_*, H_*, H2/H3_*, 14:?? 이전)은 run_f.sh가 서버 종료 시 sim/humanoid worker(multiprocessing spawn 자식 약 66개)를 남겨 load가 1→6으로 누적되고 Windows→WSL 5092 relay가 CloseWait로 막힌 상태에서 일부 수행됨. 66개를 PID로 정리하고 run_f.sh에 종료 시 자식 정리+leftover_mp 기록을 추가한 뒤 **J_* / JG_* / I2_p0ws를 5094 포트로 재측정**(leftover_mp=0 16회 확인, load 0.6~1.6). 최종 판정은 J_*, JG_*, I2_p0ws만 근거로 한다. (이 worker 잔존이 서버 코드 문제인지 하네스의 SIGTERM 종료 방식인지는 미규명; 기준선 코드에서도 발생했으므로 이번 변경 탓으로 보지 않음.)
### 최종 판정 (A=cc37144 별도 트리 ~/work/rp_base_vf, 3쌍 J_A/Bhttp/Bwspoll/Bwspush, 쌍별 차이 부트스트랩 CI, out/J_ci.txt)
| 항목 | 판정 | 근거 |
|---|---|---|
| pytest | PASS | 81 passed |
| F2 update RTT | PASS(입증) | W1 p95 15.0~16.8 → 2.3ms, 차이 -13.8 CI[-14.5,-12.7]; p50 -3.15 CI[-3.4,-2.9]; W2 p95 -15.0 CI[-15.3,-14.6]; 처리율 100% 동일 |
| F2 서버 CPU (폴링 유지, WS만) | PASS(소폭 입증) | W2 main -3.0%p CI[-3.5,-2.7], 트리 -2.7 CI[-3.3,-2.3] |
| F3 push 추가 효과 | PASS(입증) | W2 main 11.9% (A 19.6~21.6), 차이 -8.4 CI[-9.8,-7.7]; 트리 -11.0 CI[-11.9,-10.4]; 상태 요청 23.8 → 14.0 msg/s CI[-9.8,-9.76]. 주의: push 구독자 1개(탭 1개) 기준, UI 동일성은 부모가 실화면 확인 |
| 내장 receive→publish p95 | 차이 입증 안 됨 | CI 0 포함(±3ms) |
| 처리율/수신 Hz | 이미 100%/30.0, 개선 여지 없음 | |
| preview HTTP RTT p95 | 경미한 회귀(입증) | 폴백(Bhttp) +3.0ms CI[+0.4,+5.6], ws hybrid +9.1ms CI[+4.8,+13.0](13.6~18.5 → 23.2~24.4ms). 처리 수는 900/900 동일. 원인 미규명(UI 카메라 FPS·지연에 미치는 영향은 미측정) |
| HTTP 폴백 회귀 | PASS | update p95 +0.19 CI[-1.8,+2.0], CPU main -0.23 CI[-1.7,+0.9], 상태 응답 p95 3종 CI 0 포함, 처리율 100%. 이전 +1.9ms(W2)는 재현 안 됨(오염 구간 산물 또는 잡음) |
| G1 fps/gap/p95 (A vs B WS 입력, 2쌍 JG_*) | PASS(상대, 소표본) | 모두 32.00fps, gap>200ms 0, max gap 41~42ms, 프록시 p95 A 31.0/31.6 vs B 29.3/29.1, 내장 p95 48.9/49.3 vs 52.2/47.2. n=2라 CI 정의 불가 |
| P0 HTTP·WS 검증 동일성 | PASS | I2_p0ws.json mismatch 0(17 route payload + preview 5종), 오류 후 같은 연결 정상, 구조 오류 400/404 |
| P0 대용량 | PASS | WSL·Windows(5094) 모두 5MB 바이너리 → 0.06~0.19s에 413 JSON 응답, 1MB 텍스트 413, 이후 같은 서버 정상. Windows 5092는 relay 막힘으로 실패했었음(환경 문제, 5094로 재확인) |
| P0 Origin / status 상한 | PASS | 타 Origin 양쪽 종료, 10 동시 중 8 수신 |
| 연결 누수 | PASS(제한적) | I2_p0ws 스레드 32→29→27, fd 29→26→23 (24+24+12 open/close) |
| P0 동시 ON/OFF·kill -9·첫 끊김 | PASS(이전 구간 F2_vw/F2_crash, 변경 전 realtime.py) | hybrid 이후 재실행 안 함 → 보류 표기 |
미실시: 실카메라/MediaPipe, 브라우저 실화면(부모), 조용한 창 절대 판정(부모), hybrid 이후 vw/crash P0 재실행, WS 입력 중 kill -9.

## 2026-11-06 F 라운드 조용한 창 최종 (V-Q2, 기본 NEEDS WORK)
대상: 작업 트리(HEAD cc37144 + 미커밋 F 라운드, dirty=20 포함 로컬 전용 수정). 합성 입력(사람 랜드마크 630프레임 순환 + 노이즈 JPEG 640x360), PERCEPTION=stub, 실카메라·MediaPipe 없음. 하네스 bench/verify_q2/ (q2_win.py, sender_q2.py, run_q2.sh=서버 트리 전체 정리 포함, summ_q2.py), 원자료 bench/verify_q2/out/. 포트: **Windows→5092 relay에 CloseWait 8개가 남아 연결 실패(G1_dbg) → 5094 사용**. 이중 락 안, 서버 기동~종료 약 50초.
**측정 시각:** pytest 13:46, G1 r1 13:48 / r2 13:49 / r3 13:51 / http참고 13:53 (13시대 묶음). P0(아래)는 17시대에 별도 실행 → 두 시각대가 다름. 시스템 시계 자체가 불안정(WSL time.time이 monotonic 대비 ±91070초로 약 5초 주기 진동)하므로 "시각"은 참고만.
**환경:** G1 창 직전 load1 1.35 / 0.53 / 0.53 / 0.36. 시작 시 잔존 python worker 0, 5092/5094 리스너 0. openclaw(pid 279, :18789) 5초 CPU 0.4~1.0% (건드리지 않음). GPU: D3D12 AMD Radeon RX 7600, 사용률 N/A(미수집). 창 안 벽시계 점프: 모든 창 14회(±91070초 쌍, gap>200ms 0건).
**발견(서버 종료):** 매 실행 SIGTERM 3초 뒤에도 서버 자식 3개(spawn worker 등)가 전부 생존 → run_q2.sh가 트리 전체 kill로 정리, 종료 후 잔존 0 확인(각 .env의 children_at_kill/alive_after_SIGTERM). SIGTERM 종료 시 worker 잔존은 이번에도 재현됨(서버 종료 처리 문제 후보, 미규명).

### 1. pytest
| 항목 | 기준 | 결과 | 판정 |
|---|---|---|---|
| 전체 pytest | 81 passed | 81 passed, 5 warnings, 28.32s (out/pytest.txt, 락 안) | PASS |

### 2. G1 30초 창 x3 (Windows py3.13.7 → WSL 5094: update=/tracker/ws 30Hz, preview=HTTP 30Hz, /status/ws push 구독 1, MJPEG 2(/humanoid/video 프레임 계수, /teleop/preview.mjpg))
| 항목 | 기준 | r1 | r2 | r3 | 판정 |
|---|---|---|---|---|---|
| 개수 fps (T0~END 30.0s) | ≥29.7 | 32.031 (961) | 31.998 (960) | 32.031 (961) | PASS 3/3 |
| max gap / >200ms | 참고 | 38.3ms / 0 | 41.7 / 0 | 41.3 / 0 | PASS |
| 프레임 간격 p95 | 참고 | 33.9 | 34.2 | 33.8 | 참고 |
| 서버 p95 프록시(POST→다음 프레임) | ≤80ms | **측정 불가** | | | NEEDS WORK(항목) |
| 내장 receive→publish p95 | 참고 | 49.2 | 47.4 | 50.7 | 참고 통과(<80) |
| update RTT p50/p95 (WS) | - | 1.93/2.36 | 1.93/2.31 | 1.93/2.35 | 참고 |
| preview RTT p50/p95 (HTTP) | - | 4.06/23.77 | 4.09/22.89 | 4.10/24.74 | 참고 |
| 처리율 update / preview | ≥99% | 900/900=100% / 100% | 100% / 100% | 100% / 100% | PASS 3/3 (수신 30.0Hz) |
| 서버 CPU main / tree | 참고 | 12.2 / 72.4 | 12.1 / 73.6 | 12.0 / 73.5 | 참고 (tree=worker 포함, 100%=1코어) |
| push 메시지 | - | 14.4 msg/s, 약 131KB/s | 동일 | 동일 | 참고 |
- 프록시 불가 사유: 입력이 Windows 송신기라 POST 시각(Windows 시계)과 프레임 도착(WSL 시계)을 같은 시계로 비교할 수 없고 WSL time.time이 불안정. 대체로 프레임 간격 p95(~34ms)와 내장 p95(<51ms)를 기록. 과거 WSL 내부 송신 프록시 p95는 29~33ms(V-Q, JG_*).
- 개수 fps 32.0은 렌더 루프 목표치 근처.

### 3. 참고 1회: HTTP 폴백 (--transport http + 상태 폴링 3, G1_http, 13:53)
fps 31.998(960), max gap 37.9ms, >200 0, 프레임 간격 p95 34.0, 내장 p95 53.0, update RTT p50/p95 5.00/13.75, preview 5.32/11.55, 처리율 100%/100%, CPU main 20.2 / tree 82.7, 폴링 11.03+11.03+3.33=25.4 req/s. (WS+push 대비 main CPU 약 8%p 높음, 1회 참고라 CI 없음). 판정: 참고(단일 창).

### 4. P0 재실행 (hybrid 이후 첫 실행, 17:34~17:36, 포트 5094, WSL 내부 HTTP, load 1.2→2.2, 원자료 out/P0_vw.*)
| 항목 | 기준 | 결과 | 판정 |
|---|---|---|---|
| 동시 ON/OFF 8개 | 최종 모순 0 | 코드 [200,200,409,200,409,200,409,200], 최종 state off/enabled False | PASS |
| 10회 ON/OFF 사이클 | 매회 200/ready→off | 10회 모두 on=200 ready, off=200 off, 자식 3 고정 | PASS |
| worker kill -9 → 자동 off, 재ON | off 전환, 재ON ready | kill 후 0.25s 첫 확인부터 8회 모두 off/False, 재ON ready True, OFF 후 Panda 정상 | PASS |
| 모드 ON 후 첫 끊김 x3 | ≤200ms | first_gap 20.4 / 24.8 / 29.1 ms (6초 max gap 41.4/37.2/37.1) | PASS |
| 잘못된 payload (HTTP) | 400, worker 생존 | 형식오류 9종 400, bad JSON 400, 이후 ready, OFF→ON 200/200 ready, 퇴화 4종은 200(기준선과 동일) | PASS(HTTP측, WS 동일성은 아래) |
| 참고: WSL 내부 HTTP 입력 프록시 p95 (POST→다음 프레임, 15초 vw) | ≤80ms | 31.6ms (p50 16.3, max 41.7), 479프레임 31.99fps | 참고 통과 (G1 3창의 프록시 대체 근거, 단 15초·HTTP·WSL 내부) |
| **WS 입력(Windows py→/tracker/ws 30Hz + preview HTTP) 중 G1 worker kill -9** (17:36, out/P0_killws.json) | WS 생존/자동 재연결, 서버 생존, 자동 off, 재ON | 송신 6초 시점 worker(pid 747) kill -9: 0.25s 첫 확인부터 12회(3s) 모두 state off/enabled False. sender 20초 완주: update 600/600 ok, err 0, **재연결 0**(WS 연결 유지), preview 600/600 ok, 서버 /status 200 생존, 자식 3개로 복귀. 재ON 200→ready, 이어서 WS 송신 6초 180/180 ok 처리율 100%, 종료 시 state ready. (worker가 죽은 동안 update는 200으로 수락되어 input_count만 증가: 기존 HTTP와 같은 동작) | PASS |
| 잘못된 payload HTTP·WS 동일성 (17:38, out/P0_ws.json) | 상태코드 mismatch 0, 오류 후 연결 생존 | 17 route×payload + preview 케이스 총 32건 mismatch 0, 오류 후 같은 연결 정상, status/ws 10 동시 중 8 수신, 누수 스레드 33→28→26, fd 31→26→23 | PASS(제한적, 장시간 추세 미실시) |
| 5MB 413 (Windows py→WSL 5094, out/P0_ws.huge_win.json) | 413 + 서버 생존 | binary 5MB → 0.08s에 `status 413 "JPEG size limit 250KB"`, text 1MB → 413, 70001B 비JPEG → 400, 이후 같은 서버 update 200. HTTP 5MB는 이번에 별도 실행 안 함(HTTP 70000B 413은 p0_ws 케이스에서 확인) | PASS(WS 경로) |

### 5. 최종 판정 (기본 NEEDS WORK, 직접 잰 것만 PASS)
- PASS: pytest 81, G1 fps x3 (31.998~32.031), 처리율 update/preview 100% x3, max gap<42ms, 내장 p95<51ms, P0 전 항목(동시 8, 10회, kill -9, 첫 끊김, WS 입력 중 kill -9, payload 동일성, 5MB 413).
- **NEEDS WORK(미충족/측정 불가): 3창 각각의 "서버 p95 프록시(POST→다음 프레임) ≤80ms"는 Windows 송신 구조상 직접 측정 못함.** 대체 근거(프레임 간격 p95 ~34ms, 내장 p95 47~51ms, WSL 내부 HTTP 15초 프록시 p95 31.6ms)는 모두 ≤80ms이나 요구한 정의 그대로의 3창 측정은 아님.
- 참고: HTTP 폴백 1회 정상(fps 32.0, 처리율 100%, update p95 13.75ms).
### 한계·미실시
- 실카메라·MediaPipe 실처리, FP 워밍업 defer(PERCEPTION=fp 없음) 미실시. 합성 입력, 개수 fps 32.0은 렌더 목표치 근처.
- G1 3창은 13:48~13:51 연속(약 1~2분 간격), P0는 17:34~17:38. 서로 다른 날/부하 조건은 아님. 브라우저 실화면은 미확인(push 구독자는 simple_websocket 클라이언트 1개로 모사).
- Windows→5092 relay CloseWait 8개로 5094 사용. GPU 사용률 N/A, openclaw는 건드리지 않음(0.4~1.4% CPU; 17시대에는 pid 283으로 재기동됨).
- SIGTERM 종료 시 서버 자식 3개 잔존이 매 실행 재현(run_q2.sh가 트리 kill로 정리). 서버 정상 종료 경로 점검 필요.
- 스크립트: bench/verify_q2/ (커밋 안 함, 운영 코드 수정 없음).

### 6. 추가: 서버 p95 프록시 보완 측정 (WSL 내부 송신기, 17:39~17:44, 포트 5092 사용 가능, 원자료 out/W3_r1~r3.*)
구성: 송신기를 WSL 내부(Linux py3.12 + websocket-client/urllib3, bench/verify_q2/sender_q3.py)로 옮기고 나머지는 §2와 동일(update=/tracker/ws 30Hz, preview=HTTP 30Hz, /status/ws push 구독 1, MJPEG 2, G1 30초). 시계는 Linux perf_counter=time.monotonic(CLOCK_MONOTONIC) 하나라 송신 시각과 프레임 도착을 직접 비교. 실행 전후 잔존 worker 0, 리스너 0(각 .env). 창 직전 load1 0.69 / 0.39 / 0.61, openclaw 0.4~0.6%, 창 안 벽시계 점프 각 14회(gap>200ms 0).
**프록시 정의 (V-Q의 HTTP 정의와 다른 점):** V-Q/V-W2는 HTTP POST의 응답까지 읽은 시각(POST return) → 다음 MJPEG 프레임 도착이다. 이번 WS는 (a) **WS 메시지 send() 완료 시각 → 다음 프레임 도착**(요청한 정의, 응답 대기 시간을 포함하므로 HTTP 정의보다 길게 나오는 쪽), (b) 참고로 응답 수신 시각 → 다음 프레임(HTTP의 POST return과 가장 가까운 정의)을 둘 다 기록. 둘 다 프레임 주기(~31ms)가 섞인 상한 근사이며 입력은 WS update이고 preview HTTP·push·MJPEG 2개가 함께 걸린 상태라 V-Q(HTTP 입력만)보다 부하 조건이 다르다.
| 항목 | 기준 | r1 | r2 | r3 | 판정 |
|---|---|---|---|---|---|
| **서버 p95 프록시 (send 완료→다음 프레임)** | ≤80ms | 30.6 (p50 14.7, max 35.6) | 30.7 (14.8, 32.8) | 30.7 (14.6, 36.0) | **PASS 3/3** |
| 참고 프록시 (응답 수신→다음 프레임) | 참고 | 29.8 | 29.8 | 29.9 | 참고 |
| 개수 fps | ≥29.7 | 32.033 (961) | 32.000 (960) | 32.000 (960) | PASS 3/3 |
| max gap / p95 gap / >200ms | 참고 | 38.4 / 33.7 / 0 | 45.6 / 33.9 / 0 | 38.2 / 33.7 / 0 | PASS |
| 내장 receive→publish p95 | 참고(<80) | 49.1 | 51.4 | 49.4 | 참고 통과 |
| update RTT p50/p95 | 참고 | 1.41/1.83 | 1.43/2.11 | 1.40/2.18 | 참고 |
| preview RTT p50/p95 | 참고 | 2.78/3.62 | 2.95/3.73 | 2.93/3.67 | 참고 |
| 처리율 update / preview | ≥99% | 100% / 100% | 100% / 100% | 100% / 100% | PASS 3/3 |
| 서버 CPU main / tree | 참고 | 11.9 / 69.9 | 12.4 / 71.8 | 12.1 / 71.0 | 참고 |
- Windows→WSL 구간의 preview RTT p95(23~25ms)는 WSL 내부 송신에서는 3.6~3.7ms로 나와, §2의 preview 지연 대부분은 Windows↔WSL 경로 차이(원인은 여전히 미규명)다. 서버 자체 처리는 정상.
- 한계: 입력이 WSL 내부 합성이므로 실제 Windows 트래커 경로의 프록시가 아님. 3창은 약 1~2분 간격 연속. 개수 fps 32.0은 렌더 목표치 근처.

### 7. 최종 판정 표 (갱신, 기본 NEEDS WORK, 직접 잰 것만 PASS)
| 항목 | 기준 | 결과 | 판정 |
|---|---|---|---|
| 전체 pytest | 81 passed | 81 passed | PASS |
| G1 개수 fps x3 (Windows 송신 / WSL 송신 각 3창) | ≥29.7 | 31.998~32.031 / 32.000~32.033 | PASS |
| 서버 p95 프록시 x3 (WSL 송신, 같은 시계) | ≤80ms | 30.6 / 30.7 / 30.7 | PASS |
| 내장 receive→publish p95 | 참고 | 47.4~51.4 | 참고 통과 |
| 처리율 update·preview | ≥99% | 6창 모두 100% | PASS |
| HTTP 폴백 1회 | 참고 | 정상(fps 32.0, 100%) | 참고 |
| P0: 동시 8, 10회 사이클, kill -9 off·재ON, 첫 끊김 x3, WS 입력 중 kill -9, payload 동일성, 5MB 413 | 각 기준 | 전부 통과(§4) | PASS |
| 미실시 | | 실카메라·MediaPipe 실처리, FP 워밍업 defer, 브라우저 실화면, Windows 경로 프록시 | 미실시 |
