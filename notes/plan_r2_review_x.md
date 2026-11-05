# 다음 개선 계획 r2 구현 검토: R2-X(Codex)

검토: 지정 초안·근거 문서와 sim/humanoid_{ik,retarget,teleop}.py, web/humanoid*.py, web/{sim_worker,app}.py, tools/teleop_tracker_win.py 정적 읽기. 코드/서버/추론 실행 없음. 쓰기는 이 파일만. HEAD=1da4b93 확인. git status는 UNC 조회 timeout으로 완료 못 해 clean은 주장하지 않는다. 아래 소요·새 기준은 계획 제안이며 신규 실측이 아니다.

## 1. 핵심 판단

- A1 팔 길이 정규화는 이미 존재: humanoid_teleop.py:126-127에서 u1/u2에 로봇 L1/L2를 곱해 E_t/W_t를 만든다. 재구현보다 원인분해가 먼저다.
- A5 전제도 낡았다: tracker:222-234는 2손 minimum-sum 전수 1:1 할당이다. 2x2에서는 전역최적이므로 Hungarian 교체 삭제. 교차/가림/재등장 회귀와 엄지 대립 시험만 남긴다.
- 관절각 ≤8° 대신 FK 상완/전완 방향과 손목 위치를 주지표로 한다. 사람→로봇은 관절분해가 다르고 IK 해가 비유일하다.
- A2 soft 반발항이나 contact ON만으로 관통0 보장은 불가능. 양팔 결합 후보·명령 이동경로·실제 물리 q까지 검사한다. 보장 범위는 정해진 캡슐 근사와 시험세트다.
- 손실 시 자동 중립은 위험하다. 복귀가 몸통/반대팔을 통과할 수 있으므로 안전 감속 hold가 기본, 중립은 충돌 검사된 명시 옵션으로 둔다.
- 권장 순서: P0 입력/수명주기 → A1 진단/개선 → A2 → A7 폴백 → A3 품질 → A6 카메라 준비. A3 계측/A4 웹 안정성은 sim과 병렬. C/P/T는 재측정부터, E 배치는 마지막.

## 2. 코드에서 추가로 보이는 결함·기술 부채

1. **혼합 pose 행 길이**: web/humanoid.py:26,47은 각 행의 길이3/4를 독립 허용한다. 33행 혼합이면 servo:97 np.asarray(..., float)의 ragged ValueError가 worker 종료로 이어질 수 있다. 전체 행 길이를 통일하거나 ingress에서 정규화해야 한다.
2. **퇴화 입력**: torso_frame/palm_frame은 동일 어깨·0길이 팔·일직선 손에서 유효 회전행렬을 보장하지 않는다. norm/cross/직교성 검사, 마지막 유효 frame 유지, invalid 진단 필요. visibility 범위도 계약화한다.
3. **부분 가림 hold 불일치**: servo:122-124는 tracking=false 후 continue만 하므로 des는 이전 목표다. 팔이 이전 목표까지 계속 갈 수 있다. H=None 때 손가락도 이전 des를 향한다. 그룹별 des/cmd/vel 감속 정책을 명시해야 한다.
4. **손 회전 task 단절**: H=None이면 R_t=None(:128-133)으로 목적함수가 바뀐다. 검출 62/89 녹화본 같은 끊김에서 팔/손목 점프 위험. 신규 A7로 처리한다.
5. **reset 보정 의미**: reset_state:49는 B0=B_CAM으로 초기화하면서 calib_seen을 보존한다. 같은 marker는 다시 적용되지 않는다. 보정 유지/초기화 중 하나로 API 의미와 상태를 일치시킨다.
6. **G1 record/replay 누락**: tracker:265 record는 Panda features만, :55-57 replay는 mode 무관 /teleop/update만 전송한다. 현재 replay는 G1 수락시험 재현 도구가 아니다. pose/hands/options/seq/capture 시각 v2 schema가 필요하다.
7. **수명주기**: Runtime.status는 process가 죽으면 state만 off로 덮어 cached enabled와 불일치 가능. start/stop 경합, join 중 재시작, 재시작 잔류 frame/sample/status-cache, G1 crash 후 Panda render_pause 복구 경로를 시험해야 한다.
8. **운영 관측**: capture_latest는 camera read 실패 시 break만 하여 seconds=0이면 대기 지속 위험. 카메라 분리 신호·재시도/종료 정책 필요. preview 예외 무시, latest-only overwrite/drop 미노출도 기술부채다.
9. **후순위 IK**: _cost는 elbow 항을 제외하며 restart의 성공/최선 선택 목적함수가 다르다. 온라인 restarts=0에는 영향 없지만 offline 해석 주의. nullspace 조건 J.shape[0]<7은 rank 조건과 다르다.
10. **근거 최신성**: 현재 worker는 render thread+별도 MjData snapshot 구조다. changes의 초기 JPEG future 설명을 그대로 새 구현 근거로 삼지 않는다. render_ready는 있으나 API/브라우저 ready 계약은 없다.

