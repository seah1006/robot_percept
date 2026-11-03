# robot_percept 팀 작업 규칙 (Phase B: 계획 2·3a·3b·4)

최종 계획: notes/next_plan_draft.md + notes/plan_review_rc.md + notes/plan_review_rx.md (합의본은 부모 보고 기준)
기준선: git tag `baseline-1102` (repo: /home/user/work/robot_percept). 구현자는 커밋하지 말 것 — 검증 PASS 후 부모가 커밋.
환경: `source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept; cd /home/user/work/robot_percept; source sim_test/gl_env.sh; export HOST=127.0.0.1`
pip 설치는 반드시 `-c notes/rp_constraints.txt`. 스모크 테스트: `python -m pytest -q tests/test_smoke.py` (변경 후 항상 통과해야 함).

## 페어와 소유권
| 페어 | 구현자(Codex) 소유 파일 | 포트 | 검증자(Claude) |
|---|---|---|---|
| E 평가 하네스 (계획 2 + 4 측정) | eval/run_benchmark.py, eval/harness/, eval/report/, bench/eval/ | 없음(headless) | V-E: bench/verify_e/ |
| P 인식 (계획 3a SAM2 mask) | perception/ (fp_runner 제외 SAM 관련 신규 파일), web/perception_stub.py, web/app.py 의 select_at/segment 부분만 | 5083 (검증 5084) | V-P: bench/verify_p/ |
| C 제어 (계획 3b + 4 정답 보조 옵션) | sim/grasp.py, sim/control.py, sim/ik.py, web/sim_worker.py 의 pick/place/home 부분, tests/test_pick_place.py | 5085 (검증 5086) | V-C: bench/verify_c/ |
다른 페어 파일은 읽기만. 인터페이스 변경이 필요하면 해당 페어 구현자에게 message_agent 로 요청.
사용자 서버 5080, 기존 5081/5082 는 절대 건드리지 말 것. 자기 포트 프로세스만 종료.

## GPU 공유 규칙 (8GB, 측정 간섭 방지)
GPU 를 많이 쓰는 작업(SAM2/FoundationPose 추론, 벤치마크)은 반드시 전역 락으로 감쌀 것:
`flock /tmp/rp_gpu.lock -c "<command>"`  (락 대기 시간은 결과에 기록). 렌더링만 하는 짧은 테스트는 예외.

## 교차 검증 루프
구현자는 변경 묶음마다 검증자에게 message_agent(to=검증자 id)로: 바뀐 파일, 이유, 자기 측정치, 재현 명령. 검증자는 독립 스크립트로 재측정 + diff 리뷰(git diff baseline-1102 -- <files>) 후 PASS/FAIL 회신. 둘 다 부모에게 라운드 요약(message_agent, to 생략). 최종 PASS 후 구현자가 notes/<pair>_changes.md 작성.

## 공통 사실 (리뷰에서 확인)
- 놓기(place_object)·집기 높이(z0)·grasp-assist weld 가 GT 자세를 사용 → 계획 4에서 옵션화/공개.
- 추적 FPS 지표는 추론시간 역수 → 실제 초당 추정 갱신 수로 바꿀 것(P 또는 E).
- export_fp 는 mustard 만, randomize=False → 하네스는 내부 함수 재사용.
- mustard grasp 계획 지연: IK 실패 재시도 꼬리(최대 1600 iter) → C.
- SAM IoU 11%: 같은 프레임 비교 확인됨, 단일 점 multimask 선택 가설 → P 가 진단 먼저.

## 프로세스 종료 규칙 (추가)
\pkill -f web.app\ 처럼 넓게 죽이는 명령 금지. 자기 포트의 PID만 종료: \ss -ltnp | grep :<PORT>\ 로 PID 확인 후 kill.
