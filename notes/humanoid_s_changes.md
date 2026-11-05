# I-S R2 작업 기록 (2026-11-03, 1차 10분 작업)

## 상태
- P1a A1: FAIL, 원인분해 완료 아님. 온라인 IK 반복/가중치 변경 없음.
- P1b A7: 부분 구현, 독립 검증 요청 중. 정량 회전점프/실제 q/FPS gate 미측정, PASS 아님.
- P1c A2: [blocked] A1 미완료 및 실행시간 제한. 충돌회피 미구현. 기존 contact OFF 유지.
- 커밋 없음, 5080/카메라/다른 포트 접촉 없음, 5093 서버도 미실행.

## A1 진단 (GT 보조)
- 신규 bench/humanoid_s_diagnose.py: tools.humanoid_synth의 11시점, 양팔 정적 settle, 8/16/32 iterations와 가중치 sweep. 각 표본은 초기 solve+8 warm solve, 실제 온라인 동적 추종 지표가 아님.
- 기존 길이 정규화는 L1*u1, L2*u2 세그먼트별로 이미 존재함. rest shoulder_roll_link 좌표 고정 S가 pitch 시 이동할 수 있어 신규 geometry 벤치로 원인 분리 예정.
- 결과 열은 [상완방향 deg, 전완방향 deg, wrist mm, 개별 solve ms].
- 기본8회 w_rot=.25/w_elbow=.35 max=[17.331,20.422,6.95,4.999], p95=[17.031,19.996,6.898,4.0].
- 기본16회 max=[17.244,20.363,6.91,14.945], 기본32회 max=[17.208,20.338,6.9,34.65]. 반복 증가만으로 해결 안 됨.
- 8회 w_rot=.1/w_elbow=1.0 max=[6.843,6.861,24.12,7.967]. 방향 개선과 wrist 악화가 동시에 나타나 단순 가중치 변경 기각.
- 측정 lock 사용, 시작 load=6.21/3.37/2.57, GPU2%,6837MiB. 공유 부하 높음, 정식 성능 PASS 근거 아님.
- 최초 sweep은 iters wrapper가 첫 solve만 적용되는 오류 있었음. 수정 후 위 수치로 대체함. 기본8회 결과 동일.
- 신규 bench/humanoid_s_geometry.py: shoulder 실제 이동/관절 한계 margin/robot-FK reachable GT 비교. 실행 결과 /tmp/humanoid_s_geometry.json (락 대기일 수 있음).
- 스윙/팔 평면 잔차 및 계층 IK는 아직 실험하지 않음. 좌우 오차차 gate/robot FK 방향 gate 아직 미집계.

## A7 변경
1. sim/humanoid_retarget.py
   - 동일 어깨/비정상 좌표 torso는 B_CAM+hips false. 공선 up은 수치적으로 직교한 축 선택.
   - palm_frame은 zero/공선/비유한/shape불량에서 None. 유효 hand만 finger mapping.
2. sim/humanoid_teleop.py
   - reset_state는 B0와 calib_seen 함께 보존(보정 행렬만 초기화되던 버그 제거).
   - 손 유실 시 마지막 torso-local 회전 목표 유지하여 회전 task on/off 제거. 재등장 회전 블렌드는 아직 없음.
   - quality.hands state=held/missing은 새 손 타깃으로 사용하지 않음. I-K와 필드 합의.
   - 손가락 미검출/옵션off는 des=cmd 감속 hold. 자동 중립 복귀 없음.
   - 팔 저visibility/zero-length는 des=cmd, q_ik=cmd로 warm start 재동기화. 현재 vel는 기존 가속제한으로 감속하므로 즉시정지 아님.
   - hips 없음은 기존 pitch0 graceful 동작이며 실제 기울기 정확도 보장 아님.
3. tests/test_humanoid.py 솔버 테스트 4개
   - 퇴화 frame, 손/팔 hold, reset 보정 보존, 상체만+퇴화 팔+속도/가속 상한.

## 검증
- smoke+humanoid: 변경 후19PASS/10.11s, 타페어 테스트 추가 후21PASS/11.70s. 전체 pytest 미실시.
- V-S=2iTaT7W78qb9xd3y에 변경묶음/재현 전달, 회신 대기.
- A7 손목 프레임간 회전 최대 변화 baseline/current와 -50% 임계 확정은 미실시. 실제 q overshoot 미측정.
- 30초 JPEG 개수 >=29.7Hz 및 양팔 IK p95<=33ms 정식 재측정 미실시.

## 재현
```sh
source /home/user/anaconda3/etc/profile.d/conda.sh
conda activate robot_percept
cd /home/user/work/robot_percept
source sim_test/gl_env.sh
export HOST=0.0.0.0 PYTHONPATH=$PWD OPENBLAS_NUM_THREADS=1
python -m pytest tests/test_smoke.py tests/test_humanoid.py -q
flock /tmp/rp_measure.lock -c 'uptime; nvidia-smi; python bench/humanoid_s_diagnose.py'
flock /tmp/rp_measure.lock -c 'uptime; nvidia-smi; python bench/humanoid_s_geometry.py'
```

## 재개 지점 (항상 마지막 갱신)
1. V-S 피드백 먼저 확인하고 수정. A7은 부분 구현이며 재등장 회전 블렌드/팔 손실 경계/actual q 검사 추가 필요.
2. geometry 결과로 fixed shoulder 기준과 joint limit 및 로봇-FK reachable 차이를 분리. 방향/위치 동시달성 가능한 세트 정의 후에만 swivel/계층 task 실험.
3. A7 baseline/current paired dropout 벤치, 녹화본 및 합성 모두에서 회전점프/속도/가속/actual q 지표. 30fps 정식 measurement lock.
4. A1 PASS 후 A2 캡슐 결합후검사/경로/actual q/감속마진 구현. 현재 충돌안전 보장 없음.
### 1차 종료 보충
- geometry 재실행은 약3분간 measurement lock 대기. 도구 세션1080(자기 실행 트리)만 terminate하여 대기 취소, 측정 결과 없음(/tmp/humanoid_s_geometry.json 0byte). 타 측정 lock/PID 건드리지 않음.
- 임시 patch helper/run shell은 저장소에서 제거. 유지 신규 bench는 소유 범위인 humanoid_s_*.py 2개뿐.
- 전체 상태: P1a FAIL, P1b PARTIAL/검증대기, P1c 미실시. V-S 회신은 후속 세션에서 반영 필요.
# 2라운드 (2026-11-03 10:27~)

## P1a 20도 출처 분해 (GT 보조, 서버 없는 정적 운동학)
수치들은 서로 독립적인 가산 오차가 아니다. 표의 ablation은 동일 가중치/반복횟수에서 기준점만 고친 비교이며 다른 행은 기하학적 크기다.

|확인 항목|수치/관찰|판정|
|---|---|---|
|세그먼트별 길이|L_upper=184.5003mm, L_fore=138.3747mm. 기존에도 E=S+L1*u1, W=E+L2*u2.|전체 길이 단일스케일 문제 아님|
|어깨가 shoulder pitch 중심인가|아님. 기존 S는 shoulder_roll_link 중심. pitch→roll 거리40.4388mm. roll 중심은 pitch 회전에 따라 움직임.|rest고정 S가 주원인|
|고정 S와 실제 S|기존 해에서 forward90 17.917mm 이동, 개선해에서165도 팔 27.486mm 이동. 고정 origin 목표는 서로 비일관적.|매 반복 실제 FK shoulder를 기준으로 변경|
|링크 방향/오프셋|E→W와 elbow_link local+x는4.21758도 차이. actual L_upper=183.975~184.758mm(표본), L_fore=138.3747mm 일정.|local축을 팔 방향으로 쓰지 않으며 FK 두 점 차이로 비교. 남은 길이근사 <0.53mm|
|관절한계|개선 후11시점 표본 최소 margin18.53도, V-S12대칭자세 최소22.72도.|20도 오차의 불가피한 관절한계 아님|
|고정 S→실제 S ablation|11시점 settled 상완max17.331→1.496도, 전완20.422→2.135도, wrist6.95→0.70mm.|전완 잔차18.287도 제거. 가중치/반복8 유지|
|반복증가만|기존8→32회 전완20.422→20.338도.|반복횟수가 주원인 아님|
|가중치만|기존elbow1.0은 방향6.861도/wrist24.12mm.|가중치 절충은 증상, 근본수정 아님|

- 이전 geometry warm-sequence에서는 오른팔165도가 shoulder_roll 한계0.01도/wrist76.7mm에 갇힘. 이것은 도달불가의 증명이 아니며 수정 후 동일자세 margin18.53도, 방향2.135도/위치0.339mm의 실현가능해를 찾음. 따라서 '최선의 불가피한 관절한계'로 오인하지 않는다. 전역최적해 증명은 하지 않음.
- robot FK로 생성한 도달가능 8표본은 기존솔버도 wrist max1.09mm/rot0.27도. 사람목표 구성에 집중한 이유.

## P1a 구현
- sim/humanoid_ik.py: 선택 인자 relative_targets=(shoulder_body_id, elbow_offset_world, wrist_offset_world). 각 반복 p_target=FK shoulder+offset, Jp/Je에서 shoulder point Jacobian 차감.
- sim/humanoid_teleop.py: 매 solve에 Rt*L1*u1, Rt*(L1*u1+L2*u2) 전달. 진단/3D marker도 solve 후 actual S 기준 갱신. fingertip mode는 tip offset까지 포함.
- shoulder pitch 중심으로 임의교체하지 않았음. 검증 FK u1가 shoulder_roll→elbow이므로 동일한 기하 정의를 유지하면서 실제 이동점 처리. pitch 중심을 해부학적 어깨로 택하려면 GT 방향 정의·길이·검증을 함께 변경해야 하며 현재 계약과 혼용하지 않는다.
- wrist 위치 기준도 명시적으로 rest S가 아니라 각 해의 실제 S+L1u1+L2u2. rest고정 GT로 개선했다고 주장하지 않음.
- swivel/가중치/반복 증가 없음. relative Jacobian 수치미분 테스트 및 raised-arm FK 회귀 추가.
- V-S12대칭자세 목록 cold-rest→30warm solves: max 상완1.40480도, 전완1.98949도, wrist1.58mm, 좌우차2.21e-12도. 정확도 gate 자체는 provisional PASS, V-S 및 30fps/IK p95 gate는 대기.