## 3. 항목별 구현·소유·합격·소요

소요: 구현자1인 작업일(6~8시간) 추정, 카메라/GPU 대기 제외. 테스트는 고정 replay와 독립 검증자 측정으로 수행한다.

### P0/A4 입력·상태·시작 안정성
- 난이도 중, 구현0.5~1.5일+검증0.5일.
- 소유: 웹 페어 web/humanoid.py, humanoid_worker.py, 필요 시 static/humanoid.js. sim reset/hold는 sim owner에게 요청.
- 구현: uniform pose shape, 퇴화/visibility 계약; requested mode·process state(starting/ready/stopping/off/crashed)·servo state 분리. generation별 cache/frame/sample 초기화, bounded start/stop, 실패 시 Panda 렌더 복구. 첫 JPEG/ready 이후 스트림 연결+로딩 UI. 미사용 G1 상시 프리워밍으로 자원을 점유하지 않는다.
- 합격: 혼합행/비정상 입력400+worker 생존. ON/OFF/중복요청/worker실패/재시작/reset/보정 각10회에서 stale frame·고아 worker·pause 잔류·상태 모순0. start→ready와 ready→첫프레임을 따로 기록. ready 후60초 최대 gap100ms 제안, cold-start 총시간 목표는 baseline 후 확정. 1.7초 정지는 아직 원인 확정 아님.

### A1 팔 자세 정확도
- 난이도 상, 진단0.5일+개선1~2일+독립검증0.5~1일.
- 소유: sim/humanoid_ik.py, humanoid_retarget.py, humanoid_teleop.py, tests/test_humanoid*.py, 별도 bench/verify_r2/.
- 진단: reachable/unreachable 대칭 FK 세트, iters4/8/12/16, rotation/elbow on-off, 가중치, clamp 빈도, 초기값을 offline sweep. 고정 S가 initial shoulder_roll_link 위치이므로 어깨 관절축/사이트 오프셋 근사도 검사. 반복 증가를 자동 온라인 채택하지 않는다.
- swivel 구체안: a=unit(W-S), n=unit((E-S)-a*(a·(E-S))). 목표와 현재 n 사이 signed angle=atan2(a·(n×n_target), n·n_target). 기존 absolute elbow3행을 scalar1행으로 대체한다. 사람 목표도 이미 정규화된 로봇 길이 W로 같은 축 기준을 사용한다.
- Jacobian: S/E/W point Jacobian으로 축·투영을 미분. S가 움직이는 모델이면 shoulder Jacobian도 포함. finite difference는 offline 검산용만. 직선/완전접힘/작은 직교성분에는 직전 swivel 유지 또는 weight0, angle unwrap 적용.
- 위험: wrist3+rotation3+swivel1=7행으로 여유를 다 쓰고 현 nullspace 항도 꺼진다. 3→1행은 중복을 줄일 뿐 정확도 개선 보장 아님. m/rad 잔차 스케일·가중치 제곱효과 정규화. wrist를 1차, 허용 위치오차 내 swivel/rotation/rest를 2차로 푸는 제한된 계층화와 비교한다. full QP는 필수 범위 아님.
- 합격: 고정 reachable static 세트 settling 후 각 표본 FK u1/u2 방향≤8°, wrist≤10mm, 좌우 대응 오차차≤3°. 동작은 p50/p95/max+lag 별도 보고. unreachable은 경고/유한 명령. 관절각≤8°는 로봇 FK 생성 GT의 보조지표만. 4절 성능 gate 적용.

