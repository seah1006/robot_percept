# G1 상체 따라하기
시뮬레이션 전용. 로봇 선택에서 Unitree G1을 선택하면 왼쪽 웹캠/스켈레톤, 오른쪽 G1이 표시됩니다. Panda로 돌아가면 G1 worker를 종료합니다. 기존 Panda DOM은 유지합니다.

## 트래커
Windows 환경변수 PYTHONHOME/PYTHONPATH/VIRTUAL_ENV/PIP_PREFIX/PYTHONNOUSERSITE 삭제 후 tools/teleop_tracker_win.py --mode both --url http://127.0.0.1:5091 실행. 사용자 5080 적용/재시작은 부모 담당. 검증은 --video C:\Users\USER\Documents\sam_camera\teleop_round2_async.mp4 --seconds 8 사용. 실제 카메라를 열지 않았습니다.
--mode panda는 기존 한손 TCP 경로, humanoid는 G1만 전송, both는 두 경로. PoseLandmarker Lite + HandLandmarker 2손, 미러 프레임에서 pose 손목과 hand 손목의 최소 거리로 연결. One-Euro로 world pose/양손 필터링. 제어/미리보기는 latest-only 별도 스레드, 스레드별 requests keep-alive. 프리뷰20Hz 제한 제거, 처리 프레임마다 JPEG 전송.

## 매핑
미러 pose LEFT는 robot LEFT. 몸 좌표 x 전방/y 왼쪽/z 위. 허리 ZXY yaw/roll/pitch. 어깨-팔꿈치-손목 방향을 로봇 팔 길이로 정규화. 기본 wrist, 선택 fingertips는 검지/중지 끝 평균 방향. 손바닥 방향 선택은 API /humanoid/options.
MCP는 근위지골의 손바닥 평면 투영과 실제 지골 사이 각도로 굽힘 측정하여 부채꼴 펼침을 배제. Dex3-1 검지에 사람 검지, 중지에 사람 중지/약지/소지 평균. 엄지 MCP/IP와 엄지 끝의 상대 거리로 굽힘/대립. 엄지 빨강/검지 노랑/중지 초록/약지 파랑/소지 보라. 로봇은 3색만 사용. 사람 손바닥 중심은 작은 흰 점.

## 진단과 한계
관절패널 각도/한계 막대/속도, IK 오차/반복/ms/경고 표시. G1 목 관절 없음. 골반 고정, 자기충돌 회피 없음. 손 미감지/입력 .35초 이상은 hold. 관절 속도/가속도 제한은 시뮬레이션 명령 제한이며 실물 안전 보증 아님.
실시간 IK restarts=0, 양팔8회. 팔꿈치 허용오차5mm로 통일. 30fps는 목표이며 실측 미달은 changes 문서에 공개. 합성 스트림은 GT 생성 입력으로 방향/회귀 검증이며 실제 사람 추적 정확도가 아닙니다.

## 11/3 옵션 정정
트래커 기본은 --mode panda이며 이때 Pose를 생성하지 않고 한손만 인식합니다. G1은 명시적으로 --mode humanoid 또는 both를 사용합니다. --infer-width 640(기본)/480/320, --serial(비교용). 손이 있는 녹화본에서는 병렬640 약27.3Hz로30미달. 손목 연결은2x2최소합 전수할당. Pose가 없으면 좌우를 연결할 수 없어 G1 손가락도 hold합니다. 실제카메라가 분리돼 실카메라 검증은 미실시입니다.

## safety_brake 기본 ON 및 전환 판정 (2026-11-05 확정)
- 기본 True, 참조 속도/가속 여유 0.6. OFF는 반응이 빠르지만 실제 한계를 넘을 수 있다. 검증은 합성 세트 기준이며 모든 동작/실물 하드웨어 안전 보장이 아니다.
- ON→OFF는 고정200ms crossfade가 아니라 .75속도/.6가속 캐치업을 사용한다. 참조목표오차<5e-5rad 및참조속도<.01rad/s일때만fast직결로해제하므로전환은200ms보다길수있다.
- OFF→ON 확정 비교기준: 첫40ms의실제가속은동일관절·동일첫500Hz step의OFF유지대조이하,40ms이후실제가속비<=1.0. 전환직후속도초과가있는경우단조감소를확인한다.
- 첫step가속비는t=.3/.6/.9/1.2초전환에서.635/1.255/1.525/1.164로1을넘을수있다. 같은관절OFF대조는4.09/6.42/6.78/7.76,40ms후는.598/.597/.599/.380. 따라서'ON으로바꾸는모든순간절대가속<=1'이라는보장은하지않는다.
- signed가속은OFF음수→ON양수로바뀌므로'동일잔류응답이그대로남았다'고인과단정하지않는다. 40ms는OFF대조비교및후속상한을독립검증해확정한전환판정창이다.
- 원시500Hz자료: bench/humanoid_s_out/20261105T045230Z_matched_summary.json, 같은prefix의control/전환npz9개,manifestSHA256. V-S가저장qdd대신qd를직접2ms차분하고상한표를독립확인해수치재현.
- 부모확정기준으로P1a/P1b독립PASS. P1c충돌회피는별도defaultOFF이며이PASS에포함되지않는다.
## P1c 최종 마감: 기본 OFF 실험 기능 (2026-11-05)