## P1b 측정
bench/humanoid_s_round2.py. git1da4b93 servo를 메모리에 읽고 비교(파일 덮어쓰기 없음). A7-only는 새relative_targets를 제거하여 A1 효과와 분리.
- GT보조 정적 pronation69도, 3초settle 후9초, 손on/off1.5초, 물리2ms, 회전관찰34ms(30fps 유사, 정확33.333ms 아님), 양팔526개 차분.
- 실제 wrist link 회전 프레임간 max: baseline8.660546도 → A7-only0.000102148도 / full_current0.000114874도. full_current 감소99.998674%, 이 제한된 정적손실세트 -50% gate PASS.
- 같은 static dropout에서 baseline actual velocity cap1.60765x/acc74.6670x. A7-only 및 full은 settle후 정지라 거의0. 이를 동작중 상한 보장으로 일반화 금지.
- 별도 full_current 9초 합성 팔동작(앞3초settle, synth t5~14), 500Hz actual q 확인: velocity max6.500188rad/s, cap비2.138136x; acceleration max2594.2913rad/s², cap비103.476907x. 최악 ratio 관절 right_shoulder_yaw_joint. **actual q 속도/가속 gate FAIL**.
- command velocity/acceleration 비1.0(부동소수1e-12 오차) 유지. position actuator 물리응답은 command limiter와 다름. qvel강제클램프 미실시.
- 기본모델은 이미 kp=500, dampratio=1, implicitfast. 단순 무감쇠로 단정 금지. 50Hz ctrl계단/관성 coupling/가변감쇠 원인분리 필요. 물리step 목표보간 후보는 후속이며 지연 증가량 함께 측정해야 함.
- 녹화본 재등장/팔가림 최대각변화, actual 추종지연/overshoot, FPS는 아직 미측정.

## 파일/검증
- 소유 변경: sim/humanoid_ik.py, humanoid_retarget.py, humanoid_teleop.py; tests/test_humanoid.py 솔버테스트(이번2개).
- 신규 bench/humanoid_s_round2.py, humanoid_s_static.py; 기존 diagnose/geometry 유지.
- smoke+humanoid **24PASS/11.48s**. 타페어 테스트 포함 분모이며 S만24개라는 뜻 아님. 전체pytest 미실시.
- 결과 /tmp/humanoid_s_round2.json, /tmp/humanoid_s_static.json, /tmp/humanoid_s_dynamic_sweep.json. correctness 계산은 measurement lock 대기 취소 후 실행. time_ms 값은 성능 근거로 사용하지 않음.
- V-S에 변경/수치/재현 전달했고 회신 대기. 부모에 actual q FAIL 공개.
- P1c는 P1b FAIL로 미착수. 5093/5080/카메라 접촉없음, 커밋없음.

## 재현 추가
공통 conda/gl_env/PYTHONPATH 설정 후:
```sh
python bench/humanoid_s_round2.py
python bench/humanoid_s_static.py
python -m pytest tests/test_smoke.py tests/test_humanoid.py -q
```

## 재개 지점 (2라운드 최종)
1. V-S(2iTaT7W78qb9xd3y) 피드백 확인, 특히 실제 S 기준 계약과 상대 Jacobian 독립검증.
2. P1a 정식 measure lock 아래 저부하 30초JPEG≥29.7Hz·양팔IK p95≤33ms 재측정. 기존 correctness 계산 time_ms로 대체금지.
3. P1b 실제q상한 FAIL 해결. 먼저 보간20ms와 baseline을 offline paired 비교, 지연증가/실제q/명령제한 함께. 원모델 dampratio1이므로 관성/커플링 확인. env.step 내부 보간이면 worker가 이미 env.step(1)을 쓰므로 연결 별도변경 필요성부터 I-W와 합의. URDF effort 유지, qvel클램프 금지.
4. 재등장 큰회전 blending/녹화본/팔가림 case 추가, V-S와 cap noise허용량 합의(현103x는 noise 아님).
5. P1b 판정 후만 P1c 캡슐 충돌회피. 현재 충돌안전 보장 없음.
### 보간 후보 실험 (2라운드 끝)
- bench/humanoid_s_interp.py: production env/worker 미변경, subclass에서20ms linear ctrl ramp만 적용. 같은9초 동작에서 actual speed max4.07326rad/s, cap비1.07586x; acc max65.5780rad/s², cap비2.18593x. 기존2.138x/103.477x보다 크게 개선되나 여전히FAIL.
- target ramp horizon20ms 추가, 실제 운동응답 지연 증가량은 미측정. 단순20ms보간만으로 PASS 주장 금지. 후속은 cubic/acceleration-continuous trajectory 및 동작제한 여유, 실제qlag 함께검증. kp500/dampratio1/URDFeffort는 실험에서도 유지.
- 모든 CPU벤치 종료. I-W measurement 요청으로 추가벤치 중단. production S파일 더 이상 변경하지 않음.
# 3라운드 P1b (2026-11-03 10:37 재개)

## 구현
- sim/humanoid_env.py: JointSetpoint, goal만50Hz 갱신하고 step()마다500Hz 참조 위치/속도/가속 상태를 적분하는 선택형 API. env(...,setpoint_scale=.6/.8/1.)로 활성화. **기본 None/OFF, 운영 안전성 개선을 아직 주장하지 않음**.
- 가속target bounded + jerk=10*amax bounded. 현재 advance는 piecewise constant jerk의 정확한 cubic 적분으로 p/v/a를 연속 연결. goal 변경에 상태 리셋 없음. forcerange/kp/damping/qvel 직접수정 없음.
- worker는 env.step(1) 호출 중이므로 별도연결 필요없음. worker코드 변경 안 함.
- sim/humanoid_teleop.py: 같은어깨/zero torso축/공선 torso축은 IK수행 전 des=cmd 및 q_ik=cmd로 hold. 임의직교축으로극단자세를 생성해 warmstart오염하는 경로 제거.
- tests/test_humanoid.py: boundedjerk/acceleration 및 collinear 후 복귀 회귀2개 추가(실행 대기).

## 최초 후보 A 비교 (완료, lock 사용)
10:40:35 시작 load3.00/4.70/5.39, GPU1%,1727MiB. 이 실행은 advance 초기 semi-implicit적분 버전을 메모리에 로드했음. 이후코드는 정확한cubic으로 보강했으므로 최종버전 재측정이 필요. latency step10-90추가 전 실행이며 표에없는10-90값은 아직없음.

|scale|actual V/cap|actual A/cap|cmd목표→actual위상 ms|입력목표→손목 p50/p95 ms|tick p95 ms|판정|
|---|---:|---:|---:|---:|---:|---|
|OFF|2.1381|103.4769|64|66/66.7|8.634|FAIL|
|0.6|0.6275|3.0907|96|98/98|6.736|FAIL|
|0.8|0.8257|3.6046|88|90/90|6.091|FAIL|
|1.0|1.0234|4.0073|84|86/86|4.557|FAIL|

- actual가속 최악은 모두right_wrist_roll_joint. speed최악 .6 left_shoulder_pitch, .8 right_shoulder_pitch,1.0 right_shoulder_yaw. 속도는개선됐으나가속≤1.0미달. 지연만보고0.8을운영채택하지않음.
- phase는 .35Hz 합성sinusoid, command=servo.des shoulder_pitch와실제q cross-correlation. 손목은 입력에서구성한wrist target x와실제wrist x,4초창/0.5초stride p50/p95. **오프라인receive→물리응답지연 대용값이며 사람camera capture→실제손목E2E지연이 아님**. 렌더/네트워크/추론불포함.
- tickp95는 각공유부하변동 포함, OFF보다빠르다는인과주장금지. 렌더30fps는미측정.

## 퇴화 복귀 시나리오
bench/humanoid_s_round3.py: 정상3초→bad0.5초→정상2초,500Hz물리,기본필터OFF. zeros/collinear/zero_arm_len/hand_degenerate 모두finite=True, control대비회복u1방향차0.0도. V-S의control+2도안에들지만구현자GT보조벤치이며독립검증대기. mixed_row_len은I-W소유400검증이라수정안함.

## 다음 진행
- 정확한cubic고정버전+original/zero Coulomb마찰분리벤치(bench/humanoid_s_friction.py)와10→90% step계측은measure.lock대기(exec1008). zero마찰은subclass ablation뿐production마찰변경없음.
- 원모델joint frictionloss=.3이wrist저관성에서stick-slip가속을유발하는지분리. 결과확인전원인단정안함.
- 소유파일원상태보존: defaultOFF. 전역측정락/자기실행트리만관리,5080/카메라미접촉. 커밋없음.

## 재개 지점 (3라운드 중간)
1. exec1008 결과회수, 새cubic설정별actual V/A·phase·10→90% 수치기록.
2. pytest smoke/humanoid 새2테스트포함확인. V-S 독립recovery/비대칭/이중S기준FK회신반영.
3. 실제A≤1.0설정이없으면미채택. 사용자에게안전기준완화요청하지말고마찰/관성/목표궤적원인추가분해.
4. 안전통과후에만default활성화와30fps정식서버측정. P1c미착수.
## 3라운드 최종 보충 (10:45 종료 준비)
- 정확cubic버전 measure.lock 재측정:10:43:05,load2.96/3.93/4.99,GPU29%,1751MiB.

|C2 scale|actual V/cap|actual A/cap|최악속도관절|최악가속관절|판정|
|---|---:|---:|---|---|---|
|0.6|0.627733|3.137730|right_shoulder_pitch|right_wrist_roll|FAIL|
|0.8|0.826433|3.649320|right_shoulder_pitch|right_wrist_roll|FAIL|
|1.0|1.024030|4.104127|right_shoulder_yaw|right_wrist_roll|FAIL|

- frictionloss=0 ablation가속비는 .6/.8/1에서3.47147/4.00165/4.31452로오히려악화. **Coulomb마찰이주원인이라는가설기각**, production마찰유지.
- zero-friction실험 step(shoulder_pitch 약-0.8633rad, flex .3→1.2): command10→90=240ms(입력후t10=100,t90=340); actual10→90=.6에서406ms(t10=230,t90=636),.8에서324ms(218/542),1에서284ms(212/496). 이 값은production baseline이아님.
- baseline/defaultOFF step10→90은아직미측정. 재현함수 bench/humanoid_s_round3.py step_response(None). zero-friction수치를production으로대입하지않는다.
- smoke+humanoid **27PASS/7.52s**, 신규boundedjerk/collinear복귀테스트포함. 전체pytest미실시.
- jerkfactor .2/.1 추가sweep(bench/humanoid_s_jerk.py)은globalmeasurement락5개대기,시간내실행불가판단으로 **자기exec1017만terminate**. 측정결과없음. 타세션락/PID미접촉.
- 원본C2 .6/.8/1 중안전상한통과설정0개. 따라서권장안은 **운영채택보류/defaultOFF**, 사용자에게가속기준완화결정을요청할단계가아님. 낮은jerk·coupling/actuator의실제가속원인분해가먼저다.
- render30fps영향은 [blocked] 안전gate통과후보없고측정락장기대기. tickp95후보A수치는위표에있지만env.step추가비용/renderer효과를포괄하지않음.
- V-S에변경묶음/수치/복귀시나리오전달. 독립회신대기. I-W에step함수와production수치미측정사실공유.

