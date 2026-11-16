# V-W2 검증 (Claude, 11-16, HEAD a297220 + 미커밋 I-W2 묶음)

판정: **NEEDS WORK** (순수 투영·unflip·보정 수식은 직접 재현 PASS, 아래 5개 미해결). 원자료: bench/verify_w2/verify_w2.py, out_A~E.json. 실카메라 미사용, 구현 파일 미수정.

## 직접 재현 (독립 코드)
| 항목 | 결과 |
|-|-|
| A 왕복(3D→픽셀→localize), K 무왜곡·왜곡(k1=-.18) 각 3000점 | 최대 7e-13mm / 1e-6mm. 픽셀을 정수 반올림하면 p50 0.56mm, max 1.36mm |
| A top_center 높이 보정 ON (mug/mustard/block, 각 600) | 오차 <1e-5mm. OFF는 독립 교차식과 정확히 일치(차 0), 진짜 편향 mug 83 / mustard 342 / block 61mm(p50) |
| A T_base_world 변환, 기울어진 평면 300점 | 0.0mm, 1e-12mm |
| A 오류 코드 | cal id 불일치·크기 불일치→CALIBRATION_MISMATCH, mirrored·overlay·미지 클래스·앵커 밖/NaN·top 앵커 없음·잘못된 kind→INVALID_INPUT, det.error 통과, 평면 0벡터→CALIBRATION_MISMATCH, 지평선 위·평행(위로 향한 카메라)→INVALID_INPUT, capture_at=None→received_timestamp_only 플래그. gt_assist=false |
| B unflip/스케일 | 정수 preview 픽셀 왕복 최대 0px. 실제 cv2.flip+resize 블롭 300개 → 원본 복원 p95 8.7e-5px. 경계 (0,0)→(1278.5,0.5). 박스 왕복 1e-9, 영상 기준 박스 에지 ±1px(preview 해상도 한계). scaled_intrinsics가 리사이즈 블롭과 p95 4e-5px. interfaces.unflip_center/box와 preview_transform 일치(스케일 1) |
| C 독립 합성 체커보드 12장 1280x720(다른 K·자세, 노이즈 σ2+블러, 왜곡 k1=-.15 포함) | K 오차 최대 0.65px, 카메라 위치 0.15~0.38mm, 회전 0.011~0.041도, 평면 잔차 0, 재투영 최대 0.054px, 보정모델로 localize 최대 0.036mm |
| D 40시드/120물체 1280x720, GT 메시 투영 박스 | 박스 +1 규약(I-W2와 동일)이면 물체별 p50/p95가 I-W2 표와 일치(ball 9.841/11.057, mustard 33.993/43.103, cup 36.233/36.375 등). 내 규약(hi 그대로)은 약 2~2.5mm 낮음(ball 7.6/9.0, cup 33.8/34.0, 전체 p50 25.9 p95 35.0). top ON ≤0.1mm, OFF 물체별 p95 29~363mm(I-W2와 동일). top ON+±2px 균일잡음 오차 전체 p50 3.0 p95 5.6mm(I-W2 지표는 "기준 대비 최대 이동"이라 정의가 달라 값 6.4~7.1mm) |
| 전체 pytest 1회(락 안) | **358 passed, 0 failed** (93s) |

[시뮬GT] 배지: bench_w2.py/보고서에 명시됨, gt_assist=true 표기, '실물 위치 정확도 아님' 취지(가림·검출기 없음) 확인.

## 미해결 (NEEDS WORK 사유)
1. 높이 보정은 top_center 명시 앵커에서만 작동. 검출기 박스(bottom_contact)는 ON/OFF 동일 → 실제 파이프라인 오차는 박스 근사 편향 9.8~43mm 그대로, "높이 보정 후 수치"는 GT 특징점이라 실성능 아님. 박스만으로 보정하는 경로(예: 박스 중앙 광선+높이/2) 또는 한계 명시 필요.
2. estimate()에 품질 게이트 없음. I-W2 synthetic_views 결과 max K 오차 7.49px, 카메라 중심 6.5mm(내 독립 영상은 <0.7px) → 시점 다양성/RMS/K 합리성 검사가 없어 나쁜 입력도 모델로 저장됨.
3. 외부값은 첫 체커보드 기준. 계약의 책상 ArUco T_world_cam, 독립 격자점 검증(validation_error_m=null)은 미구현(회사 PC 후속, 명시됨).
4. 사거리 게이트 없음: 거의 수평 광선 앵커가 9.38m 지점 OK 반환. 최대 거리/최소 입사각 거부 필요.
5. 운영 파일 diff: sim/control.py, web/app.py, web/perception_stub.py, web/sim_worker.py가 수정됨(W2 소유 아님, W2 파일 목록과 무관, 다른 쌍 작업으로 추정, 귀속 미확인). perception/interfaces.py diff 0. camera_owner는 fuser 부재 시(returncode 127) 충돌로 보지 않음, 실카메라 미시험.

