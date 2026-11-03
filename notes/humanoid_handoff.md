# Humanoid (Unitree G1) 따라하기: 인계 노트 (I-R → Codex 구현자)
상태: py_compile OK. 서버/브라우저로 끝까지 실행해 본 적 없음, V-R 검증 전, 커밋 안 함. Panda 파일(sim/teleop.py, ik.py, env.py, scene_builder.py)은 수정하지 않음.

## 1. 파일과 상태
- sim/humanoid_env.py (완성, 단독 테스트함) HumanoidEnv: menagerie unitree_g1/g1_with_hands.xml, freejoint 제거(골반 고정), URDF effort를 forcerange로 적용, 접촉 끔, 중력 보상, lab 씬, front/side 카메라, 사이트(*_elbow_site, *_wrist_site, *_palm_site, *_{thumb,index,middle}_tip), mocap 목표 구(group 1, 기본 숨김).
- tools/g1_lowpoly.py + assets/g1_lowpoly/ (완성) open3d로 메쉬 단순화, 630k→112k 삼각형. 없으면 원본 메쉬로 대체.
- sim/humanoid_ik.py (완성, 벤치함) ArmIK: 팔마다 가중 DLS. 손목(또는 손끝 평균) 위치, 손 방향, 팔꿈치 위치를 목표로 쓰고 Chan-Dubey 관절 한계 가중, 조작성 기반 감쇠, 정확한 영공간 자세 항을 넣음.
- sim/humanoid_retarget.py (완성, 실행 검증 안 함) torso_frame, zxy_angles, arm_directions, palm_frame, finger_angles, robot_finger_targets. 순수 numpy.
- sim/humanoid_teleop.py (작성됨, 실행 검증 안 함) HumanoidServo.tick(sample, ctrl, now_wall) 50Hz: retarget → IK(8 iter, warm start) → 속도/가속 제한 → set_targets. joint_groups()와 overlay()가 상태 JSON을 만듦.
- web/shm_channel.py (완성) Blob: seqlock 공유메모리. write(bytes) / read(last_seq) 반환값은 (seq, bytes|None).
- web/humanoid_worker.py (작성됨, 실행 검증 안 함) run_humanoid_worker(names{in,status,frame}, cfg). 물리 500Hz, 서보, 30fps 렌더, JPEG를 frame blob에 씀, status JSON 15Hz.
- web/humanoid.py (작성됨, 실행 검증 안 함) Blueprint와 HumanoidRuntime(spawn 프로세스, 모드 켤 때만 기동).
- web/app.py (수정) create_app에서 humanoid blueprint 등록 2줄. import만 하고 워커는 띄우지 않음.
- tools/humanoid_synth.py (작성됨, 실행 검증 안 함) 합성 pose와 손 랜드마크, 정답(gt) JSONL. --url로 30Hz 스트리밍.
- bench/humanoid_ik_bench.py (완성).
- 미착수: UI(web/static/humanoid.js/css, teleop.js 토글), 트래커(tools/teleop_tracker_win.py의 PoseLandmarker, 양손, 30fps 미리보기), tests/test_humanoid.py, notes/humanoid_teleop.md.

## 2. 인터페이스
- HumanoidEnv(width=640, height=480, shadows=False, cam='front', lowpoly=True). 주요 멤버: .groups{left_arm,right_arm,waist,left_hand,right_hand}, q/qd/tau(names), set_targets({joint:rad}), step(n), render(), camera_K(), T_world_cam(), set_mocap(name, pos|None), reset().
- ArmIK(model, side, rest=q7).solve(qpos_full, q0, p_target, R_target=None, elbow_target=None, mode='wrist'|'fingertips', iters=12, pos_tol=.002, rot_tol=2°, restarts=0, seed=0) → (q7, diag{iters, pos_err_mm, rot_err_deg, elbow_err_mm, manip, time_ms, warnings[]}). 실시간 경로는 restarts=0.
- 미러 규약: 트래커는 cv2.flip한 프레임에서 MediaPipe world 랜드마크를 냄(x 오른쪽, y 아래, z 멀어짐, m). pose LEFT는 사용자의 실제 오른손이고 로봇 LEFT로 감. 몸 프레임은 x 전방, y 왼쪽, z 위 (B_CAM 참조).
- POST /humanoid/update {detected, sent_at, pose:33×[x,y,z,vis], hands:{left|right: 21×[x,y,z] (pose 쪽 기준 키)}, pose2d:33×[u,v], hands2d:{..21×[u,v]}} 400/413 검증.
- POST /humanoid/mode {enabled}, /humanoid/calibrate, /humanoid/options {arm_target wrist|fingertips, hand_orientation, torso, fingers, elbow, targets3d}, /humanoid/reset.
- GET /humanoid/status: state, fps, tick_hz, rtf, render_ms, jpeg_ms, tick_ms_p50/p95, tracking, ik{left,right}, groups[], overlay{joints[uv,axis_uv], tips[color], targets}, input_hz, latency_ms, human2d. GET /humanoid/video (MJPEG), /humanoid/frame.jpg.
- 손가락 매핑: index_0←MCP, index_1←0.6(PIP+DIP), middle←중지·약지·소지 평균, thumb_1←MCP, thumb_2←0.8(IP+MCP/2), thumb_0←엄지 끝이 검지/중지 중 어디에 가까운지 × 오므림 정도. 부호: 왼손 손가락은 음수, 오른손은 양수, thumb_1/2는 반대 (FK로 확인). 색: 엄지 #ff6b6b, 검지 #ffcc40, 중지 #4dd973. 사람 약지/소지는 로봇 중지 색 계열로 표시할 계획.
- 팔 목표 기본값은 wrist. 이유: 손목은 pose와 hand 양쪽에 다 있어 가장 안정적이고, 손끝을 쓰면 손가락 굽힘 노이즈가 팔 위치로 섞임.