**실사용 권장 아님. 기본 `collision_avoidance=False` 유지.** 최신 critical-release 코드는 침투보다 보수 정지를 우선하지만 holding이 고착될 수 있다. UI 실험 토글은 unchecked이며 clear/avoiding/holding과 경고/진단을 노출한다. `physical_stop_certified=False` 그대로다. 캡슐 proxy는 얼굴·손가락·환경 접촉을 포함한 전체 물리 안전 인증이 아니다.

### 두 후보의 실제 측정
- 방향성 가변 margin+거리 기반 자동 해제: 팔 최대 이동 **30.86°**, elbow **28.90°**로 동결을 벗어났지만, 25초 스윕 실제 최소 **-0.9494mm**, 침투 체크 **34**, 미인증 구간 **77** → 안전 FAIL. 한 unsafe 목표의 제동 +5.97mm 통과를 모든 동적 경로 보장으로 확대할 수 없다.
- 최종 critical-release(운영 코드에 유지): release는 현재 최소 clearance+2mm 이내 임박 쌍의 목표 방향이 비악화이며 적어도 하나를 개선할 때만 허용. 정착 후 pose/hand 변화 때 최대 5Hz probe, 재개 후 0.4초 command 접근속도 필터. 25초 스윕 실제 최소 **+12.1850mm**, 침투 **0**, 미인증 구간 **0**, 그러나 팔 최대 **4.33°**만 움직인 뒤 holding 고착 → 기능 FAIL. 샘플의 0 침투는 보편 인증이 아니며, command 필터는 실제 Cartesian 가속 상한 인증이 아니다.
- 최종 ON 렌더: **32.0208fps / 30.0118초**, 서보 tick p95 상태 최대 **15.24ms**, max gap **93.18ms**. 성능 목표는 해당 창 통과하지만 정지 고착으로 실용 기능 통과를 뜻하지 않는다.
- 동일 슬롯 대조: OFF **26.8760fps / max gap 4.871초**, ON **32.0109fps / max gap 66.49ms**. 긴 frame gap은 충돌 ON에만 고유하지 않으며, 환경/렌더/HTTP 원인 구분은 미완료다. 실패 창을 잘라내어 통과로 보고하지 않았다.

### V-S 독립 검증과 남은 문제
- 방향성 snapshot 정적 12자세: 방향 max **65.3°/42.0°**, 평균 **20.0°**, 손목 최대 **284.6mm** → FAIL. chest 3초→abd45는 **0.63초** 내 8° 도달, 최종 **1.3°**로 복귀만 PASS.
- 얇은 clearance 목표(rest 7.5mm, el90 13.7mm, cross_chest 4.9mm)의 보수 정지와 별개로, 충분히 안전한 OFF 끝점 fwd45 **45.3mm**, fwd90 **79.3mm**, fwd60_el100 **62.4mm**, up120 **73.7mm**도 순차 시험에서 추종 실패. 끝점의 정적 margin과 이전 자세로부터의 경로 의존성을 분리해야 한다. 이 결과는 방향성 snapshot이며 최종 critical-release의 독립 통과를 의미하지 않는다.
- P1a/P1b 보존 범위: **기본 OFF에서는 기존 IK/안전 제동 경로 유지**. IK 수학은 바꾸지 않았고 FK 계측만 추가했다. ON은 회피 목적상 목표를 수정/정지하므로 P1a 추종 무영향을 주장할 수 없다. C2 reference p/v/a나 실제 q/qd를 강제 reset/clip하지 않으며, 실측 가속 상한은 검증한 입력/상태에 한정한다.

