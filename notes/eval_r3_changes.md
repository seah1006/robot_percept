# E3 회사 GPU 평가 (2026-11-09)

## 변경
- 소유영역만 수정, 커밋 없음. web/app.py 미수정.
- eval/harness/worker.py: 구형 SAM argmax를 현행 depth-aware select_candidate + click-connected component로 수정. FP/SAM 알고리즘 새 정책 추가 없음. 기존 결과는 그대로 보존.
- eval/run_benchmark.py, eval/harness/report.py: 정책 disclosure 수정.
- eval/r3_batch.py, bench/eval/r3_matrix.sh: FP N30/object 90 + perception gt/fp x gt-assist on/off N20/object 240 = 330 trials. 2 seeds/청크, measure→GPU flock, 280s INT+10s kill, 최소 VRAM free4200MiB 대기, 새 디렉터리만 생성, 매 청크 report/progress 갱신.
- bench/eval/r3_warmup.py: 기존 bench/humanoid_w_warmup.py 복사, PORT 기본5083만 변경. r3_warmup.sh cancel/defer/guard 3모드, 이중락/290초 상한/전후 nvidia-smi+load+process list.
- wrapper set-u는 conda activate 이후에 적용. 회사 conda NVCC_PREPEND_FLAGS 미정의로 첫 실행2건은 시작 전 exit1, 출력 디렉터리 미생성. 재시작 완료.

## 검증/측정
- python -m bench.eval.check_metrics PASS.
- py_compile 4파일 PASS, bash -n 2파일 PASS.
- 시작 GPU RTX2080SUPER 8192MiB, 메모리828MiB. 성능 측정치 아직 미수집, 독립 PASS 아님.
- GT oracle identity/click, known extrinsics/contact association 공개. GT-assist off도 deployable perception-only stack 아님.
- Wilson95 분모: 완료행 모두 포함(예외/추정누락 포함). 계획330과 완료수는 별도로 표기. 중단/미실행을 완료로 취급 금지.

## 결과/재현
- FP/매트릭스: bench/eval/r3_gpu_1109a/{plan.json,*env.txt,*status.json,chunk/trials.jsonl,aggregate/}; eval/report/r3_r3_gpu_1109a.md 자동 갱신.
- 워밍업: bench/eval/r3_warmup_cancel_1109a/{result.jsonl,env.txt}.
- 새 실행: bash bench/eval/r3_matrix.sh --out bench/eval/NEW_NAME
- 재개: bash bench/eval/r3_matrix.sh --resume --out bench/eval/r3_gpu_1109a
- 리포트만: bash bench/eval/r3_matrix.sh --report-only --out bench/eval/r3_gpu_1109a
- 워밍업: bash bench/eval/r3_warmup.sh cancel bench/eval/NEW_NAME (defer/guard 별도 새 경로)
- V-E3 sRLh6BrakRu039Yt에 묶음1 전달. 독립 재계산/판정 대기.

## 재개 지점
- exec1007: 워밍업 cancel GPU 슬롯 실행/대기. bash_interact로 확인. 5083만 소유, 부모/다른 PID 종료 금지.
- exec1008: 330trial 분할 배치 실행/대기. 각 청크 종료 후 락 반환하며 raw/report 갱신. 최종330 완료 전 N30/matrix PASS 주장 금지.
- 다음: 워밍업 수치 수집→V-E3 전달, defer/guard 추가 실행. 배치 결과/실패 분모 확인, timed-out 청크는 보존 후 별도 retry 경로 필요. 전체완료는 10분 넘으므로 부모가 exec1008 계속 유지/폴링.
### 11:58 최종 인계
- eval/tests: 5 PASS/0.47s, 1 warning. 두 exec1007/1008은 현재 measure 락 대기(측정0/330).
- 집계 수정: pilot/matrix 상세보고서 별도 분모, 미실행=미측정, pilot pick/place=비대상. 실행중 batch는 이전 집계 함수를 로드했으므로 완료후 report-only를 새 프로세스로 반드시 실행.
- 재개 exec1007/1008 유지. 결과 수집/추가 defer·guard/독립 검증 및 최종 그림은 [blocked: GPU 측정 슬롯/시간].

### V-E3 분모 지적 수정 (이전 완료행 분모 설명 폐기)
- 최종 분모는 plan N30/N20 고정. 미실행/timeout/중단 trial은 missing_trial=True 성공False 합성행으로 보존. 원자료는 미변경.
- aggregate/trials.jsonl 항상330행, validation.json에 청크별 expected/observed/missing seed 집합. 현재 실제완료0, 누락330: 이는 잠정 하한이며 실제측정 결과로 오인 금지.
- cold(청크 첫 seed)/warm register 중앙값 별도 열. pilot/matrix 세부 집계 분리.
- 청크 사이5초 양보 추가. 실행중 exec1008은 구 코드 로드 상태이므로 부모에게 안전한 재시작/최종report-only 필요 전달.
- 새 report-only 실행 성공, wc-l aggregate330행. 잠정 그림 aggregate/{pilot,matrix}/success.png 생성(전체 미측정 상태).

