# G1 partial results (not PASS)
[시뮬인식], GT 보조 없음. GT visible instance bounding boxes are accessed only after detection for IoU>=0.5 scoring. clone robot_percept_g0c only; original env untouched.

## Exploratory only
3 eval seeds100000..100002 were accidentally used before tuning protocol was frozen. They are not independent final eval100 evidence. bench/g1/cell_eval.json preserves raw detections/GT scoring. The file uses the provisional .20 area cap, now REVERTED to .40 (overfit concern).
- Exploratory filter=False GT=9 TP=1 FP=11 recall=0.1111 precision=0.0833
- Exploratory filter=True GT=9 TP=1 FP=9 recall=0.1111 precision=0.1
- Per-frame ms (cold first): 10483.8921209998, 1784.90955200004, 1206.7226539998
- Device-wide sampled peak=2558.08984375 MiB, interval20ms; process allocated=1068.84814453125 MiB, reserved=1220 MiB. Device sample is not instantaneous true peak, no SAM2/FP coexistence claim.
- Self tests: 7 passed0.30s, then 9 passed0.27s on intermediate .20 configuration. Final .40+ROI+cancel patch requires rerun (queued calls terminated before lock acquisition).

## Blocked / remaining
- Tune20 GT area p99/max and final eval100 not completed. Measurement lock occupied by verifier/full pytest; own waiting processes were terminated to respect task timebox. No foreign processes touched.
- Default .40 cap alone does not reject G0 blue-table23% false positive. Calibrated table_mask enables TABLE_SURFACE_BOX IoU>=.75 rejection (model-free regression test included), but default ROI integration is still needed.
- FP ground->FP->ground, SAM2 box coexistence, runtime click/cancel regression remain unverified.
## 재개: 원인 진단 프로토콜
- eval100 동결 유지. 신규 bench/g1/diagnose_tune.py는 tune1000~1019만 사용.
- multi: 320×240/640×480/1280×720, 색 포함/명사-only, 소문자 ` . ` 구분 프롬프트. single:640×480, 사전9개 각각 단일 쿼리(장면 GT 구성과 무관하게 전부 추론).
- score>=.10 후보 보존, 계약>=.35 채점 분리. GT IoU>=.5/.25 비교 및 exact decoded-label/명사 label/클래스 무관 위치검출 분리. GT 가시 픽셀 폭·높이·면적·RGB분산 기록.
- 첫 tune시드 GT(초록)/raw검출(빨강) overlay PNG는 채점 검증 전용; 인식 입력에는 GT overlay 없음.
- 운영 환경 결정: r5는 robot_percept_g0c 기본, 원본 robot_percept에 설치 금지.

## tune20 multi completed (seed1000..1019 only)
- 120 runs=20 seeds×3 resolutions×2 prompt styles; 61 visible GT instances per setting. 103.78s, device sampled peak3699.46MiB (<7168, not true instantaneous peak). bench/g1/tune_diagnosis_multi.json, tune_multi_counts.json.
- Each count is independent per-GT proposal hit (not greedy final recall/AP). IoU>=.5, score>=.35:
  - 320×240 color: any-label16/61, exact-class8/61; noun:any8,exact4.
  - 640×480 color: any20/61, exact9/61; noun:any11,exact4.
  - 1280×720 color: any19/61, exact10/61; noun:any14,exact4.
- Resolution alone is NOT the main cure: color exact9→10 for640→1280. Pixel width min/median/max:320=7/41/87,640=15/83/173,1280=23/125/260; height=8/28/52,18/58/110,28/88/166.
- GT area ratio p99/max:320=.04807/.04875,640=.04946/.05120,1280=.03762/.03855. Default .40 cap does not clip any normal visible GT box in tune20; this is NOT proof it rejects table false positives.
- Label/class decoding is a major loss:640 color geometry hit20 vs exact-class9. Examples: GT can/block/bottle produce empty label despite IoU .56~.81 and scores .36~.58; other labels mix tokens (e.g. red pink bottle blue). Exact phrase conversion discards these, but assigning an identity from GT is prohibited. Single-query diagnosis is next.
- Matching criterion matters:640 color IoU.25 any-label30/61 vs IoU.5 any20/61. This is sensitivity, not permission to relax acceptance criteria.
- Noun-only multi prompts are worse than color prompts in all3 resolutions. Production thresholds remain .35/.25 unchanged. RGB std and per-target raw scores are in JSON; no unsupported claim that plain textures are sole cause.
- Single-query phase is queued separately in session1043 (measure→gpu, timeout285, log /tmp/g1_diag_single.log, output tune_diagnosis_single.json). Leave it running per parent direction. Afterwards summarize_tune.py and select tuning policy before eval100.

