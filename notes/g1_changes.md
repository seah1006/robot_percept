# G1 changes (I-G1, uncommitted)
## Code
- perception/grounding.py: lazy DINO tiny pinned a2bb814, DTO conversion, threshold .35/.25, default area cap .40, optional table ROI center and ROI-bbox IoU>=.75 rejection, reason codes.
- perception/segment.py: off/box-only default; optional lazy SAM2 box prompt; row-major RLE.
- web/perception_stub.py: mode-independent ground/segment_box/capabilities, op-lazy imports, CPU guards, finally offload, new RPC error codes, deadline/cancel between DINO stages. Existing click branch retained.
- tests/test_grounding_r5.py: model-free tests, benchmark CLI (tune seeds1000..1019).
## I-K 연결 요청
1. Call backend.call('ground',schema_version=1,frame=FrameMeta.to_dict(),rgb=bytes,queries=[{query_id,canonical_class,phrase}],deadline=monotonic_deadline,owner_epoch=...). Check result.error before execution. segment_box accepts segmenter off/sam2.
2. Box-only path must disable FP warmup. app perception_lock -> RPC lock order. No app.py/sim_worker.py/realtime.py edits by I-G1.
3. Supply a calibrated table ROI mask (bool HxW) for structural table-surface rejection. Never derive it from eval GT in perception. Generic input without ROI retains only .40 area cap.
4. Operating env has no transformers; only robot_percept_g0c clone used. Parent decides production deployment.
## 재개 지점
- tune20 benchmark is running under measure->gpu locks, timeout285 seconds; /tmp/g1_tune.log and bench/g1/cell_tune.json.
- Earlier eval3 seed100000..100002 is exploratory ONLY (bench/g1/cell_eval.json), not valid final eval100. .20 cap was tested then reverted as overfit. Do NOT report as final evaluation.
- Need frozen tuning decision, independent eval100 once, active FP ground->FP->ground and SAM2 coexistence validation. No complete/PASS claim.
- V-G1 XXUltoc74ZJDCHgT owns independent verification; no commits.

## 최종 재개 업데이트
- tune20 실행은 실제 시작 전 measure 락 대기로 중단(자기 프로세스만). bench/g1/cell_tune.json 없음. 최종 .40+ROI 코드 자체 테스트 재실행 필요.
- 재현: PYTHONPATH=/home/user/work/robot_percept flock -w 900 /tmp/rp_measure.lock /home/user/anaconda3/envs/robot_percept_g0c/bin/python -m pytest tests/test_grounding_r5.py -q
- tune: source sim_test/gl_env.sh; export PYTHONPATH=/home/user/work/robot_percept LD_LIBRARY_PATH=/home/user/anaconda3/envs/robot_percept_g0c/lib; flock -w 900 /tmp/rp_measure.lock flock -w 900 /tmp/rp_gpu.lock timeout 285 /home/user/anaconda3/envs/robot_percept_g0c/bin/python tests/test_grounding_r5.py

## 부모 결정: r5 실행 환경
- 운영 env robot_percept에 transformers 설치 금지. r5 서버/인식 기본 환경은 robot_percept_g0c (원본 복제 + transformers4.57.6, 기존 torch/numpy freeze 줄 불변 확인).
- TEAM_R5 반영용 문구: `r5 서버·인식은 conda activate robot_percept_g0c. 원본 robot_percept에는 의존성을 추가하지 않는다.` (TEAM_R5 자체는 I-G1 소유가 아니므로 미수정)
- tune 전용 원인 진단: bench/g1/diagnose_tune.py --phase multi|single. seed1000~1019만, eval100 미실행. multi=320x240/640x480/1280x720 × color/noun prompts; single=640x480 × 9클래스 × color/noun. 진단 threshold.10은 점수 분포용, 운영 계약.35/.25 변경 아님.

