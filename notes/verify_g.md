# V-G 검증 기록 (2026-11-06, 기본 NEEDS WORK)

## 1. 수정 전 재현 (HEAD 938c41f, git archive 별도 트리 /tmp/rp_base_g, 포트 5092, PERCEPTION=stub)
스크립트 bench/verify_g/repro.sh, 원자료 bench/verify_g/out/base(TERM, INT 무효분 포함)·base2(INT, KILL). 측정 전후 잔존 worker 0, 리스너 0 확인(FINAL 줄).
방법: 기동 후 G1 ON(또는 OFF) 1초 뒤 신호 전송, 서버 자식 트리 PID를 /proc으로 추적, 최대 약 10초 대기 후 남은 PID와 cmdline 기록, 트리 kill -9로 정리.
| 신호 | G1 | 횟수 | 서버 종료 전 자식 수 | 종료 후 잔존(자식 중) | 잔존 종류 |
|---|---|---|---|---|---|
| SIGTERM | ON | 5 | 3 | 2 (5/5) | multiprocessing.resource_tracker 1 + spawn_main(worker) 1 |
| SIGTERM | OFF | 5 | 3 | 2 (5/5) | 동일 |
| SIGINT | ON | 5 | 3 | 0 (5/5), 종료 0.12~0.18초 | - |
| SIGINT | OFF | 5 | 3 | 0 (5/5), 종료 0.9~1.3초 | - |
| kill -9 서버 | ON | 5 | 3 | 2 (5/5) | 동일 |
| kill -9 서버 | OFF | 5 | 3 | 2 (5/5) | 동일(G1 OFF여도 자식 3개 존재) |
- 잔존은 10초 대기 끝까지 살아 있었음(생존 시간 >10s, 정리는 내가 -9). 서버 본체는 SIGTERM에 즉시 죽음(핸들러 없음), 자식만 고아로 남음.
- 방법론 주의: 비대화형 셸의 & 백그라운드는 SIGINT를 무시시켜 1차 INT 시도가 무효였음(base/ 의 INT 행 폐기). 런처로 기본 핸들러 복원 후 base2 에서 재측정. I-G 가 실수로 내 서버 PID 1개를 종료한 일이 있어 INT_ON_3(base) 는 폐기, base2 는 영향 없음.
- 경과 시간 일부(90~102초)는 이 PC 의 벽시계 점프(date 기준)이며 잔존 판정에는 영향 없음.
- 판정: 재현 확인됨(SIGTERM·kill -9 에서 매번, SIGINT 는 정상). 수정 전 기준선 기록 완료.

## 2. 1차 리뷰 (I-G 작업 트리 스냅샷, 미완성 상태, 스크립트 bench/verify_g/thr.sh)
- 결함 재현: PDEATHSIG 가 요청 스레드 종료 시 발동해 G1 ON 응답({"ok":true,"ready":true}) 직후 1초 안에 /humanoid/status 가 off/enabled=False 로 바뀌고 worker 소멸(t+1·3·6초 모두). 판정: 이 상태는 FAIL(P0 회귀). 같은 구조의 perception worker 도 위험.
- sitecustomize.py: PYTHONPATH=$PWD 이면 저장소 내 모든 python 에 로드되고 환경변수 RP_PARENT_DEATH_PID 가 손자·타 서브프로세스에 상속됨. 국소 대안(진입점/Manager initializer, 부모 PID 감시, 자식에 넘긴 pipe EOF)을 I-G 에 요구함.
- 수정본 검증(각 10회 잔존 0, 종료 p95, pytest, P0, G1 A/B/A/B)은 I-G 수정 후 진행. 현재 전체 판정: NEEDS WORK.

## 3. 수정 전 재현 정정 (중요)
- 위 §1 의 G1 ON 행은 **무효**: 기준선 트리의 assets/ 가 archive 의 일부 디렉터리라 G1 모델(g1_with_hands.xml)이 없어 POST /humanoid/mode 가 503 → 실제로는 G1 이 안 켜짐(자식 3개). OFF 행과 SIGINT OFF 는 유효.
- 정정 재측정(/tmp/rp_vg_base, assets 등을 R 심볼릭 링크, bench/verify_g/out/base_on, 각 10회, G1 실제 ON, 자식 4개): SIGTERM 잔존 3개 10/10, 서버 kill -9 잔존 3개 10/10(10초+ 생존, 우리가 -9 로 정리), SIGINT 잔존 0 10/10(0.9~1.05초). 잔존 3개 = resource_tracker + Manager + G1(humanoid) worker.
- 기준선 서버 kill -9 3회 x ON/OFF 6회 후 /dev/shm psm_* 18개 증가(회당 3개 누수).

