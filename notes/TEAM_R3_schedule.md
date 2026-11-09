# r3 장시간 안정성 시험 일정

성능 판정은 측정 락 안에서만. 아래 장시간 시험과 겹친 성능 측정은 동시 진행 명시.

## T3 (V-T3 실행 예정, 아직 시작 아님)
- 담당: V-T3 uQYJdDaotP8YMpsv, 포트 5092.
- 하네스: bench/tracker_r3_company.py --long --seconds 3600 --order ws --videos <async> --server-pid <WSL서버PID> --out <새폴더>
- 시작: 미시작. 종료: 미정. V-T3가 실제 시각/결과 경로 갱신.
- 락 밖 허용: 오류·복구·RSS. 처리율 추이는 관측 참고값이며 절대 성능 판정 금지.

- V-T3 13:34 KST 부모 지시로 전체 중지. 1h 장시간은 시작하지 않음(미실시). 5092/트래커/카메라 정리됨. 재개 지점은 notes/verify_t.md 'r3 후반 추가 기록'.