## 재개 지점 (3라운드 최종)
1. 후보C2기본OFF유지. `python bench/humanoid_s_jerk.py`를measure.lock아래실행해jerk_factor .2/.1(명목jmax=2*amax/1*amax)추가sweep. 통과시같은함수에서phase/10-90자동보고.
2. productionbaseline10→90: `from bench.humanoid_s_round3 import step_response; print(step_response(None))`. 당시scale/마찰/소스hash명시.
3. 안전상한통과설정이없으면물리coupling/actuator구조분해. 참조가속이아니라actualqacc를제한해야하며Coulomb제거는효과없음. qvel클램프금지/URDF토크유지.
4. V-S독립퇴화복귀·손실동일스크립트9.9도 gate·비대칭·actualS/restS이중보고응답확인.
5. 안전통과후 env기본활성화 여부와지연tradeoff부모합의,이후30초JPEG≥29.7Hz/tickp95/IKp95정식측정. P1c미착수.
# 추가 물리 진단 (2026-11-03 10:47~)

## 관성·고유주파수·가속 정의
|관절/상태|qM 대각 kgm²|결합유효관성 1/(M^-1)jj|kp/kv|fn Hz|ωn*dt|
|---|---:|---:|---|---:|---:|
|right_wrist_roll rest|.01104376|.01096407|500/4.6931|33.8647|.42556|
|right_wrist_roll C2피크|.01325864|.01132061|500/4.6931|30.9069|.38839|
|right_shoulder_yaw rest|.04218027|.01525687|500/8.3580|17.3281|.21775|
|right_shoulder_yaw C2피크|.01630603|.01266885|500/8.3580|27.8696|.35022|

- dt=.002s, Nyquist250Hz. fn은대각관성의독립관절근사이며결합고유모드정확계산이아님. wrist결합유효fn=33.448Hz. Nyquist보다낮고ωdt<.43이나이것만으로비선형implicitfast안정성증명하지않음.
- OFF 가속 FFT:49~51Hz와100/150/200Hz고조파, wrist>100Hz전력49.411%. C2 .6:주봉1.11/2/2.33Hz,피크0.5초창4/6/12Hz, >100Hz전력.0917%. 따라서잔여3.14x의주원인이34Hz공진/alias라는가설은지지되지않음.
- 가속gate는실제qvel의2ms유한차분유지. wrist FDpeak94.1319 vsMuJoCo qaccpeak173.842, RMSE6.687. implicit계산의qacc와실제적분qvel차분은같은양이아니므로느슨한지표로교체하지않음.
- 공식Unitree G1 SDK예제 control_dt=.002/500Hz설정: https://github.com/unitreerobotics/unitree_sdk2_python/blob/master/example/g1/low_level/g1_low_level_example.py . 이것은SDK명령주기근거이며encoder내부샘플링/모터전류루프500Hz라고단정하지않음. V-S정의합의회신대기.
- 현재Menagerie armature=.01(전관절기본). mjlab v1.4.0 source는Unitree모터스펙으로5020 rotor=(.139e-4,.017e-4,.169e-4),gear=(1,1+46/18,1+56/16),반사관성=.003609725;어깨/팔꿈치/wrist_roll에사용. 4010 wristpitch/yaw=.00425. 이외부소프트웨어스펙은정확한실물revision의실측인증은아님. 현재.01보다작으므로가속억제목적으로armature를더키울근거로쓰지않음.
- 출처: https://raw.githubusercontent.com/mujocolab/mjlab/v1.4.0/src/mjlab/asset_zoo/robots/unitree_g1/g1_constants.py , MuJoCo반사관성정의 https://mujoco.readthedocs.io/en/stable/XMLreference.html#body-joint-armature . 운영armature변경없음.

## 같은2ms 기준 참조/실제 가속·범위 매핑
- 최악right_wrist_roll: dofindex=actuatorindex=33, TELEOP_ACC[wrist]=30, scale.6→generatoramax18. 참조stateamax18, 참조위치2차차분max18.00000000007. **단위/배열상한매핑버그아님**.
- 다만rawreference min=-2.023914rad, actuatorctrl하한=-1.97222. raw참조가100physicsframes범위를넘어MuJoCo의내부ctrl클램프가C2를깨뜨림. 실효reference=clip(raw,ctrlrange)의2차차분max399.6756rad/s²(t10.804). 이는rawref가속18과다른값이다.
- 추종오차max.051512rad. 제약토크max.3Nm(마찰). raw범위초과→내부클램프→실효속도꺾임이주원인후보이며아래가드ablation으로큰개선확인.

|t s|raw ref q|actual q|오차 rad|raw ref A|actual A(2ms차분)|
|---|---:|---:|---:|---:|---:|
|10.626|-1.965586|-1.954213|-.011373|13.019|11.531|
|10.630|-1.971011|-1.960008|-.011003|13.739|12.121|
|10.634|-1.976216|-1.965080|-.011136|14.459|76.084|
|10.638|-1.981190|-1.968808|-.012382|15.179|94.132|
|10.642|-1.985921|-1.971103|-.014817|15.899|81.248|
|10.646|-1.990397|-1.972312|-.018085|16.619|54.426|
|10.650|-1.994608|-1.972844|-.021764|17.339|30.957|

## 원인 수정 ablation: jerk 제동거리 range guard
- JointSetpoint에lower/upper전달,현재v/a에서jerk=-J로a=-A까지감속후정지하는거리계산. 남은범위≤제동거리+한물리스텝마진이면최대jerk브레이크. p/qvel hardclip은하지않음. 기본OFF유지.
- .6 wrist rawref min=-1.971751(하한이내),실제min=-1.971785,오차max.018526. rawrefA2차차분max18유지. 실제wrist가속94.1319→23.7519rad/s²(.792cap). 내부클램프회피가직접효과있음.

|guard scale|전체실제 V/cap|전체실제 A/cap|최악V관절|최악A관절|판정|
|---|---:|---:|---|---|---|
|.6|.619477|.831392|left_shoulder_pitch|right_elbow|GT보조9초물리세트잠정PASS|
|.8|.821202|1.275467|left_shoulder_pitch|right_elbow|FAIL|
|1.0|1.024224|1.194711|right_shoulder_yaw|right_wrist_roll|FAIL|

- 수정검증load7.34/6.02/5.31. 최신부모규칙에따라순수운동학/가속정확도는락없이수행. 성능ms/FPS주장안함.
- 수정후smoke+humanoid27PASS/17.97s,rangebraking회귀1개추가후재검증예약. V-S에상한통과후보공유.
- 성능지연/step측정은새규칙 `flock -w 900 /tmp/rp_measure.lock` 안에서예약(exec1033),5분이내배치. 안전Gate는잠정통과지만지연/FPS/독립검증전운영기본OFF유지.
- I-W productionbaseline별도계측 notes/humanoid_w_response.json:stepq-.863292rad,command100/340ms(10→90=240),actual130/366ms(236). 이값은기존OFF의기계응답이며소프트웨어전달지연과별도.
- V-S최신독립결과P1a는up120 u2=9.12도및비대칭최대60도/93.7mm로FAIL통보받음. reset+6초재검증진행중. 자체cold-static통과를독립PASS로일반화하지않음. 원인후보warm-startlocalbranch/실제정착분리필요.

## 재개 지점 (고주파 진단 후)
1. exec1033 .6guard후보vsOFF phase/step10-90·새range회귀테스트결과회수. 독립V-S cap/복귀/비대칭재측정요청.
2. 안전/정착/FPS충족전setpoint_scale=None(defaultOFF)유지. 추천후보는.6guard이나아직운영채택아님.
3. P1a독립FAIL비대칭결과에대해IK잔차와qtarget/cmd/actual로localminvs물리tracking분해. 임의온라인restart증가전에정량검증.
4. P1c미착수. 커밋없음/5080미접촉.
### 종료 인계 (부모 승인, 10:55)
- **exec_session_id=1033은종료하지않고대기유지**. 부모가즉시재개후bash_interact로poll. 세션소멸시동일명령재실행.
- 실행LF shell Windows `C:\Users\USER\.aside\u\0\s_saferesponse.sh`, WSL `/mnt/c/Users/USER/.aside/u/0/s_saferesponse.sh`.
- 내용: conda robot_percept/gl_env/PYTHONPATH 후 `flock -w 900 /tmp/rp_measure.lock -c 'date; uptime; nvidia-smi ...; python bench/humanoid_s_safe_response.py | tee /tmp/humanoid_s_safe_response.jsonl; python -m pytest tests/test_smoke.py tests/test_humanoid.py -q'`.
- 결과 `/tmp/humanoid_s_safe_response.jsonl`; 아직파일없음(락대기). .6guard vsOFF phase/step10-90,range회귀추가후전체28개예상(실측전분모확정하지말것).
- 운영파일git-blob hash: env=d6a0a16e8d065e3744d7fac9ddbd184242a296de; teleop=87f39a11ef2d3d3b08d7b2d4d1aab73d1d7a0fb0; tests=5f0bb1f568e7b8c09a447470341c24a31455b552.
- 새defaultOFF .6guard의잠정물리상한통과는9초합성세트범위만. 지연/FPS독립검증전에PASS확정/기본활성화금지.
- **다음최우선: P1a V-S와같은입력·reset+6초settle로9.12도/비대칭60도문제를재현**. 실제정착시간차인지warm-start/비대칭자세버그인지IK잔차와target/cmd/actual를함께수집. 이전cold-static측정과분리.
- V-S에최신source/판정전달. P1c계속보류.
# 5라운드 (2026-11-03 10:56~)

## exec1033
- 10:56재개시락대기유지. **11:01:52 measure.lock획득**, load7.81/5.81/5.17,GPU26%,1953MiB. OFFvs.6guard phase/step+reset.5s/6s동일입력재현+pytest배치진행중. 결과 /tmp/humanoid_s_safe_response.jsonl. 소스동결.

## P1a 독립FAIL 정확한재현
- V-S bench/verify_s/base_s.py를읽고POSES/pairs/RESET.5s/SETTLE3.2또는6s/8회0.1s샘플을동일하게구성한 bench/humanoid_s_history.py.
- 서버없이500Hz물리/30Hz입력의simulatedclock. realHTTP/jitter는없지만V-S실패수치를0.02도이내로재현하므로공유부하/settle타이밍만의문제가아님.
- 동일6쌍x좌우교환순차(리셋없이3.2초settle) actualmax60.03173도, finalIKwrist93.72mm,좌우차59.52772도.
- up120왼:actualu2=9.12255도/IK=9.12087/cmd=9.12103. q_ik wrist_roll=-1.96894rad,한계margin.188도,elbowres20.6mm.
- fwd60_el100오른:actual60.03173도/IK60.03184/cmd60.03184. elbow+wrist_roll한계margin.00573도,wrist93.72mm/elbow125.4mm.
- **실제q는잘못된IK목표를충실히따르고있음. 물리정착부족/영상샘플링이주원인아님. warm-start가joint-limit포획된로컬브랜치에들어간실제솔버버그.** 좌우미러/몸통/Rt는같은목표를다른이력으로주었을때정상해가존재하므로불가피한기구학한계가아님. 반대팔상태가운동학적으로직접커플링되는증거없음.
- reset+.5/6초에서60도가사라지되up1209.1도가남는V-S결과도이력초기화정도에따른브랜치차이와일치. reset후직전sample이fresh하면.35초간이전목표를다시풀수있어완전cold초기화와같지않음(워커reset코드읽기근거).

