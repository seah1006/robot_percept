# I-W r2 변경 기록 (2026-11-03)

## 묶음1 P0 / P1d
- web/humanoid.py: uniform pose rows, visibility[0,1], finite optional seq/capture_at, quality 검증. client_seq와 서버 seq 분리. hand quality age_ms=null 허용(I-K 계약). OFF enabled=false. start/stop/join을 단일 RLock 직렬화. 매 start sample/times/status/frame 초기화. 첫 JPEG가 게시되어 ready status가 나온 뒤 ON HTTP 응답. 100ms watcher가 worker death를 확인하면 Panda render_pause false 전송. ON/OFF와 watcher가 같은 lock으로 pause 재설정 경쟁 방지.
- web/humanoid_worker.py: received_mono→servo tick 완료(최초 명령반영)→그 snapshot render 완료→JPEG shared-memory 게시, 최신600개 게시된 sample p50/p95/n. applied_seq/published_seq/frames_total. latest-only skip 입력 제외. physical settling/브라우저 decode/HTTP flush는 측정하지 않음.
- tests/test_humanoid.py: 웹회귀6개(혼합행/visibility/OFF/HTTP400/optional quality/stop-start lock/death watcher; 테스트 함수 기준6개 중 일부 복수검사). 최신 humanoid+smoke 21 PASS,9.18s(I-S 추가4 포함), warning1 dash deprecation.
- 재현: source conda.sh; conda activate robot_percept; cd repo; source sim_test/gl_env.sh; export PYTHONPATH=$PWD; pytest -q tests/test_humanoid.py tests/test_smoke.py

## 묶음2 P4
- README.md 신규: WSL 서버/Windows tracker/녹화본/launcher/계측 의미.
- .gitignore: cad_uploads/web/ 추가. tracked 삭제 없음.
- tools/humanoid_launch.ps1/.bat: 서버와 Windows tracker 독립 PowerShell 창, 5080거부/포트중복거부/기본경로 검사. Parser0오류, dry-run tracker 파일존재 True. 실제 창 실행/호출쉘 종료후 생존은 요청대로 미실시. 독립 PID manifest/자동 readiness 대기는 미구현(README 명시).

## 검증/미확정
- V-W Eh5fPuBB8WlZJE7k에 묶음1/2 전송, 독립 결과 대기.
- bench/humanoid_w_runtime.py: flock 아래 3 cold cycles+35초 합성/마지막30초 JPEG수 기준. 첫 시도1회 ready 성공, OFF 직후 ON이 Panda pause command 처리중409. 안전 guard 유지하며 bench에 .3s 대기 적용.
- 최초 측정 부하 load8.23/4.35/2.95, GPU23%,7098MiB. 기준부하<4 충족 안됨. 따라서 저부하 최종판정 별도 필요.
- 소프트웨어 이전 baseline 없음: 현 계측 첫 측정이 baseline. 80ms 임계 확정/개선 주장 보류. physical 10-90% settling 미실시, 실제카메라 분리.

## 재개 지점
1. 5091 서버 exec1074 실행중(5080 미접촉). 측정 exec1079는 flock 대기중일 수 있음. notes/humanoid_w_measure.json 결과 확인 후 숫자 기록. 서버는 최신 frames_total 및 empty-hand 검증 추가 전 기동본이므로 최종회귀 서버 재기동 필요.
2. V-W independent 동시ON/OFF·crash/restart/firststream≤200ms×3·30초≥29.7 확인/지적 수정.
3. 측정 종료 후 /humanoid/mode false, ss :5091 소유PID만 종료. 커밋 금지.

## 추가: 5091 측정 완료
```json
{
  "cold": [
    {
      "start_ready_ms": 4802.53,
      "ready_first_ms": 14.47,
      "max_gap_ms": 51.65
    },
    {
      "start_ready_ms": 5686,
      "ready_first_ms": 5.54,
      "max_gap_ms": 56.81
    },
    {
      "start_ready_ms": 7326.68,
      "ready_first_ms": 10.15,
      "max_gap_ms": 72.92
    }
  ],
  "frames30": 886,
  "fps30": 29.533333333333335,
  "input_count": 1050,
  "latency": {
    "apply_render": {
      "n": 600,
      "p50": 38.626,
      "p95": 61.547
    },
    "receive_apply": {
      "n": 600,
      "p50": 23.464,
      "p95": 38.112
    },
    "receive_publish": {
      "n": 600,
      "p50": 69.259,
      "p95": 101.825
    },
    "render_publish": {
      "n": 600,
      "p50": 5.931,
      "p95": 13.793
    }
  },
  "bad_http": 400,
  "alive_after_bad": "ready",
  "off": false
}
```
2차 측정 load12.06/7.77/4.57, GPU24%,7228MiB. 고부하 관측값이며 저부하 최종수락은 아님. exec1079 종료, worker OFF.