## 재개 지점 (부모 허용: 대기 프로세스 유지)
- 활성 실행 세션1041, measure 대기 PID55153. 프로세스는 종료하지 않음. 락을 얻으면 GPU 이중락에서 `timeout285 ... diagnose_tune.py --phase multi` 실행 후 자동 종료.
- 로그 /tmp/g1_diag_multi.log, 점진 저장 bench/g1/tune_diagnosis_multi.json. 각 시드·해상도마다 save하므로 timeout이어도 완료 레코드는 남음.
- multi 완료 후: 같은 환경/이중락/timeout285로 `bench/g1/diagnose_tune.py --phase single` 실행.
- 두 단계 완료 후 measure락 안에서 `.../robot_percept_g0c/bin/python bench/g1/summarize_tune.py` → bench/g1/tune_summary.json.
- summary의 exact_label_loss(후처리 매핑 손실), matched_below_threshold(점수 부족), hit_iou50_any 대 hit_iou25_any(박스/가시GT 민감도), 해상도별 픽셀분포·hit를 먼저 비교. count는 후보당 독립 target hit이므로 최종 one-to-one AP/recall 판정 아님.
- 원인 확정과 튜닝 결정 전 eval100 실행 금지. 기존 exploratory eval3은 독립 eval에서 제외/오염 명시 필요.
- r5 서버/인식 기본 env robot_percept_g0c. TEAM_R5 기록은 부모 담당(이 파일에 붙여넣기 문구 기록).
- V-G1 재현 대응: TimeoutError(OSError 하위형) 매핑 순서 수정 → DEADLINE_EXCEEDED 우선. unknown op→UNSUPPORTED_OP 결과. SAM2 PositionEmbeddingSine.cache는 등록 buffer가 아니므로 model.to(cpu)만으로 해제되지 않음을 소스에서 확인, segment.py release에서 해당 dict clear 추가(재측정 필요).

## 최신 재개
- multi phase 완료120runs/20seeds/103.78s. 다음은 활성 대기 세션1043/PID59133 single phase. 결과 bench/g1/tune_diagnosis_single.json. 부모 허용대로 종료하지 않음.
- 640 color geometry-hit20/61 대 exact-class9/61: empty/혼합 decoded label 큰 손실. single 결과 먼저 보고 token span 기반 query score/클래스 매핑 개선 검토. 모델에 GT identity 공급 금지. eval100 동결.
- SAM2 cache clear/TimeoutError/unknown op 수정은 py_compile 통과, 검증자 재검증 필요.

## tune 면적 정책 확정 (셀 한정)
- seed1000~1019, 해상도3종 정상 가시GT 박스 면적 최대 .051204427, p99 .049459635 (640).
- 여유배수3 선택: ceil(.051204427 *3 *100)/100 = .16. Detector 셀 기본 상한16%, 원래 blue 테이블23~30.8% 거부. 이 배수는 tune에서만 정했으며 eval 미사용.
- 정상 GT 박스 기준 절단0/61. 예측 박스 recall/precision 영향은 span 진단 필터 ON/OFF에서 별도 측정; GT상자 여유만으로 합격 선언 금지.
- 실물 카메라/다른 FOV/셀 밖에는 이16% 상한을 일반화하지 않고 재튜닝·명시 override 필요.

## 最新 재개 (GT 오류 교정)
- Confirmed D3D12 MSAA4 GT segmentation corruption; supersede prior GT-based numbers. Background session1049 rescore_gt.py regenerates GT masks only with offsamples0 and re-scores all saved tune predictions, no model inference.
- Outputs *_corrected.json + gt_correction_summary.json. Next: read corrected summary cap; update Detector default from corrected GTmax*3 formula; compare span/single accuracy, class/pixel failure buckets; independent V-G1 confirmation. Prior16% area policy is provisional until corrected max is available.
- Original RGB remains MSAA4; GT-only re-render offsamples0 never feeds detection.

## 최종 재개: 교정 tune 정책 적용
- rescore completed: corrected GTmax .012278646 -> cap .04 (margin3, ceil2decimals); Detector updated.
- Production candidate span-min token mapping +4% cap applied. Corrected tuning TP34/61 FP21 vs HF31/61 FP27. Single-query47/61 but~7.1x latency. No final eval100 yet.
- New test_phrase_spans added. py_compile passed; model-free tests and actual production Detector equivalence require independent V-G1 rerun under locks. No commits.
- Prior .16/.40 and GT-MSAA4 diagnosis values are historical/superseded. Do not reuse them for acceptance.