## 수정: 제한된 deterministic branch recovery
- sim/humanoid_ik.py solve(recover=False선택인자),servo는recover=True.
- warm8회후position>10mm또는elbow>8mm이면**rest seed 8회probe1개만**추가. randomrestart나비제한탐색아님.
- 동일weightedtaskcost(position/rotation/elbow)20%이상개선+wrist잔차≤max(10mm,이전잔차)일때만채택. 기존속도/가속명령필터유지.
- diag branch_recovered 및iters합계제공. time_ms는복구probe포함. 복구탐색이반대팔goal/프레임을변경하지않음.

|동일연속이력세트|actual방향max|finalIK wrist max|좌우차max|
|---|---:|---:|---:|
|수정전|60.03173도|93.72mm|59.52772도|
|수정후|3.08994도|1.58mm|1.74749도|

- up120왼9.12255→1.99061도, fwd60_el100오른60.03173→.59110도. 새최악fwd45왼3.08994도.
- tests/test_humanoid.py: 비대칭6쌍x좌우교환연속IK회귀추가. **29PASS/11.35s**(smoke+humanoid),전체pytest미실시.
- sourcegitblob IK10f4571325e24809cce08c20ba87ff2e1b602a95 / teleop0285b245955b520b435e524a6703e78a803120f6 / envd6a0a16e8d065e3744d7fac9ddbd184242a296de.
- V-S에cand3동일순서재측정요청,독립합의대기. 자체통과를최종PASS로표기하지않음.

## P1b 코드변경후재검증
새IK브랜치복구로목표궤적이달라져이전cap수치를그대로승계하지않고재측정.
|guard scale|실제V/cap|실제A/cap|최악V|최악A|9초합성세트|
|---|---:|---:|---|---|---|
|.6|.618331|.784178|right_shoulder_pitch|right_wrist_roll|잠정PASS|
|.8|.817793|.991774|left_shoulder_pitch|right_wrist_roll|잠정PASS,여유<1%|
|1.0|1.015530|1.197897|right_shoulder_pitch|right_wrist_roll|FAIL|
- 추천후보.6(가속여유약21.6%)를유지. .8의지연이조금작더라도.8%여유는변동/다른입력세트에취약하므로독립하드닝전채택권장안함.
- 기본setpoint_scale=None/OFF. 지연/30fps/독립검증후기본ON결정. P1c는그뒤.

## 부하규칙 변경 대응
- 위정확도/물리재현은직전부모허용규칙(순수정확도물리락없이가능)에따라수행. 11:00경부모가모든수초벤치락필수로강화하자즉시자기exec1039중단,reset6재현은exec1033-lock배치로이동.
- I-K에10:57~11:00겹침구간공유부하있었음을전달. 이후코드편집/pytest외벤치모두flock-w900,보유5분이내.

## 재개 지점 (5라운드 중간)
1. exec1033결과회수(현재실행중). reset.5/6초완전동일재현결과와OFF/.6 phase/step/새pytest기록.
2. V-S cand3동일입력+동일정착독립결과와PASS/FAIL합의. IK복구추가비용포함IKp95≤33ms/FPS≥29.7검증필수.
3. 안전/지연/회귀PASS전에.6기본ON하지않음. P1c미착수/커밋없음/5080접촉없음.
## 5라운드 완료 결과 (exec1033 종료)
- OFFvs.6guard+동일reset.5/6초재현+pytest측정락배치완료. 11:01:52획득후5분이내종료. 결과 /tmp/humanoid_s_safe_response.jsonl.
- reset.5/6초(6쌍x2)수정후 actual방향max=3.04066829260347 도, finalIKwristmax=1.58 mm, 좌우차max=1.6834622172276 도. 따라서3.2초연속이력과6초reset조건모두자체정확도gate통과. 독립V-S cand3합의대기.

|OFF vs .6guard|OFF|.6guard|증가|
|---|---:|---:|---:|
|command목표→actual q phase|64ms|96ms|32ms|
|입력목표→actual wrist p50|66ms|98ms|32ms|
|입력목표→actual wrist p95|66.7ms|98ms|31.3ms|
|servo tick p95|8.776ms|13.416ms|4.640ms|
|command step t10/t90|100/340ms|100/340ms|0|
|actual step t10/t90|130/366ms|230/638ms|100/272ms|
|actual step10→90|236ms|408ms|172ms|

- step 목표 이동량은 right_shoulder_pitch 약 -.86329rad, 기존 명령 상한3rad/s·25rad/s². phase는 .35Hz sinusoid이며 step 응답과 다른 지표다. 모두 오프라인 기계 응답으로 camera/inference/network/render를 포함하지 않는다. .6guard는 작은 신호 위상 지연+32ms이나 큰step의90%도달은+272ms이므로 체감 지연과 함께 판단해야 한다.
- **smoke+humanoid30PASS/10.63s**, 비대칭 이력·범위 가드 회귀 포함. 다른 페어 추가 테스트도 분모에 포함됨.
- 렌더30fps/양팔IKp95 정식gate 및 V-S 독립cand3합의는 대기. .6 기본은 여전히OFF.

## 재개 지점 (5라운드 최종)
1. exec1033 완료, 재실행 불필요. V-S가 최신hash로 정적/연속비대칭/reset6 및FPS/IKp95 검증 후 PASS/FAIL 합의.
2. 부모가 .6guard 안전 여유와 step90% 추가272ms를 비교. 모든gate 통과 전 기본OFF. .8은 같은9초세트 가속비.9918로 여유가 부족하므로 한 세트 통과만으로 채택하지 않음.
3. P1c 미착수. 커밋/5080 접촉 없음. CPU 벤치 모두 종료.
# 2026-11-05 13:03 재부팅 후 재개

## 현재 운영 상태 (이전 노트의 기본 OFF는 과거 기록)
- 사용자 승인에 따라 safety_brake 기본True, 고정0.6. env기본생성자ON, servo DEFAULT_OPTIONS['safety_brake']=True.
- 런타임ON: 현재actual q/qd로참조seed, 이전ctrl오차를200ms quintic으로연결. OFF: 기존C2참조→빠른goal을200ms blend. 실제q/qd를리셋하지않음. 이미OFF에서과속중인상태를ON순간즉시안전상태로만드는보장은없음.
- I-W 소유 API bool허용·root status safety_brake·UIchecked토글/OFF경고/검증세트한정안내 코드확인. web파일은S가수정하지않음.
- 남은대칭up120는8회neutralprobe가충분히수렴하지못해cost/wrist승인에실패하는문제로정식회귀재현(F:6.3944/9.1232도,iters16,branch_recoveredFalse). 잔차trigger는발동했음. neutralprobe한개만최대16회로증가후동일full12순서100관측회귀PASS. 기본warm8회유지.
- 재부팅후 py_compile 및 smoke+humanoid **36PASS/15.95s**. 이전/tmp결과/exec전부소멸한것으로취급.
- 현재gitblob hash: env55df5957b9d7668d6cf18083a430c81f2a0298e5 / IK881499eb6b5020ca3e9963aad41d18c0f98972dd / teleop40711a8b2cd4a53dd95fd4c987d2519094cf2f35.
- V-S(2iTaT7W78qb9xd3y)에최신hash기본ON묶음독립판정요청. 소스동결,독립PASS미수신.

## 렌더 gate 신규 실행
- bench/humanoid_s_render.py에literal `\\n`이실제줄바꿈대신들어있던하네스문법오류수정. 운영코드변경없음.
- 신규 exec1005. 이전exec1044/1033등은재사용하지않음.
- 실행LF shell Windows C:\Users\USER\.aside\u\0\s_rendergate_reboot.sh / WSL /mnt/c/Users/USER/.aside/u/0/s_rendergate_reboot.sh.
- `flock -w 900 /tmp/rp_measure.lock -c 'timeout 295s flock -w 900 /tmp/rp_gpu.lock -c "date; uptime; nvidia-smi ...; python bench/humanoid_s_render.py | tee /tmp/humanoid_s_render.json"'`.
- measure→gpu순서, GPU대기까지포함해measure보유295초이하. 내부스크립트SIGTERM처리finally에서modeOFF+5093listener가자기PopenPID와일치할때만종료. 5080접촉없음.
- defaultON실제q상한재확인후5093서버준비/3초warmup/30초MJPEGcount,개별IKp95·양팔IKp95상태·서보tickp95·기본옵션출력. 결과 /tmp/humanoid_s_render.json,서버로그 /tmp/humanoid_s_5093.log.
- 13:05현재measure락6개대기,5093listener없음. 결과생성후숫자를노트에복사하여재부팅유실방지할것. 아직gate PASS주장없음.

## P1c 착수 설계 (렌더/독립 gate 전 활성화 금지)
1. 공통경로: env.step의500Hz 실제ctrl적용직전에최종후검사. safety_brake ON/OFF/200ms전환모두동일경로를통과해야함. OFF라고자기충돌회피를우회하지않음.
2. 캡슐: torso pelvis→양어깨중점 r90mm, 양상완S→E/전완E→W r45mm, 손W→palm+90mm r50mm를V-S근사와맞춰시작. 얼굴/손가락/환경전체안전보장아님. 인접접합제외쌍명시; V-S기준13쌍(torso-fore/hand4+좌우팔/손9)으로교차비교, torso-upper추가쌍은어깨부착겹침을분리검토.
3. 양팔qfull을합친goal/candidate/common제동상태로평가. per-arm IK반발항만으로안전PASS주장금지. 실제q와현재참조q도별도거리보고.
4. 소수활성쌍최근접점normal 및차분point-Jacobian으로거리증가방향보정. 겹침/퇴화normal은직전유효normal/결정적축fallback. activepair개수/정지율/포기목표수기록.
5. 실행margin은base5mm부터실험하되고정5mm만으로속도안전주장하지않음. 상대접근속도·보수적제동거리·actual tracking오차·다음physics step이동bound가추가되어야함.
6. candidate거부시ctrl만이전자세로고정하면setpoint내부p/v/a가계속진행하는불일치가생김. 후보scratch/snapshot후채택에성공한상태만commit하거나동일p/v/a에서jerk제동으로계속이어야함. ON토글bridge/fastOFF도같은원칙.
7. 이미actual이침투한상태는hold만으로복구/안전이라부르지않음. unsafe진단과안전감속,자동중립으로관통하는경로금지. actual과command경로양쪽거리최소치/침투프레임을별도집계.
8. 충돌세트: rest/교차/몸통쓸기/역방향/빠른전환/dropout/stale+토글, 부호거리>=0mm 프레임100% 및연속경로bound. 판정임계/실행margin을구분. 30fps/IKp95회귀필수.
- 현재충돌회피구현은아직없음. baseline -33.5mm/90침투프레임은11/3 V-S과거합성근사관측이며현코드재측정없이현재값이라고주장하지않음.