최종 정리: exec1074 서버는 :5091 listener에서 확인한 PID만 SIGTERM하여 종료됨(exec exit 확인). 5080 미접촉. V-W 독립 결과/수정루프는 다음 재개에서 계속. 최신 compile PASS.

## 추가 P0: Panda 무시청 유휴 렌더 (부모 요청)
- web/sim_worker.py render_period: 무시청·무작업이면 .5초 주기(2fps), 시청/프레임요청lease/need_depth(추적)/teleop/active_command/held_object/busy에는 기존30fps. worker demand 확인은 최대40Hz로 manager IPC를 제한. publish의 렌더 cadence만 변경, env.step/teleop.tick/명령/C작업 본문 불변.
- web/app.py /video의 generator try/finally에서 전체variant viewer수 전달. 첫 프레임은 연결시 frame_seq보다 새 프레임을 기다려 stale idle cache를 피함. /frame.jpg는250ms demand lease.
- 회귀: tests/test_humanoid.py render_period 모든 작업·시청 분기, humanoid+smoke22 PASS8.66s.
- 구버전 baseline notes/humanoid_w_idle_before.json: 무시청CPU108.31%,렌더28.2fps(프로세스트리6초 cpu시간 delta). load7.05/7.91/5.60 GPU34%1629MiB.
- 개선 서버 exec1085, 비교측정exec1086: flock→Panda 유휴CPU/시청30초→G1 3cold+35초 순차. 결과 notes/humanoid_w_idle_after.json(JSONL), notes/humanoid_w_measure_lowload.json.
- V-W 추가검증 요청 전송 완료, 독립 결과 대기.

## P 영역 1줄, 부모 승인
- Runtime.track_loop: selected(name)가 없으면 dict(manager.status) 전체복사 전에 continue. 부모1NIgF2z2BvfBSkOh 승인(10:35경). 선택된 경로의 frame_seq/locking/perception 처리 불변.
- A/B/A/B bench/humanoid_w_ab.py는 현재 web 소스를 임시폴더에 고정복사. A는 idle-render/viewer전달/idle-poll guard만 되돌린 구버전, B는 개선본. 같은5091·같은현재Ssolver·동일설정으로 교대. 각 회차6초idle/30초video/물체선택2초추적/선택해제 확인. 마지막B서버에서G1재측정. exec1095 실행중.

## 재개: 10:39 이후
- 리셋으로 장기exec1095 및5091서버 소멸. A/B 0·1 결과만 저장. /tmp/rp_w_ab_ob8laj7j의 0/1 소스스냅샷을 그대로 읽어 sha 동일하게 A/B 2·3 + 마지막B G1 재측정 exec1009 재개. 현재락대기일 수 있음.
- 완료A: CPU91.59%, FPS28.70, 첫67.11ms, 선택200/추적27회13.65Hz/해제true.
- 완료B: CPU24.80%, FPS27.63, 첫81.40ms, 선택200/추적26회13.39Hz/해제true. CPU-72.9%, 시청FPS-3.72%지만 2회만으로 최종회귀판정 보류. 첫두회 측정 중 tests/test_teleop.py 실행6.90초가 겹쳤으므로 엄격동일부하 한계가 있음; 나머지 회차에는 테스트/컴파일 병렬실행하지 않음.
- web/teleop.py 편집창구 부모승인 인수. /teleop/status input_count+preview_count cumulative, 기존90max deque Hz계산 보존. 유효수신만증가, tests/test_teleop.py4 PASS6.90s(95회 카운터 회귀 포함). I-K 전달완료.
- I-P2 요청으로 app.py Runtime.warmup_loop 연결: realworker ready/K/objects최대60초대기→measure.lock→perception_lock→active selection없을때 frame RGB-D/K/objects로 warmup_async, 반환thread.join. GPU락은backend내부소유(measure→gpu순서), stub즉시skip. /status perception_warmup state/error/seconds. mock연결회귀 추가, 실행은AB완료후.
- 운동학 step10-90%(command/actual)는 I-S에 요청했고 baseline/C2 .6/.8/1.0 벤치에추가중. 소프트웨어receive→publish지연과 분리해 S수치수신후보고.