## 重大 correction: GT mask MSAA contamination (confirmed)
- MSAA4 segmentation creates scattered false object-ID pixels on D3D12. GT bounding boxes can therefore enclose multiple unrelated objects. check_gt.py on tune1000: small_box0 bbox82x72 ->29x20 after GT-only offsamples0; small_box1 41x67->26x27. See gt_msaa_check.json and gt_msaa_4.png/gt_msaa_0.png.
- All preceding MSAA4 GT recall/geometry/pixel-size/area statistics are SUPERSEDED and must not support a tuning policy or final quality claim. Diagnostic source files now recreate the GT-only renderer with offsamples0, keeping original inference RGB unchanged.
- Saved raw RGB predictions are re-scored (no inference changes) by bench/g1/rescore_gt.py -> tune_diagnosis_multi_corrected.json, tune_diagnosis_single_corrected.json, tune_span_corrected.json, gt_correction_summary.json. Background session1049, log /tmp/g1_rescore.log.
- New area cap must be recomputed from corrected tune GT max *3; previous16% cap is pending correction, not final evidence.
- Until corrected scoring completes, span methods all TP9/61 and single15/61 are also provisional. Latency inference measurements remain valid (they do not depend on GT masks).

## Corrected tune20 conclusion (GT-only offsamples0, original predictions unchanged)
- 60 evaluation masks corrected in74.32s. GT box area max=.012278646; margin3; ceil(max*3*100)/100=.04. Cell default cap4%, real-camera/FOV generalization prohibited without retuning.
- Color multi geometry/exact hits:320=46/32,640=54/31,1280=54/39 (each denominator61). Noun exact=11/12/12. Hence geometry is88.5% at640, not33%; major earlier localization failure was MSAA GT scoring error.
- Single color exact47/61=77.0%, noun35/61=57.4%; latency nine-query sum1670.47/1592.34ms per scene. Multi640 color mean236.09ms; span pass mean293.69ms (different sequential runs, not strict latency equivalence).
- Corrected one-to-one scoring, 640 color (TP/FP; no filter ->4% area cap): HF31/51->31/27; span-max34/70->34/38; span-mean34/58->34/29; span-min34/47->34/21.
- Tune candidate selected: span-min +4% cap, recall34/61=55.7%, precision34/55=61.8%, versus HF+cap recall50.8%,precision53.4%. Single is higher recall but approx7.1x inference latency, so not the default. Eval100 remains frozen until verifier validates this production implementation.
- Detector now uses query token offsets + per-phrase minimum token confidence, argmax phrase per proposal. Threshold defaults.35/.25 unchanged. No GT identity or instance selection feeds inference.
- Full corrected raw/score artifacts: tune_diagnosis_{multi,single}_corrected.json; tune_span_corrected.json; gt_correction_summary.json; tune_span_counts_corrected.json; tune_failure_breakdown_corrected.json.
- Geometry residual class/size failures are in corrected breakdown; the earlier failure_breakdown.json is invalid (MSAA4).

## Single query corrected one-to-one scoring
[{"style":"color","filter":false,"gt":61,"tp":47,"fp":280,"recall":0.7704918032786885,"precision":0.1437308868501529},{"style":"color","filter":true,"gt":61,"tp":47,"fp":157,"recall":0.7704918032786885,"precision":0.23039215686274508},{"style":"noun","filter":false,"gt":61,"tp":35,"fp":232,"recall":0.5737704918032787,"precision":0.13108614232209737},{"style":"noun","filter":true,"gt":61,"tp":35,"fp":127,"recall":0.5737704918032787,"precision":0.21604938271604937}]
- Above is merged9-query greedy same-class IoU.5; original single47/61 independent target hits are not substituted for precision. latency measured separately above.

