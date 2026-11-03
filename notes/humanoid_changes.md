# I-R2 변경 및 측정 (2026-11-03)

검증 상태: V-R2 iPmCUS5bJdhobqpn 독립 검증 진행 중, PASS 미수신. 커밋 없음. 5080 및 실제 카메라 미접촉. 카메라 물리적 분리로 실카메라 검증 미실시.

## 변경
- 기존 인계: G1 환경/IK/retarget/servo/shared-memory worker/API.
- sim/humanoid_retarget.py: MCP 굽힘은 손바닥 평면 투영 각도로 계산하여 펼침 배제.
- sim/humanoid_ik.py: elbow 조기종료/최종 성공 허용오차 5mm 통일.
- sim/humanoid_teleop.py: reset 시 calibration marker 유지. 새 입력/옵션/보정 때만 IK, 속도·가속도 제한 적분은 50Hz 유지.
- web/humanoid_worker.py: 누적 데드라인 렌더링, JPEG 별도 single-thread future(최대1개), 완성 JPEG 게시 수로 FPS. 부모 PID 변화 시 종료 및 고아 공유메모리 정리. 새 지표 ik_ms_p50/p95는 새 입력에서 양팔 solve 시간 합계(hold tick 제외).
- web/shm_channel.py: close 실패와 무관하게 unlink 수행.
- web/humanoid.py: 기본 목표32fps(30fps 수신을 위한 여유), HUMANOID_FPS로 설정. 현재5091는 이전설정30으로 실행된 상태이므로 서버 재기동해야32 적용.
- tools/teleop_tracker_win.py: 기본 panda/한손으로 기존 경로 복구. humanoid/both만 PoseLite+양손, 독립 Tasks를 ThreadPool2로 병렬 실행. --serial 비교 옵션, --infer-width 320/480/640(기본640). 손목 최소합 전수할당, OneEuro. 양손5색팁+작은중심점. 프리뷰 프레임별 JPEG/스레드별 keep-alive. 카메라 open 실패는 명확한 메시지 후 종료. 최신 변경은5080에 배포하지 않음.
- 신규 web/static/humanoid.js/css 및 index script: G1/Panda 선택, 좌웹캠/우로봇, 관절패널/한계meter/속도/IK, 사람5색팁/로봇3색팁/관절이름. G1→Panda는 안전상 Panda 추종 자동시작 안 함.
- tests/test_humanoid.py, bench/humanoid_tracker_bench.py, notes/humanoid_teleop.md.

## 측정 (GT 아닌 영상 모델 기준 차이)
WSL 시작 load average 1.91/.66/.24. 공유 부하는 변동하므로 타 측정과 절대비교 금지.
45프레임 teleop_round2_async.mp4, 카메라/HTTP 없는 추론 벤치:
- 직렬640:25.14Hz, inference p50/p95 38.90/47.32ms, Pose45/45, hand1/45.
- 병렬640:39.30Hz,24.75/31.99ms, Pose45/45, hand1/45, Pose차이0px.
- 병렬480:31.31Hz,32.28/38.86ms, Pose45/45, hand6/45, Pose차이12.29px.
- 병렬320:28.45Hz,33.48/46.27ms, Pose45/45, hand28/45, Pose차이15.00px.
640 병렬은 GIL 병렬화 효과가 있고 동일 검출/좌표. 축소는 모델 ROI/검출 변화로 더 느려 채택 안 함. 이 45프레임은 손 양성 성능보장 아님.

손 양성 teleop_final_hand.mp4 동일89프레임:
- 직렬640:16.515Hz,59.94/73.21ms, Pose89/89, hand62/89.
- 병렬640:27.322Hz,36.34/46.17ms, Pose89/89, hand62/89, Pose차이0px.
- hand 검출률 회귀 없음. 손좌표 차이와 양손 동시 검출률은 미측정. 30Hz 미달.

30fps 페이싱 round2 전체89프레임 end-to-end:89updates/4.53s=19.64Hz, HTTP88(최종 pending 유실1),network errors0, inference38.86/45.31ms(hand36.70+pose27.10 병렬). 영상은30fps로 읽지만 처리밀리면 지연되는 현재 video 경로라 실카메라 latest-frame drop과 동일하지 않음. 실카메라는 latest-only 캡처.