## 4. 수정본 검증 (스냅샷 web 해시 50addb547ef8 = 리뷰 반영 최종, 포트 5092, PERCEPTION=stub, 시계 /proc/uptime)
| 항목 | 기준 | 직접 측정 결과 (원자료) | 판정 |
|---|---|---|---|
| 신호 x G1 ON/OFF 각 10회 잔존 | 0 | TERM/INT/KILL x ON/OFF 60/60 잔존 0 (out/fix2/summary.txt; 이전 스냅샷 3c820f 도 60/60, out/fix) | PASS |
| 종료 소요 p95 (자식 전부 소멸까지) | 참고(상한 5s) | TERM ON 1.33 / INT ON 1.29 / KILL ON 0.74 s; OFF 기동 직후 신호: TERM 3.03 / INT 3.27 / KILL 1.45 s; OFF 이고 sim ready 후(12s 대기, out/late2 5회씩) TERM/INT 최대 0.79 s | PASS(5초 상한 내). OFF 3s 는 sim 기동 비협력 구간(join 3s 후 terminate)이며 기동 직후 신호에만 해당 |
| pytest | 85 passed | 85 passed, 40.0s (out/pytest_final.txt, 작업 트리) | PASS |
| P0 worker kill -9 자동 off·재ON·10회 사이클 | 통과 | t=1 초부터 off, 재ON ready, 10회 on/off 200/200, children 4 유지(누수 없음). 이전 스냅샷(out/p0) + 최종 스냅샷(out/p0b) 모두 | PASS |
| P0 동시 ON/OFF 8 | 서버 생존·최종 일관 | 200/409 혼재, 최종 state off, 서버 정상 (out/p0, out/p0b) | PASS |
| P0 첫 끊김 x3 | <42ms | 최종 스냅샷 24.4/24.8/20.7ms (이전 32.4/4.2/28.9) | PASS |
| P0 payload·5MB 413·origin·WS 10 (p0ws, 이전 스냅샷 3c820f 만) | 불일치 0 | mismatch 0, 413 정상, status ws 10 중 8 수신(F 라운드와 비교 기준 없음) | PASS(최종 스냅샷 재측정 안 함) |
| 서버 kill -9 후 /dev/shm psm 신규 | 0 | 수정본 6회 신규 0 / 기준선 6회 18개 | PASS |
| G1 30초 창 A/B/A/B (WSL 송신, ws+push, out/ab3, 스냅샷 3c820f) | -2%p 이내 | fps A 32.033/32.000, B 32.033/32.000; 쌍 차이 -0.033~0.033, 0 포함 → 차이 입증 안 됨. 트리 CPU% A 72.8/72.0 B 70.8/72.7 (쌍 차이 -2.0~0.7, 0 포함, 입증 안 됨), main CPU 12.6/12.4 vs 12.4/12.5. update RTT 평균 A 0.963 B 0.940ms 부트스트랩 B-A -0.023 CI[-0.046,0.000] (상한이 0 → 개선 주장 안 함). gap p95 A 34.1/34.0 B 33.9/33.9 (소폭, 수 0.1ms). 내장 p95 A 50.9/51.2 B 48.4/46.7(참고, 부하 load0 1.0~3.5 상이). 처리율 100%. 프로세스 수 A5 B6(watchdog +1) | 회귀 없음(개선 입증 안 됨) PASS |
## 5. 한계
- A/B·p0ws 는 최종 직전 스냅샷(3c820f) 기준이며 최종(50addb)에서는 신호 60회·pytest·p0vw 만 재측정. 변경분(sim shutdown Event, 2차 신호 _exit)은 신호/P0 로 확인했고 G1 30초 창은 재측정하지 않음.
- A/B 는 창 2개씩(n=2), 에이전트 동시 작업 중이라 load 가 다름. 부트스트랩은 RTT 개별값 기준, fps/CPU 는 창 단위라 CI 가 의미 약함(쌍 차이 범위로 표기).
- 미실시: MJPEG/WS 구독자가 열린 채 신호, 기동 중(create_app) 신호, 실카메라, Windows 경로. 서버 기동 중 첫 SIGTERM 은 초기화 후 정리(I-G 기록).
- 수정본 부작용: watchdog 프로세스 +1 (0.25s 폴링, CPU 차이는 측정오차 내).
## 6. 최종 판정
**PASS (조건부)**: 목표(서버 종료 시 자식 잔존 0)는 직접 재현으로 60/60 달성, 기준선은 TERM/KILL 에서 20/20 잔존. P0 회귀 없음(1차 PDEATHSIG 결함은 제거 확인). 위 한계 항목은 미검증으로 남김.