## 3. 남은 작업
1) 서버 기동 후 worker 실행 확인(디버그), 합성 스트림으로 방향/부호 검증: 허리 축 부호, 손바닥 방향, 미러 좌우. 2) finger_angles의 MCP 굽힘을 손바닥 평면 투영 방식으로 바꾸기 (현재 방식은 검지/소지의 부채꼴 각도가 굽힘으로 잡힘, 아래 5번 참조). 3) UI: 비교 레이아웃의 Panda/휴머노이드 토글, 관절 패널, SVG 오버레이(관절 라벨/축, 손끝 색 점, 웹캠 손끝 5색 점). 4) 트래커: PoseLandmarker와 Hand 2개, 손목 거리로 pose 쪽에 연결, One-Euro, 30Hz, keep-alive 미리보기 30fps. 5) tests와 notes. 6) V-R 검증 루프(검증자 bjV8VIbGpDQP1I8C, 포트 5091/5092).

## 4. 재현과 측정 (load avg ~13 공유 환경)
- env: `source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept; cd /home/user/work/robot_percept; source sim_test/gl_env.sh; export PYTHONPATH=$PWD`
- `python bench/humanoid_ik_bench.py --n 200`: 6D 콜드스타트(재시작 8회) 성공률 L 98% / R 98.5%, 중앙값 3.3/3.6 ms, p95 ~60 ms(재시작 때문). 위치+팔꿈치 51-55% (팔꿈치 허용 5mm인데 solver는 10mm에서 멈춤, 맞춰야 함). 경로 400샘플 warm start: 오차 중앙값 0.07mm, 0.27 ms, 최대 관절 점프 0.057 rad.
- 렌더(640x480, 렌더만): 원본 메쉬 + 반투명 목표 구 약 50 ms → lowpoly + 불투명 약 19 ms → 목표 구 그룹 숨기면 약 12 ms. 평면 바닥 격자/스카이박스 영향은 작음. Panda RGB 렌더는 같은 조건에서 약 28 ms. mj_step 약 100-130 µs (접촉 끔).
- `python tools/humanoid_synth.py --out /tmp/s.jsonl` 또는 `--url http://127.0.0.1:5091 --loop`

## 5. 알려진 문제
- G1에는 목 관절이 없어 머리 방향은 표현 불가(status.head에 안내 문구).
- URDF velocity(20-37 rad/s)는 모터 측 값이라 서보는 TELEOP_VEL(팔 3, 손목 4, 허리 1.2, 손 3 rad/s)과 TELEOP_ACC를 사용.
- 접촉을 꺼서 팔과 몸통이 서로 통과할 수 있음(자기충돌 회피 없음).
- 30fps 목표: 렌더+JPEG 약 17-25 ms라 가능해 보이지만, 같은 GPU에서 Panda 워커와 경합하는지 측정 안 함.
- Python 3.12 shared_memory resource_tracker 경고가 날 수 있음(sim_worker와 같은 방식).