## 재개 지점 (11/5 중간)
1. exec1005를poll하여기본ON렌더gate결과회수,5093자기PID정리확인. 세션소멸이면위LF shell재실행.
2. V-S최신P1a+P1b독립판정과불일치수정루프. gate후P1c위공통setpoint경로로프로토타입착수.
3. 모든수초벤치는measure-w900(필요시gpu)안에서5분이내,pytest/편집만예외. 커밋금지/5080금지.
## 11/5 렌더 gate 완료 (exec1005 정상 종료)
- measure→gpu 13:10:21 획득. 시작load3.32/2.45/1.20,GPU11%/1288MiB. 종료load2.12/2.25/1.19. 보유5분이내.
- 기본ON 최신중립probe16+0.6guard 실제q재검증: 속도비.618331/가속비.784178(최악right_shoulder_pitch/right_wrist_roll). GT보조9초동작세트한정.
- 약30초수집JPEG960장,첫/마지막프레임span29.972757초,개수기반(N-1)/span=31.99572fps. **렌더기준≥29.7 PASS**, maxgap68.53ms. 정확히30.000초cutoff를적용한별도rawtimestamp분모는하네스가저장하지않으므로관측eventspan과30초수집루프를구분해보고함.
- 개별IK관측p95=.9315ms, 양팔IKp95상태의관측max=2.981ms, servo tickp95상태관측max=8.08ms. **IK≤33ms PASS**, tick추가비용도현조건예산내. 상태p95의max와모든원시tick의통합p95는같은통계가아님.
- options.safety_brake/root safety_brake 둘다True,HTTPerrors0. 하네스finally에서modeOFF+5093listener PID일치시에만자기서버종료.
- 원시출력(재부팅으로/tmp가사라져도유지):
```text
DEFAULT_ON_CAPS={"velocity_max": 2.400102261639972, "acceleration_max": 23.525340160121274, "velocity_cap_ratio": 0.6183311747608546, "acceleration_cap_ratio": 0.7841780053373758, "worst_velocity_joint": "right_shoulder_pitch_joint", "worst_acceleration_joint": "right_wrist_roll_joint", "physics_dt_ms": 2, "active_seconds": 9}
{"load": "2.12 2.25 1.19 1/338 19253", "frames": 960, "window_s": 29.97275727300007, "fps": 31.99572169037255, "max_gap_ms": 68.5301089999939, "individual_ik_p95_ms": 0.9315, "paired_ik_p95_max_ms": 2.981, "tick_p95_max_ms": 8.08, "safety_brake": true, "root_safety_brake": true, "errors": []}

```
- V-S에같은source기본ON묶음gate결과전달, 독립최종PASS/FAIL회신대기. 자체FPS/테스트성공을독립합의로일반화하지않음.
- P1c는상기설계까지준비했으나**P1a+P1b독립묶음판정대기로미활성/미구현**. 기존충돌안전보장없음.

## 재개 지점 (11/5 최종)
1. exec1005완료,재폴링/기존서버재사용불필요. notes에gate원시결과저장완료.
2. V-S(2iTaT7W78qb9xd3y)최신IK881499eb/env55df5957/teleop40711a8b 기본ON독립판정회신확인. 불일치시같은입력/settle/source로직접수정루프.
3. 독립gate후P1c구현착수: common500Hz최종setpoint경로,상태rollback/jerk제동일관성,actualq/candidate/중간경로,동적제동margin. 위설계8항참조. 안전감속OFF/전환구간도우회금지.
4. 모든수초벤치measure-w900(필요GPUmeasure→gpu)안에서5분이내. 커밋/5080금지. 사용자결정기본ON은유지.
## V-S 독립 중간 회신 (11/5, 동결hash 일치)
- env55df5957/IK881499eb/teleop40711a8b 일치,5094락내기동,load1.6~2.5,GPU4~10%.
- **P1a 독립 PASS 합의:** 대칭12순차상완max1.53도/전완2.10도/실제S손목1.51mm/좌우차0. 비대칭6쌍x2리셋없이max3.08도/손목1.59mm/좌우차1.75도. <=8도/10mm/3도 충족,up120잔여실패해소.
- P1b 기본ON21초합성: 독립status관측속도비.614(left_shoulder_pitch),가속비하한.791(waist_yaw). OFF대조1.588/2.111. 주의: 낮은빈도status qd차분의하한≤1은500Hz최대가속≤1의독립증명이아님. S의500Hz raw차분.784세트결과와분리표기.
- 정지중토글on→off/off→on각2회:maxpoll간Δq.1도/속도.6도/s이하,관측튐없음.
- 손끊김최대회전.1도(기준선19.8도,-99.5%,임계9.9도) PASS,손목위치점프0mm.
- 남음: 동작중토글/독립30초FPS·IKp95/퇴화복귀. P1b최종PASS합의는보류. 그후P1c활성구현착수.
# 7라운드 P1c 분리 모듈 (11/5 13:15~)

## 변경 범위 / 동결
- 신규 sim/humanoid_collision.py, bench/humanoid_s_collision.py, bench/humanoid_s_toggle.py만추가. 운영env/IK/teleop/retarget4파일은동결hash55df5957/881499eb/40711a8b/d3c1676a 유지,통합없음.
- DEFAULT_ENABLED=False; project(...enabled=True)명시시에만회피적용. 기본OFF통합설계이며production은모듈을import/호출하지않음.
- V-S P1b최종판정은동작토글이상치때문에보류. 동결해제/운영연결조건불충족.

## 캡슐/거리/방향/제동 구현
- V-S비교용반경몸통90/상완·전완45/손50mm,13쌍일치. torso pelvis→shoulder mid,upper S→E,fore E→wrist_pitch,hand W→wrist_yaw+90mm.
- closest_segments는점/공선/평행방어. signed=축최근접거리-r1-r2. overlapnormal은이전유효normal/결정적y축fallback.
- 최근접점의선형결합pointJacobian으로distancegradient계산,양팔14+waist3DOF를공동투영. 예제FD대조오차3.17e-11.
- cartesian제동margin=base5mm+vclose*20ms+vclose²/(2*a) (a=2m/s²는실험가정,물리검증된하한아님). examplev=.25m/s→25.625mm,정지시간125ms.
- 거부시마지막안전자세hold는오프라인kinematicprototype일뿐actual q안전정지/제동state일관성을구현한것이아님.

## 최초 벤치 결과 (exec1013 완료, lock13:21:38)
- load시작1.75/1.66/1.44,GPU2%/1944MiB,종료1.87/1.69/1.46. 1da4b93 servo를메모리에서로드(파일교체없음),envfast경로,같은12초코사인24초교차스윕.
- 378개는t1~25의균등simulated-clock관측. V-S원래HTTPpolltimestamp는미저장이라정확동일시계열이라주장하지않음.
- baseline min **-33.6530mm / 침투90프레임**, V-S과거-33.5/90에근접재현.
- 5회bounded projection+4분할경로후검사: min **+5.11354mm / 침투0/378**,accepted378,hold0. palm x RMS변형6.534mm,lagproxy0ms(샘플해상도63.492ms,기하변형과순수지연을분리못함).
- 계산p50/p95 **9.589/19.047ms**. 서보50Hzgoal전처리에도비싸며500Hz그대로통합불가. P1c PASS아님(실제물리/연속경로/토글/스테일미검증).
- 최초mesh audit의torso body선택은headvisualmesh까지포함해max241.48mm로과대평가됨. **수정전audit값으로몸통반경246mm를선택하면안됨**. 모듈은현재headmesh제외로수정했고새audit재측정대기.
- foremesh는reference축끝wrist_pitch보다distal하게연장되어max76.81mm;팔반경을82mm로단순확대하면부정확하고rest가불가능해짐. 전완collision끝점을wrist_yaw까지분리하고wrist/palm별caps를두는형상수정이후필요. handmax54.14mm/uppermax50.14mm도reference반경을초과해proxy가완전메쉬포괄아님확인. 손가락/얼굴은범위제외.
- 아래원시JSON은최적화/머리제외수정전결과이며원본보존용:
```json
{
  "load": "1.87 1.69 1.46 2/350 52066",
  "n": 378,
  "legacy_reference": {
    "min_mm": -33.65301675111255,
    "below0": 90,
    "note": "same analytic sweep, 378 UNIFORM simulated-clock observations from t1..25; NOT original HTTP poll timestamps"
  },
  "mesh_audit": {
    "torso": {
      "radius_mm": 90.0,
      "mesh_radial_p95_mm": 223.6665382633962,
      "mesh_radial_max_mm": 241.4814787137637,
      "uncovered_vertices": 4411,
      "vertices": 9372
    },
    "left_upper": {
      "radius_mm": 45.0,
      "mesh_radial_p95_mm": 46.578472235232745,
      "mesh_radial_max_mm": 50.14011441576329,
      "uncovered_vertices": 263,
      "vertices": 2898
    },
    "left_fore": {
      "radius_mm": 45.0,
      "mesh_radial_p95_mm": 68.19956471116228,
      "mesh_radial_max_mm": 76.81106844548312,
      "uncovered_vertices": 350,
      "vertices": 3273
    },
    "left_hand": {
      "radius_mm": 50.0,
      "mesh_radial_p95_mm": 46.167551881279,
      "mesh_radial_max_mm": 54.14106350634711,
      "uncovered_vertices": 35,
      "vertices": 5962
    },
    "right_upper": {
      "radius_mm": 45.0,
      "mesh_radial_p95_mm": 46.54749514042341,
      "mesh_radial_max_mm": 50.0220718466959,
      "uncovered_vertices": 257,
      "vertices": 2908
    },
    "right_fore": {
      "radius_mm": 45.0,
      "mesh_radial_p95_mm": 67.81332626167875,
      "mesh_radial_max_mm": 76.81106902183612,
      "uncovered_vertices": 324,
      "vertices": 3161
    },
    "right_hand": {
      "radius_mm": 50.0,
      "mesh_radial_p95_mm": 46.293506580296956,
      "mesh_radial_max_mm": 54.14106345746092,
      "uncovered_vertices": 39,
      "vertices": 5991
    }
  },
  "mesh_envelope_proposal": {
    "radii": {
      "torso": 0.2464814787137637,
      "upper": 0.05514011441576329,
      "fore": 0.08181106902183612,
      "hand": 0.059141063506347104
    },
    "rest_clearance_mm": -148.18073301814115,
    "note": "rest-pose enclosure only; if rest overlaps, refine multi-capsules, do not shrink radii"
  },
  "avoidance": {
    "min_mm": 5.1135382880831415,
    "below0": 0,
    "accepted": 378,
    "held": 0,
    "held_fraction": 0.0,
    "compute_p50_ms": 9.589323500108549,
    "compute_p95_ms": 19.046542800072075,
    "position_lag_proxy_ms": 0.0,
    "palm_x_rms_error_mm": 6.534144822883313,
    "sampled_path_note": "4-subdivision finite candidate-path check only; rejected paths hold last accepted q; NO actual physics/path-continuity certification"
  },
  "gradient_check": {
    "analytic": 0.08378932695293657,
    "numeric": 0.0837893269212131,
    "absolute_error": 3.17234710722758e-11
  },
  "braking_example": {
    "required": 0.025625000000000002,
    "available": 0.03,
    "brake": false,
    "stop_s": 0.125
  },
  "perpair_safe_min_mm": {
    "torso|left_fore": 22.76359422352027,
    "torso|left_hand": 126.19203642361192,
    "torso|right_fore": 22.762978614476584,
    "torso|right_hand": 126.18744822116574,
    "left_upper|right_upper": 5.113538288083156,
    "left_upper|right_fore": 5.113538288083156,
    "left_upper|right_hand": 116.6429844108469,
    "left_fore|right_upper": 5.113538288083156,
    "left_fore|right_fore": 5.1135382880831415,
    "left_fore|right_hand": 116.6429844108469,
    "left_hand|right_upper": 116.64314462730806,
    "left_hand|right_fore": 116.64314462730806,
    "left_hand|right_hand": 139.53393103157964
  },
  "production_enabled": false
}

```