### A2 자기충돌
- 난이도 상, prototype1일+hardening2~3일+검증1일.
- 소유: 같은 sim 페어가 A1 뒤 순차. 신규 sim/humanoid_collision.py, env proxy 계약.
- 구현: torso/양팔 upper·forearm 캡슐 signed distance=segment distance-r1-r2. 인접 접합 제외쌍, 손/손목 포함 범위를 명시. 고정 소수쌍 broadphase, margin 이내만 closest-point normal과 point Jacobian 차로 반발/제약항. 겹침 normal은 안정 fallback.
- per-arm solve의 qfull은 반대팔 새 해를 반영하지 않는다. 양팔 후보를 full q에 결합한 공통 후검사 필수. 좌우 순서편향 시험, 필요 시 교대 보정1회만 허용하여 시간 상한 유지.
- soft항 뒤 acceptance guard: 실제 q·양팔 cmd·다음 적분후보와 사이 경로를 검사, 이전 안전 command로 제한/안전감속. 유한 경로샘플만으로 연속안전을 주장하지 않고 최대 joint step/거리변화 bound와 braking/tracking 오차로 margin 설정. actual q는 offline physics-step 단위 검증. 이미 충돌한 상태 hold는 복구가 아니다.
- contact ON은 보류: env:128 전역 CONTACT disable 해제 외 pair filter/geom/position actuator와 contact solver 힘 경쟁이 생긴다. 선택쌍 안전이 플래그 하나로 되지 않음. full14DoF QP/전신접촉은 후속.
- 합격: rest/self-touch/교차/몸통쓸기/역방향/빠른전환/dropout/stale 세트에서 command와 actual proxy d<-1mm 프레임0, min d 기록. 1mm는 수치 판정오차 제안이며 관통 허용목표 아님. 실행 margin은 별도로 수 mm 이상 튜닝. 불가능 목표는 안전 fallback, 활성률/정지율/step 보고. visual mesh 관통은 문제포즈 별도 시각검증. 안전 때문에 포기한 표적에 A1 정확도 gate를 동시강제하지 않는다. 팔-몸통/반대팔 범위이며 손가락·얼굴·환경 전체 보장 아님.

### A7 신규: 손 검출 끊김·상체 프레임·퇴화 폴백
- 난이도 중, 1~2일+검증0.5일. 소유 sim 페어(A2 뒤), tracker 필요분은 단독 owner 요청.
- 마지막 손 회전 유지+confidence/timeout에 따른 weight 연속전환. pose 손 점 회전 폴백은 신뢰도 검증 후 적용. ID 재할당/장기소실 후 OneEuro reset. 부분 팔/손가락 hold를 명시하고 hips 비가시 pitch=0 정책 공개.
- 합격: 62/89 손검출 영상+dropout/교차/재등장/상체만 입력에서 crash/NaN0, cmd 속도·가속 제한 위반0. 검출경계 회전점프 baseline 최대 대비50% 감소 제안(거의0 baseline은 절대한도 병용, 진단 후 고정), actual q overshoot 별도. 합성만으로 실검출률 PASS 금지.

### A3 지연·떨림·버스트
- 난이도 중상, 계측0.5~1일+튜닝1~2일. 웹 페어 web/humanoid*.py, tracker/JS는 단독 owner, sim은 seq/applied-seq 계약.
- sample seq와 capture/infer/send/receive/apply/render/publish/browser decode 시점을 연결. snapshot에 applied seq를 넣어 비동기 JPEG와 매칭. received_at 대신 seq를 관찰 ID로, 로컬 age는 monotonic 사용. Windows/WSL monotonic을 직접 빼지 말고 clock offset/불확도 기록.
- 현재 latency_ms는 추론 후 sent_at→서버 도착뿐이다. 최초 command 반영과 tau=.06/속도·가속도 제한에 따른 실제 운동 응답도 다르므로 분리한다.
- 합격 제안: receive→해당 seq 최초 JPEG publish p95≤80ms는 baseline 후 확정. capture→화면120ms는 실카메라·clock 보정 후 장기목표. 10-90% 운동 응답은 표적크기별 별도 보고. 정지 녹화 구간 확보 뒤 settling 후 torso 기준 wrist std≤3mm(각축/3D RMS 정의). 무노이즈 합성은 수치안정성만.
- arrival p50/p95/max, age/drop부터 측정. latest-only·bounded pacing 유지. 균등 도착률을 만들기 위해 FIFO로 오래된 입력을 쌓지 않는다.

### A5 수정: 할당 회귀와 엄지 대립
- 난이도 소, 0.5~1일. sim 테스트는 sim owner, tracker gate/ID는 tracker owner.
- Hungarian 신규구현 삭제. 2손 최소합 반례/1손/가림/교차/재등장 fixture, visibility·거리 gate .3 회귀. 엄지 flex/opposition 좌우 부호·range·손끝거리 수동라벨 시험. 현재 식이 좌우 동일하다는 이유만으로 버그 단정 금지.
- 합격: 할당 fixture 전부 통과, 지정 sequence ID 혼선0, 엄지 대립/펴기 반응방향·범위 통과, 검지/중지 회귀0.

