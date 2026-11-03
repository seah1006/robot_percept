# V-R 검증 노트 (pair R) - 기준선 측정 (구현 전달 전)
공식 한계 출처: https://frankarobotics.github.io/docs/robot_specifications.html (FER 표), 데이터시트(Hand: 80mm, 50mm/s/손가락, 연속70N/최대140N, 페이로드 3kg).
FER: q_max=[2.8973,1.7628,2.8973,-0.0698,2.8973,3.7525,2.8973], q_min=[-2.8973,-1.7628,-2.8973,-3.0718,-2.8973,-0.0175,-2.8973], dq_max=[2.175x4,2.61x3], ddq_max=[15,7.5,10,12.5,15,20,20], tau=[87x4,12x3].
기준선(git tag baseline-1102) 측정 (bench/verify_r/limits_check.py, ik_bench.py):
- joint range/ctrlrange/forcerange(87/12Nm) 이미 공식값과 일치.
- 속도 상한 모델 내 없음: open-loop 스텝 응답 peak qvel = 12.8,2.3,12.9,4.5,10.3,9.2,11.4 rad/s (한계 2.175/2.61).
- 그리퍼 닫힘 최대 259 mm/s/손가락 (공식 50), actuator8 forcerange +-100 (공식 70/140N 아님), 손가락 range 0..0.04.
- 총질량 팔+손 17.45kg (FER 약 17.8kg 팔 + 손 0.73), hand 0.73kg OK.
- DLS IK 200개 무작위 도달가능 6DoF: 성공 100%, pos 중앙 0.3mm, rot 중앙 0.01deg, 시간 중앙 8~20ms, p95 16~296ms, max 750ms. 원형경로(자세 스윕) 400점: 실패 45, 최대 dq/step 0.56rad, 6스텝 dq>0.2.
구현 후 재측정 대기. 재현: python bench/verify_r/ik_bench.py sim.ik 200 / baseline_ik 200

## 범위 변경: 휴머노이드(Unitree G1) 검증 기준 (구현 전달 대기)
공식 출처: https://support.unitree.com/home/en/G1_developer (관절 번호/한계 표), https://www.unitree.com/g1
- 팔 5DoF(어깨3+팔꿈치2; 손목 2 선택), 허리 1DoF(Z +-155deg; EDU 허리 X +-30~45, Y +-30), 손목 P/Y +-92.5deg, 손목roll +-1.972rad, 손목 pitch/yaw +-1.6144rad, R_SHOULDER_PITCH -3.0892~2.6704, 팔 최대하중 약2kg(EDU 3kg), 관절 최대토크 120Nm(무릎), Dex3-1 손 7DoF, 키 1320mm, 팔폭 0.45m.
- Panda 기준선 측정은 위 섹션 그대로 보관.

## V-R2 라운드1~2 (2026-11-03, 포트 5092, 합성/녹화본, 실카메라 미실시: 카메라 분리)
도구: bench/verify_r/hum_measure.py(HTTP만), panda_fps.py, run_meas.sh. 합성 GT(tools/humanoid_synth)는 보조.
| 항목 | 기준 | R2 측정(부하 3.9~6.7) | 판정 |
| 로봇 MJPEG | >=30fps | 26.19(1차), 27.56(2차, 실측구간 33.5s/923프레임; status p50 29.9/p95 33.0); 합성스트림 없을 때(트래커 무) 32.04 | FAIL(입력부하시) |
| 입력 갱신 | >=30Hz | 합성 30.0Hz PASS; 녹화본 Windows 트래커 13.9Hz(89프레임 6.41s, 추론 p50 58/p95 76ms), 20.5Hz(I-R2 loop) | FAIL |
| 웹캠 미리보기 | >=30fps | 서버 릴레이 30.02fps(합성JPEG 30Hz 송신), 트래커 실미리보기는 입력과 같은 Hz라 위와 동일 | 릴레이 PASS/트래커 FAIL |
| IK p95 | <=33ms | 서보tick p95 p50 17.3/p95 22.7/max 23.1ms, IK time p50 1.0/p95 8.5/max 17.6ms | PASS |
| 관절한계 | 위반0 | 0/303샘플 | PASS |
| 좌우 미러 | 대칭 | abd85: roll +80.1/-80.1, yaw +33.4/-33.4, pitch/elbow 동일 | PASS |
| 허리 GT 상관 | + | yaw .996 roll .99 pitch .985 | PASS |
| 손가락 GT 상관(보조) | + | index/middle/thumb 좌우 r=.986~.994, lag .15-.2s | PASS(합성 한정) |
| 왼팔 굽힘 | GT 90 | shoulder_pitch -72.1(오른 165->-168.3). I-R2 FK: u1 오차 L11/R17도, elbow weight 1로 감소 | 가중치 타협, 문서화 필요 |
| Panda 회귀 | 기준선 이상 | 같은 부하에서 baseline-1102 13.6/15.5fps(load5-6) vs 현재 16.5/24.3(load 7); 현재 29.1(load 3.8) | 회귀 없음(부하 의존, 측정 잡음 큼) |
UI 실확인(5092 openTab): Panda/G1 토글, 비교화면, 웹캠 5색 손끝 점+몸 스켈레톤, 로봇 손끝 3색 마커, 관절 패널, G1->Panda 복귀 OK. 지적: Panda 선택 시 'G1 기준 자세/G1 리셋/팔 목표' 툴바 계속 표시, 비교화면 웹캠 패널 하단 여백, 트래커 pose2d 400(발 invisible |uv|>3, I-R2 수정), 사람 SVG viewBox 640x360 하드코딩.