## 10:48 이정표 / 다음 재개
- A/B/A/B 완료 notes/humanoid_w_ab.jsonl. A CPU91.59/120.99%, B24.80/32.00%, 평균106.288→28.397(-73.283%). A viewer28.70/27.70fps, B27.633/28.133fps, 평균28.20→27.883(-1.123%). 두 paired 변화는 -3.72%/+1.56%로 부호가 달라 일관된 저하로 단정 못함. 다만 엄격 무감소 또는29.7fps PASS 아님.
- B 첫 프레임81.40/88.02ms PASS. 선택HTTP200×4/선택해제true×4. 추적Hz A13.647/14.802 vs B13.392/12.033, 평균 -10.631%로 회귀가능성; GPU동시작업 제거 후 재확인 필요.
- G1 notes/humanoid_w_measure_final.json: 30초784장=26.133fps FAIL; receive_publish p50/p9564.106/148.664ms FAIL; receive_apply20.100/49.598,apply_render40.283/92.853,render_publish4.676/18.717. tickp9520.83/IKp9514.031/render33ms. first5.66/15.63/6.30ms, gap70.20/42.77/47.19ms PASS×3. mixedrow400+workerready/OFFenabledfalse PASS.
- 동시작업: V-P2 FP84클릭 GPU벤치가 gpu.lock만 소유하며 진행 중이었음. 따라서 G1/추적 FPS는 저부하 수락 결과가 아님. 부모 새 규칙: 모든 성능 measure.lock, GPU측정 measure→gpu 순서, -w900, 5분내 분할. V-P2 이미 실행중인84클릭 종료후 재측정.
- 운영 warmup_loop의 measure.lock 사용은 부모 지적으로 제거완료. RP_PERCEPTION_WARMUP=0/false/off 또는stub이면 즉시disabled. GPU락은 P2 backend RP_GPU_SERIALIZE=1 선택시에만. FPwarmup-G1 overlap 검증은 외부harness가 measure→gpu 소유하고 RP_GPU_SERIALIZE=0 backend warmup trigger 방식, 이번라운드 미실시.
- 운동학 baseline+최신통합테스트 exec1021: flock measure안에서 bench/humanoid_w_response.py→pytest humanoid/teleop/smoke. 결과 notes/humanoid_w_response.json 및 notes/humanoid_w_tests.txt 확인. baseline scale=None, step .3→1.2rad, 초기3초settle, 2msphysics/34ms입력, command/actual 오른쪽shoulder_pitch10→90% 시뮬레이션시간. 소프트웨어wall-time receive→publish와 혼합하지 말 것.
- 5091은 AB harness finally에서 자기PID/자식만 종료(서버잔류 별도확인예정). 다른서버/5080 미접촉. I-P2 app수정요청창구 계속I-W.

## 10:49 최종 기록
- 최신 통합 pytest humanoid+teleop+smoke **31 PASS,14.10s**, warning1(deprecation). FP warmup mock 연결/active-selection skip/stub disabled 포함.
- 운동학 production baseline step **-0.863292rad**, command t10/t90 **100/340ms**, 10→90 **240ms**. actual **130/366ms**, 10→90 **236ms**. arm command caps3rad/s·25rad/s². 이는 시뮬레이션시간의 step응답이며 HTTP/렌더 소프트웨어지연 및 운동학 안전성 PASS와 별개. Source hashes는 response JSON 참고.
- 5091 listener 없음 확인. GPU 사후36%,1839/8192MiB 기록 notes/humanoid_w_gpu_final.txt(동시 V-P2 작업 가능, 저부하보장 아님). exec1021 종료, 측정락 반환.
- **다음 할 일**: V-P2 84클릭 종료 통지→measure→gpu 이중락으로 G1 30초fps/seq연결지연 및 선택물체추적A/B 재측정. G1≥29.7/p95≤80 아직FAIL·개선미완료, 추적-10.63% 원인분리 미완료. V-W 독립 P0결과/지적수정루프 회신 대기. FPwarmup-G1 overlap 영향 외부harness 미실시. 위 항목을 PASS로 보고하지 말 것.

10:49 V-P2(00oPpDPfKgNa4CaF) 통지: GPU84클릭 종료·락해제, 겹친 구간10:36~10:49약11분(워밍업포함) 확인. 따라서 본라운드AB/G1/추적 수치는 GPU경합 오염가능성이 확인됐음. 다음재개 즉시 이중락 재측정 가능(더 이상 V-P2 대기 불필요). CPU idle 감소는 참고관측, 수락용 FPS/지연/추적은 재측정 우선.