## 7. 커밋 전 보완 2건 (최종 작업 트리 = 스냅샷 web 해시 50addb547ef8, 포트 5092, 측정 락 안)
### 7-1. 열린 연결 중 종료 (bench/verify_g/openconn.py, 원자료 out/openconn/all.json·openconn.log)
조건: G1 ON, /humanoid/video·/teleop/preview.mjpg 구독 2, /status/ws 구독 1, sender_q3(ws, /tracker/ws update 30Hz + preview HTTP 30Hz) 송신 중 5초 시점에 신호. 각 10회.
| 신호 | 잔존 | 서버 종료(자식 포함 전부 소멸) p50/p95/max | 종료 코드 | 5초 상한 |
|---|---|---|---|---|
| SIGTERM x10 | 0/10 (자식 5개 모두 소멸) | 1.12 / 1.22 / 1.22 s | 0 (정상 종료) | 초과 0 |
| SIGINT x10 | 0/10 | 1.16 / 1.29 / 1.29 s | 0 | 초과 0 |
- 클라이언트 쪽: 열린 연결 60개 전부 서버 종료와 동시(최대 1.28s)에 끊김. MJPEG 2종은 매번 IncompleteRead(연결 중단, 정상 종료 아님), /status/ws 는 close 프레임 없이 연결 끊김(WebSocketConnectionClosedException 13회, 잘린 프레임으로 WebSocketProtocolException(rsv) 7회). 서버가 먼저 정상 close 를 보내지 않는 것은 이전 동작과 같은 추정(기준선 열린 연결 종료는 측정 안 함). tracker sender 는 서버 소멸 뒤 마지막 /humanoid/status 조회에서 MaxRetryError 로 종료(20/20, 결과 json 미생성이라 sender 쪽 코드별 집계는 없음).
- 판정: PASS (잔존 0, 상한 내, 걸림·교착 없음).
### 7-2. G1 30초 창 A/B 1쌍 (A=938c41f 새 트리 /tmp/rp_vg_base, B=최종, WSL 송신 ws+push, out/abf)
| 항목 | A | B | B-A |
|---|---|---|---|
| 개수 fps (프레임) | 32.000 (960) | 32.000 (960) | 0 |
| main CPU % | 12.2 | 12.7 | +0.5 |
| 트리 CPU % (프로세스 수) | 70.5 (5) | 72.9 (6) | +2.4 (watchdog +1) |
| gap p95 / max (ms) | 34.2 / 41.3 | 33.9 / 45.7 | -0.3 / +4.4 |
| 내장 receive→publish p95 (ms) | 51.4 | 52.4 | +1.0 |
| 처리율 update/preview | 100%/100% | 100%/100% | 0 |
| load0 | 0.87 | 0.52 | |
- 창이 1쌍(n=1)이라 부트스트랩 CI 계산 불가 → 차이 입증 안 됨. 앞선 2쌍(§4, out/ab3)에서 트리 CPU 쌍 차이 -2.0~+0.7%p, 이번 +2.4%p 로 부호가 일정하지 않아 CPU 증가 입증 안 됨(관찰 범위 약 3%p 이내, 상대 -2%p 기준 병행 시 fps 는 동일). 개선 주장 안 함.
- 기동 중(ready 전) 신호는 미검증으로 남김(I-G: 첫 신호는 초기화 후 정리).
### 갱신된 최종 판정
| 항목 | 판정 |
|---|---|
| 신호 TERM/INT/KILL x ON/OFF 잔존 0 (각 10회, 60/60) | PASS |
| 열린 연결(MJPEG 2·status ws·tracker ws 송신) 중 TERM/INT 10회씩 | PASS (잔존 0, p95 1.22/1.29s) |
| pytest 85 passed | PASS |
| P0 회귀 (kill -9 자동 off·재ON, 10회, 동시 ON/OFF, 첫 끊김, payload) | PASS |
| shm 신규 누수 (kill -9) | PASS (0, 기준선 18) |
| G1 30초 창 A/B (3쌍: 직전 스냅샷 2 + 최종 1) | 회귀 없음, 개선·CPU 증가 모두 입증 안 됨 |
| 기동 중 신호, 실카메라, Windows 경로 | 미검증 |
**최종: 조건부 PASS (미검증 3항 제외)**