## 최적화 / 재측정 대기
- 부모제안반영:13쌍최근접점폐형식NumPy벡터화,활성거리이내쌍만Jacobian계산,endpointJacobian캐시,FK한번당자료재사용. 3단위테스트PASS/1.75s(100랜덤벡터화vs스칼라포함),운영파일동결확인.
- 다음 broadphase는axis AABB거리하한으로멀리떨어진pair만제외. 현재13쌍vectorized검사는모두계산하며큰pair목록으로확장전broadphase추가필요.
- 투영은목표50Hz/새입력에서만,500Hz는commonsetpoint최종가벼운거리/제동후검사로설계. 거리검사완전생략은actualq/중간경로보장없으므로불가. 목표projectp95<=3ms.
- **exec1020** measure-w900/295초상한배치대기:최적화collision벤치→V-S요청동작토글500Hz벤치.
- 실행LF shell C:\Users\USER\.aside\u\0\s_collision_opt.sh (WSL /mnt/c/Users/USER/.aside/u/0/s_collision_opt.sh).
- 결과 /tmp/humanoid_s_collision_opt.json 및 /tmp/humanoid_s_toggle.jsonl. 대기/실행세션은부모재개시poll,소멸이면동일shell재실행.

## P1b 독립판정 보류와 추가 요청
- V-S동작중OFF→ON a하한2.665,ON→OFF v2.165관측. 운영수정금지유지하고sameinput synth t5시작/stream.6s토글,ONkeep/OFFkeep/ON→OFF/OFF→ON 4조건500Hz실제v/차분a/ctrl2차차분/범위초과를새벤치로비교하도록예약.
- 정지토글PASS를동작토글PASS로일반화하지않음. 추가결과후운영bridge원인분해와수정루프가먼저,그뒤P1c연결.

## 재개 지점 (7라운드 최종)
1. exec1020최적화/500Hz토글결과회수. P1b독립PASS수신전운영4파일수정금지,그시점까지신규모듈만수정.
2. mesh head제외audit/전완끝점재정의근거를정리하고reference-radii결과와mesh-fitted결과를분리. 과소캡슐로0침투라고전체메쉬안전주장금지.
3. 최적화p95<=3ms/50Hzgoal projection+500Hzcheapguard설계. actual q·제동상태p/v/a동시검사/연속경로bound/반응지연검증후만활성통합.
4. 운영통합flag기본OFF,sourcehash별V-S직접루프. 커밋/5080접촉없음.
### V-S 동작 토글 최종 확정 (7라운드 종료 시 수신)
- 같은synth t5시작/0.6초토글2회: ON무토글v.614~.617,OFF무토글v.99~1.01.
- OFF→ON v.834~.858,a관측하한0~.06,Δq9.4~11.1도(OFF무토글11.4~12.1)로전환튐PASS. 이전OFF→ON a하한2.665는재현되지않아이전중간의심을정정.
- **ON→OFF v2.183/2.101(right_shoulder_pitch),a하한3.556/1.732,Δq18.8/22.0도,2/2재현FAIL**. 200ms blend로지연된ON참조가앞서있는OFF목표를따라잡으며급가속하는문제. 정지토글PASS와별개.
- P1b는이동중ON→OFF1건FAIL잔존. 나머지손끊김/퇴화/기본ON측정은PASS유지.
- 다음최우선: exec1020의500Hz대조군확인후ON→OFF전환램프를1.0캡이내속도/가속으로제한. 단순200ms crossfade는참조오차크기에비례한급가속을만들수있으므로고정시간보다동적수렴궤적필요. P1c운영연결은여전히P1bPASS후만.
- 이번라운드에서는운영4파일미수정유지. 부모에게FAIL확정전달후후속라운드에서bridge수정루프.
# 부모 최종 토글 기준 후 추가 라운드 (11/5 13:27~)
- 합의 A: ON/OFF→ON 실제가속비<=1.0,초기속도초과는단조감소면허용. B: ON→OFF 같은OFF무토글대조속도/관절변화+10%이내.
- exec1020완료: P1c벡터화후kinematicmin5.1135mm/침투0유지,p50/p95=2.9816/4.8260ms(목표3ms미달). head제외torso mesh radialmax113.432mm,r118.432제안시restproxy-20.132mm로여전히부적절. fore끝점분리·복수torso캡슐필요. 운영연결안함.
- old200ms브리지500Hz재현에서ON→OFF v2.158/A95.54(3.6초창에는synth t8단절포함),OFF→ON A1.182. 이후V-S정확창은stream t5..8의총3초이므로벤치를총3초로정정함.

## 수정1: 속도제한 캐치업 / 상수 좌표 offset
- env ON→OFF 고정200mscrossfade삭제. 기존참조p/v/a유지,vcap1.0/amax.6로목표수렴,goalerror5e-5rad및refvelocity.01이하일때만fast직결해제. self.brake_catchup_s 및전환진행여부로가변시간관측.
- ON은q/qdseed와상수referenceoffset으로ctrl연속/goal과range동일좌표변환. 물리q/qd리셋없음.
- 4시점(.3/.6/.9/1.2)×2 500Hz 결과: ON→OFF v=.908/.914/.977/.991,가속비.603~.629로기존2.1x해소. 그러나1.2s OFF대조v.822대비속도+20.6%/관절변화+32.6%로B FAIL.
- OFF→ON 가속비=.637/1.182/1.602/1.341로A는.6/.9/1.2시점FAIL. 저빈도status에서누락되던실제가속이므로P1b PASS확정금지.
- 3초끝모든OFFcatchup은아직진행중,goalerror약.00010~.00014rad. release시간미확정(null)을수렴시간0이라고해석하지않음.
- 이변형에서전체smoke+humanoid40PASS/14.59s(임시patch삭제후재실행경고가앞에있었으나pytest자체40PASS). 수치결과 /tmp/humanoid_s_toggle_fix.jsonl.

## 수정2 (현재검증대기): ctrl C1 seed와보수적캐치업
- 부모추가힌트반영: OFF→ON generator를actualtrackingerror좌표가아닌직전ctrl위치와직전physicsstep ctrl기울기에서초기화. ctrl기울기/가속은매2ms기록. 실제q/qd는그대로유지.
- 초기refacc는관측ctrlacc를.6amax안에서제한. goal/range좌표offset은현재0. 물리force응답상한이자동증명되는것은아니므로500Hz재검증필요.
- ON→OFF catchup vcap을.75로낮춰늦은토글OFF대조대비+10%여유확보시도(ON.6보다는빠름),amax.6/jerklimit유지. 고정시간해제금지.
- 새회귀2개: OFF해제중p/v/a보존+200ms가지나도미수렴이면계속캐치업,ON좌표/goal/range일치. 초기참조seed검증은현재ctrl/ctrl미분계약으로갱신.
- **exec1027**: /mnt/c/Users/USER/.aside/u/0/s_toggle_fix2.sh, measure-w900/timeout295배치대기. 결과 /tmp/humanoid_s_toggle_fix2.jsonl. 같은4시점×2회/ON·OFF대조.
- **exec1028**: 전체pytest+최종hash출력진행중. /mnt/c/Users/USER/.aside/u/0/s_toggle2_tests.sh.
- 운영파일변경은부모가토글FAIL후수정요청함에따라env만수정. IK/teleop/retarget은기존해시그대로. P1c는기본OFF/미연결유지.

## 재개 지점 (토글 수정2)
1. exec1028 pytest+hash회수,exec1027 500Hz토글결과회수. 단위회귀PASS와물리gatePASS분리. 수정2결과가없으므로현재P1b판정FAIL유지.
2. A actual가속<=1/B OFF대조+10%를4시점×2회모두충족시env blob hash를V-S에직접보내동일TOGTS재측정요청. 초기과속단조감소조건은실제초기과속인경우에만판정.
3. catchup지속시간/잔차도보고. 미수렴3초제외지표와순수E2E지연혼용금지.
4. P1bPASS전P1c운영연결금지. P1c는p954.826→3ms개선/복수torso형상·전완끝점/actual연속경로검증이남음. 커밋/5080접촉없음.
## 전환 수정 최종 인계 (13:37)
- ctrl C1 seed 실험(env실험hashc0ad7512)은OFF→ON A비.994/1.834/2.225/1.978로오히려악화. 근거없는개선채택하지않고ON부분은actualq/qd+상수좌표offset방식으로복원. 현재ON→OFF만.75vcap캐치업유지.
- .75catchup B 결과(.3/.6/.9/1.2각2회):실제v비.76375/.76378/.76466/.76353; OFF대조속도비.5674/.5674/.5681/.9293;관절변화대조비.7588/.7587/.7595/1.02185. **B 8/8자체PASS**,actualA.601~.612. 수렴해제는3초끝아직진행중,마지막참조오차.00010~.00023rad. 고정200ms해제없음.
- ON쪽복원으로최대A1.602가남은이전조건을유지하므로A 엄격기준FAIL유지. 현재코드전체pytest40PASS/16.13s와물리안전PASS는별개.
- 현재운영gitblob env3b51935731fe0c3266c116178450896d460af29c / IK881499eb6b5020ca3e9963aad41d18c0f98972dd / teleop40711a8b2cd4a53dd95fd4c987d2519094cf2f35. 소스동결.
- V-S에현재blob과B만독립재측정요청. P1b전체PASS아님/P1c연결금지.

### 부모 추가 잔류응답 가설 / 다음 재개
- 전환후첫40ms를OFF계속유지대조와비교하고40ms이후actualA<=1을분리. 이는가설검증이며40ms를그냥버려기준완화하는것아님. 둘다충족할때만V-S에기준합의제안.
- **exec1031** 측정락대기: /mnt/c/Users/USER/.aside/u/0/s_toggle_residual.sh,결과 /tmp/humanoid_s_toggle_residual.jsonl. 현재원복ON코드로4시점×2,각first40ms/after40ms peak시각·관절·ratio및OFF대조출력.
- 부모재개시exec1031poll,세션소멸시동일LF shell재실행. 결과불충족이면토크/추종오차/물리초기상태분해계속. actualqvel클램프없음/URDF토크한계유지.
- raw /tmp/humanoid_s_toggle_fix.jsonl(수정1),fix2.jsonl(철회C1실험) 혼용금지. notes의최종해시가현재본.
# 40ms 잔류 가설 결과 회수 (11/5 추가 재개)
- exec1031완료,현재env3b519357/IK881499eb/teleop40711a8b동결본. lock13:37:20,load1.89/2.21/2.03.
- sameinput syntht5시작,총3초창,각토글.3/.6/.9/1.2초×2. 실제500Hz qvel유한차분. 반복2회동일수치(결정적simclock),실제HTTPjitter반복검증은V-S대상.