## 새 수락 라운드 (10:50~)
- web/humanoid_worker.py pipeline_ms snapshot/render/jpeg 각 원시최근600개p50/p95/n추가. 기존EWMA와분리해렌더꼬리원인분해용. 기능변경아님.
- bench/humanoid_w_ab.py RP_AB_SEQUENCE=AB지원 및선택후10초countdelta/실walltime의tracking_delta_hz 추가,none상태도기록. 기존2초status EWMA비교의노이즈제거.
- exec1029: w_clean.sh, measure -w900→gpu -w900. PandaA/B각30초viewer+10초tracking/none+최종B G1 3cold+35초. 예상락보유<5분. 결과notes/humanoid_w_clean_env.txt(clean환경),clean_ab.jsonl,clean_g1.json. 현재대기일수있음.
- bench/humanoid_w_warmup.py 신규: 실FP Flask Runtime 자동warmup0으로시작, G1 baseline30초→harness가RP_PERCEPTION_WARMUP1로manualbackend warmup_async(realRGB-D/K/mesh-only)trigger,RP_GPU_SERIALIZE0→warmup최대100초전체G1frames+after30초. 운영측정락없고외부harness만이중락소유. exec1034(w_warmup_run.sh) 대기열등록. 결과warmup.json/warmup_env.txt. 각묶음5분내.
- 동시작업: V-P2 84클릭은종료확인됐으나측정락앞선CPU/GPU벤치여러개대기중. 10:54경lslocks holder69050와대기6개확인,이후holder종료확인. 아직새수락숫자없음.

## 11:02 재개 지점 (이번 라운드 10분 절단)
- clean exec1029 완료. measure→gpu 이중락, load3.31→3.26/3.15, GPU초기33%, 기존GL프로세스56449/83626관측(측정중 FP84벤치는종료됨). clean_env.txt에전후nvidia전체보존.
- **G1 수락 PASS**: 949JPEG/30s=31.633fps(≥29.7), receive→publish p50/p9549.547/70.698ms(≤80). receive_apply14.696/25.238,apply_render29.887/46.447,render_publish3.256/6.360. pipeline render14.826/25.217,jpeg3.259/6.229,snapshot.189/1.129. tickp9511.84/IKp958.173. 3회first7.21/6.64/5.09ms, maxgap43.10/74.92/38.16ms. bad400+workerready/OFFenabledfalse PASS. V-W독립확인요청전달.
- Panda viewer A871/30=29.033fps,B869/30=28.967(-.230%), first64.17/71.00ms. idleCPU94.99→23.80(-74.95%). 선택HTTP200/해제idle양쪽PASS.
- **추적 FAIL 실재**: 10초countdelta A18.520Hz/B12.247Hz(-33.87%), 종전GPU오염제거해도저하. 원인후보 Manager dict(status) 필드별RPC경합. 사용자추적회귀수정범위로 track_loop st=self.status.copy() 단일atomicRPC로변경(선택없음guard보존). field-by-fieldcopy금지/선택없음copy0회 회귀추가. 아직성능개선PASS아님.
- 최신py_compile 및 humanoid+teleop+smoke **34 PASS22.43s**, warning1deprecation. JS node--check PASS. V-W독립P0/P4 PASS수신:9종bad400+생존/동시8/10cycle모순0/crash0.25s복구/first15,17,4.5ms. 비차단coldlock대기는 README4~9초명시+JS전환중안내/선택disabled/실패복원으로대응, V-W UI확인요청.
- **대기중 exec1034**: FPwarmup-G1외부이중락하네스, 11:01:54기준warmup_env.txt빈파일(아직락슬롯미획득). 결과warmup.json없으면실행전/중. -w900만료시exit확인후재등록. RP_GPU_SERIALIZE0/realRGB-D/K/meshonly,activeP선택없음. 자동warmup0→manual1. baseline30/during≤100/after30 약3분묶음. P2계약검토OK.
- **대기중 exec1040**: atomicManagercopy개선후A/B재측정, tracking_fix_env.txt빈파일(아직락슬롯미획득). RP_AB_SKIP_G1=1로약2분묶음. 결과tracking_fix_ab.jsonl에서tracking_delta_hz/none/viewer비교. 원본A는idle/poll/copy/viewer전달변경모두되돌림.
- 최신테스트22.43초는위두슬롯시작전대기중실행했으므로이두벤치와중복없음. 직전clean묶음도종료후였음.
- 다음: exec1034/1040 결과확인→추적잔여FAIL수정→V-W결과묶음전달/독립판정. README G1전용RP_PERCEPTION_WARMUP0권장추가(불필요FP작업회피). 워밍업영향수치아직없으므로효과크기주장금지. 5080미접촉. 현재5091은두대기하네스가획득후에만사용,다른서버종료금지.