## V-R2 라운드3 (최신 worker, 별도 GL 스레드)
- 정확히 30.0s 창, 합성 30Hz 입력, load 6.8->8.0(5080 실사용 포함): robot MJPEG 27.67fps(881프레임, max_gap 146ms), status fps p50 29.8/p95 32.0, render p50 24.2/p95 47.9, input_hz 30.0, 서보 tick p95 17.7ms, IK p95 7.7ms, 한계 위반 0, 미러/허리/손가락 상관 유지(.99). 첫 시도(load 5.3->9.1, I-R2 벤치 동시) 13.1fps 오염.
- I-R2 자체 30.19fps(load 2.6->3.7)는 재현 못 함(부하 차). 판정: 부하 <4 조건 미충족, 30fps FAIL(조건부).

## V-R2 라운드4 (5080 정지, 단일 서버, 부하 1.5~3.3)
- 합성 30Hz 입력만: robot MJPEG 31.66fps(30.0s창 992프레임, max_gap 98.7ms), 입력 30.0Hz, 서보tick p95 22.5ms, IK p95 5.1ms, render p50 13.1/p95 20.6.
- Windows 트래커(최신 repo, 녹화본 loop) 단독: 트래커 자체 28.6~29.0Hz(1716/60s, 1304/45s), 서버 수신 약 26~30/s, input_hz p50 26.4/p95 29.8/max 30.7 -> 30Hz 미달(FAIL). 미리보기 송신 29.0Hz(FAIL 근소). 동시 로봇 fps 31.92(1010프레임/30s), IK p95 2.05ms, 한계 위반 0.
- 주의: 중간 측정 3회는 run_meas.sh가 --no-stream 없이 내 합성 스트림을 같이 보내 input 57Hz/preview 54fps로 오염(무효). 트래커 이중 실행도 겹침. 유효값은 위 단독 측정과 서버 로그 초당 카운트(30/s).
- UI 3건 수정 확인: Panda에서 G1 컨트롤 숨김, G1->Panda 복귀 시 Panda 29.4FPS 재개. Panda 회귀 없음(저부하 29.4 vs 이전 29.1).

## V-R2 라운드5 (R7 묶음: QPC+source FIFO+pipeline 기본ON, 5080 정지, load 1.3~1.8, 실카메라 미실시: 카메라 분리)
- 트래커 단독(녹화본 loop) 2회 x 45s: 송신 1350/45.0s=29.99Hz, 처리/입력 99.93%(1350/1351), 드롭 0, 오류 0, preview 송신 1349~1350. 서버 로그 수신 1350/45s=30.0Hz, preview 1349~1350. 30s 슬라이딩 창 수신(초 단위 로그) run1 min 29.27/mean 29.73/max 29.93Hz, run2 min 29.33/mean 29.92/max 30.13Hz. 순간 input_hz 중앙값 28.8/28.4(참고, 도착 jitter), 초당 최소 23/최대 60(버스트). 도착간격 p95는 미측정.
- 로봇 MJPEG(트래커 동시): run1 954프레임/30s=31.8fps(단, 첫 구간 max_gap 1735ms 1회, cold start 추정), run2 1010프레임 31.98fps max_gap 73ms. status fps p50 31.9~32.0 p95 33.0. render p50 16/p95 21~23ms. IK p95 2.0ms, 서보tick p95 6.2ms, 한계 위반 0.
- 트래커 단계: neural p50 31.5/p95 40(38), preprocess .6, retarget .5, overlay 1.0ms. 판정(부모 기준: 처리비 >=99%, 개수기반 수신 >=29.7Hz, 미리보기 >=29.7): PASS(창 min은 29.3로 근소 미달, 45s 전체 및 mean은 통과).