## I-R2 중단 인계 (2026-11-02, 사용자 오늘 작업 종료)
- 커밋 없음. 사용자 5080/실제 카메라 미접촉. 5091만 사용.
- 추가 변경: sim/humanoid_retarget.py MCP를 손바닥 평면 투영과 근위지골 사이 각도로 변경(펼침 배제); sim/humanoid_ik.py elbow 조기종료/최종 판정5mm 통일.
- 신규 web/static/humanoid.js/css: Panda/G1 선택, G1 비교 화면(웹캠 왼쪽/로봇 오른쪽), 몸·손끝 오버레이, 로봇 관절 이름/축/3색 팁, 관절 각도/한계 meter/속도/IK JSON. index.html script 한 줄 추가. 기존 Panda DOM 보존. 브라우저 실검증 아직 안 함.
- tools/teleop_tracker_win.py: --mode panda|humanoid|both (현재 기본 both), PoseLite + Hand2, pose 손목 거리 greedy 연결, world OneEuro, 양손5색팁/작은 중심, 프레임마다 preview(20Hz cap 제거), 스레드별 requests keep-alive. Documents/sam_camera 복사본 동기화 완료. 부모만 5080에 적용/재시작.
- 주의: 기본 both는 Panda-only 사용 시 추가 Pose 비용이 있어 다음 세션에서 기본 panda 또는 UI 모드 연동을 검토해야 함. 양손 연결은 최단후 greedy이며 전역 최적 assignment 아님. 미러/허리/손바닥 FK 방향 실제 검증 미완료. thumbs MCP 해석도 추가 검증 필요.
- 신규 tests/test_humanoid.py(평면MCP, torso축부호, API검증) 작성만 완료, 실행 전 중단. notes/humanoid_teleop.md 작성. notes/humanoid_changes.md 미작성.
- 마지막 확인: py_compile 신규 tracker와 humanoid 전체 성공(초기 버전), 이후 replay 잘못 치환 수정했고 녹화본 실제 실행 성공. smoke tests/test_smoke.py 2 PASS 8.36s.
- worker 실기동 ready 확인. idle sample: robot26.9fps, render18.4ms, JPEG4.8ms, servo49.9Hz, RTF1.003. hold tick p50 .51/p95 1.47ms는 IK 성능 아님. 합성 송신720/23.98초=30.03Hz errors0. 합성 중 IK/robot fps 캡처 미완료.
- Windows 녹화본 --mode humanoid --url http://127.0.0.1:5091 --video .../teleop_round2_async.mp4 --seconds8: 87updates/9.05s=9.62Hz, errors0, inference p50 76.49 / p95 123.96ms, hand p50 44.79ms + pose p50 31.07ms. 30Hz 미달. preview 수신fps 미측정. 손가락 굽힘 일치도 미측정.
- V-R bjV8VIbGpDQP1I8C에 변경/측정 및 중단 통보. PASS 전, 검증 루프 미완료.
- 정리: /humanoid/mode enabled=false로 worker 종료 확인. ss에서5091 소유PID3664만 kill, 종료 후5091 listener 없음. 합성 종료됨. Windows 녹화본 결과 출력 후 interrupt 요청(카메라 미사용).
- 다음 시작: git diff/현재 파일 확인 → 신규 pytest →5091 재기동+합성 중 IK/fps 정량 수집 → 브라우저 UI 검증 → 추론 병목 병렬화/해상도/모델 옵션 검토(30Hz 미달 공개 유지) → 미러/손바닥/허리/손가락 정량검증 → V-R 재요청 → changes 문서. 실물 안전/성공을 주장하지 않음.

## I-R2 11/3 라운드 인계
- notes/humanoid_changes.md에 최신 변경/측정/미완료 모두 기록. V-R2는 iPmCUS5bJdhobqpn으로 변경.
- 병렬640 채택: 같은 프레임 Pose차이0px/손검출 회귀없음. round2 첫45프레임39.30Hz이나 hand1/45. 손양성 final_hand89프레임에서는16.515→27.322Hz(62/89동일검출),30Hz 아직미달. 480/320 축소는 성능/좌표 악화라미채택.
- worker 누적deadline+JPEG별도singlefuture+새관측만IK. 10sGT보조합성 시29.4~30.7fps(목표30),tickp95최대13.93ms. 이후목표기본32와ik_ms_p50/p95(양팔solve합)추가, 독립재측정대기. JPEG 게시 수가fps임.
- 부모PID변화시worker종료+orphanunlink, Blob unlink분리, reset calibration표식유지. tracker기본panda/1hand, G1만Pose+2hands/병렬/손목최소합할당,카메라없음명확메시지,5색팁. 5080복사본 최신배포는안함(PASS후부모담당).
- 5pytest PASS(최종실행중),browser openTab도구모드오류로UI검증V-R2담당. 검증자초기코드26.19fps FAIL/IKp95 7.75ms PASS/관절한계0/좌우미러PASS/허리GT상관.976~.986/손가락GT보조상관.99+. 단왼팔GT90도에-72.1로18도부족미해결. 새worker재측정요청함.
- 다음: V-R2최신worker32fps실측회신→왼팔18도부족조사→UI증거→손양성30Hz용LIVE_STREAM/ROI/프로세스후보실험(아직안함)→GT오차추가검증→PASS루프. 현재커밋없음. 실제카메라분리로실검증미실시. 5091은라운드마감정리중,5092는검증자소유.

