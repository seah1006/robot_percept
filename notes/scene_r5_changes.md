# r5 셀 장면 변경 (I-SA)

## 범위
- 기존 sim/env.py·scene_builder.py·objects.py·grasp.py 및 web/* 미변경.
- 새 sim/cell_scene.py: 셀 전용 테이블·트레이·목적지2(각 단층2slot), 장면2~4개.
- 물체9: mug,small_box,can,ball,block,bottle,mustard,box,cup. 8종 ≤70mm strict_top; mustard191.408mm side_preferred.
- 단순 원기둥 mug/bottle은 실물 대체형상, 집기 성공을 보장하지 않음.
- config JSON은 YAML1.2 부분집합. 치수/높이/면적/대칭/색/원점/grasp/충돌/질량 명시.
- 관측 open_cell→CellCamera.capture: RGB/source/assist만. 평가 open_evaluation_scene→ground_truth: id/pose. Python 악성코드 샌드박스가 아닌 API capability 경계.
- seed tune1000..1019(20), eval100000..100099(100), split/config/asset/source hash. 동일클래스 방해물20%. 가림은 unmeasured 명시, 가림 정확도 주장 금지.
- GT 평가는 실제 변환 mesh vertices min-z 사용(곡면을 bounds cube로 평가하면 거짓 관통).

## 검증
- V-SA 기준선 HEAD ebbb8f4: 104 passed /69.41s.
- 최초 신규: 47passed/17failed → 곡면 최저점 평가 수정.
- 구현자 최초 기준선 명령은 PYTHONPATH 전달 오류로 collection4error, 기준선으로 쓰지 않음. python -m pytest로 교정.
- 전체pytest와 렌더는 measure 락, 렌더 GPU 추가 gpu 락.

## 재현
    source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept
    cd /home/user/work/robot_percept; source sim_test/gl_env.sh
    flock -w 900 /tmp/rp_measure.lock -c "python -m pytest -q"
    flock -w 900 /tmp/rp_measure.lock -c 'flock -w 900 /tmp/rp_gpu.lock -c "python -m tools.build_cell_assets_r5"'

## 재개 지점
- exec1006: 전체 pytest→manifest/PNG3 생성 실행중. 로그 bench/sa/full_tests.txt, render_log.txt.
- 검증자 M8uaOyvb7UbPP2g7 직접검증 대기. 아직 PASS 아님.
- 미완: 가림 여부 실제 visible segmentation 측정/층화, CAD 기존 자산 upstream 재배포 허가 확인.

## 재착수 — 안착 16건
- 전체 267passed/16failed(90.65s), 실패는 max_speed<0.01만. bottom gap/contact는 통과.
- max_speed는 전역 qvel 절댓값 최대: m/s 및 rad/s가 섞인 값, 이동거리 아님. 부모에 단위 정정 전달.
- 최초500step(모델 timestep 기준) 뒤 고정 종료하므로 곡면 잔류회전 가능성. 진단 전 원본 bench/sa/cell_scene_before.py.txt 보존.
- 임계값 완화/속도 강제0/자유관절 고정 금지. 실제 접촉 마찰 및 정지 연속조건으로 수정 예정.
- 기준 진단 exec1010(8seed), bench/sa/settling_before.json. TEAM_R5에 따라 전체pytest 재실행 금지.

## r2 수정 묶음
- 구형 ball: 기존 condim3는 선마찰만 있고 굴림저항 없음. 설정에 condim6 / sliding0.8 / torsional0.01m / rolling0.002m(고무 대체형상) 명시, XML은 설정에서 읽음. 일반 물체 기존마찰 유지.
- 초기 높이 +2mm, 자유관절 유지. 물리 step으로만 안착.
- 고정500step 종료 → 최소500/최대2000step, qvel<0.003 연속100step 확인. 기존 합격0.01 임계 유지하며 더 엄격한 정지시간 조건 추가.
- diagnostics: max_linear_speed_m_s / max_angular_speed_rad_s / settle_steps / settle_converged 추가.
- 신규 settled 테스트는 기존 조건 모두 유지, 단위별 조건 및 converged 추가.
- exec1011: 자기파일 -k settled 50개, 측정락 대기. 전체pytest 미실행.

## r2 진단 결과 / r3
- r1 before8scene: 실패예6개 모두 ball 각속도0.0840~0.2842rad/s, 선속도 최대0.000331m/s. 원자료 settling_before.json.
- r2 재검증: settled50개 36PASS/14FAIL(25.20s). 기존 gap/contact/0.01 속도 조건은 전부 통과. 추가한 0.003 연속100조건만 실패.
- r2 실패3scene(100003/100007/100042) 모두 mustard의 동일 접촉 limit-cycle 각속도0.00360558rad/s. ball은 ~1e-12rad/s로 정지. 원자료 settling_r2.json.
- r3: 임계는 유지. 원본 mustard 바닥mesh의 비평탄 접촉 떨림을 막기 위해 셀 전용 table에 고무매트 6D 접촉(마찰0.8/비틀림0.01m/굴림0.002m). 원본 mesh·기존장면은 그대로. 자유관절 유지, 속도0강제 없음.
- 목적지2slot 색은 진회색/밝은회색으로 변경, can은 진한 주홍색으로 mustard 노랑과 구분.
- CAD box/cup은 tools/make_samples.py(CadQuery), tools/stp_to_mesh.py 자체 생성 확인(a408c2d). notices 정정, 외부라이선스 불확실 항목 해소.
- 결정론 정의: 같은 source/config/seed에서 plan 및 settled qpos 해시 동일. RGB는 d3d12 readback 미세잡음으로 바이트해시 비교 금지, maxabs<=1 허용(V-SA 동일프로세스3회 23~67pixel/최대1차이 확인).
- 가림 메타 unmeasured 유지. 가림/인식 정확도 주장 금지.

## 재개 지점 (r3)
- exec1016: tests/test_cell_scene_r5.py만64개→진단3scene, measure락. 로그 cell_r3.txt/settling_r3.json.
- 전체pytest는 실행하지 않음. V-SA가 최종1회 담당.
- PNG/scenes.json은 아직 r1 산출물이므로 r3 확인후 tools.build_cell_assets_r5 재생성 필요.

## r3 구현자 확인 완료
- [시뮬GT] 자기파일만 64passed /24.90s, 원자료 bench/sa/cell_r3.txt. 전체pytest 추가실행0.
- 진단3scene(100003/100007/100042): 500step 수렴3/3, 접촉/관통0, gap≤0.0151mm, 선속도≤1.21e-6m/s, 각속도≤3.23e-5rad/s. settling_r3.json.
- exec1018 완료: PNG3 및 scenes.json 새 config/source/asset hash로 재생성. render_r3.txt 세장면 모두500step수렴/접촉관통0.
- notices 정정완료, 가림은 유일한 명시적 미측정 항목.
- 측정시 load: settled시작0.97/1.16/0.92; 다른작업은 측정락으로직렬화, GPU측정G0와동시실행아님. GPU렌더 measure→gpu 이중락.

## 최종 재개 지점
- 구현자 실행중 작업 없음(exec1010/1011/1013/1016/1018 종료).
- V-SA M8uaOyvb7UbPP2g7가 r3 독립검증 및 전체pytest 최종1회 담당. 부모 전달완료. 아직 검증자 PASS아님.
- 추가수정은 V-SA 지적 대응만. 기존장면/공유운영파일 미변경, 커밋0.
