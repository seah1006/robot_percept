# V-K 검증 기록 (r5 K페어, 검증자 Claude)

기본 판정: **NEEDS WORK** (직접 재현 원자료만 PASS). 대상 HEAD a297220, 5096 전용.

## A. 기준선 (I-K 묶음 도착 전, 2026-11-16 12:45~12:46, load 0.15)
| 항목 | 결과 | 재현 |
|-|-|-|
| 기존 웹 테스트 6파일(realtime/shutdown/teleop/monowait/smoke/pick_place) | 31 passed, 21.6 s (측정 락 안) | pytest 명령 |
| 5096 기동 | /status 200까지 2 s | bench/verify_k/baseline.sh |
| 실행 중 자식 | resource_tracker 1 + spawn 자식 3 (sim_worker 등) | 동 |
| SIGTERM→종료 | 3.495 s (≤5 s) | 동 |
| 종료 후 잔존 프로세스 / 포트 | 0 / free | 동 |
참고: 작업트리에 비커밋 변경(contract_r5_changes.md, localize 등 W2 파일)이 있으나 K와 무관, 웹 파일 변경 없음.

## B. I-K 묶음 검증 (대기 중)
(1)~(8) 미착수: I-K 묶음 미도착.