## 재검증 (I-W2 게이트 반영 후)
- A 재실행: 왕복 오차 불변(무왜곡 0.0, 왜곡 1e-6mm). C 재실행: K 오차 최대 0.65px, 위치 0.15~0.38mm 불변(정상 입력은 거부 안 됨). I-W2 자기 테스트 17 passed.
- 사거리/입사각 게이트 경계 직접 확인(bench/verify_w2/gates2.py): 입사 8°·9.5° 거부, 10.5°·12° 통과. 슬랜트 2.9m 통과, 3.1m 거부. 수평 광선 9.4m OK 문제 해소(E bottom_row INVALID_INPUT).
- 보정 게이트(gates.py): 거의 동일 자세·회전 0.05rad(~3°) 10장 거부(viewpoint diversity), 6장 미만 거부, 회전 0.5rad 정상 통과(RMS .046). 회전 0.12rad는 통과, 심한 노이즈 σ25+블러3도 통과(RMS .139): 게이트는 퇴화 입력 거부용이며 정확도 보장 아님(I-W2 명시와 일치).
- camera_owner: fuser rc0 충돌, rc1만 무소유, 그 외 fail-closed 코드 확인(실카메라 미시험).
- 운영 diff 귀속(부모 확인): sim/control.py·web/app.py·web/sim_worker.py=I-K, web/perception_stub.py=I-G1 → W2 범위 밖.
- 미재검증: I-W2 재벤치(40시드) 최종 수치, 게이트 후 전체 pytest(358은 게이트 이전 스냅샷). 남은 미해결: 박스 하단 기준 높이 보정 없음(한계 명시로 처리, 편향 9.8~43mm), ArUco 외부값·독립 격자점(회사 PC).
- 최종 판정: 순수 로직 범위 **조건부 PASS**(재현 원자료 기준), 실물/ArUco/독립 검증은 [blocked, 회사 PC].

## 최종 재검증 (bbox midheight 보정 + 최종 eval)
- 독립 재계산(verify_w2.py D, 40시드/120물체, 같은 +1 규약): bbox ON p50/p95 ball .13/.16, box .65/.69, bottle .65/.71, can .70/.83, cup .91/1.04, block .53/.78, mug .84/.90, small_box .88/1.26, mustard 6.32/10.6mm. I-W2 최종 표와 일치. OFF는 기존 하단 기준 9.8~43mm와 일치.
- +1 규약을 빼면(내 기본) ON은 물체별 p95 0.8~2.4mm(mustard 9.4): 박스 경계 규약만으로 ±1~2mm 차이. ±2px 균일잡음(박스 4변 독립) ON 전체 p50 2.6 / p95 5.75mm(I-W2 물체별 p95 5.3~5.7, mustard 14.3).
- 해석 한계: 박스가 GT 메시 투영(타이트, 가림 없음, 직립 물체)이라 midheight 계수 0.5가 이상적으로 맞음. 실검출기 박스·가림·눕힌 물체(mustard 6~14mm 신호)는 미측정 → [시뮬GT], 실물 위치 정확도 아님.
- I-W2 자체 합성 보정: K 최대차 3.52px, 카메라 중심 2.74mm(내 독립 영상 K<0.7px, 위치<0.4mm). 게이트(RMS≤.5)는 통과하나 K 오차는 큼. 정확도 보장 없음, 독립 격자 검증 필수.
- 전체 pytest 358은 게이트·bbox 보정 이전 snapshot. 최종 snapshot 전체 pytest는 미재실행.