GT 보조 합성입력30Hz 중 새샘플IK/JPEG분리 후10초(렌더목표30): robot29.4~30.7fps, input30.0~32.0Hz, servo tick p95최대13.93ms, render12.9~17.7ms,JPEG3.2~9.5ms. 양팔 개별 IK snapshot .19~5.30ms, restarts=0. 엄밀한>=30 지속 달성 판정은 보류. 신규ik_ms 지표/목표32는 이 측정 뒤 추가되어 재측정 필요.

## 테스트/미완료
- tests/test_humanoid.py + tests/test_smoke.py:5PASS(5.77s, 최신 servo/JPEG수정후8.85s).
- UI 브라우저 도구가 original browser mode unavailable 오류. 부모/검증자 UI검증 요청함. 스크린샷 미확보.
- LIVE_STREAM detect_async/프로세스/pose손목ROI crop 후보 미측정. 손 양성27.3Hz가 현재 확인 최대치이며30 목표 미달.
- 미러/손바닥/허리/엄지 부호 FK와 합성GT 오차/굽힘 일치도 미완료. Pose없으면 G1 손가락도 hold(전신 좌우 할당이 없기 때문).
- latest tracker Documents복사본은 어제 버전이며, 최종PASS후 부모만5080에 적용.

## 11/3 라운드 추가
- 최신py_compile 및5pytest PASS10.24s. 5091 /mode false 후 소유PID1653만 종료, listener없음. 종료시load7.08/3.83/1.62.
- LIVE_STREAM bench/humanoid_async_bench.py final_hand89프레임30fps페이싱: hand callbacks76/pose88/동일stamp paired75=25.281Hz,hand-positive48,콜백완료latency p50/p95 48.85/79.33ms. 같은프레임serial Pose차이2.18px(GT아님). 병렬VIDEO27.32Hz보다불리하여미채택.
- V-R2 5092최신32목표 독립측정: 보고값27.56fps(statusp5029.9/p9533),renderp5016.3/p9527.4ms,JPEG5.5/13.7ms(max49). 단 frames923/30s 산술은30.77이므로 실제측정분모검증요청,최종판정보류. IK개별p501/p958.5/max17.6ms,서보p95최대23.1ms PASS. preview relay30.02fps(Pose실추론속도와별개). UI G1토글/비교/관절/로봇3색마커정상(V-R2),웹캠녹화본UI후속검증중.
- V-R2합성GT보조: mirror대칭/허리축부호/손가락상관.986~.996,한계위반0. 왼팔단일shoulder_pitch와GTflex18도차이는FK upper-arm방향기준검증요청(관절분해coupling가능,아직미해결).

## 11/3 R4 동일 프레임 후보 비교
bench/humanoid_tracker_candidates.py, final_hand89프레임, detector모델초기화 제외, frame변환/IPC포함, startup부하는별도. 픽셀차이는원본serial640같은프레임손landmark차이(GT정확도아님). load측정2.86/3.44/2.00, 후보간공유부하변동있음.

|후보|Hz|p50/p95 ms|손 검출 프레임|손 delta 평균/p95 px|판정|
|---|---:|---:|---:|---:|---|
|직렬640|21.06|44.44/63.25|62/89|0/0|기준|
|스레드640|37.03|27.61/34.75|62/89|0/0|유지|
|별도프로세스640|33.51|30.05/35.81|62/89|0/0|스레드보다느림|
|손만480,Pose640|29.93|34.00/43.11|63/89|4.62/12.87|속도개선없어미채택|
|손만320,Pose640|29.38|34.41/42.32|52/89|5.40/14.85|검출저하로기각|
|이전bbox/posewrist ROI320+fullfallback 초기|20.01|49.73/65.65|35/89|7.12/16.98|검출저하로기각;89회fallback,동일VIDEO모델crop/full전환문제|
|tracking confidence .3|31.44|33.68/39.79|62/89|0/0|기존640스레드보다느려미채택|

ROI후속은crop IMAGE모델과full VIDEO모델분리로재검증중. 새FK좌우대칭회귀테스트4개pitch추가,전체6testsPASS6.84s(재기동시11.20s). tracker requests.raise_for_status추가하여HTTP404도실패로집계(이전network_errors0만으로서버수락보증안됨). --loop-video지원,처리루프종료시Hz측정하여thread정리시간제외,최종pending전송drain추가. 실제카메라미사용.

