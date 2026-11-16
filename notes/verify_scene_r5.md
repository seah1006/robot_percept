# verify_scene_r5 (V-SA)

판정: **NEEDS WORK (미검증, 구현 산출물 없음)**

## 상태 (2026-11-10)
- git status 기준 셀 장면 관련 파일(config/objects.yaml, vocab_ko_en.yaml, 장면 생성기, tests/test_cell_scene_r5.py, 렌더 PNG) 아직 없음. 완료 알림도 미수신.
- 검증 항목 전부 미실행: 회귀(diff 목록, 전체 pytest 104), 결정론, 시드 분리, 겹침/관통, 안착(N>=50), PNG 육안, mesh 높이/grasp 70mm, 라이선스/용량, GT 분리.

## 재개 지점
I-SA(ujx84ahFemm3SWiP) 완료 알림 수신 후: git status/diff 로 파일 목록 → bench/verify_sa/ 에 독립 스크립트(결정론, 시드 겹침, 겹침/관통, 안착 N>=50) → 렌더 PNG Read → objects.yaml vs mesh 치수 → 라이선스/용량 → GT 분리 → flock 안에서 전체 pytest.

## 기준선 (V-SA 직접 재현, 2026-11-10)
- HEAD ebbb8f4, 회사 PC, env robot_percept, flock /tmp/rp_measure.lock 안 `pytest -q -x`: **104 passed, 5 warnings, 69.41 s** (시작 load 1.79, 종료 load 2.03, 동시 작업 없음 가정). [시뮬GT] 해당 없음(회귀 테스트).
- 공유 운영 파일 미변경 확인 대상: web/app.py, web/sim_worker.py, web/realtime.py, web/perception_stub.py, web/static/humanoid.js, index.html, 기존 장면 파일(sim/ 기존).
- 재개 지점: I-SA 묶음 수신 후 위 \"재개 지점\" 절차 그대로.

## 1차 직접 재현 (r1 코드, 2026-11-16 12:18~12:30, 측정 락, load 1.4~2.0, [시뮬GT] 평가용 진단)
스크립트 bench/verify_sa/{verify,diag,rgbdiff}.py, 원자료 full_result.json, PNG render_*.png(640x480, 6장).
- 공유/기존 파일 diff: sim/·web/ 기존 파일 수정 0 (신규만). PASS(r1 시점).
- 결정론: plan scene_hash 5시드 PYTHONHASHSEED 1/2 동일. 물리 qpos 해시 동일(시드 100000, 4회). **RGB 바이트 해시는 같은 프로세스에서도 불일치**(렌더 3회 비교 6시드 maxabs=1, 23~67픽셀 차이, d3d12 렌더 잡음). 판정기준은 plan·qpos 해시 + RGB 허용오차(<=1)로 정의 필요.
- 시드: tune 20/eval 100(manifest), 시드 겹침 0은 구현 테스트 근거, 내 verify.py 출력 앞부분 유실 -> r2에서 재실행 예정. eval 클래스 분포(일부) block27 mug31 mustard33 small_box39, 동일클래스 장면 20/50.., 물체수 2/3/4 = 33/34/33 (eval 100).
- 안착(70장면 = eval50+tune20, 추가 물리 3 s): 최대 이동 0.031 mm, 바닥 간격 최대 0.105 mm, 물체간/로봇 접촉 0, 관통 0 mm, AABB 겹침 0, 트레이 밖 0. 단 **max qvel 0.0435 > 0.01**(ball 각속도 잔류, I-SA 진단과 일치), 최대 기울기 변화 3.95 deg(구 굴림). r2(ball 6D 접촉, 정지조건)로 재검증 필요.
- 육안: 물체 색 구분 OK(빨강 mug·주황 can·노랑 mustard·보라 ball 등). 주의: can(.95,.65,.06) vs mustard(.85,.65,.12) 색 근접(형태·텍스처로 구분), blue box(.12,.3,.85)/cup(.15,.6,.9)와 목적지 파란 slot 색 혼동 가능, 로봇 그림자가 트레이 중앙 큼. mug는 단순 원기둥(can·bottle과 형태 유사, 색으로만 구분).
- 정책: 70mm 경계 can(0.07)=strict_top, mustard(0.191)=side_preferred 일치. GT 분리: CellCamera.capture 키 4개, _CellCamera__capture 이름 변조 접근은 API 경계 수준(적대적 아님).
- 미측정: 가림(occlusion=unmeasured), 라이선스 notices(I-SA 작성중, 기존 CAD upstream 재배포 확인 필요), 용량(assets/objects/cell_r5 52K).

## 재개 지점
I-SA r2 묶음(ball 6D, 정지조건, PNG3, manifest) 도착 후: verify.py full 재실행(앞부분 포함 전체 출력 저장) -> 안착 qvel<=0.003 재확인 -> 라이선스/notices -> 최종 전체 pytest 1회(PYTHONPATH=/home/user/work/robot_percept 절대경로, 측정 락).

## 최종 (r3, cell-r5-2, 2026-11-16 12:31~12:36, 측정 락, load 1.3~1.8) — 판정: **PASS(조건부, 가림 제외)**
- 원자료: bench/verify_sa/full_result_r3.json, 전체 pytest **316 passed, 85.30 s** (기준선 104 + 신규 212, PYTHONPATH 절대경로).
- diff: 기존 sim/·web/·tests/·assets 수정 0(모두 신규). 책상 rubber(condim6 .8/.01/.002)는 sim/cell_scene.py 셀 전용 XML 수정, scene_builder 불변. 수정 공유 파일은 THIRD_PARTY_NOTICES.md뿐.
- 시드: tune 20/eval 100 겹침 0, 내용(layout) 겹침 0, eval 100 layout 고유 100. 물체 수 2/3/4=33/34/33, 동일클래스 장면 20, 클래스 27~39회.
- 결정론: plan·qpos 해시 동일, RGB 차이<=1(문서화됨). manifest 재생성 sets 동일(추가 필드 asset/source sha256만 스크립트 추가).
- 안착(70장면, 추가 3 s): 이동 max 0.053 mm, 바닥간격 0.022 mm, qvel max 3.3e-6, 접촉/관통/겹침/로봇접촉/트레이밖 모두 0. 기울기 7.56deg는 대칭 물체 yaw 포함 쿼터니언 변화(이동 0.05mm)로 안착 문제 아님.
- 육안: scene_100000/100002 PNG(320x240) 확인, 보라 구·파란 박스·청록 블록·파란 원통 구분, 목적지 slot 회색(진/연)으로 변경되어 물체 색과 분리. 해상도가 작아 소형 물체(~35mm bottle) 구분은 640x480 이상 권장.
- notices: 자체 6종·CAD 자체 생성·mustard CC BY 4.0 정정 확인. 용량 assets 52K, bench/sa 272K.
- 미해결: 가림 unmeasured(I-SA 명시), mug/can/bottle 원통 형태 유사(색으로만 구분), 수정 파일 미커밋(부모 커밋 대상).