## 2026-11-05 13:03 재부팅 후 재개
- PC 재부팅으로 이전exec·서버·WSL /tmp는모두소멸. oldexec1046/1034등을살아있는상태로간주하지않음. 파일기록은남음.
- 작업트리확인: app warmup_loop는 G1ctrl.enabled 동안deferred_g1로.25초대기→OFF후워밍업. 이미warmup중G1ON은자기FPchild만nice19낮춤. 운영rp_measure.lock없음. P2 env RP_PERCEPTION_NICE/RP_PERCEPTION_CPU_THREADS옵션존재확인.
- safety_brake APIbool허용/root현재값·옵션값경로/기본checkedUI·OFF경고존재확인. S DEFAULT_OPTIONS True/env연결존재. JS node--check PASS.
- 전체root pytest-q는무설정벤더/백업복제수집으로10collectionERROR(mujoco_menagerie/accelerate없음,modulemismatch). 129초후자기pytestPID1531만INT로중단,원본로그 notes/humanoid_w_1105_pytest.txt. 다른프로세스종료없음.
- pytest-q tests: **44 PASS,1 FAIL**,49.55초. test_env만rtree미설치(ModuleNotFoundError)로기존실패. deps설치·테스트skip없음.
- 부모승인 pytest.ini 신규: testpaths tests+eval/tests, norecursedirs vendor/assets/bench/data/backup/FoundationPose등. web/test_pipeline.py는test함수없고5081서버에명령보내는수동스크립트이므로단위수집제외. README python-mpytest-q한줄설명추가. canonical python-mpytest-q새실행exec1011/결과canonical_pytest.txt확인중.
- 새bench/humanoid_w_warmup.py는실서버 safety기본True→False→True root/workeroptions일치와invalidstr400검사추가. warmup100초timeout시스레드살아있으면실패명시. fp_worker_nice/요청CPUthreads도출력. 이전FP-Warp stdout섞임때문에결과파일첫definition JSON행파싱필요.
- 새측정exec1009(Windows tmp/w_1105_measure.sh): measure-w900→gpu-w900,RP_WARMUP_DEFER_TEST1/NICE19/CPU_THREADS1,5091만사용. 결과 notes/humanoid_w_1105_warmup_defer.json/env.txt. 13:10기준앞선Srender/C장애물/V-Wr2등락대기중,환경로그0byte. 5분이내실행묶음,워밍업G1ON30초미룸→OFF후워밍업→ON복귀후30초.
- exec1009측정뒤기본pytest도자동실행예정(같은canonical파일에덮어쓸수있음). measure코드의마지막nvidia-smi가exitcode를덮을수있으므로성공판정은JSONwarmup_state/error+실데이터로확인할것. 이부분개선은다음실행래퍼에서반영필요.
- V-W에11/5API/safetyUI독립검증요청전달(브라우저불가면API+부모최종UI). parent에rootpytestconfig승인및기존실패보고. 5080미접촉/커밋없음.

## 2026-11-05 13:14 절단점
- 정식 `python -m pytest -q` 완료: **49 PASS / 1 FAIL / 49.50s**, warning5. 유일FAIL 기존tests/test_env::test_env=rtree미설치. 전체통과아님. 부모지시로의존성설치/skip하지않음. canonical로그보존, V-W전달완료.
- 워밍업지연정책·safety실API 재측정 **exec1009는13:13:33에이중락획득/실행시작**(대기끝). 초기load2.10/2.33/1.40. 13:13:53 listener5091 PID38662확인, 현재이작업서버로간주하되종료전argv/ownprocess확인필요. 5080미접촉.
- 다음재개: `bash_interact(1009)` 우선폴링, JSON파일첫definition행에서baseline/during/after fps/gap·deferred_state=deferred_g1·warmup_state=ready·errornull·safety_api defaultTrue/False/True/invalid400·fp_worker_nice19 확인. 결과 notes/humanoid_w_1105_warmup_defer.json + 환경warmup_env.txt. 완료후하네스가5091자기서버/worker정리,자동후속pytest도실행(기존rtreeFAIL예상).
- oldWindows실행명령은measure Python실패를마지막nvidia코드가덮을수있으므로JSON/traceback실물로판정. 새영속재현명령 **bash bench/humanoid_w_run_defer.sh** 추가, LF/bash-n PASS,Pythonexit보존수정. 기존exec1009가종료/만료된뒤에만재실행(중복금지).
- `pytest.ini`, README 테스트범위, benchmark API검증/timeout/priority출력은이번수정. 안전토글·워밍업정책운영연결은재부팅전작업트리그대로이며40타깃회귀를포함한현재프로젝트49PASS로확인. V-W독립API/UI결과회신대기(브라우저안되면부모최종UI확인).

