# P1c S4 구현 1묶음 (2026-11-09)

## 상태
- **NEEDS WORK, 기본 OFF 유지**, 커밋 없음, web/* 수정 없음, 5080 미접촉.
- 10Hz latest-only 계획을 50Hz 서보 밖으로 분리. 서보는 완료 결과 poll + 0.04rad 국소 목표 + 정확 FK 3회 후검사 + 기존 CBF/실제 q monitor 유지.
- 0.5초 이상 늦은 결과 또는 목표 차이 0.35rad 이상이면 hold. 계획 없는 동안 hold.
- sampled path를 연속 안전 인증으로 승격하지 않음. 500Hz monitor 미인증은 그대로 노출.

## 구조 선택 근거
- 별도 Python 스레드: 4초 GT 보조 A/B, ON tick p95 sweep28.29/chest98.59/jump26.62/twist48.37ms. GIL 경합으로 실패.
- spawn 프로세스 1차: sweep p95 9.39ms, 최초 ON tick 1519.77ms로 초기화 스파이크 실패. 해당 코드 tests/test_humanoid.py 57 PASS(27.30s).
- web worker daemon=True여서 multiprocessing 자식 생성은 운영 불가. 부모가 daemon=False 변경 불승인.
- 최종 수정: subprocess + socketpair/Connection, 모델 pickle은 별도 시작 스레드, 부모 PID 100ms watchdog, close terminate→wait1s→kill→wait1s, 파이프 닫기. 최종 수정은 실행 중 검증 전이며 이전 57PASS를 이 blob에 적용하지 않음.

## 한계/미완
1. 최종 subprocess 성능, G/H 정상종료·kill -9 잔존 0 검증 미완.
2. chest 고정 목표 진동 제거, twist OFF 대비 관절범위, 정적12자세 ≤8도, chest→abd45 8초 내8도 미판정.
3. thread 시도 twist 미인증23(침투0): 기능/안전 전체 통과 아님.
4. 30초 창29.7fps 미측정, A/B bootstrap CI 미계산. 현재 벤치는 실제 q500Hz·합성GT 보조이나 실시간 deadline 초과를 복구하지 않아 처리율 인증으로 쓰지 않음.
5. planning path48샘플 유지. 국소3샘플 후검사는 저비용 gate일 뿐 연속경로 인증 아님.

## 파일
- sim/humanoid_collision.py: 비동기 subprocess planner, GIL 분리, PID watchdog.
- sim/humanoid_env.py: ON 생성/OFF·reset·close 정리.
- sim/humanoid_teleop.py: 비동기 계획 읽기/국소 gate/holding 재probe.
- bench/humanoid_s4_async.py: 4패턴 OFF/ON 실시간500Hz·범위·monitor 벤치.
- tests/test_humanoid.py: planner 생성·latest·종료 1테스트.
- notes/humanoid_s4_changes.md: 본 문서.

## 재개 지점 (마지막 갱신)
- exec1001 완료(thread, 측정중 소스 교체로 신규test1FAIL/기존56PASS), exec1003 완료(spawn sync, 57PASS).
- exec1009: /tmp/s4_round3.log (spawn 백그라운드 시작판; 현재 최종과 다름).
- exec1010: /tmp/s4_round4.log (최종 subprocess판), 측정 락 대기/실행 중. 반드시 완료 후 결과를 별도 파일로 동결.
- 원자료 bench/humanoid_s4_out/async.json은 각 실행 overwrite이므로 round별 로그를 우선 확인. /tmp/s4_round*.log 보존.
- 재현: source sim_test/gl_env.sh; export PYTHONPATH=$PWD; flock -w 900 /tmp/rp_measure.lock -c '/home/user/anaconda3/envs/robot_percept/bin/python -m bench.humanoid_s4_async && /home/user/anaconda3/envs/robot_percept/bin/python -m pytest -q tests/test_humanoid.py'
- 최종 blob collision8cec2a536519a6df0b1ebe651e77ef07a73415a3 / envf5a864b12ed5db59e9d87c979e6556d609c42eb8 / teleop2081391601105555a7c8e01ffaa90ae6d9f6b1c8 / testsab044632c6b29b78a5eaf2740ca2783479ef129e / benchbfe5f9caf958053892d1c6f310aaad907cb0af63.
## 2라운드 (2026-11-09, 12:06 갱신)
### 수집 완료: 초기 subprocess판 84b9a21b
- 원자료 round4_async.json, round4.stdout, sweep/chest/jump/twist_0/1.npz. GT 보조, 각 OFF/ON 4초(완전한12초 sweep주기 아님), 실제q500Hz 저장.
- ON tick p95: sweep13.10 / chest3.20 / jump15.54 / twist16.73ms.
- 첫 tick=max:153.73/109.22/102.70/78.01ms →40ms FAIL. 첫 tick 제외 max21.58/7.12/20.36/23.57ms.
- 침투체크0 전패턴, 미인증0/0/0/2 →안전기준 FAIL.
- 최대 관절범위ON/OFF sweep74.07/76.15°,chest0/103.98°,jump15.64/87.43°,twist67.54/74.99°. twist약90%는초기접근포함이라지속비틀기회복인증아님.
- chest는4초창계획완료0개, 접근실패. 장기고착여부는이창만으로미판정.
- 선택회귀58PASS/20.45s. 최종후속수정에이PASS를이식하지않음.

### 후속 수정
- 초기submit이child준비전이면버려지고,동일입력collision latch시재submit되지않아영구무계획가능한교착발견.
- collision0bcf7253aadcf1d51af91458deaf8132540ec216: pending보존,latest poll에서준비후송신.
- testsdd0f739109b7f96efde7ef48238be77ea2e53c3a: 시작전8회submit→나중latest결과검사,즉시OFF3회누수검사.
- 부모다음방향: G1준비중planner사전기동/더미계획,planner_ready노출,ON→ready시간과ready후성능분리. 아직미구현. 현재ready전hold이지빠른안전투영fallback아님.

### 준비/실행한 새 벤치
- bench/humanoid_s4_lifecycle.py: 5093정상TERM2회·KILL2회,planner포함자손잔존·신규shm,collisionON/OFF10회,fullmodeON/OFF3회. 다른서버가5093사용중이면중단. 실패정리는포착한자기자손만.
- bench/humanoid_s4_function.py: 순차12자세OFF/ON 각4초, chest3초→abd45 8초, 방향오차/미인증/침투. 완료후같은슬롯최종4패턴재측정자동연결. 합성GT보조.
- bench/humanoid_s4_async.py: 첫tick/steady별도,500Hzqpos+tick원시npz,load/GPU/동시프로세스기록.

### 재개 지점 (이 항목이 최신)
- exec1010 완료: round4는84b9a21b판.
- exec1014 실행 중(PID15613shell,15622 flock): 1슬롯 measure→gpu, timeout280초, 전체pytest→lifecycle. /tmp/s4_r2_job1.log, bench/humanoid_s4_out/pytest_all.txt,lifecycle.stdout,lifecycle.json.
- 이후 동일exec1014가락반환후재획득: function→최종async. /tmp/s4_r2_job2.log,function.stdout,function.json,async.json(최종),*.npz(최종으로overwrite).
- V-S3 EaLlhRBFShBul3O0에기존숫자/교착수정/소스blob/재현명령전달완료,독립판정대기.
- 정적/복귀/종료/전체pytest는로그완료확인전까지[blocked:측정락직렬화·실행중]. 30초렌더fps·bootstrapCI도미완. 기본OFF유지,커밋없음.
### 2라운드 마지막 갱신 (12:08, 이전 재개 지점보다 우선)
1. 전체pytest 실행은98PASS/59.98s/5warnings. 단 실행중pending요청수정(12:05:50)이있어최종blob전체를실제로검사했는지모듈캐시증명불가. **최종소스동결후전체pytest재실행필요**. 이전58PASS는84b9a21b판.
2. lifecycle첫시도는하네스ROOT=parents[2]가잘못되어서버ModuleNotFoundError:web로실패. 제품종료회귀실패가아님. ROOT=parents[1]로수정,로그임시디렉터리정리. 잔존측정수치아직없음.
3. exec1014의첫슬롯완료. 두번째슬롯대기중: shellPID15613,flockPID22058. **22527은다른페어T이므로절대종료하지말것.** 현재V-S16723이락보유.
4. 두번째슬롯은timeout280초안에function.py가 lifecycle(내부GPU락추가)→12자세OFF/ON+복귀→4패턴재측정순실행. 현재최종pending수정판collision0bcf7253에서실행예정. lifecycle.stdout대신이번재시도출력은function.stdout에합쳐짐,lifecycle.json별도.
5. 최종blob: collision0bcf7253aadcf1d51af91458deaf8132540ec216,testsdd0f739109b7f96efde7ef48238be77ea2e53c3a,lifecycle533282f270f36ae85e209457bdac8945e7086d2a,function7037f787508a26a7c97c66691d3dee3ad7188358. env/teleop은이전f5a864b1/20813916유지.
6. [blocked] 최종소스4패턴/전체pytest동결재실행/종료·KILL·ONOFF누수/정적12자세/복귀: 측정락직렬화로이번10분구간내완료불가. 실행중exec1014로그수집부터이어갈것. 테스트를통과로추정하지말것.
7. 부모새방향: planner_ready표시,import/model/dummyplan사전기동,ON→ready시간분리. 아직미구현이며최초tick100ms대실패가남음.
## 3라운드 planner_ready (2026-11-09 12:17)
### 구현
- G1 env생성(첫 JPEG/servo 전)에 CapsuleModel + 실제/reference CollisionPathMonitor의3개MjData를할당하고 FK/거리gradient캐시를예열. OFF공개collision_model/monitor는None유지,실제q/ctrl업데이트없음.
- 옵션ON시subprocess백그라운드시작. child import/모델로드/더미rest→rest계획1회(3mm, warmup전용)완료handshake후planner_ready=True.
- collision_status에planner_ready/planner_prepare_ms/planner_child_warmup_ms 노출. worker의기존collision_status통과경로사용,web변경0.
- ready전기존approach_safe부분접근+0.04rad국소3FK후검사+기존CBF/monitor유지. 유효부분목표없으면hold. 연속/실물안전인증아님.
- d58판에서도첫tick79~124ms잔존하여모델pickle.dumps도모드준비단계로이동. 최종05d5a3c2판은prepared bytes를백그라운드에서전송만함.

### 수집완료(d58판, 05판측정과구분)
원자료 ready_r3/measured_d58_{async,function,lifecycle}.json, measured_d58.stdout.
- 정상TERM2회자손6(planner1)잔존0,신규shm0,2.88/3.63초. KILL2회잔존0/shm0,1.55/1.41초.
- collisionON/OFF10회off planner0/on1. fullmodeON/OFF3회old planner잔존0/new1.
- 정적12자세OFF최종방향max2.127도,ON15.865도(up120)FAIL. ONtail max26.449도(hum80),미인증최종8,침투체크0.
- chest3초→abd45:8도내1.18초,최종max1.169도,침투0/미인증0:자체조건충족(독립판정전).
- 4초패턴순서sweep/chest/jump/twist: ON전체p95 11.83/16.68/18.08/16.49ms,첫tick=max78.91/104.21/88.80/124.34ms(40ms FAIL).
- ready후p95 7.47/10.66/16.43/13.36ms,max12.47/13.53/27.84/20.85ms. ON→ready1.418/1.401/1.418/1.459초.
- 침투0전패턴,미인증0/0/0/22 FAIL. chest최대관절범위33.12도(동결벗어남),후반2초범위13.47도라무진동입증안됨. twist전체73.63도 vs OFF74.99도(98.2%,초기접근포함,지속비틀기인증아님).

### 최종 소스 동결 전체 회귀
- collision05d5a3c2004afa93c7ceeb2285015a0cd74a8fcc / env294d0bc190ef33b29bbda5990c153dc3d6100680 / teleop1ed6520e2ae45dfaf0776768ec2c40734d243485 / tests709885eb63c8176c5519ff7315fb15c85048c188.
- 부모지시로기능pytest는락없이실행:98PASS/1FAIL/5warnings/88.38s. before/afterblob파일동일.
- 유일FAIL:기존test_shutdown startup[0.4]에서0.4초시점captured=[](Manager자손아직없음)준비타이밍assert. 잔존FAIL아님. timing-sensitive3파라미터만락재검증대기.
- 원자료ready_r3/pytest_final.txt,pytest_blobs_before.txt,pytest_blobs_after.txt.

### 재개 지점 (12:17 최신)
- exec1014 완료(종료·정적·복귀·d58패턴수집).
- exec1016 락대기취소. exec1017 최종pytest완료(98PASS/1FAIL).
- exec1018 취소후 exec1019 새예약: measure락→startup timing test3개재시도→최종05판4패턴+첫tick단계profile. timeout110초,락대기900초.
- 로그 /tmp/s4_final_dyn.log, ready_r3/pytest_timing_retry.txt,async_final.stdout,async_final.json,async_blobs.txt.
- bench/humanoid_s4_async.py는first_tick_profile(ik/retarget/projection/brake/integration/total)을저장. total-다른단계합으로옵션전환/초기화잔여비용추적가능. solver수학변경없음.
- exec1019미완료면위명령(도구transcript)재실행. 최종05판coldtick개선은실측전이므로PASS금지.
- V-S3에원자료·최종blob·98PASS/1FAIL의타이밍원인·종료/기능FAIL조건전달. 기본OFF,physical_stop_certified=False,커밋없음,web변경없음,5080미접촉.
- 남음: 최종05판tick/첫tick,타이밍재시도,static up120추종·hum80tail진동,twist미인증22,30초렌더fps/CI. 전체NEEDS WORK.
## 4라운드 (2026-11-09 12:27)
### 05판 수집 완료
- exec1019 완료. 준비타이밍shutdown재시도3PASS/2.59초.
- 첫tick sweep/chest/jump/twist 20.11/19.48/16.96/16.09ms: modelpickle를모드준비로옮겨이창의cold79~124ms문제해소.
- 전체p95 17.63/20.85/23.44/16.15ms,max33.81/41.73/59.46/36.81ms. chest/jump성능기준은여전히FAIL.
- 첫tick projection6.4~8.2ms,IK1.6~7.1ms. warmup전체goal에8~17FK중복검사비용이남아국소3FK로변경(아래).
- 05twist미인증12,침투0. 원자료ready_r3/async_final.json,async_final.stdout,*_0/1.npz.

### (a) up120 진단과 수정
- old05 servo스냅샷으로hum80→up120 4초/8초진단. 실제fore충돌쌍거리102mm,planner direct path최소74mm,targetclearance74mm로충분한데holding,planned_path_min=-1.0 위험사유로제동.
- 4초최대28.60도/8초28.17도,cmd_des차이0(hold),실제cmd차이0.01rad미만,rawtarget과cmd차이0.907rad. 즉물리추종오차/10mm margin한계가아닌계획수락·제동고착이다.
- async의candidate/planned_target 0.35rad필터가큰IK분기변경을계속거부할수있어제거. 마지막안전계획을0.5초안에서사용하되현재cmd에서국소후검사/CBF유지.
- 계획없음의path_min=-1을실제hold시작clearance로대체. 계획이없으면명령hold일뿐,원거리의음수clearance를가정해물리제동을걸지않는다. 실제8mm guard·CBF·monitor는유지. margin낮추지않음.
- .04rad/tau.06의인공속도상한.667rad/s도발견: ready국소범위를.12rad로허용하되검사간격≤.02rad(최대7FK,이전3FK)유지. 추종회복/성능은새실행검증전.

### (b) twist 미인증 분해와 수정
- 동일05 q500Hz2000점replay: 기존fixed2mm미인증12/침투0/FK267,adaptive미인증0/침투0/FK1049. 최소실제거리8.722mm동일.
- 실패시점t2.696~3.036초,한2ms구간운동bound4.9~6.1mm인데refresh임계2mm라다음누적bound가이미음수가된뒤늦게FK한것.
- refresh임계=2mm+2×직전step운동bound로조기갱신. 계수는원래waist포함보수Lipschitz그대로,해상도축소/반경축소/침투숨김없음. 실제bound음수이면기존대로uncertified++유지.
- 비용:해당qreplayFK약3.93배. 새실시간q·500Hz/servo성능에서별도재확인필요.
- 새단위시험:작은waist회전구간미인증0,갑작스런1rad점프는미인증1로반드시보고(숨김방지).
- 원자료round4/diagnose.json,/tmp/s4_diagnose.log,baseline_05_teleop.py.

### 동결과 회귀
- 최종collision75b68ce5054e46b769b5ebe8ccd8bd584617f22c / env294d0bc190ef33b29bbda5990c153dc3d6100680 / teleop7d5a3e85a1e6ea76e4f67ec2b2a74169d25e05b3 / testsd0fdfa303bb599375c1066793b9cc922de8c4d47.
- stale고착최종수정전101PASS/68.49초. 최종수정후전체pytest재실행exec1028진행중(락없이,부모허용),round4/pytest.txt와before/afterblob비교필수.
- 새벤치diagnose.py(old05servo+monitor동일q비교),validate.py(12자세OFF/ON+복귀+4패턴),function.py스냅샷(계획/hold/거리/목표cmd차이).

### 재개 지점 (12:27 최신)
- exec1022 diagnose완료(12.0초정적+동일q재생),exec1019완료.
- exec1028: 최종전체pytest실행중. 로그round4/pytest.txt,blobs_before.txt,blobs_after.txt.
- exec1026: 최종재측정대기중,shell53110/flock53116,timeout200초。measure락획득후validate.py→function.json/async.json을round4하위로복사. 로그/tmp/s4_round4_measure.log,round4/measure.stdout。
- 현재12:27 T슬롯50869락보유,뒤S53116→V56275순. **다른페어PID를종료하지말것**。
- 새 투영·adaptive 수정판 최종 실시간 결과는 미수집. 동일 q replay의 0을 새 궤도/실물 안전 PASS로 확대하지 않는다.
- 기본OFF,커밋없음,web변경0,5080미접촉. V-S3에원인·수정전후동일q수치·최종동결정보전달,독립판정NEEDS WORK유지。

### 12:28 최종 재개 정정
- exec1028 완료: **100 PASS / 2 FAIL / 71.86s**, 전후 source blob 동일. 두 FAIL은 기존 shutdown[0.4]/[0.6]에서 captured=[] 준비 타이밍 assertion이며 잔존 FAIL이 아님. 최종102개 전체 PASS로 표기하지 말 것.
- exec1026 validate 시작부에 timing test3개만 measure→gpu 락 안 재시도 추가. round4/pytest_timing_retry.txt 후 확인. 전체 static/release/4patterns 재측정은 아직 T50869 뒤 대기. 최종 solver source는 동결 유지.

## 5라운드 (12:34, 현재 측정표는 cap .12판)
- exec1026 완료. 정적12 OFF최종방향max2.127°, ON2.230°(tail2.231°),up1201.884°/1.30초이내8°도달: ≤8° 자체충족. 정적미인증0/침투0.
- chest→abd45 .72초에8°내,최종1.751°: ≤8°/8초 자체충족.
- 아래는 원복 전 cap .12판: p95≤20ms/max≤40ms 모두충족하지만jump침투가생겨전체FAIL. 최종cap .04판수치로재사용금지.

| 패턴 | tick p95 ms (≤20) | max ms (≤40) | 침투 checks (=0) | 미인증 (=0) | 최대 관절범위 ON/OFF ° |
|---|---:|---:|---:|---:|---:|
| sweep | 10.75 | 21.94 | 0 | 0 | 76.17 / 76.14 |
| chest | 14.53 | 31.07 | 0 | 0 | 37.3 / 103.98 |
| jump | 15.17 | 23.6 | 29 | 48 | 83.34 / 87.43 |
| twist | 9.32 | 34.85 | 0 | 0 | 38.77 / 74.99 |
- jump actual최소-0.828mm,침투29/미인증48. 조기refresh는실제안전여유가음수이면기존대로미인증을보고하므로통계를숨기지않음.
- .12/tau=.06의빠른접근이실제q추종오버슈트를키웠을가능성으로local범위를.04로원복(teleopbb1639312b01f9b4196694427b8d54fb09cafb23). stale허위제동수정·warmup3FK·adaptive조기refresh는유지. 마지막7FK검사루프는.04에서3FK로자동축소.
- 조기FK1049의비용은위4초창에서servo예산을깨지않음. 무의미한임계완화보다안전회귀수정우선.
- 30fps: 아직미측정. 4초비렌더q측정을30fps통과로확대하지않음.

### shutdown 준비조건 수정(판정약화 아님)
- 기존.4/.6/.8초kill자체는유지. 단'0.4초면반드시Manager자식생김'은환경부하의존잘못된준비가정이라삭제.
- start_new_session으로격리한서버process group을kill전후전수스캔하여뒤늦게태어났거나init으로재부모화된자식도잔존0검사. 포착된기존자손0검사도유지.
- 별도first_spawn포착즉시kill파라미터추가. 15초내자식미포착이면실패하므로실제spawn/종료coverage는보강.
- tests/test_shutdown.py blob11b31bc17e8de7e9217e72707e6d6bea4deeea09.
- cap .12 solver+테스트수정동결본 전체103PASS/60.10초,전후blob동일. cap .04로원복한최종전체pytest는exec1032재실행중.

### 재개 지점(12:34 최신)
- exec1026완료. 안전FAIL 원자료round5/unsafe_cap12_async.json,cap12_function.json,unsafe_cap12_*_1.npz.
- exec1030(30fps만측정하던큐)는취소.
- exec1031 최종통합측정큐: measure→gpu,timeout280초. ON12자세+복귀→OFF/ON4패턴→침투/미인증모두0이면30fps4패턴각30초,아니면render차단파일작성. 로그/tmp/s4_round5_final.log,round5/function_final.json,async_final.json,render30.json또는render_blocked.txt,measure_blobs.txt.
- exec1032 최종cap .04전체pytest(락없이)진행. round5/pytest_cap04.txt,cap04_before.txt,cap04_after.txt.
- 최종제품동결: collision75b68ce5/env294d0bc1/teleopbb163931/tests_humanoidd0fdfa30/tests_shutdown11b31bc1.
- 기본OFF,physical_stop_certified=False. 최종cap .04안전/추종/성능미확인. 전체NEEDS WORK 유지,부모/V-S3에jump침투즉시통보.
### 5라운드 최종 cap .04 수집 (12:38 최신 재개 지점)
- 전체pytest103PASS/90.53초,5파일전후blob동일. source최종75b68ce5/294d0bc1/bb163931/d0fdfa30/11b31bc1.
- 정적12자세4초/자세 최종방향max2.142° ≤8° 자체충족. up1203.36초에8도내. 접근마지막1초tail max15.484°(아직이동중부분포함)도함께공개,4초최종점기준이며1초내내8도이하였다는주장아님.
- 복귀1.80초에8도내/최종2.056°: ≤8°/8초 자체충족. 정적/복귀침투0·미인증0.
- 아래동적은각4초(200servo tick/2000physics step),GT보조. 지속24초/전체sweep주기/실물인증아님.

| 패턴 | p95 ms ≤20 | max ms ≤40 | 침투/미인증 =0/0 | 실제 FK 최소 mm | 관절범위 ON/OFF ° |
|---|---:|---:|---:|---:|---:|
| sweep | 8.72 | 15.56 | 0 / 0 | 12.13 | 74.68 / 76.15 |
| chest | 15.79 | 27.65 | 0 / 0 | 10.41 | 98.49 / 103.98 |
| jump | 13.76 | 27.37 | 0 / 0 | 7.55 | 33.3 / 87.43 |
| twist | 11.12 | 38.36 | 0 / 0 | 8.84 | 74.6 / 74.99 |
- 네패턴자체수치기준충족. 범위는초기접근포함전체관절최대값으로,지속동작범위/무진동을인증하지않음. 특히chest후반2초범위63.93°는접근/우회가포함되어무진동확정불가, V-S3의후반10초누적경로/안전경계접근스캔독립판정필요.
- 30fps진행중: sweep30초957프레임=31.90fps,error0. chest/jump/twist30초창은진행중/미완으로PASS금지.
- exec1031 계속실행(12:35:53락획득,timeout280초),shell73609/flock73615/timeout82662/자체서버5093 PID82849. **종료하지말고완료수집부터**. 4창및정리완료예상12:40전후.
- 로그/tmp/s4_round5_final.log,round5/function_final.json,async_final.json,render30.json,measure_blobs.txt。원자료*_0/1.npz도현재cap .04로root bench/humanoid_s4_out에덮어써짐. cap .12원자료는unsafe_cap12접두어로보존.
- 부모규칙변경수신: 앞으로전체pytest도반드시measure락안에서실행. 현재전체pytest는종료했으며락밖CPU벤치없음. 단일짧은테스트만예외.
- 최종자체4초게이트는통과했으나30fps3창·긴구간안전/무진동/접근최적성·bootstrap CI 미완. 기본OFF/NEEDS WORK,부모가최종기본값결정. V-S3에이동결후보최종독립판정요청.
## 6라운드: exec1031 수집 완료 / 코드 동결 유지 (2026-11-09 12:43)

### 30fps 판정표 보완
기준: 각30초창 ≥29.7fps(891프레임). 아래는창자르기없이30.0초안에수신한JPEG개수/30,GT보조. 각1창이므로반복신뢰구간/개선주장없음.

| 패턴 | 창 길이 | JPEG 개수 | fps_count | 기준 대비 |
|---|---:|---:|---:|---|
| sweep | 30.0초 | 957 | 31.900 | 자체충족 |
| chest | 30.0초 | 961 | 32.033 | 자체충족 |
| jump | 30.0초 | 958 | 31.933 | 자체충족 |
| twist | 30.0초 | 958 | 31.933 | 자체충족 |

- 전창sender오류0. 마지막status의실제q monitor누적침투0/미인증0전부. 단렌더창안전은서버monitor진단이며클라이언트독립500Hz재구성자료라고주장하지않음.
- 원자료 round5/render30.json(도착monotonic시각및패턴말status),/tmp/s4_round5_final.log. 종료후5093 listener0/자체planner0확인.
- round5/measure_blobs.txt=cap04_after.txt 완전동일: 제품5파일동결유지,새코드수정없음.

### jump33.3° vs OFF87.4°: 목표 clearance 분포
추가분석은제품코드수정없이별도임시진단스크립트만사용,measure락안에서실행. 동일4초합성jump의collision OFF raw IK목표를50Hz로재생성(200목표),기록된ON q500Hz에서같은servo시각의q를골라비교. raw목표와실제q/서보명령을혼동하지않음.

| 입력 단계 | raw IK 목표 수 | 목표 clearance min/median/max | 목표 침투 비율 | ON 실제q clearance min/median/max |
|---|---:|---:|---:|---:|
| rest | 110 | +7.598 / +7.598 / +7.598mm | 0/110 (0%) | +7.572 / +17.112 / +38.162mm |
| cross | 90 | -106.000 / -106.000 / -106.000mm | 90/90 (100%) | +7.550 / +14.155 / +37.389mm |

- 4초창전체raw목표의45%(90/200)가자기충돌proxy를관통한다. 따라서OFF87.4°를그대로모두재현하는것은안전기준과양립하지않으며**어느정도의범위제한은정당**하다.
- rest시작q→cross목표의직선q경로를5mm경계까지접근한보조스캔(대표t=.60/1.18/3.58초)은모두진행률7.031%,경계거리+5.259mm,최대관절변화7.121°였다. ON33.3°는이단순직선부분접근7.1°보다더이동하므로'직선투영만으로제자리과잉정지'와는다르며우회가개입한다.
- cross단계ON실제최소+7.550mm는5mm경계보다2.550mm밖이다. 안전경계근처접근은관측했다.
- **단33.3°가최대가능접근/최적범위라고입증한것은아님.** 안전한rest목표(+7.598mm)는존재하며10mm계획margin보다작고,0.6초마다전환되는입력에속도·가속도·C2제동과.04국소범위제한이추가보수성을줄수있다. 정적전역안전경계/의도거리최적화가없으므로'차이54.1°전부가불가피'또는'과잉제동0'으로단정하지않는다. V-S3의정적안전경계스캔및장기후반동작판정에맡긴다.
- 위5mm경계는한직선상의유한샘플보조분석이지전역최근접자세/전체물리인증이아님.
- 원자료 round5/jump_goal_clearance.json, /tmp/s4_jump_clearance.log. 임시스크립트는세션tmp/jump_goal_clearance.py. 분석후제품코드변경0.

### 재개 지점 (12:43 최신, 수집 요청 완료)
- exec1031 완료:4개30fps창·정리·blob검증완료. exec1033 jump목표분포분석완료.
- 최종제품5파일동결75b68ce5/294d0bc1/bb163931/d0fdfa30/11b31bc1 그대로.
- V-S3 EaLlhRBFShBul3O0에30fps4창과jump목표분포·경계보조값전달. 이제독립판정대기,NEEDS WORK지적수신전수정금지.
- 기본OFF/physical_stop_certified=False,커밋없음,web변경0,추가벤치실행0. 남은독립항목:긴창500Hz안전/실제추종,p95반복창,흉부후반무진동/안전경계최대접근,최종통합판정.
## c5 수정 라운드 (13:05, V-S3 NEEDS WORK 수신 후)
- V-S3 c4독립24초:침투0/미인증0전부,p95 12.8/8.2/13.1/7.7ms. chest max42ms1회FAIL. jump8초후영구hold(후반12초경로0.3도)기능FAIL. 4초자체창통과를장기추종PASS로확대했던한계확인.
- c4 raw_c4_jump_c1.json:command path_min8.598mm<planning10mm,rest끝점project10mm와차이1.402mm<기존escape요구2mm. 따라서안전한소폭회복도영구infeasible. 또한release허용closing1e-4와brake발동1e-5불일치로8.7e-5m/s잔류closing에서release직후재latch기록.
- c5:끝점10mm유지,48샘플최소가시작gap보다1µm이상악화하지않는소폭개선escape허용. risk closing임계를release와1e-4로통일(8mmguard·actual/ref/C2유지). 1e-4m/s의60ms이동은6µm,거리guard축소아님.
- c5단일회귀8.6→10mm탈출1PASS/2초. c5전체pytest104PASS/63.17초(측정락안). 제품5파일before/current동일.
- c5동결: collision6be22eb6429ccae8017ca7815618a14f27001830 / env444b9d7462c133de675635004334f636efe7add5 / teleopbb1639312b01f9b4196694427b8d54fb09cafb23 / tests_humanoid3d73db1ec0275f9a6241438f173bfbc821051dbd / tests_shutdown11b31bc17e8de7e9217e72707e6d6bea4deeea09.

### 사용자 테스트 동시 진행: c5성능 판정 제외
- 부모사용자5080+실카메라테스트공지로새성능측정금지. 이미락을잡은c5exec1035중단:Windows toolinterrupt가WSL까지전달되지않아자체wrapper149675/child151486및포착planner만TERM. 다른페어PID/5080/카메라접근없음.
- 이번락내c5관측은모두'사용자 테스트 동시 진행'으로표기하고수락판정제외. jump24초관측후반12초경로441.76°/범위44.58°로영구hold해소양상이었으나자체p9521.78/max43.37ms(t14.26)로성능도미달,통과주장없음. 침투/미인증관측0/min8.05mm도새수락근거로사용금지.
- spike profile:retarget41.27ms(내IK6.16/projection13.72),brake1.44ms. cold만이아닌14초후spike로GC/CPU스케줄링/거리계산을분리할필요. 후속bench에thread_cpu_ms/GC이벤트기록추가(제품수정0). jump프로세스에는추가계측적용전이므로해당필드없음.
- bench/humanoid_s4_c5_inproc.py는V하네스복제(24초wall-paced,500Hzq,전체spikeprofile,200ms마다hold/plan snapshot,후반경로). bench/humanoid_s4_c5.py는jump24→pytest→chest/sweep/twist24→ON12+release순서. static/release도달전중단,완료로추정금지.

### 재개 지점 (13:05 최신)
- 부모'재개'공지전새성능측정금지. 코드검토/락안pytest만가능. 5080/카메라접근금지.
- exec1035중단,raw부분자료 bench/humanoid_s4_out/c5/raw_c5_*.json/npz,pytest.txt,blobs_before/current.txt,/tmp/s4_c5.log. 24초행동개선/미달성능모두동시테스트로판정제외라재측정필수.
- 재개후동일command를measure→gpu락안timeout280초로재실행(도구transcript의exec1035). 먼저jump후반12~24초지속추종/안전/예산,그리고spike의CPUvsGC원인확인. c4와c5동결을혼동하지말것.
- V-S3에c5원인·패치·104PASS·측정중단/수락제외전달. c4서버체인은V가독립관리. 기본OFF/NEEDS WORK,커밋없음,web변경0.
### 13:05 V-S3 c4 최종 판정 추가
- c4 NEEDS WORK. 독립static 방향max7.52/7.72°는8°이내이나up120 손목33.3mm(기준10mm)FAIL,나머지손목≤9.73mm. release2.33초/최종1.4°PASS.
- jump영구hold/chest42ms1회외에up120손목오차도c5재진단필수. 30fps4창·비대칭12·OFF회귀·planner종료/kill9/반복은V가카메라테스트공지로미실시했으므로독립PASS가아님.
- V의기준원자료 notes/verify_s.md r3섹션,bench/verify_s/r3raw,out_c4_stON.json. 재개공지후c5동결6be22eb6/444b9d74/bb163931/3d73db1e/11b31bc1로별도검증.
