# 서버 종료 시 worker 잔존 수정 (I-G, 2026-11-06)

## 범위와 기준
- 작업 브랜치 `wip/r2`, 시작 HEAD `938c41f` (master 기준 `16e49a8`). 커밋하지 않음.
- 동작/API/P1a/P1b/P1c 로직은 변경하지 않았다. 운영 코드에 측정 락을 넣지 않았다.
- 실측은 `/tmp/rp_measure.lock`, 포트 5093, `PERCEPTION=stub`, `RP_PERCEPTION_WARMUP=0`에서 했다.
- GPU: AMD Radeon RX 7600, WSLg `D3D12 (AMD Radeon RX 7600)` 경로. 이번 종료 반복은 GPU 수치가 목적이 아니어서 별도 GPU 사용률은 N/A.

## 재현과 원인

### 수정 전 증거
- 별도 기준선 트리(HEAD 938c41f), G1 ON/OFF, 포트 5093에서 SIGTERM 3회씩:
  - ON: 매회 4자식 중 2개가 10초 뒤에도 잔존.
  - OFF: 매회 3자식 중 2개가 10초 뒤에도 잔존.
  - 잔존은 `multiprocessing.resource_tracker`와 `multiprocessing.spawn` Manager 서버였다.
  - 원자료: `bench/shutdown_probe/out/baseline_term/summary.txt`.
- V-G 기준선 kill -9 직접 측정도 ON/OFF 각 5회 모두 같은 2개가 10초 뒤 잔존했다. 원자료: `bench/verify_g/out/base2/summary.txt`.
- 기준선 SIGINT는 대부분 자식 0으로 정리되었다. Python의 기본 SIGINT가 `KeyboardInterrupt` 정상 종료 경로를 탈 수 있기 때문이다. 단, 벽시계 점프로 한 회의 `date` 기반 elapsed가 90초로 오염됐다. 이번 수정/측정은 monotonic 기준이다.

### 원인
1. 기존 `python -m web.app`는 `app.run()`과 `atexit`에 정리를 맡겼다. 기본 SIGTERM/SIGKILL은 Python 정상 종료가 아니므로 `atexit`와 `Runtime.close()`가 실행되지 않는다.
2. sim/humanoid/perception은 `daemon=True`지만 daemon 표시는 부모의 정상 multiprocessing 종료 때만 의미가 있다. 부모가 신호로 즉시 죽으면 자식 종료를 보장하지 않는다.
3. Manager와 resource tracker는 별도 non-daemon 보조 프로세스다. 부모 사망만으로 Manager가 종료되지 않았고, Manager가 tracker FD를 잡은 채 남아 tracker도 함께 잔존했다.
4. G1의 기존 `getppid()` 검사는 humanoid worker에만 있었고 Manager/sim/lazy perception 전체를 덮지 못했다.
5. 1차 시도였던 Linux `PR_SET_PDEATHSIG`는 폐기했다. Linux에서 이 신호는 프로세스 전체 부모가 아니라 자식을 생성한 스레드의 종료에도 발동한다. 요청 스레드에서 G1을 spawn하므로 POST 응답 직후 worker가 죽는 P0 회귀를 V-G가 재현했다. `sitecustomize.py` 방식도 전역 로드/환경변수 상속 위험 때문에 전부 제거했다.

## 최종 수정

### 부모 서버
- `werkzeug.serving.make_server(threaded=True)`를 별도 서버 스레드에서 실행한다.
- 메인 스레드의 SIGTERM/SIGINT 핸들러는 종료 Event만 설정한다. 메인 스레드가 `server.shutdown()`/`server_close()`를 호출하므로 `serve_forever()` 자기 스레드 shutdown 교착을 피한다.
- `close_app()`은 humanoid → sim/perception → shared memory/Manager 순서로 기존 정리 경로를 명시 실행한다.
- 모든 multiprocessing child는 공통 monotonic deadline 안에서 `join → terminate → kill`한다. 서버 shutdown 시작 시점부터 총 worker 정리 예산은 5초다.
- `Runtime.close()`는 lock/closed flag로 멱등 처리했다.

### 부모 kill -9 대비
- sim: 기존 main loop에 0.25초 간격 `os.getppid()` 확인을 추가했다.
- humanoid: 기존 main loop의 `os.getppid()` 확인을 유지하고 기대 부모 PID를 명시 전달한다.
- lazy perception: RPC `Queue.get()`에 오래 막힐 수 있어 0.25초 monotonic PPID 감시 daemon thread를 worker 내부에서 시작한다. 생성 요청 스레드의 종료와 무관하다.
- Manager: Manager 내부에 감시 thread를 넣으면 이 WSL 환경에서 Manager/Panda 스케줄링이 달라지는 현상이 보여 폐기했다. 대신 독립 daemon watchdog 프로세스가 부모 PPID를 0.25초마다 확인하고, 부모가 사라지면 Manager에 TERM→1초 뒤 KILL을 보낸다. Manager 종료 뒤 resource tracker도 EOF로 종료된다.
- 플랫폼 비호환/이미 종료된 PID는 예외를 무시해 정상 경로를 방해하지 않는다.