## 2026-11-05 13:17~ 후속 결과 수집
- exec1009는측정완료후세션만료(다시살아있는것으로오인하지말것). 1105_warmup_defer.json 첫definition행에서실데이터수집.
- **지연정책확인** deferred_state=deferred_g1; G1ON30초동안실제워밍업미룸→OFF후warmup42.268초 ready/errornull. FPnice19,CPUthread요청1확인.
- baseline959/30=31.9667fps/gap65.0247ms/p9564.166ms; deferred955/30=31.8333fps/gap70.6377ms/p9567.092ms. 기존동시워밍업gap1779ms에비해G1ONdeferred구간은큰개선. **단실제GPU워밍업을동시에한비교가아니며워밍업시작을OFF까지미룬효과**.
- **복귀FAIL잔류** after850/30=28.3333fps/gap2659.541ms/p9581.217ms. laststatusfps31.9/IKp952.8ms로주로일시정지. 전체정책완료PASS로처리안함.
- safety실API defaulttrue/Falsefalse/Truetrue/invalidstr400,root+workeroptions일치 PASS. 전환순간q/qdot/ctrl불변·다음2msctrl변화<.02rad는S회귀통과근거(실API상태검사와별도). 모든동작안전보장아님.
- AFTER원인후보: 하네스가OFF/coldON에도30Hz를계속POST하고고정과거deadline따라밀린입력catch-up,HTTPtimeout2개. 이를운영코드결함으로단정하지않음. 하네스를late-deadline skip/latest-only pacing으로수정,OFF/cold동안inputpause/resume. long_gaps발생offset/firstdelay출력추가,deadline회귀추가.
- 재확인 **exec1015**(tmp/w_1105_latest.sh) measure→gpu -w900,Python285sINT+10s후강제종료(락묶음<5min),파일notes/humanoid_w_1105_defer_latest.json/env.txt. 13:20:43기준환경파일0byte,아직락대기. 다음재개우선폴링,원본결과덮어쓰지않음.
- 사후canonicalpytest가하네스RP_PERCEPTION_WARMUP0을상속해warmup mock테스트가환경의존으로추가FAIL(48PASS2FAIL)이었음. 테스트에RP_PERCEPTION_WARMUP1명시하고OFF경로도검증하도록수정(skip없음). 새exec1017은RP_PERCEPTION_WARMUP0상태로기본전체pytest재확인중,결과notes/humanoid_w_1105_pytest_env0.txt.
- V-W/부모에원본지연개선·afterFAIL·safety상태PASS·재확인계획전달완료. 원본2개입력오류까지정직기록. 5080미접촉/커밋없음.

## 2026-11-05 13:25 절단점 / 재측정 2차 수집
- exec1015 완료, 결과 notes/humanoid_w_1105_defer_latest.json/env.txt(첫definition JSON행파싱). phase baseline943/30=31.4333fps/gap107.638ms/p9579.713; deferred828/30=27.60fps/gap2635.427ms(구간7.451s지점)/p9599.774; after940/30=31.3333fps/gap99.907ms/p9582.823.
- deferred_state=deferred_g1,OFF후실워밍업ready25.884초/errornull,FPnice19/threads1. input2841/errors0/pacing_resets23(밀린입력drop). safety실API defaulttrue/Falsefalse/Truetrue/invalid400 재확인PASS.
- **워밍업개선전체PASS아님**: 1차after2659ms스톨이2차deferred2635ms로이동. catch-up제거만으론안됨. eager FPworker startup의heavyimports가warmup요청전에도실행됨(backendconstructor즉시proc.start; _worker는torch/FPRunner/SAM2선import). CUDA/Warp초기화가앱warmupdefer를우회할가능성후보. 인과는아직확정아님.
- P2(nVplH0Ugwy763n9f)에게 첫RPCcall때FPworker lazyspawn으로수정요청,부모/V-W에두차수전체수치/한계전달. P2소유파일은W가직접수정하지않음. **다음재개: P2lazyspawn반영확인→동일하네스이중락재측정**. RP_NICE19/CPU_THREADS1 유지,baseline/deferred/afterFPS와longgap offset기록.
- env0상속mock회귀수정+deadline회귀추가후정식python-mpytest(-RP_WARMUP0) **50PASS1FAIL45.35s**,유일기존rtree실패. 파일notes/humanoid_w_1105_pytest_env0.txt. 사후canonical옛로그48PASS2FAIL은수정전기록이며최신으로혼동금지.
- safety전환연속성은S회귀의전환순간physicalq/qdot/ctrl정확불변및다음2msctrl변화<.02rad통과+실API상태반영통과를별도근거로보고. 전체동작/모든전환의안전보장문구금지. V-W독립판정회신대기.
- 현재활성W벤치없음(1015exit0),모든과거exec재사용전확인. 5080미접촉/커밋없음.

