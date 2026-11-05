# robot_percept 다음 개선 계획 초안 (r2, 2026-11-03, 부모 1NIgF2z2BvfBSkOh 작성)

기준: 커밋 1da4b93 (태그 humanoid-30fps-pass). R조 30fps PASS. 실제 USB 카메라는 현재 분리됨(녹화본/합성으로 진행, 실카메라 항목은 '미실시'로 별도 표기).
사용자 최우선: 휴머노이드(G1)가 사람을 자연스럽게 따라하기. 그 다음 기존 Panda 파이프라인 마무리.

## 알려진 상태 (근거 파일)
- R: notes/humanoid_changes.md, notes/verify_r.md. 남은 것: 왼팔 어깨 굽힘 합성 정답 대비 약 18도 부족(손목·팔꿈치 가중치 타협), 모드 ON 직후 /humanoid/video 1.7s 정지 1회, 도착 간격 버스트(초당 23~60), 접촉 OFF라 팔-몸통 관통 가능, 양손-포즈 연결이 greedy, 실카메라 미검증. /humanoid/status 에서 state=off 인데 enabled=true 로 보이는 불일치 관찰.
- C: notes/control_changes.md. V-C N=10 PASS. N=20 회귀, 장애물 있는 원위치 복귀(negative) 테스트 미실시. gt_assist=off 머스터드 놓기 0/10.
- P: notes/verify_p.md, perception_changes.md. SAM2 클릭 마스크 실패 15/84 → I-P r5 0/84(독립 재확인 필요). FP 경유 자세 오차·클릭→등록 지연 미측정.
- E: notes/verify_e.md, eval_changes.md. 하네스 GT/CPU PASS. FP N30, 추정 자세 집기 매트릭스(gt/fp × assist on/off, N20) 미실시.
- F: notes/focus_view.md. V-F r2 PASS. 남은 것 없음(실 FP 스크린샷 정도).
- T(Panda 따라하기): notes/verify_t.md r5. 입력 스트리밍 시 메인 FPS -26%/-47% 회귀(목표 <10%), 미리보기 11~14Hz → 새 트래커(30Hz)로 재측정 필요.

## 우선순위 초안
### P1. R 휴머노이드 품질 (CPU 위주)
- A1 팔 자세 정확도: 팔꿈치 '위치' 목표 대신 팔꿈치 방향(swivel/팔 평면) 목표 + 팔 길이 비율 정규화. 목표: 합성 정답 대비 양팔 각 관절 오차 ≤8°, 손목 위치 오차 ≤10mm, 좌우 오차 차이 ≤3°.
- A2 자기충돌: 팔-몸통/팔-팔 관통 방지(캡슐 거리 기반 IK 반발항 또는 해당 쌍만 접촉 ON). 목표: 합성 동작 세트 관통 프레임 0, 30fps 유지.
- A3 지연·떨림: 입력 sent_at → 관절 반영 → 영상 프레임 end-to-end 지연 p50/p95(목표 p95 ≤120ms), 정지 자세에서 손목 jitter std ≤3mm, 도착 버스트 평탄화.
- A4 안정성: 모드 ON cold start 정지 제거(워커 프리워밍, ready 후 스트림 연결), status enabled/state 불일치 수정, 손 상실 시 hold→천천히 중립.
- A5 양손 연결 Hungarian(전역 최적), 엄지 대립(opposition) 검증.
- A6 실카메라 수락 테스트 스크립트(카메라 재연결 시 명령 1개로 30fps·검출률·지연 측정). 실행은 카메라 연결 후.
### P2. 기존 파이프라인 마무리
- C: N=20 회귀, 장애물 원위치 복귀 negative 테스트 → PASS 시 C 확정.
- P: r5 정책 독립 84클릭 재확인 + FP 경유 자세 오차/지연 측정 → PASS 시 P 확정.
- T: 새 트래커로 Panda 따라하기 메인 FPS 회귀·미리보기 fps 재측정.
### P3. 평가 (GPU 무거움, 마지막/야간)
- E: FP N30, 추정 자세 집기 매트릭스 N20. GPU 락 필수.
### P4. 엔지니어링
- 서버+트래커 원클릭 실행 스크립트(도구 세션이 끝나면 백그라운드 프로세스가 죽는 문제 → Windows 쪽 런처/작업 스케줄러 검토), README 실행법, .gitignore에 cad_uploads/web 추가.

## 진행 방식 초안
- 각 항목: 구현자(Codex gpt-6.1-sol) + 검증자(Claude sonnet) 페어, 서로 task id로 직접 피드백 루프. 부모에게는 이정표만.
- 포트: R 5091/5092 유지, C 5085/5086, P 5083/5084, T 5089/5090. 5080은 사용자 서버.
- 측정 간섭: FPS/지연 측정은 전역 측정 락(/tmp/rp_measure.lock)으로 한 번에 하나. 배치 작업(C N=20, E)은 nice 19 + GPU 락. 다른 세션의 Ollama가 GPU를 쓸 수 있으니 측정 시 nvidia-smi 기록.
- 동시 서브에이전트 ≤8.

## 검토자에게 묻는 것
1) 빠진 개선점/과한 항목, 2) 우선순위·병렬화 순서, 3) 각 항목의 정량 합격 기준이 측정 가능하고 적절한지, 4) 파일 소유권 충돌(특히 web/app.py, web/sim_worker.py, tools/teleop_tracker_win.py), 5) 위험(측정 간섭, 회귀).
