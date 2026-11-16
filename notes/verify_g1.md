# V-G1 검증 (r5 G1 페어, 검증자 Claude)

기본 판정: **NEEDS WORK** (I-G1 묶음 미도착, 기준선만 기록). HEAD a297220, 11-16 12:45 KST, load 0.16, GPU used 1024MiB.

## 기준선 (I-G1 변경 전)
- web/perception_stub.py 270줄. 현재 동작: 워커 시작 시 torch/FPRunner/sam2 즉시 import(L19,26-29), fp 모드 아니면 RPC 거부, RPC 대기 180s 고정.
- 관련 기존 테스트 7건(tests/test_humanoid.py -k 'warmup or perception or fp_idle or deferral') **7 passed / 55 deselected, 1.55s** (measure 락 안, 직접 실행): test_fp_warmup_hook_uses_rgbd_and_skips_active_selection, test_fp_warmup_defers_until_g1_off, test_warmup_harness_drops_overdue_input_deadlines, test_fp_idle_backend_deferral_creates_no_process_or_cuda_import, test_failed_g1_start_releases_warmup_reservation, test_g1_running_process_blocks_warmup_after_start_reservation_released, test_successful_g1_start_releases_warmup_reservation. PerceptionBackend 직접 import 테스트는 test_fp_idle_...(L498) 1건.
- env freeze(직접 pip freeze 재현, bench/verify_g1/freeze_*.txt):
  - 원본 robot_percept: 149줄, SHA256 5212c735e645c4f948fd3b8de873dac69ba55a772396ec56e85a6e3de685ec00 (g0_results 기록값과 일치)
  - 복제 robot_percept_g0c: 155줄, SHA256 78471400f02386a62df1e8910d93209a817f416d3a2b86c55131458f82dd22fc; torch 2.14.0+cu130, torchvision 0.29.0+cu130, transformers 4.57.6
- 작업트리 기준선 dirty: M sim/control.py, web/sim_worker.py(I-K 소유, I-G1 변경 아님), notes/contract_r5_changes.md; ?? perception/localize.py 등 W2 산출물. perception_stub.py·app.py·realtime.py는 변경 없음.

## 검증 항목 (I-G1 묶음 도착 후 채움)
(1) DTO/오류코드/lazy import / (2) fp 회귀·GPU 해제 / (3) 'a blue cube' 필터 / (4) 셀 eval recall·정밀도·지연 / (5) 소유 파일 diff / (6) 전체 pytest 1회 — 미실시.

## 1차 코드리뷰 (11-16, I-G1 1차 코드, 테스트·측정 전)
- [재현 FAIL] perception/segment.py RLE가 열 우선(order='F'). 계약 v1.2는 row-major. 8x6, 박스(1,2,4,5) counts=(8,3,3,3,3,3,25): row-major 복원 불일치, col-major 일치. bench/verify_g1/rle_check.py.
- [코드 근거 FAIL] RP_PERCEPTION_CPU_THREADS 처리 삭제(회귀). finally가 모든 op마다 set_default_tensor_type+empty_cache(FP register/track 영향 미재현, 요재현).
- [코드 근거] 40% 면적 필터는 blue 오검출(약23%) 미해결; 기본 경로에 table_mask 없음. 'a blue cube' 거부 여부 미재현.
- [코드 근거] 오류가 DTO error가 아닌 예외 문자열, 14종 코드 미매핑, cancel_token 시작 시 1회.
- 항목 (1)~(6) 판정은 I-G1 테스트/측정 도착 후. 현재 NEEDS WORK.