## 회귀 테스트
- `tests/test_shutdown.py`
  - 실제 subprocess 서버를 임의 포트에 기동한다.
  - SIGTERM/SIGINT/SIGKILL 각각 부모 종료 후 캡처한 전체 자식이 5초 안에 0인지 확인한다.
  - 다른 짧은 thread에서 worker를 spawn하고 그 thread가 끝난 뒤에도 worker가 살아 있는지 확인한다. PR_SET_PDEATHSIG 회귀 방지용이다.
- 전체 pytest: **85 passed**, 5 warnings, 38.53초.
  - 원자료: `bench/shutdown_probe/out/pytest_watchdog_final.txt`.
- G1 실제 생존: mode ON 응답 후 t=1/3/6초 모두 `enabled=true`, t=6 fps 31.9.
  - 원자료: `bench/shutdown_probe/out/g1_survive_t1.json`, `...t3.json`, `...t6.json`.

## 최종 신호 반복 실측
G1 worker를 실제 ON으로 만든 뒤 서버 직계/하위 자식 5개(resource tracker, Manager, watchdog, sim, humanoid)를 캡처했다.

| 신호 | 반복 | 잔존 | 종료 p50 | 종료 p95 | 최대 |
|---|---:|---:|---:|---:|---:|
| SIGTERM | 10 | 0/10 | 1.9194s | **2.0470s** | 2.0693s |
| SIGINT | 10 | 0/10 | 1.8941s | **2.0470s** | 2.0695s |
| SIGKILL | 10 | 0/10 | 0.4271s | **1.4953s** | 1.5317s |

- 모든 반복에서 부모와 캡처 자식 잔존 0, 포트 리스너 잔존 0.
- 원자료: `bench/shutdown_probe/out/signals_current.json`, `signals_watchdog_final.txt`, 개별 server log.

## G1 30초 같은 슬롯 A/B 1쌍
A는 최종 코드에서 Manager watchdog만 끈 임시 트리, B는 최종 코드다. 합성 입력/GT 보조 없음.

| 지표 | A | B | B-A | bootstrap 95% CI |
|---|---:|---:|---:|---:|
| fps_count | 32.00 | 32.00 | 0.00 | [0.00, 0.00] |
| proxy p95 | 30.1ms | 30.9ms | +0.8ms | [+0.8, +0.8] |
| main CPU | 7.43% | 7.73% | +0.30%p | [+0.30, +0.30] |
| tree CPU | 48.67% | 67.33% | +18.66%p | [+18.66, +18.66] |

- watchdog 자체 PID CPU는 측정 해상도에서 0.00%였다.
- **CPU 차이 입증 안 됨/판정 유보**: n=1이라 bootstrap CI가 점추정으로 붕괴해 추론력이 없다. 또한 A에서 Manager 0.03%, Panda sim 0.00%로 비정상 정지 수준이었고, 기존 조용한 창의 정상 tree CPU 69.9~71.8%와 맞지 않는다. B 67.33%는 그 정상 범위에 가깝다. 따라서 +18.66%p를 watchdog 비용으로 해석하지 않는다. 개선 주장도 하지 않는다.
- fps와 proxy p95에는 실질 회귀가 보이지 않았지만, 한 쌍뿐이므로 성능 동등성 확정은 V-G 재측정에 맡긴다.
- 원자료: `bench/shutdown_probe/out/g1_A.json`, `g1_B.json`, `g1_A/B.out`, `run_g1_ab.sh`.

## 한계
- perception은 stub이라 실제 FoundationPose worker를 기동하지 않았다. 다만 같은 PPID watcher 진입점과 실제 subprocess 단위 테스트를 통과했다.
- SIGKILL은 정상 정리를 실행할 수 없으므로 child는 즉시/감시 주기 내 강제 종료된다. shared memory는 resource tracker 종료 경로에 맡긴다.
- 벽시계 점프가 반복 관찰되어 elapsed 판정은 모두 `time.monotonic()` 기준이다.