### R4 전송/ROI/FK 후속
- crop IMAGE와full VIDEO 모델 분리한 ROI 재시험: serial15.70Hz(부하상승),ROI13.80Hz p50/p95 70.54/94.81ms,검출62/89·손delta0px·89/89fallback. 검출보존했으나속도악화로미채택.
- tracker HTTP400원인확정: MediaPipe invisible feet의2d좌표가API |uv|<=3를초과. preview_coords()로표시2d만[-2,2]제한(world3d제어좌표불변),in-frame좌표불변 회귀추가.
- 수정후final_hand loop15초:308처리/15.047s=20.469Hz,실HTTP수락303,networkerrors0. 추론p50/p9541.97/56.78ms,handp5038.52/posep5027.36ms(병렬). 따라서동일프레임순수벤치37Hz는실전송30Hz보장이아님. 공유부하+전처리/오버레이/JPEG/통신포함목표미달. 실제카메라미실시.
- FK GT보조 warm0..7초: L단일pitch-72.14° vs 실제upperarmflex79.08°,u1角오차11.32°/u2 11.92°/elbow28.7mm/wrist5.92mm. R pitch-168.20° vs FKflex167.75°,u1오차17.22°/u2 20.35°/elbow48mm/wrist6.91mm. 즉단일pitch비교는부정확하지만실방향오차도존재(좌측만아님).
- elbowweight .35→1 ablation은 L u1오차5.07/u2 2.94°로감소하나손목13.94mm로악화; R4.60/5.88°로감소하나손목23.23mm로악화. rotationweight.25→.1변경효과거의0. 다중목표가중절충임을확인,임의가중치변경미채택. elbow잔차10mm이상명시경고추가. V-R2 FK교차판정대기.

### V-R2 회신 및 다음 계측 (R4 마감)
V-R2는연결정상/장기측정중이었음(목록미표시가연결실패는아님). FPS분모합의:923프레임은실제33.5초구간으로27.56fps가맞음. 30초는요청시간일뿐이므로923/30사용금지. 검증자는정확한30초창으로재측정예정.
최종현재판정FAIL: 입력없을때32.04fps/입력있을때26~28fps,실추적13.9~20.5Hz,실웹캠미리보기는추적처리율종속. PASS:IKp958.5ms/서보p9522.7ms,관절한계0,미러/허리/손가락GT상관.98+,서버preview릴레이30Hz,UI모든요청기능/Panda회귀. UI경미미완료:Panda선택시G1버튼표시/웹캠하단빈영역/viewBox640x360고정. 왼팔차이는부호버그아닌가중목표절충으로상호확인.
- 새계측추가: tracker JSON직렬화ms/bytes,POST RTT p50/p95,서버 process_ms,loop_ms. /humanoid/update 응답에process_ms추가(서버재시작필요). 최신문법검사PASS,이새계측후전체pytest는미재실행(직전7PASS16.39s).
- 다음실행은Documents구복사본아닌repo tracker사용: WindowsPython312.exe \\wsl.localhost\Ubuntu-24.04\home\user\work\robot_percept\tools\teleop_tracker_win.py --mode humanoid --url http://127.0.0.1:5091 --video C:\Users\USER\Documents\sam_camera\teleop_final_hand.mp4 --loop-video --seconds30 . 모델startup제외후POST/JSON/server/loop/infer격차를분해. sender는latest-only이며전송pending덮어쓰기로sent<processed가능. 측정부하와30fps실시간페이싱명시.
- 5091 /mode false 후소유PID18077만종료. 사용자5080/실카메라미접촉. 최종PASS아님.