## 2차 독립 재현 (11-16 ~12:55, robot_percept_g0c, measure→gpu 이중 락, load 0.9~1.3, [시뮬인식] GT 보조 없음; GT는 검출 후 평가 전용)
- RLE row-major 수정 확인(자체 test_rle_row_major 통과, 내 재현은 수정 전 FAIL이었음). 기존 7건+grounding 일부 13 passed 1.58s. 전체 pytest 미실시(묶음 미확정).
- (1) lazy import [재현]: 워커 ready 직후 torch/transformers/sam2/fp_runner/cv2 모두 미import. capabilities 후 torch+perception.grounding만 로드(transformers 미로드, 모델 미로드). ground 후 transformers 로드, sam2·fp_runner는 계속 미로드. 단 capabilities가 torch를 import함(계약 "모델 미로드"는 충족, 무import는 아님).
- (1) 오류코드 [재현, 워커 스레드 직접 구동 bench/verify_g1/lazy_vram*.py]: OOM→OUT_OF_MEMORY, 예외→INTERNAL_ERROR, queries=[]→INVALID_INPUT, cancel_token→CANCELLED OK. **deadline 경과→MODEL_UNAVAILABLE(오류, DEADLINE_EXCEEDED여야 함: TimeoutError가 OSError 하위라 먼저 매핑)**. 미지원 op는 UNSUPPORTED_OP error가 아니라 ok=False+traceback.
- (2) VRAM [재현]: 정상 ground 1회 후 장치 사용 1082→1113MiB(+31, 모델 CPU 오프로드 OK, process max_alloc 1058MiB). 예외 주입(OOM/INTERNAL/INVALID/CANCEL) 후 장치 사용 기저 대비 -44~-7MiB(1281→1237/1274)로 원복(기저는 Windows 영향으로 ±수십MiB 변동). **segment_box segmenter=sam2 1회 후 장치 +186MiB, torch allocated 146MiB 잔류**(오프로드 불완전, 반복 시 누적 여부 미확인). 주의: 첫 시도의 +550MiB 잔류는 내 주입 텐서가 트레이스백에 잡힌 아티팩트(256MiB)였음.
- (3) blue 케이스 [재현, sim_test/results/egl_d3d12/rgb.png 640x480, 기본 파라미터 .40]: "a red cube. a blue cube." → blue score .510 box[111.7,180.3,528.8,407.3] 면적 30.8%가 **통과**(filter on). 전체프레임 98.7% 박스(score .382)만 BOX_AREA_EXCEEDED로 제거. G0 기록(23.0%,.494)과 면적이 다르나 .40에서는 어느 쪽도 거름 못 함. table_mask 없이는 미해결, table_mask ROI 연동은 호출자(W2/K) 몫이고 기본 경로에 없음.
- (4) 셀 eval [재현, 평가 장면 seed100000~100009 N=10 (최종 eval100 아님), 640x480, 9개 고정 vocab 프롬프트 동시, box .35/text .25]: GT 30 → filter on TP4 FP30 **recall 13.3% 정밀도 11.8%**; filter off TP4 FP36 (recall 13.3% 정밀도 10%). I-G1 3장 탐색치(recall 11.1%, 정밀도 8~10%)와 ±20% 내 부합이나 합격 수준 아님. 지연: 첫 9892ms(cold), warm p50 864ms/장(9구문 단일 프롬프트, 640x480, G0의 134~183ms와 다름: 구문 수·해상도·load). 장치 sampled peak 2327MiB, process max_alloc 1069MiB. 원자료 bench/verify_g1/eval_out.json.
- (5) 소유: 작업트리 diff는 web/app.py, sim_worker.py, realtime.py, sim/control.py, sim/grasp.py에도 있음. I-G1은 "타 소유, 수정 안 함"이라 답했으나 내가 변경자를 확인할 수 없음. perception_stub.py만 I-G1.
- (6) 전체 pytest 미실시.
- 판정: NEEDS WORK (recall 13%, blue 미해결, deadline 코드 오매핑, sam2 잔류).

## 정정 (11-16, 부모 지시)
- (5) 소유: web/app.py, sim_worker.py, realtime.py, sim/control.py, sim/grasp.py 변경은 I-K 소유(grasp.py는 부모가 checkpoint 인자만 예외 승인). G1 범위는 perception_stub.py, perception/grounding.py, segment.py, tests/test_grounding_r5.py. 이 범위 밖 diff를 I-G1 위반으로 보지 않음.
- **검증자 사전 열람**: 위 eval_cell.py 실행은 평가 분할 seed 100000~100009 10장을 사용했다(eval 분할은 동결 후 1회 채점용). 이 10장은 최종 eval 집계에서 제외하거나 별도 표시해야 하며, 위 recall 13.3%/정밀도 11.8%는 예비 진단치일 뿐 최종 eval 근거가 아님. 이후 G1 검증은 tune 시드(1000~1019) 또는 별도 검증 시드만 사용.

## 3차 재현 (11-16, tune 시드 1000~1019 N=20 / lazy_vram3, 이중 락, load 1.3~1.4, [시뮬인식] GT 보조 없음)
- a/b [재현 OK]: deadline→DEADLINE_EXCEEDED, 미지원 op→UNSUPPORTED_OP(ok=True error 필드). 예외 주입 VRAM 원복 유지.
- c [부분]: sam2 segment_box 후 torch allocated 잔류 146→40MiB, gc+empty_cache 후 장치 사용량은 호출 전 수준(1310MiB)으로 복귀. 40MiB 잔류와 반복 호출 누적은 미확인.
- (3) blue [재현 OK, 면적 상한 현 .16]: 같은 640x480 rgb.png에서 blue .510 박스(30.8%)와 전체프레임 박스(.382) 모두 BOX_AREA_EXCEEDED로 제거, red(.745, 0.4%) 유지. 정상 물체 recall 손실 0: tune 20장에서 filter on/off 모두 TP 9. 단 .16은 tune 최대 면적 .0512x3 근거로 정한 값이며 큰 실물/근접 촬영 물체에는 일반화 미검증.
- (4) 셀 tune20 독립 재계산: GT 61 → filter on TP 9 FP 61 **recall 14.8% 정밀도 12.9%**, filter off FP 73 정밀도 11.0%. I-G1 수치(TP 9/61)와 일치. warm p50 854ms/장(cold 10095ms), 장치 sampled peak 2577MiB, process max_alloc 1069MiB. eval100 미사용. 원자료 bench/verify_g1/eval_out_tune.json.
- 판정 NEEDS WORK: recall 14.8%로 목표(미정이나 실사용 불가 수준), I-G1 GT bbox MSAA artifact 의심은 check_gt.py 결과 대기, 전체 pytest 미실시.