## V-G 2차 리뷰 반영
- V-G 직접 측정(수정 스냅샷, 포트 5092, `/proc/uptime` monotonic): TERM/INT/KILL × G1 ON/OFF 각 10회 모두 잔존 0. 1차 P0(PDEATHSIG로 G1 즉시 OFF) 해소 확인.
- G1 OFF TERM/INT가 약 3초 걸리던 지적에 대해 sim 전용 `multiprocessing.Event`를 추가했다. 부모 close가 Event를 먼저 set하고 sim loop가 `Queue` feeder와 무관하게 즉시 협력 종료한다. Queue의 기존 shutdown op는 호환 경로로 유지한다.
- 첫 종료 신호는 정리 Event를 설정한다. 정리가 이미 요청된 상태에서 두 번째 SIGTERM/SIGINT가 오면 `os._exit(128+signum)`으로 즉시 강제 종료한다. 첫 신호가 `create_app()` 초기화 도중 오면 부분 Runtime을 안전하게 닫기 어려워 초기화 완료 뒤 정리한다는 한계는 남는다. 두 번째 신호는 이 대기를 우회한다.
- PDEATHSIG 음성 대조: 1차와 같은 `sitecustomize` 조기 arm 방식을 짧은 생성 thread에서 spawn한 child에 적용하면 thread 종료 0.7초 뒤 `alive=False`, exitcode -15였다. 현재 `test_parent_watch_is_independent_of_spawning_thread`는 같은 상황에서 child 생존을 요구하므로 당시 구현에서는 실패한다. 원자료 `bench/shutdown_probe/out/pdeath_site_negative.txt`.
- 후속 재측정에서 G1 OFF TERM/INT 약 3초는 Event 추가 뒤에도 유지됐다. 자식별 추적 결과, 하네스가 `/humanoid/status`만 응답하면 곧바로 신호를 보내 sim worker가 아직 `SimEnv` 생성/첫 `publish(True)` 중(R/D 상태)이었다. 이 구간은 main loop의 Event/Queue 확인 전이라 협력 취소할 수 없고, 3초 join 뒤 terminate된다. 즉 idle loop가 shutdown op를 놓친 것이 아니라 **sim startup의 비협력 구간**이다. MuJoCo import/첫 render 내부 취소는 범위와 위험이 커 변경하지 않았으며, 5초 총 상한은 지킨다. sim ready 이후에는 Event가 Queue feeder와 무관한 즉시 종료 경로다.
- G1 ON 서버 kill -9 전후 `/dev/shm/psm_*` 집합을 비교했고 새 잔존은 **0개**였다. Manager watchdog 종료 뒤 resource tracker가 shared memory를 회수했다. 원자료 `bench/shutdown_probe/out/shm_kill_summary.txt`, `shm_kill_new.txt`.

### V-G fix2 직접 재측정(2차 반영 후)
| 신호 | G1 ON p95 | G1 OFF p95 | 잔존 |
|---|---:|---:|---:|
| SIGTERM | 1.321s | 3.026s | 각 0/10 |
| SIGINT | 1.290s | 3.180s | 각 0/10 |
| SIGKILL | 0.735s | 1.450s | 각 0/10 |

원자료 `bench/verify_g/out/fix2/summary.txt`. OFF의 약 3초는 위 startup 비협력 구간 설명과 일치한다.
- V-G가 sim ready 이후 G1 OFF를 별도로 5회씩 확인한 결과 TERM p95 0.79s, INT p95 0.79s, 잔존 각 0/5였다. 따라서 Event 협력 종료는 startup 이후 정상 작동하며, 약 3초는 startup 신호에만 한정된다. 원자료 `bench/verify_g/out/late2/summary.txt`.

### V-G 직접 G1 A/B/A/B 최종 성능
V-G가 수정 전 A(프로세스 5개)와 수정 후 B(watchdog 포함 6개)를 같은 슬롯 A1/B1/A2/B2로 직접 측정했다.
- fps: A 32.033/32.000, B 32.033/32.000. 쌍 차이 범위 -0.033~+0.033, 0 포함 → 차이 입증 안 됨.
- tree CPU: A 72.8/72.0%, B 70.8/72.7%. B-A -2.0~+0.7%p, 0 포함 → watchdog CPU 회귀 입증 안 됨.
- main CPU: A 12.6/12.4%, B 12.4/12.5%. B-A -0.2~+0.1%p, 0 포함 → 차이 입증 안 됨.
- gap p95: A 34.1/34.0ms, B 33.9/33.9ms. 성능 저하 없음.
- 원자료 `bench/verify_g/out/ab3/analysis.txt`, `AB_A1/B1/A2/B2.json`. 이 결과가 앞의 I-G 단일쌍 CPU 이상치보다 신뢰도가 높으며 최종 성능 판정 근거다.