### 후속 과제 (이번 작업에서는 추가 튜닝 중단)
1. 정적 각 자세를 매번 rest 시드로 독립 실행하여 정적 geometry와 순차 경로/히스토리 문제를 분리.
2. release 방향 조건과 안전 계획 경로를 함께 재설계. 감소 중인 clearance, reference a/jerk, 물리 추종 지연·법선 변화와 재가속을 예측해 작은 clearance에서 재진입을 막을 것.
3. 단일 목표 투영과 단순 직선상 부분 접근은 전역 최적 경로가 아니다. 안전한 중간 waypoint/kinodynamic trajectory와 사용자 의도 최대 접근이 필요.
4. MJPEG 도착·raw HTTP status·worker render/GIL/heartbeat·generator seq trace를 같은 창에 보존하여 cold start/스케줄링/렌더/전송을 분리. 측정은 기존 measure→GPU 잠금 규칙을 지킬 것.
5. 정적/복귀/4패턴 무침투·실제 팔 움직임·30fps를 모두 독립 통과하기 전 기본 ON 금지.

최종 소스 blob: env `0cd1b0bad7cd31d5d4fdad03d5975ff6683a51d8`, teleop `893eb6c6a7d62195bf20c83f2f28d40f45d1c950`, IK `fcd3fb9eaa8ba76046fee8a01587e7986df117bb`, collision `996ebffd534cf55f251087d8e3b44ce505b8024c`. 커밋 없음. 5080 미접촉. 자체 5093 listener 없음 확인.
### V-S 최종 독립 마감 확인
최종 critical-release env0cd1b0ba/teleop893eb6c6의 순차 정적12자세 방향 max **75.6°/117.1°**, 평균 **35.4°** → FAIL. chest→abd45는 **0.63초** 내8°, 최종 **1.3°**로복귀만PASS. 직전 all-near-pair 후보는 max83.3°/117.1°,평균45.2°였고,각자세를rest시드로분리해도max77.4°/42.0°,평균15.7°여서히스토리외정적/제동과잉보수도남는다. **P1a PASS / P1b PASS(40ms 전환기준) / P1c FAIL·기본OFF실험**으로독립판정종료. 추가P1c튜닝/4패턴측정없음.

마감 전체pytest초회는67PASS/기존test_env1FAIL(누락`rtree`의존성)이었다. 소스/test를숨기거나skip하지않고,PyPI rtree1.4.1공식Linux wheel을SHA-256 `12de4578f1b3381a93a655846900be4e3d5f4cd5e306b8b00aa77c1121dc7e8c`검증후`pip --no-index --no-deps`로프로젝트conda환경에만설치해전체재실행. 이환경보완은P1c알고리즘변경이아니다.

**최종 전체 회귀: python -m pytest -q → 68 PASS, 5 warnings, 40.07초 (exit 0).** 누락 rtree1.4.1 의존성 보완 후 전체 통과. 소스/테스트 skip 없음. P1c기본OFF동결·한계문서완료·V-S마감통보완료. 5093 listener없음,5080미접촉,commit없음.

### 마감 후 W 렌더 gap 원인 분리 및 하네스 수정
W watchdog 보고: OFF clientgap4999ms/serverpublish4997.538ms 중idle_before4906.694ms,실render87.692ms/JPEG2.755ms/shm.028ms. 해당monotonic4997.538ms동안REALTIME(time.time)은109.719ms만진행해약4.888초역행. Conda3.12 Event.wait의sem_timedwait realtime timeout이렌더/송신을동시에연장한사례로파악했다(GPU/충돌코드고유아님). 이는W의rawwatchdog진단이며S가원시로그를재분석한주장은아니다.
S는운영IK/충돌코드를동결한채bench/humanoid_s_render.py의stream/poll stop.wait만monotonic deadline+time.sleep≤10ms슬라이스+stop.is_set취소검사로교체했다. 모의REALTIME -4.9초역행에서도100ms monotonic deadline완료/사전취소즉시반환/stop.wait제거검사PASS,py_compilePASS. 실제프로세스종료proc.wait는정상유지. 기존1065/1069FPS는구wait하네스이므로이문제에오염가능성이있는측정으로보존하며수정후실측통과를주장하지않는다. 추가벤치측정없음. 다음승인된재현은rawHTTP JSONL/도착trace와Wwatchdog를함께분석할것.