## v2r final frozen policy, tuning-only comparison
Rule: absent specificity >=85%, then max correct-selection accuracy, tie min instruction latency. 85% chosen from tune b.35=87.8%; no further changes.
| mode | threshold | correct/n | absent correct/n | wrong present | ms/instruction |
|---|---:|---:|---:|---:|---:|
| a_single | 0.35 | 39/61 (0.6393) | 55/123 (0.4472) | 11 | 182.65 |
| a_single | 0.45 | 37/61 (0.6066) | 79/123 (0.6423) | 9 | 182.65 |
| a_single | 0.55 | 30/61 (0.4918) | 92/123 (0.7480) | 3 | 182.65 |
| b_span_min | 0.35 | 31/61 (0.5082) | 108/123 (0.8780) | 4 | 290.50 |
| b_span_min | 0.45 | 25/61 (0.4098) | 118/123 (0.9593) | 2 | 290.50 |
| b_span_min | 0.55 | 6/61 (0.0984) | 122/123 (0.9919) | 0 | 290.50 |
| c_agreement | 0.35 | 30/61 (0.4918) | 111/123 (0.9024) | 3 | 473.15 |
| c_agreement | 0.45 | 22/61 (0.3607) | 119/123 (0.9675) | 0 | 473.15 |
| c_agreement | 0.55 | 5/61 (0.0820) | 123/123 (1.0000) | 0 | 473.15 |
Selected=b_span_min,threshold=0.35, hash=66b2a23c573c22793e6df563edb3731a7c693b20dd8cdb52216b8a26d4506628

## Final one-shot selection eval100 (v1 / result-blind v2r)
[시뮬인식], GT 보조 없음, GT-only offsamples0.
v1 frozen pre-collection; v2r final frozen after collection started, before outcome inspection; superseded v2(c.55) never scored. Raw prediction hashes sealed_hash_final.json.
- include_all_100/v1_a_pre_collection (a_single,threshold=0.35): selection208/300=0.6933, Wilson95[0.6390,0.7428]; absent correct231/620=0.3726; wrong_total=431; NO_DETECTION=50; p50/p95=154.3/268.7ms; aux recall/precision=0.7867/0.22979552093476144
- include_all_100/v2r_result_blind_freeze (b_span_min,threshold=0.35): selection180/300=0.6000, Wilson95[0.5436,0.6538]; absent correct553/620=0.8919; wrong_total=90; NO_DETECTION=97; p50/p95=169.0/219.4ms; aux recall/precision=0.6467/0.6830985915492958
- exclude_preseen_10/v1_a_pre_collection (a_single,threshold=0.35): selection190/270=0.7037, Wilson95[0.6467,0.7550]; absent correct201/558=0.3602; wrong_total=395; NO_DETECTION=42; p50/p95=154.5/264.2ms; aux recall/precision=0.7963/0.23293607800650054
- exclude_preseen_10/v2r_result_blind_freeze (b_span_min,threshold=0.35): selection166/270=0.6148, Wilson95[0.5555,0.6709]; absent correct501/558=0.8978; wrong_total=78; NO_DETECTION=83; p50/p95=169.0/223.8ms; aux recall/precision=0.6593/0.7007874015748031
- Same-class duplicate instances use identical catalog colors/phrases; not color-distinguishable. Separate counts in JSON.
- No fixed success cutoff. Wilson intervals are descriptive; same-scene correlation not adjusted.
- Gallery PNGs are v1 scoring overlays collected without inspection; never used as model input.

- Audit chronology verified: v2r freeze 1794803212.22287, first outcome parse 1794803331.54229 (strictly later). Final unit tests10passed0.30s.
- GPU chunk metadata (20ms device samples, true instantaneous peak not claimed; no SAM/FP coexistence): [{"part":0,"scenes":25,"elapsed_s":97.8660505529997,"device_peak_mib":2649.83984375,"allocated_mib":1068.84814453125,"reserved_mib":1140.0},{"part":1,"scenes":25,"elapsed_s":95.73433796999961,"device_peak_mib":2649.71484375,"allocated_mib":1068.84814453125,"reserved_mib":1140.0},{"part":2,"scenes":25,"elapsed_s":97.587399559,"device_peak_mib":2650.83984375,"allocated_mib":1068.84814453125,"reserved_mib":1140.0},{"part":3,"scenes":25,"elapsed_s":99.4368596559998,"device_peak_mib":2564.46484375,"allocated_mib":1068.84814453125,"reserved_mib":1140.0}]
- Gallery contains a_single and b_span_min raw-comparator overlays; both originally generated without human/model outcome inspection during sealed collection.