- 자체테스트세션1051/로그/tmp/g1_final_selftest.log 대기중. 재개 시결과확인. Single merged-query greedy수치는bench/g1/tune_single_greedy_corrected.json.

## 선택 정확도 주지표 재동결
- bench/g1/selection_freeze.json: tune20 a_single/.35/.25/area.04 선택, hash b4d7150b8728a0e34c7190506ceeead8418bcd07a4a9574897e04c6738844f52. eval 관측 전 저장.
- Tune top1 present accuracy a39/61=63.9%, b31/61=50.8%. 지시당 모델지연 a182.6ms,b290.5ms. 대상없음정상거절 a55/123,b108/123. a의대상없음오선택약점명시. 같은클래스중복은동일색/동일문구로색구분불가,두모드모두3/8.
- Detector/RPC: queries1개면 mapping=single (전토큰최대score), queries여러개면span_min. mapping명시가능(single은query1개필수). 최종선택은대상query검출중score최대1개,없으면NO_DETECTION/needs_help. 인스턴스GT tie-break금지.
- I-K 연결 요청 갱신: 지시대상하나의 canonical_class/색명사phrase만 ground에전달. multi보다single을동결기본으로선택. 단일지시에서9개질의합지연을비교하지말것.
- Eval100 자동배치: 세션1057, bench/g1/run_selection_eval.sh. 25scenes×4, 매번measure→gpu,timeout285. 결과selection_eval_part0..3.json, log/tmp/g1_selection_part0..3.log. 존재하는part는재실행거부(일회채점보호).
- 완료후summarize_selection.py 자동실행: selection_eval_summary.json, notes/g1_results.md에포함100장/사전열람10장제외90장두줄Wilson95CI·absence·중복·보조탐지지표추가. gallery최대6장400×300PNG. eval중단되면기존part재실행하지말고완료수/누락수를명시하여부모결정필요.

## 시간순 평가 보류/재동결 감사 이력
1. v1 freeze 저장 후 배치1057 시작. 부모 긴급보류 수신 때 part0 이미실행중, 진행로그 seed번호만확인했고정오/GT결과JSON은열지않음.
2. 부모지시대로 실행배치는그대로유지. summarize_selection.py 맨위에SEALED SystemExit삽입해자동eval열람/보고차단. v1freeze는수정하지않음.
3. 2026-11-16T13:23:20.2004457+09:00 원시예측파일내용해석없이파일명/크기/SHA256만읽어 bench/g1/sealed_hash_initial.json기록. 활성part파일은계속커질수있으므로완료후별도final hash필요.
[{"file":"selection_eval_part0.json","bytes":260862,"sha256":"ff6300ff95c609b04fe2769e2567456bda5c87902addb8e5e7c9acae1c9d2045","observed_at":"2026-11-16T13:23:20.2004457+09:00","state":"sealed, contents not inspected; active file may grow"},{"file":"selection_eval_part1.json","bytes":44837,"sha256":"ec70426735d10f2a5cc49575c874d10219518c7509f76b075011c114980243ec","observed_at":"2026-11-16T13:23:20.2004457+09:00","state":"sealed, contents not inspected; active file may grow"}]
4. tune_selection_v2.py는tune기존예측만읽어c동의수락방식추가비교. v2동결전eval결과열람없음. 세션1058은measure락대기.
5. 부모승인: v2동결해시기록후sealed예측에한번만v2규칙적용,추론재실행없음. 최종보고v1(a)/v2모두와결정시점명시.

- v2 후보군은 원래 tune 임계값 grid .35/.45/.55를 a,b,c 모두에 동일 적용. 동결규칙은 wrong_present+absent_false 최소 → 정확선택률 최대 → 지연 최소. 거절만늘어나는정책으로퇴화할가능성도숨기지않고NO_DETECTION을함께보고.
- score_sealed_v2.py는 v2 freeze존재·100장완료를전제로final raw SHA256을먼저기록한후첫eval결과semantic parse시각을기록. v1과v2및c.35사전지정비교안만일회채점. 기존summary는SEALED차단유지.