## R5 (11/3) 병목 실측 및 렌더 분리
### 실추적 baseline (repo 최신,final_hand loop12초,서버수락확인)
- 274/12.015s=22.805Hz,송신274/274/errors0.
- POST RTT p50/p95=13.52/28.14ms,JSON직렬화p50=.452ms,payload중앙6271bytes,serverprocess p50=.624ms.
- loopp50=47.00ms,추론p50/p95=39.25/51.10ms(hand36.95,pose27.01 병렬). sender는latest-only이며이번에는모두보냄. 병목은직렬화/서버가아니라실추론+후처리. payload축소만으로30Hz달성주장불가.
- G1전용OpenCV스레드1실험(이때로봇렌더도실행):250/251전송,20.863Hz,RTT22.64/45.50ms,server1.142ms,추론41.70/57.74ms. 다른부하조건이므로OpenCV1효과판정보류. --opencv-threads로비교가능;Panda경로는설정변경하지않음.
- G1 preview JPEG 인코딩을latest-only preview sender로이동(원시프레임참조는이후수정하지않음). Panda기존인코딩경로유지. preview_encode_ms_p50/preview_post_ms_p50/preview_sent추가. 후속실측은V-R2단독측정요청으로중단(Windows1045모델startup중terminate),효과미검증.

### 로봇 렌더 스레드 분리 (640x480/JPEG80 유지)
- 물리/servo main과독립GL render thread. render_env는동일불변MjModel+독립MjData/renderer. main은qpos/qvel/mocap/ctrl/time의새배열tuple만atomic publish. render thread가자기MjData에복사→mj_forward→render→JPEG→frame Blob. live물리data에접근안함. reset/parentdeath/stop은event+threadjoin으로정리.
- bench/humanoid_runtime_bench.py 신규: GT보조30Hz합성,33.5초고정창안JPEG만계수,분모(first~lastarrival)도출력.
- 자체1012JPEG/arrivalspan33.491167s=(1012-1)/33.491167=30.18706fps,최대gap117.2ms. load2.62→3.65. statusfpsp50/p9531/33,tick50Hz/rtf1/input30Hz.
- renderp50/p9519.3/33.75ms,JPEG5.7/7.3ms,snapshot.351/.694ms. IK합p95상태값p50/p9512.895/15.665ms,servo tickp95상태값15.41/21.085ms. 자체조건30fps통과이나독립V-R2최종판정대기.
- V-R2동시측정은5091+5092+Windows벤치중첩으로load5.3→9.1/렌더67ms/fps13.1로오염. 검증자요청에09:34:39 KST /5091/mode false로워커중지,내모든벤치/트래커종료,Flaskidle만유지. 최소3분간새CPU/GPU측정안하기로회신.

### 검사/전달
- 최신worker/preview비동기후7pytestPASS16.83s,load9.20/6.24/4.50(이후idle정리).
- UI경미지적추가수정:Panda선택중G1버튼/목표옵션숨김,웹캠/로봇feed둘다4:3 contain으로하단빈카드영역정리,사람SVG viewBox와normalized좌표를실제이미지naturalWidth/Height로계산. V-R2브라우저회귀필요.
- 재현: WSL conda+gl env에서python bench/humanoid_runtime_bench.py --url http://127.0.0.1:5091 --seconds33.5 (5091서버별도실행). 검증자5092로변경. worker/thread구조변경은새worker재기동필수.
- Windows repo tracker --mode humanoid --url http://127.0.0.1:5091 --video C:\Users\USER\Documents\sam_camera\teleop_final_hand.mp4 --loop-video --seconds30 . Documents복사본최신동기화안함/PASS후부모배포.
- 남음:V-R2단독33.5초FPS판정,실추적/실preview30Hz(아직FAIL),asyncpreview효과와전처리/후처리추가분해. 5080/실카메라미접촉,커밋없음.