|토글 s|OFF유지 첫40ms 최대A비|전환 첫40ms 최대A비|전환40ms후 최대A비|초과peak시점|
|---|---:|---:|---:|---|
|.3|3.963061|.636921|.603877|.3s(첫step,초과없음)|
|.6|8.431719|1.182184|.607205|.6s(첫step)|
|.9|8.735353|1.602017|.605809|.9s(첫step)|
|1.2|5.185144|1.341049|.420758|1.2s(첫step)|

- 관측상4시점×2 모두첫40ms는OFF대조이하/40ms후<=1.0. 따라서부모가제시한분리판정의관측조건은충족. 이것만으로순수잔류응답인과를증명하지는않음(첫40ms全관절max의최악관절이대조와전환에서다른경우있음).
- V-S에이표/같은blob으로A판정기준 '첫40msOFF대조이하,이후<=1.0' 합의제안,그기준과B캐치업을묶어독립재판정요청. 아직합의최종PASS미수신.
- 같은관절·같은firststep의OFF대조를추가검증하도록 **exec1033** 예약. Windows C:\Users\USER\.aside\u\0\s_residual_matched.sh / WSL /mnt/c/Users/USER/.aside/u/0/s_residual_matched.sh.
- 결과 /tmp/humanoid_s_toggle_matched.jsonl:각시점전환최악관절의OFF동일관절first40/동일step비교. 논거불일치이면잔류가설단정/기준완화금지,토크상태분해계속.
- 같은배치후반P1c투영시간/4분할경로체크시간분리재측정 /tmp/humanoid_s_collision_split.json. 런타임운영파일변경없음.

## P1c exec1020 회수 확정
- 벡터화후min+5.113538mm/침투0/378/hold0유지. 전체計算p50=2.981589ms/p95=4.825970ms. 목표p95<=3ms **미달**.
- 기존전체시간은projection+5개경로점FK/거리+최종확인포함. 새split계측으로50Hz투영부분과500Hz후검사후보를분리해보고하되통계분모를바꿔전체3ms달성이라고주장하지않음.
- head제외mesh audit:torso max113.432mm/upper50.140mm/fore76.811mm/hand54.141mm. rest-envelope반경torso118.432/upper55.140/fore81.811/hand59.141mm로rest clearance-20.132mm. 한캡슐반경확대만으로실용적안전모델이되지않음→전완끝점/몸통복수caps근거검토필요.
- prototype근사침투0은전체mesh/actualq/연속경로PASS가아님. 기본OFF/운영미연결유지.

## 재개 지점 (40ms 결과 회수 후)
1. exec1033matched동일관절/동일step결과와P1c split결과회수. 40ms가설반증여부먼저판단.
2. V-S A분리기준합의여부+같은envblob3b519357로B4×2독립재판정회신확인. 합의전엄격A FAIL상태를최종PASS로바꾸지않음.
3. 운영hash동결,추가수정필요시근거수치후V-S직접루프. 커밋/5080접촉없음.
## 500Hz 원시 영속·P1b 최종 독립 합의 (11/5 추가 재개)
- bench/humanoid_s_out/20261105T045230Z_matched_summary.json 및동일prefixrawnpz9개(control1+4시점x2전환),manifest SHA256 저장. raw자료10개(요약포함)15,116,650bytes,manifest별도. /tmp유실과무관하게저장됨.
- 최종raw는정확30Hz입력/500Hz물리(dt=.002,n1500),t는물리스텝시작시각이며q/qd는해당스텝적분후상태. 과거34ms입력벤치와수치분리.
- 같은관절right_shoulder_pitch/같은첫step OFF절대A=4.089907/6.423415/6.776424/7.755853; 전환A=.635066/1.254786/1.525132/1.163585;40ms이후전체maxA=.597534/.597257/.599393/.380293. 4시점x2통과.
- signed가속OFF음수→ON양수:동일잔류응답인과단정금지. 비교크기/시간창기준의조건만입증.
- V-S가raw qd로직접차분/독립상한표/동결env3b519357 확인해동일수치재현. 부모가40ms비교기준확정함에따라 **P1a·P1b 독립 PASS 합의 확정**. 엄격전순간A<=1은여전히첫step3건FAIL이므로기준범위반드시명시.
- notes/humanoid_teleop.md에기본ON/캐치업/40ms기준/원시경로추가기록(부모요청으로해당파일문서화허용).
- 운영동결해제승인수신. P1c는이후새defaultOFF경로로만통합,기본ON제안은별도측정후.
- P1c split신규영속결과 bench/humanoid_s_out/20261105_collision_split.json: projectionp95=1.925898ms(50Hz목표투영<=3msPASS),경로4분할p95=3.276261ms,전체p95=5.284658ms. 전체3ms달성이라고주장하지않음. 침투0/378,min5.113538mm유지.
- union mesh audit에서foremesh는handcaps와합쳐전부포괄(미포괄0)하므로fore단독76.8mm라는이유만으로반경82mm로키우는설계는잘못. torso union미포괄2714vertices/max21.255mm,upper약5.14mm/hand4.14mm바깥점은실제로남음. 현재proxy0침투를전체mesh안전보장으로과장금지.
# P1b 최종자료/P1c 기본OFF 통합 (11/5 13:51 재개 결과)
- 부모가V-S 500Hz독립재계산과40ms비교기준을확정, **P1a/P1b 독립PASS 확정**. raw영속경로/첫step엄격1.0예외/signed반전주의를notes/humanoid_teleop.md에도기록완료.
- P1c50Hz목표투영p951.9259ms로목표3ms내. 별도4분할경로검사p953.2763ms,전체p955.2847ms이므로전체3ms달성은아님. 영속JSON bench/humanoid_s_out/20261105_collision_split.json.
- 캡슐합집합mesh audit추가:foremesh는handcaps와합쳐미포괄0. 단일fore반경82mm확대는잘못된분해. torso합집합밖최대21.255mm/upper5.14mm/hand4.14mm가남아완전mesh포괄아님. 따라서defaultON추천보류.

## 기본 OFF 운영 통합
- DEFAULT_OPTIONS collision_avoidance=False,env.set_collision_avoidance(bool),I-W /options bool허용완료(UI/자동활성없음).
- 50Hz/new-observation IK양팔+waist를합친목표에margin10mm투영,채택시des/q_ik동기화. 실패시goalhold(물리긴급정지인증아님).
- 500Hz safety_brake ON/OFF/전환모두공통env.step의참조ctrl·실제q경로감시. ancestorlink길이합으로endpoint변위전역상계를계산하고joint변화절대누적(순변위아님)→13쌍거리하한을추적. 하한2mm근처에서만freshFK,하한<=0이면uncertified계수증가해연속안전이라고부르지않음.
- goalprojection과C2 p/v/a는목표만변경하고state를rollback/하드정지하지않아기존제동상태연속유지. monitor는unsafe시진단만하며독립긴급정지제어기는아직아님. collision_status.physical_stop_certified=False명시.
- 전체smoke+humanoid+collision단위 **47PASS/13.00s**.
- 락13:59:37/load.62/.90/1.58,25초500Hz교차스윕: actual exactFK 최소5.687608mm/침투관측0/uncertified구간0,ref exactFK최소6.592327mm/침투0/uncertified0. actual253회/ref252회만fullFK(12500스텝중),나머지는보수적하한감시. exactFK최소는모든스텝의직접최소와동일통계아님. tickp955.449607ms. summary영속 bench/humanoid_s_out/20261105_collision_runtime.json.
- 참조proxy/선택쌍범위의단일교차세트검증이지전체mesh/얼굴/손가락/환경/모든시작상태안전인증아님. 기본OFF유지추천.

## 남은 측정 / 재개 지점
1. **exec1041** measure-w900→총295s gpu-w900 배치예약: runtime재실행(rawqpos12500스텝NPZ영속저장추가)후5093 collision_avoidance=True + safety_brake=True 30초렌더gate. script /mnt/c/Users/USER/.aside/u/0/s_collision_render.sh.
2. 결과 raw bench/humanoid_s_out/20261105_collision_runtime_path.npz,summary runtime.json,render 20261105_collision_render.json. 이전1039는완료,raw추가전summary만있었음.
3. exec1041결과회수/5093자기PID정리확인→V-S최신sourcehash/옵션ON/capsuleproxy범위/連続bound자료로P1c독립판정요청. 결과없으면PASS확정금지.
4. 별도비정상초기상태/빠른전환/드롭아웃/토글세트와mesh불포괄부분의정교한복수캡슐/긴급제동제어검토전defaultON하지않음. 커밋/5080접촉없음.
# P1c 두차단점 마무리 시도 (11/5 14:01~)
- exec1041완료: 구proxy기준collisionON렌더952장/eventspan29.97956s=31.72162fps,maxgap105.51ms,개별IKp951.6106ms/양팔IKp95상태max4.278ms/tickp95상태max16.48ms,errors0. 5093정상cleanup. 이는새meshprofile/제동latch전코드의측정임.
- 새mesh프로필torso118/upper53/fore45/hand57mm. fore는handcaps합집합으로이미덮여45유지,나머지는선택시각메쉬최대반경+2~4mm여유. 49표본audit에서몸통밖최대.307889mm(5vertices),양팔상완/전완/손밖0mm -> 요청<=2mm목표표본범위PASS. restclearance17.1118mm. 얼굴/손가락/전관절공간모든자세포괄보장은아님.
- collisionrequest브레이크latch API: 참조p/v/a·실제q/qd를리셋하지않고현재참조position을stopgoal로고정,이후입력goal은무시. safety제너레이터의jerk/.6가속상한으로수렴. 재시작은collision기능OFF/ON등명시적해제필요(자동resume없음).
- 최초actualclosing v²/(2*.5)예측margin실험: 실제A비.785는통과했으나trigger.12s/정지1.288s/실제침투-20.157mm로**긴급정지FAIL**. 이결과은폐금지.
- 보강: reference v/a의jerk포함joint stopping-distance상계+reference/actual 추종오차를기존chain-Lipschitz계수로Cartesian변위상계에변환. 실제closing과referenceclosing모두고려,scalarassumptionmargin과최댓값을사용.
- 보강후측정: trigger.04s,정지.730s뒤,실제가속비.410745/속도비.115833,상태jump0,실제min13.69766mm. 단이실행의target이runtime경로파일덮어쓰기때문에+7.79298mm인안전목표였음을발견 -> **이숫자만으로충돌임박제동인증불가**.
- 현재bench수정: fullcross IK(양팔flex1.4/abd-.6/elbow1.4)에서직접unsafegoal생성,제동없는동일목표대조와함께실제침투/제동후A/정지시간검증. sourcepath가실제로음수인지출력값반드시확인.
- smoke+humanoid+collision단위51PASS/19.86s. P1c기본OFF유지. 새프로필후normalcrossrun actualexactmin9.31927/ref9.49099mm,침투0/uncertified0,tickp9512.201ms,brake는7.78s발동(여러입력에대한latch/전면hold사용성문제남음).
- V-S구snapshot독립PASS수신(스윕/chest/jump/twist관측0침투,FPS31.78/31.76/31.86). 단그snapshot은새반경/제동latch와다르며현재본의독립PASS아님. 구chest/jump전면hold및twist0.5mm마진우려유효.