## 4차 (11-16 ~13:12, 최신 코드 면적 상한 .04 + span-min 매핑, GT는 quality.offsamples=0 재렌더)
- GT 채점 오류 확인: MSAA4 segmentation 오염으로 GT 박스가 부풀었음(I-G1 check_gt 및 내 재채점으로 확인). 교정 전 내 수치(recall 14.8%/정밀도 12.9%)는 폐기. 내 eval_cell.py는 offsamples=0 별도 Renderer로 GT 생성(RGB는 원래 MSAA4 유지).
- [재현] tune 1000~1019 N=20, GT 61, 9 vocab 구문 동시, box .35/text .25, filter on: TP34 FP23 **recall 55.7% 정밀도 59.6%**; filter off FP49(정밀도 41.0%), TP 동일 34. I-G1(TP34 FP21, 55.7%/61.8%)와 recall 동일, 정밀도 ±20% 이내(채점기 차이 FP2). 원자료 bench/verify_g1/eval_out_tune_nomsaa.json. 지연 warm p50 820~876ms/장(cold 10.1s), 장치 sampled peak 2455MiB(상한 7168MiB 미만), proc max_alloc 1069MiB, load 1.3~2.2.
- [재현] blue: 같은 rgb.png에서 blue 박스(30.8%, .501)·전체 박스(98.7%) 모두 BOX_AREA_EXCEEDED, 큰 박스 오검출 제거. 단 blue_only 질의에서 작은 빨간 큐브(0.4%)가 blue .352로 통과 = 색 오분류 FP 잔존(면적 필터로 해결 불가).
- 상한 .04는 tune GT 최대 1.23%x3 근거(tune 시드에 맞춤). 큰 물체/근접/실물에는 미검증, 정상 recall 손실은 tune에서 0(on/off TP 동일 34).
- lazy/VRAM 최신: ready 직후 torch/transformers/sam2/fp_runner 미import, ground 후 transformers만 로드. 오류코드 전부 OK(OOM/INTERNAL/INVALID/DEADLINE/CANCEL/UNSUPPORTED_OP). 예외 후 장치 1110MiB(기저 1060, warm 1110)로 원복. sam2 segment_box 후 +48MiB·torch alloc 40MiB 잔류(반복 누적 미확인).
- [재현] 전체 pytest 1회(robot_percept env, measure 락, load 1.12, PYTHONPATH 절대경로): **376 passed, 96.9s, 0 failed**(타 페어 테스트 포함).
- 미검증: FP ground->FP->ground 회귀, SAM2+FP 공존/워밍업, 클릭 SAM 경로 직접 호출, eval100(동결 전, 미실행), 실물·ROCm.
- 판정: NEEDS WORK 유지(조건부 진전). eval100 1회 채점 및 위 미검증 해소 필요.

## 5차 (13:22 KST) eval100 봉인 대조 기준 (결과 도착 전 스냅샷)
- v1 동결: bench/g1/selection_freeze.json mtime 13:19:59, 파일 sha256 b6020095d024461c… (I-G1 메시지 해시 b4d7150은 파일 내부 sha256 필드로 추정, 미대조).
- eval_selection.py mtime 13:18:32, run_selection_eval.sh 13:20:44, selection_eval_part0.json 13:22:33(241009B, 작성 중 갱신). 부모 지시: part0는 v2(혼합안 c) 동결 전부터 생성 중 → 원시 예측 sealed 보존, v2 동결 후 규칙만 1회 적용.
- 대조할 것: (1) 원시 예측 sha256 기록 시각 < v2 동결 mtime, (2) 결과 요약 파일 생성·열람이 v2 동결 이후(mtime), (3) v1·v2 수치 모두 보고, (4) 사전열람 10장 포함/제외 두 줄, (5) Wilson 95% CI 독립 재계산, ±20%, 지시당 지연·VRAM≤7168MiB. 미완.