### 부모 지시 재개 (최신 exec)
- exec1008 interrupt가 WSL 프로세스로 전달되지 않아 확인된 자기 PID4954(배치)/5725(락대기)만 TERM. dest 미생성·env0byte 확인. 다른 프로세스 미접촉.
- 새 exec1013: bash bench/eval/r3_matrix.sh --resume --out bench/eval/r3_gpu_1109a. 최신 계획분모/cold-warm/5초 양보 코드 로드. 기존 env 있으면 retry_TIME.env.txt로 원본 보존하도록 수정.
- warmup exec1007 계속. batch 재개는 exec1013(1008 폐기). 진행표 eval/report/r3_r3_gpu_1109a.md, validation bench/eval/r3_gpu_1109a/aggregate/validation.json.

## 12:26 최신 재개점 (이전 exec 모두 폐기)
- exec1013 만료, 고아락25871 청크004는 정상2행 완료 후 소멸. 워밍업1007 종료/5083없음.
- exec1020 셸문법 오류로 즉시 종료. exec1021 대형24trial을150.880초에 정상완료.
- 현재exec1027: 최신driverPID53181, --resume, 집계 measure→gpu 락 대기. CUDA프로세스0/VRAM904MiB(12:25:48).
- 실제완료30/330, pose30/30, 완료청크3개 exit0/1개는 driver종료로 exitnull(원자료완결), 확인된timeout0.
- 속도초기13trial/h→대형청크순수572.6trial/h; 전체관측 60.6trial/h. cold26~28초/warm2.43~2.53초. 초기락대기248/241/509초가약90% 지연 원인.
- optimize_plan: 시작한원자료/seed불변, 미시작만 target210초/25%여유/최대24 자동조정. FPworker청크간유지안함(cold1회 상각). 현재 plan_before_TIME 백업 보존.
- progress.json 속도/ETA 자동갱신, 상세표/그림은 집계락대기. 최신원자료30 표기 추가.
- 안전조치: report-only/plot도 measure→GPU락(900초대기). 전체슬롯 timeout235+kill5=240초. Client.close terminate/kill/join/queue정리.
- V-T3 오염12:20:23~12:22:04, E대형슬롯12:22:08이후라 GPU원인미확정. 락밖 report CPU경로는 발견/수정. 부모/V-T3/V-E3 전달.
- 다음: exec1027 폴링→청크진행/ETA확인. 도구세션만료시driver/고아청크PID실제확인→현재청크완료대기→--resume. 커밋없음.

## 13:03 사용자 실제카메라 동시 테스트 정책 (최신)
- 5080/카메라 미접촉. 시작전 E driver/benchmark 활성프로세스 없음을13:03:28 확인.
- eval/r3_batch.py 미시작 청크만 target65초/25%여유/최대8seed 자동재편성. 내부75초INT+5초kill, 슬롯전체85초INT+5초kill=최대90초. 기존시작청크/seed/계획분모 보존.
- bench/eval/r3_matrix.sh RP_E_CONCURRENT_CONTEXT=사용자 테스트 동시 진행 기본export. 새 trial/manifest에 concurrent_context 저장, 보고서에도 13:03이후 지연cold/warm 동시작업 표기. 사용자테스트 종료통보시 해당export 해제 필요.
- 최신exec1038: 회귀1개를measure→gpu 안에서 실행 후성공시에만 --resume 자동실행. 이전exec1027은 만료, 현재새GPU측정없음.
- 재개: exec1038 폴링. 진행표 eval/report/r3_r3_gpu_1109a.md, progress bench/eval/r3_gpu_1109a/progress.json. 시험/집계/그림모두락안.

## 13:08 사용자 테스트 종료/240초 복원 (최신 재개)
- 부모13:06종료공지. target210초/최대24seed/전체235초INT+5초kill=240초 복원. 기존시작청크/seed/분모 보존.
- exec1038 회귀1 PASS0.88초→box000 N5 exit0→box005 N5까지 정상완료(raw5행). 기존driver152199만STOP후청크159270종료확인→TERM/CONT하여최신코드로전환.
- 현재exec1040: 락안적응회귀1개→성공시에만 --resume. 보고서/ETA도락안자동갱신. 이전exec1038폐기.
- 실제완료40/330(기존30+box10), 최근표는35/330으로다음집계슬롯대기.
- concurrent_window.json은13:03~13:06분단위부모공지보존. 새wrapper는동시flag기본빈값. box005는13:06:44락획득(종료후)이지만구wrapperflag상속→aggregate에서recorded_concurrent_context보존하고effective concurrent_context빈값보정. raw/manifest미수정. window겹침청크box000은보수적으로동시표시유지.
- 5080/카메라미접촉. 사용자측정종료후에도전체pytest/집계/그림락규칙유지.