## 재개 지점 (두차단점 최신)
1. **exec1047** poll: /mnt/c/Users/USER/.aside/u/0/s_mesh_brake_counterfactual.sh. measure-w900→총295s gpu-w900안에서unsafegoal/no-brake대조/제동검증후5093새mesh collisionON렌더gate.
2. 결과 bench/humanoid_s_out/20261105_collision_mesh_brake.json 및collision_brake_raw.npz,20261105_collision_mesh_render.json. /tmp/humanoid_s_mesh_brake_counterfactual.log. 음수target/no-brake침투확인과제동min>=0/actualA<=1을모두확인전인증금지.
3. 새sourcehash+새반경기준으로V-S coll_job sweep/chest/jump/twist독립요청. 작은reference반경은더큰clearance를주므로보수적이아닌낙관적수치,새MESH반경컬럼이필수.
4. 양쪽차단점이데이터로해결되어도전면hold/실제경고UI/토글/비정상초기상태/빠른전환확인전defaultON추천보류. 현재권고defaultOFF+실험UI토글/정지이유경고. 커밋/5080접촉없음.
### exec1047 완료 최종 수치
- 명시적unsafe IKgoal min=-40.619596mm,무제동동일목표실제min=-54.533938mm로진짜침투대조확인.
- 제동latch t=.04s,이후.81s정지,actualmin+13.697055mm,실제가속비.392814/속도비.120622,statejump0. 선택한동일위험목표시나리오에서실제제동·침투방지측정PASS(보편인증은아님).
- 이실행49pose메쉬audit미포괄0mm(새로저장된보수적정지경로표본이므로이전광범위49pose의최대.307889mm결과도같이보존;다양성축소를개선으로과장금지).
- **새프로필+제동ON 렌더FAIL:**857장/29.959466s=28.571938fps<29.7,maxgap126.49ms,양팔IKp95상태max14.311ms/개별p953.03025ms(33ms내),servo tickp95상태max41.86ms. HTTPerrors0. 끝load2.21/2.06/1.81.
- 따라서모델메쉬표본/제동한정시나리오가통과해도**기본ON불가**. 성능회귀와전면hold/경고UI가남음. 현재defaultOFF유지+실험토글제안이타당.
- 새긴급제동후에도IK/goalprojection을매관측계속반복하는중복비용/비가용목표warmbranch비용을다음프로파일링. 정지latch중정적goal을cache/안전한명시resume상태로전환해불필요solver를줄이되재개안전경로검증필요.
- exec1047완료,다음세션에서재폴링불필요. summary/raw/render모두bench/humanoid_s_out영속. 5093finally종료경로실행,다음첫callss로listener없음재확인할것.
# P1c 성능 라운드 11/5 14:15~14:25 (기본OFF)
- 단계계측servo.profile(ik/retarget/projection/brake/integration/total_ms,IK/투영_fk_calls) 및IK/geometryFK counter추가.
- beforeprofile22s/1100ticks: allp9515.908ms,movingp9528.016/latched12.965ms. projectionp95moving14.584ms,latched6.624ms. latch중에도IK FK p959회/투영FK6회불필요반복확인. load2.92시작/2.63끝. bench/humanoid_s_out/profile_before.json.
- 최적화: latch즉시IK·투영skip(트래킹hold),goal17joint변화2mrad미만이면직전절대안전투영해reuse,13쌍AABB하한으로activepairnarrowphase/Jacobian만계산,수정없는project는중복최종FK없이1회결과반환.
- 불가goal: 5iter투영실패시현재cmd→goal직선에서최초불가구간까지8분할+6회binary로최대안전fraction시도(전역최적IK해주장아님). 양수fraction/목표미침투unitPASS. reset은명시latch해제·monitor재초기화.
- collision_state clear/avoiding/holding,goal_projection accepted/modified/progress_fraction/cache_hit/status연결. I-W UI실험토글기본unchecked OFF,hold/회피warning+proxy안전미보장+진단완료,50Hzsnapshot/게시15Hz/UI10Hz유지. W targetedPASS,전체66PASS1기존rtreeFAIL보고.
- S smoke/humanoid/collision **56PASS/19.81s**.
- 새hash env28979bfb62b938ef48c80b7f23a9e142d65ed4ed/ikfcd3fb9eaa8ba76046fee8a01587e7986df117bb/teleopad91f64aa25588ba7e1f3bfa30f5c584fd7563cc/collision996ebffd534cf55f251087d8e3b44ce505b8024c. V-S전달.
- exec1053후계측은total_ms를별도키와**profile에중복전달한bench버그발견,**벤치수정완료**. 프로덕션문제아님.
- exec1053렌더최신W연결포함:30swindow29.970s,866frames,28.862fps **FAIL**,maxgap212.4ms,양팔IKp95max2.765ms/개별1.554ms,tickp95상태max25.93ms **20목표FAIL**. load4.72→5.56로높음. 마지막latchedtickprofiletotal.626ms/IK·투영0/FK0은최적화실행근거(이한tick으로전체p95통과주장금지).
- **기능차단남음:** V-S이전새반경+제동snapshot은4패턴actual범위0도·안전자세/release추종FAIL. 현재최적화가**제동margin의worst-joint-stop상계가restclearance17mm보다커서즉시latch하는문제와자동safe-targetrelease문제를고치지는못함**. latchskip은성능개선이나기능동결해결이아님. margin단순축소는최초실제-20mm침투재발위험. 참조계획경로의가용안전통로/방향성stopbound+추종오차/명시resume재설계후독립검증필요. 현재기본ON비추천.

## 10분 재개지점
- **exec1057**: /mnt/c/Users/USER/.aside/u/0/s_collision_fast_retry.sh. measure→gpu-w900,획득당295s로수정후profile_after.json+20261105_collision_fast_render_retry.json생성중. 조용한현재창재측정결과poll.
- 1053정상종료/5093listener없음14:24:12확인. 1057이5093사용시끝나면자기서버finallycleanup확인. 5080접촉/commit없음.
- V-S에는latesthash전달하고우선static/release빠른기능FAIL확인요청(FAIL이면불필요4패턴longrun보류). rest상시latch해결전전체P1cPASS불가. I-W연결완료UI는V-W검증대기.
# P1c 기능 동결 해소 시도 14:26~14:36
- 부모/V-S힌트반영: worstjoint절댓값stopbound를폐기하고pair gradient로법선접근속도/추종오차투영. stationary/separating시static3mm만,현재/참조법선접근v최댓값으로margin=3mm+v²/(2*.04)+v*.18+양수법선trackingerror. a=.04m/s²,latency180ms는empirical보수값이며보편인증된물리상한아님.
- 실제v만사용한중간안은trigger.08s/min-7.5799mm침투FAIL. 참조v도현재법선으로포함해phaselead하면trigger.06s/actualmin+5.971858mm/A비.656429/속도비.223470/stop+.984s/statejump0. unsafegoal-40.62/no-brakeactual-54.53동일대조에서한정PASS.
- 자동release: 모든근접pair접근v_n<=1e-4m/s,실제max|qd|<.02rad/s,clearance>static3+hyster2=5mm. C2p/v/a절대reset안함,servocmd만actualpose로재seed하고IK/goalcache무효화해추종재개.
- 충돌검사_retarg/newinput30Hz내부에서**50Hz공통tick으로이동**. 관측없어도제동·재개동작,중복FK안함. 30Hz관측검사면40ms공백으로20ms주기bench의안전마진이유효하지않을수있어필수수정.
- directional오프라인22s프로파일(공통50Hz이동직전,계측값은참고): allp955.292/moving12.328/latched2.105ms. latency검사stage는최신소스에서brake_ms에정확포함.
- 회귀**57PASS/12.31s**(정지rest에서latch미발생/수동latch자동해제/in-flightlatchIKskip/reset/부분안전접근포함).
- 최신해시env3a49949fbc6a3de713f5abdaada863012b1fef54/ikfcd3fb9eaa8ba76046fee8a01587e7986df117bb/teleop191db4b9d74d50119a319689036822adbfcf3a17/collision996ebffd534cf55f251087d8e3b44ce505b8024c. V-S에static12/release먼저,통과시4패턴요청.
- 이전frozen최적화(exec1057) 조용한FPS32.0263PASS이나tickp95상태max24.5FAIL,offlinep95.245는99%정지의통계라새방향성기능수정본PASS아님.

## 재개
- **exec1062**: s_directional_gate.sh. 57tests완료후measure→gpu-w900대기/검증중. bench/humanoid_s_out/20261105_directional_runtime.json 및directional_render.json. 25초실제qraw는collision_runtime_path.npz 덮어쓰므로완료후이름버전복사·armrange deg추출권장. 양팔이실제로움직이는지/침투0/정적12추종/chest3s→abd45복귀8s≤8deg를모두봐야기능PASS.
- V-S실제정적/복귀결과대기. clearance에서멀어지는방향허용은접근v_n부호로처리,실제v와참조v부호가반대인관성구간은실제접근이남으므로제동유지할수있음.
- 여전히defaultOFF+실험토글. 5080접촉/commit없음. 자체5093은1062finallycleanup예정.
### exec1062 완료: 방향성 실제 동적 스윕 **FAIL**
- 실제actualmin **-0.949406mm**,penetrationchecks34,uncertifiedintervals77; refmin-.740615mm,penetration29,uncertified45. 개별unsafe목표+5.97mm한정PASS를일반스윕보장으로확대하면안됨. 아직현기본OFF필수.
- servo tickp953.565ms(offline)/렌더상태p95max15.27ms로20ms목표PASS. 양팔IKp95max5.416ms.
- renderer880frames/30.017335s=**29.28308fps FAIL**,maxgap2611.95ms(원인미확인;제거/클립해서PASS금지). load.93→.90,HTTPerrors0. collision_state최종clear→기능전체동결만은벗어났으나추종정확도는V-S결과대기.
- 다음우선안전문제: 재개threshold5mm근처에서제동/해제반복으로이미작은clearance에속도가누적될수있음. 제동중법선추종오차·미래referencea/jerk반영,release는거리만이아닌안전goal방향/계획경로검증을포함해재진입관성을막아야함. 무조건a/latency를키워동결복귀시키는해법은원요구충족못함.
- 1062종료. directional_runtime/render JSON영속. rawqpos는directional_runtime_path.npz로별도보존,armrange는directional_motion.json. 5093finallycleanup실행됨. 다음단계V-S기능결과와함께FAIL유지.
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