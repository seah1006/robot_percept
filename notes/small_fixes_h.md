# 작은 수정 H (I-H, 2026-11-06)

## 범위와 환경
- 브랜치 `wip/r2`, 시작 HEAD `c1656d7`, master `452378f`. 커밋하지 않았다.
- P1c/collision 로직은 건드리지 않았다.
- WSL Ubuntu-24.04, Python 3.12.16, `PERCEPTION=stub`, `RP_PERCEPTION_WARMUP=0`, 포트 5093/5095.
- 반복 실험과 전체 pytest는 `/tmp/rp_measure.lock` 안에서 실행했다. GPU 작업이 아니므로 GPU 사용률은 N/A. GL 경로는 기존 환경 기록의 `D3D12 (AMD Radeon RX 7600)`이다.
- 측정 종료 뒤 uptime load average는 2.37/2.43/2.05였다. 부모 구현 작업과 V-H 준비가 동시 진행 중이었다.

## 1. 기동 직후 SIGKILL 경쟁 상태

### 재현
- 하네스: `bench/verify_h/early_kill.py` (V-B 하네스를 현재 트리/포트 5093용으로 이식, 20ms 간격으로 자손 수집, monotonic 경과 사용).
- 수정 전 0.4/0.5/0.6초 각각 10회, 총 30회 SIGKILL.
- 0.6초 10회 중 1회에서 자식 2개가 15초 뒤에도 남았다.
  - `multiprocessing.resource_tracker ... main(5)`
  - `multiprocessing.spawn ... spawn_main` (Manager 서버)
  - 둘 다 원 서버 부모가 아니라 WSL subreaper PID로 재부모화돼 있었다.
- 원자료: `bench/verify_h/out/baseline.log`, `early_kill_0.6_baseline.json`.

### 원인과 수정
- 기존 Manager watchdog은 부모 PID를 인자로 받았지만, 웹 부모가 `ctx.Manager()` 생성 도중 죽으면 watchdog 자체가 아직 spawn되지 않을 수 있었다.
- sim worker는 `SimEnv` 생성과 첫 publish가 끝난 뒤 main loop에서야 PPID를 확인했다.
- 일반 parent-watch는 감시 thread를 시작한 뒤 thread가 스케줄돼야 첫 비교가 이뤄져 작은 틈이 있었다.
- `exit_if_parent_changed(expected_parent_pid)`를 추가해 child 진입점에서 thread/import/초기화 전에 동기 비교한다.
- Manager는 `SyncManager.start(initializer=..., initargs=(parent_pid,))`로 명시 부모 PID를 서버 프로세스에 전달하고, initializer가 즉시 동기 비교 후 감시 thread를 시작한다. 기존 독립 watchdog도 유지한다.
- sim/humanoid worker도 함수 첫 진입 시 명시 parent PID를 즉시 비교한다. perception worker는 기존 `start_parent_pid_watch` 호출이 새 동기 비교를 포함한다.

### 수정 후
- 0.5/0.6/0.7초 각각 10회, 총 30회 SIGKILL: 15초 잔존 0/30, 5초 초과 0/30.
- clear 최대 0.44초, `/dev/shm` 증가 0, 포트 잔존 0.
- 원자료: `bench/verify_h/out/fixed_and_status.log`, `early_kill_{0.5,0.6,0.7}_fixed.json`.
- 회귀 테스트: `tests/test_shutdown.py`에 0.4/0.6/0.8초 startup SIGKILL 실제 서버 테스트를 추가했다. shutdown 집중 테스트 7 passed.

## 2. tests/test_pick_place.py 경로 이식성
- 저장소 루트 `ROOT = Path(__file__).resolve().parents[1]`를 정의했다.
- strip/results 출력은 `ROOT / "data" / "c1_check"`를 사용한다.
- 디렉터리는 `parents=True`로 생성한다. 집 PC에서 계산된 OUTPUT_DIR은 `/home/my/work/robot_percept/data/c1_check`, `/home/user` 문자열은 0건이다.
- pick/place 계산, 시드, 출력 JSON 병합 동작은 변경하지 않았다.

## 3. 10Hz /status ready 미관측
- 하네스: `bench/verify_h/status_poll.py`, 포트 5095, 각 요청 timeout 0.3초, monotonic 20초 상한, 매 회 정상 종료 및 포트 해제.
- 10Hz 12회: 실패 0, ready 4.606~5.307초.
- 20Hz 8회: 실패 0, ready 4.507~4.757초.
- 총 20회에서 ready 미관측을 재현하지 못했다. 코드 변경 없음.
- 20Hz 목표 12회 중 8회 뒤, SIGKILL 30회와 한 flock 명령으로 묶은 전체 명령이 5분 제한에 도달해 중단됐다. 중단 뒤 5093/5095 listener와 저장소 worker 잔존은 0이었다. 완료된 20회만 결과로 기록한다.
- 원자료: `bench/verify_h/out/fixed_and_status.log`, 개별 `status_*.log`. 최종 JSON은 명령 중단 전에 쓰는 구조라 생성되지 않았으며 로그 행이 원자료다.

## 테스트
- 전체 pytest: **90 passed, 5 warnings, 43.34초**.
- 원자료: `bench/verify_h/out/pytest_full.txt`.
- `git diff --check` 통과. 5093/5095 listener 0 확인.

## 한계
- startup kill 재현 빈도는 스케줄링 의존이며 수정 전 표본도 1/30이다. 수정 후 0/30은 경쟁 창 제거와 일치하지만 독립 검증 전 PASS 근거로 쓰지 않는다.
- `/status` 60초 미관측은 이번 10Hz 12회, 20Hz 8회에서 재현되지 않아 원인 분석이나 운영 코드 변경을 하지 않았다.
- GT 보조 pick/place 성능 반복은 이번 경로 문자열 수정 범위가 아니며, 전체 pytest와 경로 계산만 확인했다.