## 2026-11-05 13:30 FP lazy-start 반영 재측정 PASS
- P2 web/perception_stub.py lazyspawn구현수신/소스확인. FP생성자는process/queue/torch import없음; 최초실RPC에서만spawn, 초기drop은spawn없음,closed후RPC차단.
- W하네스window별fp_worker_started추가,영속run_defer.sh RP_WARMUP_TAG지원으로원본보존. **exec1021완료**, 파일notes/humanoid_w_1105_lazy_warmup_defer.json/env.txt.
- baseline955/30=31.8333fps/gap118.613ms/p9564.158ms/FPprocFalse → deferred960/30=32.0000fps/gap61.688ms/p9567.412ms/FPprocFalse → OFF실warmingready32.624초 → after959/30=31.9667fps/gap65.632ms/p9564.280ms/FPprocTrue.
- deferred_g1/errornull,FPnice19/CPUthreads1,input2857/errors0/밀린deadline drop8. safetyAPIdefaulttrue/offfalse/ontrue/invalid400재확인PASS. G1ON중FPproc없음→OFF첫RPC후실GPU정상으로lazyFP첫GPUcall도입증. **이전2635/2659msstall이번동일하네스에서없음**. 단1회관측이며모든환경무정지보장아님.
- load baseline2.255/deferred2.096/after2.232, GPU13%2523MiB/18%2523/20%4551. 환경전후nvidia로그보존,이중락/5분제한준수. README구버전overlap1779ms에구버전표시+현재defer/lazy성공수치추가.
- P2·V-W·부모에즉시자료전달및독립판정요청. tests/test_humanoid.py에idleFPbackend(no process/no queue/no new torch import/drop/disabled/closed)회귀추가,전체pytest는아래priority실험끝난뒤진행예정.
- **현재exec1025 진행**: FPworker nice10상태로실warming먼저시작→2초뒤G1ON→runtime동적nice19완화경로. RP_WARMUP_START_THEN_G1=1/DEFER_TEST0/CPUthreads1. notes/humanoid_w_1105_priority.json/env.txt. 슬롯13:31:37획득,baseline/during(실제겹침)/after/g1_cpu_nice_applied/reentry_ready_ms확인예정. CPU완화만으로GPU선점보장없음,실제overlap이여전히나쁘면READMEready후ON권장유지.