### R5 후반/다음 재개 지점 (09:39)
- 480x360 옵션33.5초GT측정:999frames/33.48005span=29.80879fps,maxgap1935.8ms. load3.89→3.97,renderp50/p9514/25ms,JPEG2.6/3.75ms. 중앙값개선했으나큰stall포함FPSFAIL,기본640유지.
- 부모추가승인에따라same-serverPanda렌더pause훅구현: app의humanoid등록인자panda_runtime=rt만변경. humanoid modeON/OFF가teleop_render_pause command큐전송. sim_worker의teleop/렌더훅에localbool,nonforcedpublish만skip,physics/Ccommands/forcedrefresh불변. OFF는framecounter/deadline초기화해즉시재개. 파지/실행중Panda이면G1시작409. UI는G1ON에서기존Panda img.src보관+제거/OFF복구. 실제새서버pause/resume검증은다음라운드필요.
- test_g1_mode_pauses_only_same_server_panda_render 추가(mockruntime mode플럼빙/409),최신8testsPASS6.66s. 코드재기동필수(Panda worker와blueprint둘다바뀜).
- /dev/shm psm_ 누수prefix구분은아직미착수. Blobclose unlink분리는기존반영됨.
- 09:39부모가사용자승인으로5080정지. 다음판정조건은단일서버+Windows트래커,기본640. V-R2와동시측정금지. 부모만5080재기동.
- R5마감5091 /mode false+소유PID37281종료. Windows트래커/내벤치모두종료. 5080은부모가관리,나는미접촉. 커밋없음.
- 다음순서: V-R2와단독측정시간합의→5091기본640새서버→Panda pause flag/프레임seq멈춤 및OFF즉시복귀 실검증→GT입력33.5초MJPEG→같은조건최신repo트래커--opencv-threads1 --loop-video --seconds30에서asyncpreview효과/추론stage계측→필요시2세트교차추론/프로세스우선순위후보→pytest/문서/검증요청. Documents복사본은미동기화,repo직접사용.

## R6 (단일 서버,5080정지) 진행/다음 재개
- 신규 bench/humanoid_pause_bench.py 실기동검증: G1 ON 후Panda frame_seq245→245(1초정지),OFF후253으로즉시복귀. stub GT보조 pick/place 둘다PASS. 물리/C명령변경없음.
- 자체30초MJPEG측정은V-R2독립측정진행회신을받아중단(서버종료로IncompleteRead),완료된FPS결과아님. 내5091전체PID42705종료/트래커미시작,검증자6분단독측정구간에새벤치안함.
- V-R2중간독립판정(최신worker+pause훅,load2.6,30.0초창): robot31.66fps(992frames,maxgap98.7ms) PASS. statusfps32/33,render13.1/20.6ms,JPEG3.75ms,input30Hz,servo tickp9522.5ms,IKp955.1ms,미러/허리/손가락유지. 트래커/Panda/UI최종회신대기.
- bench/humanoid_pipeline_bench.py 신규준비(미실행): final_hand동일89프레임 baseline / inference-next+postprocess-current 2단 / 짝홀두세트VIDEO검출기4neuralthreads를비교. 각인스턴스timestamp단조증가. 검출률/같은프레임손delta/second-difference jitter/loop/infer/draw/JPEG/JSON p50·p95출력. 모델초기화제외,HTTP없는순수후보벤치이므로최종판정은실repo트래커HTTP조건에서해야함. 아직채택/트래커파이프라인적용안함.
- 최신repo tracker단계계측추가:stages_ms.pacing/preprocess/neural/retarget/overlay/queue의p50/p95. 기존POST/JSON/server/preview계측과함께실병목표작성가능. 이추가후pytest/문법검사는V-R2독점측정종료후실행필요(직전R5 8PASS).
- 다음:V-R2 '측정 종료' 메시지확인(확인전새CPU/GPU벤치금지)→WindowsPython으로repo bench/humanoid_pipeline_bench.py 실행→baseline대비검출62/89미만/jitter악화안기각→우세안만repo tracker에적용→기본640단일서버+GT아닌realvideo30fps페이싱HTTP실측→pytest/smoke→5091/모든tracker종료→V-R2묶음전달. Documents복사본미동기화.
- 현상태최종PASS아님,로봇만독립PASS중간확인. 5091종료/내추론벤치0/Windows카메라미사용/5080부모관리/커밋없음.

### R6 구현 준비 추가 (V-R2 독점 측정 대기 중)
- repo tracker --pipeline 옵션 구현(기본OFF): N결과완료즉시N+1프레임추론을단일coordinator future로시작하고main은N리타게팅/오버레이/전송을처리. neural Tasks자체는기존독립2thread. VIDEO timestamp순서보존,한pair가동시에동일Task를호출하지않음. 카메라모드도기존latestcapture사용. --pipeline성능/정확도실측전이므로아직기본채택안함. py_compile PASS.
- web/shm_channel.py: 새자동생성segment이름rp_humanoid_<uuid16>로지정해Panda psm_와구분. 기존psm_는소유불명이라삭제안함. prefix/write/read/close(unlink)회귀test추가(아직미실행).
- 후속전체pytest는9tests예상(기존8+shm1),V-R2단독측정종료후실행할것.