## I-R2 R4 인계 (11/3 09:28경)
- 신규 bench/humanoid_tracker_candidates.py: final_hand동일89frames serial/thread/process/hand480/320/ROI/tracking.3 비교. 상세표changes문서. threads37.03Hz/process33.51Hz 검출62/89·손delta0,현재thread유지. ROI는IMAGE/fullVIDEO분리후검출62유지하지만89회fallback으로13.8Hz기각. 320검출52기각. 480검출63이나29.93Hz·delta4.62px로미채택.
- 실HTTP체크에서tracker가HTTP400을성공으로세던버그발견→raise_for_status/초기3회응답오류출력. 400원인은MediaPipe몸이안보이는발2d가|uv|>3. preview_coords()로표시좌표만[-2,2]제한,world3d불변. 수정후303/15초실수신/errors0,처리20.469Hz(p50/p9541.97/56.78ms)로아직30미달. 이전errors0만의전송성공주장정정.
- --loop-video추가,종료pending전송drain/처리구간Hz(정리시간제외)추가. 양손스켈레톤선+5색팁/작은중심점. 최신tracker는Documents복사본미배포(부모PASS후담당).
- 신규 bench/humanoid_fk_probe.py는GT보조 warm0..7s FK진단. L실upperflex79.08/GT90,u1error11.32도 R167.75/GT165,u1error17.22도. 두팔다실방향잔차가있음. elbowweight1로u1오차5.07/4.60도로줄지만손목오차13.94/23.23mm로악화. 단일pitch비교는오해여지가있으나잔차자체를무시하면안됨. 기존가중치유지,elbow>10mm경고추가. V-R2교차판정대기.
- tests/test_humanoid.py에FK좌우대칭4pose및offscreen2dAPI회귀추가. 최신7testsPASS16.39s,load10.33/6.80/3.86. 마지막양손선추가후문법검사정리예정.
- preview증거 C:/Users/USER/.aside/u/0/sessions/2026-11-02_1NIgF2z2BvfBSkOh/tmp/humanoid_preview_r4.jpg 확보(녹화본사진+몸/손선/손끝점). browser자체는여전히도구모드오류라V-R2브라우저확인요청.
- V-R2로반복메시지보냈으나이번라운드응답없음,현재message_agent list에해당id가없어부모에연결확인요청. FPS923프레임/27.56분모합의/최종PASS미완료. 5091은정리중,5080/실카메라미접촉,커밋없음.
- 다음: 검증자연결복구→동일부하조건실HTTP30Hz추적병목(전처리/오버레이/JPEG/전송분리)→영상480/quality70+정확한FPS분모검증→FK잔차목표우선순위합의→UI웹캠최종증거→PASS. 순수벤치37Hz를실전30Hz로보고하지말것.

## R6 최신 재개 표지
상세는 notes/humanoid_changes.md R6. Panda pause/resume frame245정지→253복귀 및GT보조pick/place실기동PASS. V-R2 로봇31.66fps독립PASS중간회신. 내5091PID42705종료,V-R2약6분독점tracker/UI측정종료대기. 그동안파일준비만: --pipeline(기본OFF)옵션구현/py_compile PASS,6단계stages_ms계측,bench/humanoid_pipeline_bench.py baseline/pipeline/parity(아직미실행),rp_humanoid_ shm prefix 및회귀추가(전체9tests예상미실행). V-R2 '측정 종료'전CPU/GPU벤치실행금지. Documents복사본미배포,repo경로직접사용.

## R7 재개 표지 (09:59)
전체상세changes R7. pipeline純46.60Hz/hand62/89·delta/jitter불변채택,parity41/89기각. G1/both pipeline기본ON,PandaOFF/--no-pipeline가능. WindowsGetTickCount64해상도15.625ms확인→QPC로페이싱교체,비디오sourceFIFO2 선행처리. 최종실송신/preview898/30.007=29.926Hz/source901대비99.667%·3미처리slots/drop0,serverinputp50 28.65로아직FAIL. robotp50 31.9. 同89frameclock비교손delta/jitter불변이나pose운동포함2차차분proxy+.043px(0.33%)공개,모든posejitter불변으로주장금지. 최신11pytestPASS5.77s. 내5091PID985/모든Windows벤치정상종료후V-R2최종검증요청(현재미달예상수치포함)전달. Documents미동기화,repo직접사용. 다음은V-R2회신및MediaPipe CPUthreads/추론32ms꼬리·입력中央値28.65개선. 5080부모관리/카메라미사용/커밋없음.

## 최종 PASS 알림
V-R2 R7 독립재측정(45초2회)부모확정기준PASS:송신29.99Hz/처리99.93%/drop0,서버1350/45=30.0Hz,preview1349~1350,robot31.8/31.98fps,IKp952.0ms/한계0. cold-start maxgap1735ms 1회잔여(2회차73ms),ready/첫frame후video연결권장. 상세changes최종항목. 5091/5092/내tracker종료,Documents미배포/부모지시대기,커밋없음.