## 2026-11-05 14:04 워밍업 취소·회복 통합 완료 / 최종 재개 지점
### 운영 연결
- P2 defer_warmup_for_g1 API연결. Runtime.prioritize_humanoid는_starting reservation먼저설정→state_lock안에서selected없음확인+warmup-onlycancel→warmup_thread.join(3)/procNone확인. 미정리시pendingguard가다음FPspawn을금지하고suspend_worker재정리. 사용자선택/실RPC취소거절은nice19fallback. 실제인식은강제종료하지않음.
- _g1_requested는reservation/ctrl.enabled/**hr.running()** 모두검사. 성공/실패모두mode finally에서release. warmup_manager는deferred면G1OFF까지재시도대기→thread종료+procNone후자동lazyspawn·warmup. 운영측정락사용없음.
- 선택취소직전state_lock/실행중G1막기/success-failurefinally/선택nicefallback 회귀추가. I-S요청 collision_avoidance bool ingress허용만추가,자동활성/UI기본ON없음(safety_brake와독립).
### 주 GPU 측정 exec1038 완료
- 파일 notes/humanoid_w_1105_cancel.json/env.txt 첫definition JSON행. 초기load.82/1.50/1.99,이중락/285초제한,다른성능작업은락대기. 취소전FPpid7124→threadjoinedTrue/procNone/closedFalse/state_deferred_g1/pendingFalse.
- ON 요청→ready응답 **2921.123ms cold**와회복측정기준구분. **ON ack후첫1초33JPEG=33fps,maxgap38.917ms,firstframe11.399ms**. 30초 **31.9667fps,maxgap57.601ms,serverp9560.577ms** PASS. baseline31.2fps/gap78.071/p9590.571, after32fps/gap42.942/p9560.163. baselinep95는80초과관측임도보존.
- G1OFF후자동rewarm **35.007초**,첫실제click **HTTP200/ok/mustard/2.433초(≤5)** PASS. input2784/errors0/drop7. safetydefaultON→OFF→ON/options반영/invalid400 PASS.
### V-W 리뷰 보완 및 선택 GPU 케이스
- selected체크+취소를state_lock안으로이동. hr.running 및finallyrelease명시확인/회귀.
- 같은bench/humanoid_w_warmup.py에 **RP_WARMUP_GUARD_ONLY=1** 실물체선택직후G1ON 케이스추가. exec1040 완료: 첫click200ok2.902초, selectedmustard→mustard, FPpid1500→1500/live, mode200, preservedTrue PASS. load1.069/.958/1.548. 파일notes/humanoid_w_1105_selected_guard.json/env.txt.
- 최신기본전체pytest **60PASS/1FAIL/44.04초**,warning5. 유일FAIL기존test_env rtree미설치,skip·설치없음. notes/humanoid_w_1105_cancel_pytest.txt. 전체무실패PASS아님.
### 인계
- V-W/P2/부모에주측정+선택가드+최신pytest자료전달완료. V-W 독립최종판정/부모브라우저최종확인만미회신. UI는기존API·JS정적검증과단위검증완료,이세션은브라우저미사용.
- 활성W서버/벤치없음,5091 listener없음재확인,5080미접촉,커밋없음.
- 영속재현: `bash bench/humanoid_w_run_cancel.sh`(주취소/1초/30초/자동재시작/첫click), 선택가드는 `RP_WARMUP_GUARD_ONLY=1 RP_WARMUP_TAG=selected_repeat bash bench/humanoid_w_run_cancel.sh`. 두명령이중락/5분이내/자기5091중복거부. 쉘bash-n PASS. 이미실행중벤치와중복실행하지말것.
- 남은 [blocked]: 전체pytest무실패는rtree환경의존성필요(부모가설치금지했으므로보고만), V-W독립최종회신/부모UI확인. 핵심취소성능·첫click은PASS로자체검증완료.

## 2026-11-05 P1c 충돌 상태·프로파일 웹 연결 추가
- S 요청/합의: collision_state clear/avoiding/holding, env.collision_status 이유·가드진단, servo.profile={ik_ms,retarget_ms,projection_ms,brake_ms,integration_ms,total_ms,ik_fk_calls,projection_fk_calls}. 명시collision_state우선, 구버전fallback acceptedFalse→holding/modifiedTrue→avoiding/brake latch→holding.
- web/humanoid_worker.py runtime_diagnostics pure helper추가. **매50Hzservo tick성공시** env진단deepcopy+finite numeric profile_ms/counts snapshot, 신입력/IKsolve여부와독립. 기존상태게시15Hz는유지해큰JSON/GIL비용확대안함(S동의). servo_profile은호환합본.
- web/humanoid.py status root collision_avoidance/config, collision_state/status, profile_ms/profile_counts/servo_profile 기본값·worker값전달. runtimeOFF는clear/actualenabledFalse로과거holding오인방지.
- static humanoid.js/css: unchecked실험체크박스(기본OFF), 명시POST만활성, holding/avoiding경고+rawreason/guard·profile진단펼치기. clear시과거reason배너미표시. textContent사용, 캡슐proxy·실제충돌안전보장X·holding즉시완전정지아님명시. UIpoll10Hz유지, 입력끊겨도active이면경고갱신.
- README schema·50/15/10Hz·실험기본OFF문서추가. 실제시뮬레이터충돌알고리즘/옵션기본값은W가변경하지않음.
- 신규회귀: no-input snapshot갱신/deepcopy/finite JSON/profile단위분리/accepted·modifiedfallback·명시state우선/APIoff기본값·workerholding전달. targeted3PASS3.33초,최종분기2PASS2.07초. **전체66PASS/1기존rtreeFAIL55.20초**,로그notes/humanoid_w_collision_pytest.txt. JS node--check/py_compile PASS.
- S/부모/V-W에변경묶음전달. V-W독립UI/API최종확인대기(브라우저불가면부모UI). 본라운드새GPU성능측정/서버시작없음, collision새필드직렬화의실FPS영향은S/V-W최신worker성능측정에서확인필요. 5080미접촉/커밋없음.
- 남은[blocked]: 전체무실패는기존rtree환경의존성, 독립최종판정/UI확인. 사용자실카메라분리로real camera safety claim금지.