### A6 실카메라 수락도구
- 난이도 중, 0.5~1일+실행0.5일(연결대기 제외). tracker owner, 신규 tools/humanoid_accept.*, bench/verify_r2/.
- record v2/replay가 선행. 명령1개: 카메라/모델/서버 ready·중복 tracker 확인→60초 수집→raw manifest/report. 자원 없으면 blocked/skipped이며 합성으로 대체 PASS 금지.
- 합격: 기록재생 report smoke 후 연결 시 소스30fps/수신/preview/robot FPS 따로 측정. pose/left/right/both-hand 검출률은 라벨된 가시구간 분모. 비율 gate는 실제 양손 양성세트 확보 후 고정.

### C/P/T 기존 파이프라인
- C: 난이도 중, 준비0.5일+실행0.5~1일(수정 별도). 소유 sim/{control,grasp,ik}.py와 worker pick/place/home. N20×mustard/box/cup/multi fixed seeds 회귀, 장애물 home negative. default N10=10/10의 N20 유지 시험, 예외 포함 분모와 pick/place/home 분리. 방해물은 회피 또는 명확한 안전실패, 무접촉/물체이동<5mm/q오차<.02rad. assist-off mustard place0/10은 알려진 실패이며 물리파지 PASS로 일반화 금지.
- P: 난이도 중, 준비0.5일+GPU측정0.5~1일. 소유 perception SAM/web select·segment. verify_p에 독립 r5 0/84가 이미 있어 frozen84+현재hash 회귀로 표기. IoU<.5 실패0/84 유지, median/p10/min 보고. FP paired baseline/current 자세오차·성공률·cold/warm p50/p95. ~1mm/1.5°는 잠정참조로 symmetry와 함께 gate 확정; latency 비회귀10% 제안. 하네스 selector와 r5 정책 일치 여부 manifest 확인.
- T: 난이도 중, 측정0.5일, 실패수정1~2일. tracker --mode panda로 OFF/ON-idle/ON30Hz A-B-A 동일부하 재측정. Panda 기본 pipeline off이므로 G1 결과 대입 금지. 실제 HTTP main FPS 감소<10%, preview/input≥29.7Hz(30목표 허용오차), 안전/방향/집기복귀 회귀0. 실패 시 sim/teleop tick/status profiling. worker 수정은 C 뒤 순차. verify_t r4 원/사각 동작품질도 회귀.

### E 평가
- 난이도 실행 중, 준비0.5일+배치1~3일 예상, smoke 처리량으로 ETA 갱신. eval/run_benchmark.py, eval/harness/, eval/report/, bench/eval/ 소유.
- FP N30/object=90 trials, gt/fp×assist on/off×N20/object=240 trials. cold register 약50초 기록 반영.
- 합격: 예정분모 전부 row(예외/timeout 포함), hash/seed/config/GT사용/원시예측/등록·추적 wall time/VRAM, Wilson95와 per-object 독립재계산. GT wiring PASS와 FP/physical 성능 구분. assist-off 성공률은 기대치 맞추는 PASS 아닌 관측결과. oracle click/identity와 symmetry 공개, 기존 출력 덮어쓰기 금지.

### P4 엔지니어링
- 난이도 중, 0.5~1일. 전용 launcher/README/.gitignore owner.
- Windows 독립 supervisor+PID/port manifest/readiness/log/명시 stop 우선. worker parent PID 감시와 호출 세션 종료를 함께 고려. 작업 스케줄러는 사용자동의 후 선택, 기본 user 권한.
- 합격: 호출셸 종료 후 자기 서버/트래커 생존, 재실행 중복0, stop은 자기 PID만, 5080/타세션 비접촉, README 재현. ignore 추가만으로 tracked 파일은 제거되지 않음.

## 4. 30fps 예산·측정 계약