### R6 라운드 마감 상태
- 추가발견Panda회귀수정:mode=panda에도detectedFalse를/humanoid/update로추가POST하던기존sender를update_routes()로분리. panda는/teleop/update만,humanoid는/G1만,both만둘. --mode panda Pose생성없음은기존유지. 라우팅test추가. Documents복사본아직미배포.
- 최신py_compile PASS. GPU/FK/스모크를실행하지않는순수unit만선택해7PASS/1deselected1.80s(prefix/unlink와라우팅포함). 전체예상10tests(8humanoid+2smoke)는V-R2측정종료후재실행필요.
- 09:48말현재V-R2 '측정 종료'회신전이라내pipeline/parity실추론벤치는미실행,내5091/Windows추론프로세스는모두종료상태유지. V-R2의기본trackerHz/UI최종결과대기. 로봇중간31.66PASS외전체PASS아님.
- 즉시다음명령(측정슬롯확보후): WindowsPython312.exe \\wsl.localhost\Ubuntu-24.04\home\user\work\robot_percept\bench\humanoid_pipeline_bench.py . baseline/pipeline/parity동일89frames JSON출력으로속도/검출62/89/jitter비악화판정. pipeline우세시repo tracker --pipeline --mode humanoid --video ...final_hand.mp4 --loop-video --seconds30 실HTTP로재검증. 기본Panda동작은--pipeline OFF유지.

## R7 (11/3 09:50~09:59) 파이프라인 비교 및 실전송
### 동일89프레임(final_hand) 후보
|후보|순수처리Hz|loop p50/p95 ms|검출|손delta px|2차차분 jitter px|판정|
|---|---:|---:|---:|---:|---:|---|
|baseline|45.151|22.863/29.503|62/89|0|6.965964|기준|
|2단pipeline|46.602|21.863/27.255|62/89|0|6.965964|채택|
|짝홀2세트|77.817|13.125/24.936|41/89|3.573(95%10.394)|7.432043|검출/흔들림악화기각|

픽셀/흔들림은원본모델동일프레임비교이며GT정확도아님. pipeline의draw/JPEG/JSON p50=.576/.806/.122ms. parity는속도가빨라도채택안함.

### 실서버(G1 ON/Panda paused/640x480) 단계별
1) pipeline(기존저해상도시계):881/30.016s=29.351Hz,전송/preview881/881,HTTPerrors0. server input p50/p95 29.1/31.27Hz. neural31.304/39.414ms,preprocess.759/2.141,retarget.562/1.004,overlay.915/1.752,queue.009/.014. POST10.008/17.282,JSON.364ms,server1.007ms. 아직30미달.
2) 시계/복사개선: WindowsPython3.12 실제get_clock_info로monotonic=GetTickCount64 resolution.015625초,perf_counter=QueryPerformanceCounter resolution1e-7초확인. 트래커의페이싱/필터dt/기간을QPC로교체(time.time송신벽시계는유지),같은640x360resize복사제거. 결과884/30.019s=29.448Hz,source due901/처리98.113%(17미처리슬롯),여전히미달. 시계교체만으로달성주장안함.
3) 녹화본source decode/preprocess 선행: bounded FIFO2 생산스레드가30fps로준비,독립CNN coordinator와main후처리겹침. 실제카메라는기존latestcapture유지. 결과898/30.007s=29.926Hz,898송신/898preview/errors0,source due901 대비99.667%처리/3미처리슬롯. 실제파일프레임skip드롭0(슬롯미처리는queue/inflight/backlog이며별도보고). body처리지연loop p50 104.49ms로약3프레임지연이남음.
- 마지막server25초모니터44샘플: input p50/p95 28.65/30.10Hz,preview28.65/30.085Hz,모든샘플fresh/Panda pause,robotp50/p95 31.9/32.9fps. load.99→1.81. input중앙29.5요구와preview30요구는아직FAIL.
- 마지막neural p50/p95=32.035/39.559ms,preprocess.656/1.998,retarget.587/1.182,overlay1.136/2.227,queue.009/.013. sourcepacing31.445/32.665ms는생산스레드의정상대기이며직렬추론비용아님. JPEGsender encodep50=1.294ms/POST10.212ms,controlPOST10.010/17.900ms,JSON.386ms/6271bytes,server1.018ms.