## 6차 (부모 정정) v2 -> v2r
- v2(c .55)는 퇴화안(tune 5/61 정확, 오선택 0, absence 123/123)이라 부모가 eval 열람 전에 v2r로 정정: tune 후보 중 대상 없음 정상 거절률 ≥85% 만족안 가운데 정확 선택률 최대, 동률이면 지연 낮은 안. 보고는 v1(a .35 사전 동결)과 v2r 두 줄.
- 추가 대조: v2->v2r 정정 시각(동결 파일 mtime)이 결과 최초 파싱 시각(score_sealed_v2.py 기록)보다 앞서는지. sealed 원시 예측 해시 510a25902df513ac…(I-G1 보고, 파일 대조 전)가 sealed_hash_initial.json과 현재 파일 sha256에서 일치하는지.
- 아직 eval 결과 미열람, 독립 재계산 미실시.

## 7차 (13:28 KST) 시각 대조 중간 스냅샷 (결과 미열람)
- 동결 파일 mtime: v1 selection_freeze.json 13:19:59, v2 selection_freeze_v2.json 13:24:40, **v2r selection_freeze_v2r.json 13:26:52**(I-G1 timestamp 1794803212 = 13:26:52 일치).
- 원시 예측 mtime: part0 13:22:40, part1 13:24:37, part2 13:26:44 (v2r 동결 이전), part3 13:27:53 진행 중(동결 이후 계속 수집; 추론 코드 불변 여부는 최종 감사에서 확인). sealed_hash_initial.json 13:23:20(part0 완료 직후, part1~3 해시는 별도 필요 여부 확인).
- manifest/summary 파일 없음(13:28 시점) = 요약 미생성 상태 확인. 의미 파싱 시각과 최종 해시는 1061 완료 후 대조.
- 선택 정확도/Wilson/지연/VRAM 독립 재계산은 최종 manifest 도착 후.

## 8차 eval100 최종 독립 감사 (11-16 ~13:40, 추론 없음, bench/verify_g1/audit_eval100.py → audit_eval100.json)
- [재현] 해시: sealed_hash_final.json의 part0~3 sha256·bytes 모두 현재 파일과 일치. part0 해시는 sealed_hash_initial(13:23:20)과도 일치(part1은 당시 부분 파일, 최종만 대조).
- [재현] 시각: v2r freeze 1794803212.2229 < hashed_at 1794803331.5379 <= first_outcome_parse_at 1794803331.5423, summary mtime 1794803331.6003. part0~2 mtime은 v2r freeze 이전, part3(1794803322.59)는 이후(추론 수집은 규칙과 독립이며 결과 열람 전). v2c55는 채점되지 않음. v1 sha b4d7150…은 selection_freeze 내부 sha256 필드(이전 의문 해소).
- [재현] 자체 구현 채점(I-G1 코드 미사용), 선택=지시 대상 클래스 top-1 박스 IoU>=0.5, 대상 instance 300개:
  - 포함100장: v1(a .35) 208/300=69.33% Wilson95[63.90,74.28], 대상없음 거절 231/620=37.26%, 오선택 42; v2r(b span-min .35) 180/300=60.00% [54.36,65.38], 거절 553/620=89.19%, 오선택 23.
  - 사전열람10장 제외: v1 190/270=70.37% [64.67,75.50]; v2r 166/270=61.48% [55.55,67.09]; 거절 v1 201/558, v2r 501/558.
  - I-G1 요약과 정수·소수 모두 일치(차이 0).
- [재현] GT 독립 재렌더(quality.offsamples=0) 300 타깃 박스 대조: 불일치 0, 최대 오차 0px. GT 없는 타깃(box None) 1건은 오답으로 계산됨.
- 지연: 지시 1회 task ms 평균 v1 177.0/p50 154.3, v2r 174.0/p50 169.0(eval). tune의 v2r 290.5ms와 차이(-40%) 미설명, 조건 차이로만 추정. VRAM: 장치 sampled peak 2565~2651MiB(7168MiB 미만, 20ms 표본이라 true peak 아님), process max_alloc 1069MiB, load 1.0~1.8, 각 25장 95.7~99.4s.
- 한계: 동일 클래스 중복 대상 40건은 색 구분 불가·top-1 구조상 상한 존재. Wilson은 같은 장면 상관 미보정(기술적). v2r 하한 .85는 tune b specificity에서 부모가 정한 값(약한 순환). 시뮬만, 실물·ROCm 미검증, 고정 합격선 없음.
- 미검증 유지: FP ground->FP->ground, SAM2+FP 공존, 클릭 SAM 직접 경로, sam2 반복 누적(+48MiB), 면적 상한 4% 일반화.
- 판정: 측정·봉인·점수 재계산은 PASS(원자료 재현). 기능 전체 판정은 조건부 PASS, 아래 남은 항목 해소 전 최종 PASS 아님.