- period33.33ms. render 약15ms 외 JPEG/mj_forward/publish가 필요. servo/render 별도스레드여도 CPU/GIL/BLAS/GPU 경합 공유이므로 단순 합산이나 독립보장 금지.
- verify_r R5는 45초전체 약29.99Hz, robot31.8~31.98fps, IK p95 2ms/tick p95 6.2ms. 다른 부하의 tick22.5ms를 같은 실행의 동시 예산처럼 더하지 않는다. arrival burst/cold gap1735ms는 별도 미해결.
- A1 restarts=0, 온라인8회부터 유지. 양팔solve 합계 신규입력 p95≤2ms, tick p95≤8ms를 R5 저부하 비회귀 목표로 제안. baseline이 미달이면 동일조건 paired 비교+원인 공개 후 재합의, 과거22ms를 새 ceiling으로 삼지 않음.
- A2 활성쌍 analytic Jacobian/고정회수/scratch 재사용. 14DoF 수치미분×쌍×8회나 모든 mesh 검사는 실시간에서 배제. 거리/guard 추가비용 p95≤1ms는 prototype 목표일 뿐 미측정. 초과하면 설계/범위 재검토, 안전항을 조용히 끄고 FPS PASS 금지.
- 전역 measure lock 아래 fixed replay60초×3회, 앞5초 warmup 별도·cold10회 별도. 실제 JPEG 개수/정확 wall구간 사용. 30초창 robot≥30fps, input/preview≥29.7Hz·처리비≥99%는 기존 부모 허용오차 유지. status FPS만으로 판정 금지. gap p95/max, seq drop/age 병기.
- 무입력/정지/일반동작/충돌최악 분리. 신규solve와 hold tick 혼합 금지. render_ms EWMA는 p95가 아니므로 raw hist 추가. rtf≈1·실제 q 한계 확인.
- load/CPU/BLAS threads/해상도/JPEG/GPU사용/port/PID/source hash 기록. 카메라분리/중복 tracker/동시입력 run 분리. nvidia-smi 기록은 부하제거 자체가 아님.

## 5. 소유권·병렬화·락

1. sim 단독 페어: A1→A2→A7→A5 sim 시험. humanoid_ik/retarget/teleop/env/collision 독점. 같은 servo 동시수정 금지.
2. 웹 페어: P0/A4→A3, web/humanoid*.py/G1 JS. sim과 seq/ready/diag schema 먼저 합의 후 병렬.
3. tracker 단독 owner: teleop_tracker_win.py 전체. A3→A7 필요분→A6→T 큐. T 초기측정만 병렬가능, tracker 수정 금지. Panda/양손/G1 모두 회귀.
4. web/app.py: P select/segment/tracking metric, 통합owner blueprint/lifecycle. C API forwarding은 통합owner 요청. 파일전체 재포맷 금지, 섹션diff 인계.
5. web/sim_worker.py: C pick/place/home 종료 후 T tick/publish. G1 pause/crash 공통분은 통합owner 한번 반영. 독립페어 동일파일 동시쓰기 금지.
6. R5091/5092, C5085/5086, P5083/5084, T5089/5090. 5080 사용자서버 중단/재시작/측정독점 금지. 자기 listener PID만 종료.
7. C가 지적한 mesh_spec collision-hull 공용파일 생성 race 때문에 포트분리만으로 안전하지 않음. per-run 격리/원자생성+락 없으면 SimEnv 생성 자체 serialize. measure/GPU와 별도 자원.
8. /tmp/rp_measure.lock로 측정 직렬화, 다른 참여작업도 측정 중 부하를 만들지 않는 계약. GPU는 /tmp/rp_gpu.lock. 둘 다 필요하면 measure→gpu 고정순서, 대기시간 기록. nice19는 GPU/메모리 격리 대체 아님. E와 FPS측정 겹치지 않음. 동시에이전트≤8.

추천 일정: P0/계측+sim진단+P/C/T준비 병렬 → A1/웹안정성 병렬 → A2/A7순차(C/P/T측정 슬롯 직렬) → tracker A6/회귀 → E야간. critical path 약6~10작업일+E실행/카메라대기, 실패수정량에 따라 변경.

## 6. R2-C 합의·이견

상대 a0mcVx7IEyvC6h2c(R2-C Claude). 내가 A5기구현/A1정규화·7행nullspace/A2반대팔qfull/혼합행 검증 위험을 먼저 전송했다. R2-C 1차 의견 수신 후 swivel·충돌 구현/소요/소유권을 회신했고 합의안 및 '전부 동의, 남은 이견 없음' 회신을 받았다. 추가 결함/지연기준 조건도 전달했다.

합의: A5 Hungarian삭제, A1원인분해→FK기준→필요시swivel; A2동시후검사·중간경로 필수/접촉ON 기본안 보류; P0우선; sim순차·웹병렬·tracker단독; A7검출끊김/hips비가시 추가; 정지녹화 전 jitter PASS금지; 서버지연·capture/화면·운동응답 구분; 80/120ms는 아직 검증되지 않은 계획값. 소요는 R2-X추정 공통채택.

잔여 이견 없음. capsule 크기/margin, 실카메라 검출률·지연 gate, 정지 녹화 확보, cold-start 원인은 구현 전 baseline/데이터 확보 조건으로 미확정이다.
