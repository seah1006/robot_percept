# V-H 검증 (집 PC, 2026-11-06)

기본 판정 NEEDS WORK, 직접 재현한 항목만 PASS. 측정은 모두 `flock /tmp/rp_measure.lock` 안, 포트 5092, PERCEPTION=stub, RP_PERCEPTION_WARMUP=0, AMD RX 7600(GPU 사용률 N/A), load 1.5~5(다른 에이전트 동시 작업).
기준 트리: `git archive c1656d7` -> /tmp/rp_base_h. 수정본: I-H 작업트리(wip/r2, 미커밋) 스냅샷 -> /tmp/rp_fix_h (cwd 기준 프로세스 식별이 부모의 5091 서버와 섞이지 않게 복사본 사용).
스크립트/원자료: `bench/verify_h/` (sig_h.py, poll_h.py, run_*.sh, sig_h_*.json/log, poll_h_*.json/log, pytest_fix.txt). 매회 포트 비어 있음 확인, 잔존 강제 정리 후 0 확인.

| # | 항목 | 판정 |
|---|---|---|
| 1 | 기동 중 SIGKILL worker 잔존 | **PASS** (수정본 0/150, 95% 상한 2.0%; 기준 3/100 재현) |
| 2 | test_pick_place /home/user 하드코딩 | **PASS** (grep 0건, 다른 cwd에서 실행해 ROOT/data/c1_check에 기록) |
| 3 | 10Hz 폴링 60초 ready 미관측 | **NEEDS WORK(원인 미확정)**: 기준 0/50, 수정본 0/30 미재현. "수정"이 아니라 "재현 불가" |
| 4 | pytest | **PASS** 90 passed (test_env는 cad_uploads 링크 필요) |

## 1. SIGKILL 경쟁
delay ~ U(0.3, 0.8)초 무작위(시드 고정), 신호 SIGKILL, 서버 종료 후 포착 자손+cwd 트리 프로세스가 12초 안에 사라지는지.
| 트리 | 회수 | 구간 | 잔존 회 | 잔존 정체 |
|---|---|---|---|---|
| 기준 c1656d7 | 50+50 | 0.3~0.8 | **3/100** (delay 0.615, 0.654, 0.559초) | 매번 `resource_tracker`+`spawn_main`(Manager) 2개, 부모는 init |
| 수정본 | 50+50+50 | 0.3~0.8 x2, 0.5~0.7 x1 | **0/150** | - |
수정본 최대 clear 0.46초. 0/150이므로 rule of three 95% 상한 3/150 = 2.0%. 기준 3/100(Wilson 95% 약 1.0~8.5%)과 비교해 차이는 통계적으로 약함: 구간이 겹쳐 "개선 입증"까지는 못 함(0.5~0.7 구간 한정 추가 50회 포함해도 상한 2%). 다만 잔존 메커니즘(Manager가 부모 사망 후 뒤늦게 기동)을 코드로 막았고(initializer ppid 비교, 시작 즉시 비교), 회귀 테스트 test_server_sigkill_during_startup 3개가 통과.
리뷰: web/process_lifecycle.py exit_if_parent_changed, SyncManager initializer, sim/humanoid worker 시작 즉시 비교. 남는 창: 부모가 Manager spawn 시작 직전~initializer 실행 전 사이에 죽는 경우는 initializer가 막음, 그 뒤는 감시 스레드가 막음. 지적할 결함 없음.
## 2. test_pick_place
STRIP/OUT 경로가 ROOT 기준. `cd /` 에서 `--suite all --trials 2` 실행 -> pick/place 전부 성공, `data/c1_check/results.json` 생성, /home/user 없음. 한계: STRIP(multi_strip.png)은 코드에서 정의만 되고 쓰이지 않아 생성 안 됨(기존 동작과 동일 추정).
## 3. 10Hz 폴링
10Hz `/status` 폴링 기동: 기준 50회 ready 4.33~5.54초, 60초 초과 0. 수정본 30회 4.22~4.63초, 0. V-B 1회 관찰은 이 PC의 벽시계 점프(time.time +92초)로 폴링 스크립트의 time.time 기반 타이머가 오염된 것일 가능성이 높으나, 직접 재현 못 해 확정 불가. 서버 쪽 결함이라는 증거는 없음.
## 정리
5092 리스너 0, 내 worker 0 확인.