### 채택/검사/실행
- pipeline 검출/jitter 불변+순수46.60Hz/실처리율99.67%개선근거로G1/both에서기본ON,Panda에서기본OFF. --no-pipeline로기존경로비교가능. --prefetch-video/--no-prefetch-video로source선행비교,기본ON(영상+pipeline일때만). 임의추론결과복제/GTtracker사용없음.
- 고해상도clock효과동일프레임검증 bench/humanoid_clock_bench.py 추가,결과후속기록. 이벤치는실영상+가상timestamp일정이며GT아님.
- 전체pytest+smoke 최신11PASS5.77s,py_compilePASS. 5091/modefalse후소유PID985종료,부하1.24/1.35/2.37. tracker30초프로세스모두완료.
- Windows최신repo직접실행: Python312.exe \\wsl.localhost\Ubuntu-24.04\home\user\work\robot_percept\tools\teleop_tracker_win.py --mode humanoid --url http://127.0.0.1:5091 --video C:\Users\USER\Documents\sam_camera\teleop_final_hand.mp4 --loop-video --seconds30 . pipeline기본ON. Documents복사본미동기화/PASS후부모배포. 최신backend/prefix/Panda pause포함서버재기동필요.
- 최종PASS아님. 다음추론근소초과(32/40ms)및serverinput中央値28.65의원인추가조사. 후보: MediaPipeCPU delegate num_threads 조정/preview와CNN/GIL경합,sourceFIFO지연축소. 단검출62/89/jitter비악화유지. parity2sets는기각유지.

### R7 시계 비교 완료/정리
clock_bench 동일89frames:coarse/QPC둘다손검출62/89,손delta0px,손jitter6.965964동일. 상체pose raw2차차분proxy는12.82649→12.86901px(+.04253px,+.33%)로소폭증가. 이proxy는실제운동도포함하며GT노이즈오차아님; '모든pose jitter불변'으로주장하지않음. V-R2에수치공개하고허용판정요청.
시계벤치1068정상종료,내모든서버/트래커/벤치종료상태. 최종재검증슬롯V-R2에인계.

## 최종 추적 판정 기준 확정 (부모→V-R2)
30fps 입력은물리적상한이므로시작/종료경계·추론지연이포함된유한창에서정확히30.000Hz를강제하는대신,입력프레임대비실처리·실송신율을판정한다.
- 입력30fps대비처리·송신≥99%.
- 서버실수신프레임개수기반30초창≥29.7Hz.
- 미리보기실수신개수기반≥29.7fps.
- 순간/이동창Hz중앙값은참고치이며독립합격조건아님.
- R7자체898/901=99.667%,송신898/30.007=29.926Hz는새기준에부합하는방향이나서버개수기반독립재측정이최종근거. 기존input_hz中央値28.65만으로최종FAIL판정하지않는다.
V-R2 재측정결과대기중. 새측정하지않음. Documents복사본은PASS후부모지시전동기화금지. 커밋없음.

## V-R2 R7 최종 PASS (확정 기준)
검증자 iPmCUS5bJdhobqpn,5092,5080정지/단일서버,loop45초2회 독립재측정:
- 송신29.99Hz,처리율99.93%,드롭0.
- 서버실수신1350/45초=30.0Hz,미리보기1349~1350프레임.
- 30초수신창평균29.73/29.92Hz(최소29.27/29.33은참고,합격기준은확정된개수기반평균).
- 로봇31.80/31.98fps,IK p952.0ms,관절한계위반0.
- 판정:부모확정기준으로R7묶음PASS. 검증자측정종료/5092정지.
잔여한계:첫run /humanoid/video maxgap1735ms 1회(cold start 추정),2회차73ms. 모드ON직후worker/GL준비/첫프레임을기다린뒤video연결하도록후속개선권장. 원인확정이나수정완료로주장하지않음.
Documents복사본배포및5080재기동은부모지시대기,구현자커밋없음. 내5091/벤치/트래커는종료상태.