## v2 freeze 시간순 확정
- v2 frozen_at=1794803080.3852046 (UTC epoch), hash=510a25902df513ac40db7625d07dd8259eb49d9acf21132062348e18ff3578b5.
- strict min(wrong_present+absent_false) then max accuracy selects c_agreement/.55: tune wrong0, correct5/61, NO_DETECTION56/61, absent correct123/123; conservative refusal degeneration explicitly reported. c.35 comparison correct30/61, absent111/123,wrong15; c.45 correct22/61,absent119/123,wrong4.
- V1(a.35) is pre-collection freeze; V2 is post-collection-start but RESULT-BLIND freeze. No eval outcome JSON semantically read before V2 timestamp. Initial file hashes are observed snapshots; active part changes later, final hashes recorded before first outcome parse.
- run_score_sealed.sh waits for part3 completion log, then measure lock and one-shot score_sealed_v2.py (45s CPU limit). It does not infer again. Existing batch's original summarize_selection.py remains SEALED-disabled.

## v2r 최종 정정 (결과 열람 전)
- 부모규칙설계정정수신: wrong 최소만으로c.55가전부거절에가깝게퇴화하여폐기. 후보(a,b,c×.35/.45/.55)중 absent specificity>=.85인후보에서정확선택률최대,동률지연최소. .85는tune b.35의.878수준을기준으로정한안전하한(평가결과기준아님). 이후규칙변경없음.
- 세션1059(waiting scorer) 즉시종료. final_manifest_exists=False, scored_summary_exists=False. raw outcome parser 전단계manifest조차아직없으므로eval결과비열람상태유지.

- v2(c.55) waiting scorer1059 terminated BEFORE final hash manifest/outcome parse; no v2 eval scoring happened.
- Final v2r scorer is score_sealed_v2r.py, exactly two policies: v1_a_pre_collection and v2r_result_blind_freeze. It preserves v1 raw-prediction hash matching, writes final manifest before first outcome parse, refuses rerun if summary exists.
- run_score_sealed_v2r.sh waits for immutable v2r freeze and completed part3 progress log, then one CPU measure-locked score. Existing raw inference batch unchanged, no second eval inference.

- v2r FINAL frozen_at=1794803212.2228746; hash=66b2a23c573c22793e6df563edb3731a7c693b20dd8cdb52216b8a26d4506628; selected=b_span_min/.35; prior v2 c.55 intentionally retained, never eval-scored. final_manifest still absent at freeze; no eval outcome inspection.
- I-K latest override: v2r is b_span_min/.35, queries all9 fixed vocab; take highest-score Detection of instructed canonical_class only, absent=>NO_DETECTION/needs_help. V1 single path remains comparator, not selected production policy.

6. final sealed raw SHA256 manifest saved BEFORE outcome parsing: bench/g1/sealed_hash_final.json; first outcome parse timestamp=1794803331.5422907; v2r freeze timestamp=1794803212.2228746; v2r hash=66b2a23c573c22793e6df563edb3731a7c693b20dd8cdb52216b8a26d4506628

7. One-shot v2r scorer completed; selection_eval_v2r_summary.json and g1_results updated. Independent V-G1 audit still required.

## 완료 확인
- eval100 4분할 및 sealed 일회 v2r 채점 완료. 첫 결과 열람 epoch1794803331.54229 > v2r 동결1794803212.2228746 확인. v2(c.55)는 채점하지 않았고, v1/v2r 두 정책만 보고.
- 최종 원시예측 SHA256은 sealed_hash_final.json. 초기 진행 중 파일 해시와 구별.
- 최종 자체 테스트10/10 통과0.30초, 외부 패키지 warning1. /tmp/g1_final_selftest.log.
- 배치 래퍼 마지막 cat 행만 CRLF 말미로 exit1이었으나 summaryJSON/notes는 성공. shell LF 정규화 완료. 재채점·재추론하지 않음.
- 다음: V-G1 독립 감사(순서/해시/일회 채점/구현 동등성). 고정 품질 합격선 없이 오선택·거절·정확도를 모두 보고. 커밋 없음.