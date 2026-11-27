# 작업자 G: O3 RGB-D 인식 (V1–V4), 2라운드

조건: **O3 시뮬 렌더**(MuJoCo head RGB-D 480x640, 무질감, 캘리브레이션된 고정 테이블/트레이). 실사 일반화 근거가 아니다. 평가 대상은 dev 100장면(seed 10000–10099, GT 508개)이며 test split은 쓰지 않았다. 원자료는 `~/m2a_data/percept/raw/`.

## 변경 파일 (커밋 없음)

- `m2a/percept/v1.py`: 깊이 기반 plateau 분할(아래), GDINO 박스 구조 유지, GDINO 구제(`rescue_proposals`, 기본 꺼짐), `SAM31Adapter` 자리.
- `m2a/percept/o3.py`: 재작성. 가림/잘림(cut) 인식 식별·자세, `obj_pose_T`, `pose_reliable`, `consistent_parts`.
- `m2a/percept/geometry.py`: `edge_angle`(윤곽선 직선 방향), `norm_yaw` 추가.
- `m2a/percept/eval.py`: `--seg {plateau,legacy}`, `--mode knn`, `--rescue`, `--split train`(튜닝·점검용), 잘림별 지표 추가. `compare_pose.py`: 잘림 비율·잘림 제외 길이 오차 추가.
- `tests/m2a/test_g_percept.py`(기존 5), `tests/m2a/test_g_plateau.py`(신규 4). `python -m pytest tests/m2a -q` → **120 passed**.

## 사용 모델

| 이름 | revision | 라이선스(HF 카드) | 위치 |
|---|---|---|---|
| `IDEA-Research/grounding-dino-tiny` | `a2bb814dd30d776dcf7e30523b00659f4f141c71` | Apache-2.0 | `~/m2a_data/models/hf/hub/models--IDEA-Research--grounding-dino-tiny/snapshots/<rev>` |
| `facebook/dinov2-small` (frozen, CLS) | `ed25f3a31f01632728cabb09d1542f84ab7b0056` | Apache-2.0 | `~/m2a_data/models/hf/hub/models--facebook--dinov2-small/snapshots/<rev>` |
| SAM2 / SAM 3.1 | 미사용 | - | SAM2 패키지·체크포인트 없음. SAM 3.1은 어댑터 자리만 |

모델 카드 원자료 `raw/*_hf.json`. 갤러리 = train 0–199의 GT 가시 마스크 crop 844개(`train_dinov2_gallery.npz`, 가시 인스턴스만).

## V1 분할: plateau 방식 (이전 높이 히스토그램 분할 대체)

1. 테이블·알려진 트레이 바닥/벽 제거(고정 보정 사용), 높이 7 mm 초과·13.5 cm 미만만 전경.
2. 점군에서 표면 법선을 구해 **윗면(nz>.95)**만 뽑고, 이웃 높이차 3 mm 초과 지점은 끊어 plateau(평평한 윗면) 연결 성분을 만든다. 윗면 픽셀 20개 미만은 버림.
3. plateau를 시드로 측면 픽셀을 깊이 연속(15 mm)·윗면 이하 조건으로 가까운 plateau에 배정(다중 시드 확장). 마스크 = 윗면 + 측면.
4. 각 plateau에서 `cut`(영상 경계 또는 더 가까운 다른 물체와 맞닿은 윗면 픽셀)을 구한다.

이전 방식은 선 모양 측면(세워 둔 다월·캠락)의 높이가 연속이라 "적층 피크"로 오인해 조각내고(1라운드 dev 기준 정밀도 77.7%), 합쳐 버리는 일이 잦았다. 새 방식은 윗면 단위라 붙은 물체도 윗면 높이·깊이 단차로 분리된다.

**GDINO 융합**: GDINO 박스와 plateau 마스크 박스를 IoU≥.25로 일대일 매칭(검출 점수 부여), 박스 없는 plateau는 그대로 통과. `--rescue`(박스에 plateau 없으면 느슨한 기준 nz>.85·8px로 재탐색)도 구현했으나 **dev 100에서 구제 0건**(TP·예측 동일). GDINO tiny 단독 박스: 재현율 가시 60.2%, 정밀도 44.8%(TP 256/예측 572)로 깊이 plateau(91.1% / 99.7%)보다 크게 낮다. 시뮬 무질감 렌더에서는 GDINO가 검출 품질을 올리지 못한다(추정: 도메인 불일치).

## V2 식별: 치수 + 색 + 두께 + DINOv2-S kNN (+ 잘림 처리)

손실 = 윗면 치수 오차(길이 .014·폭 .009 m 허용, 임의 지정) + 14·색 chroma 거리 + 윗면 높이(적층 대비 두께) + 5·(1−갤러리 top-3 평균 코사인, 부품별) + 잘림 시 train 빈도 사전 0.6·(−log p)(임의 지정 가중). 결과는 softmax 상대값(보정 확률 아님).
- **잘림 처리**: 잘린 축은 관측 치수를 "하한"으로 보아 관측이 카탈로그보다 **길 때만** 벌점. 신뢰도 ×0.6, `cut=true`.
- 잘린 판재(P01/.20, P02/.16, P03/.10)는 보이는 길이가 하한일 뿐이라 구분이 불가능하다. 이때는 사전·kNN이 순위를 정하고, `consistent_parts`에 손실이 근접한 후보를 모두 담는다(dev에서 정답 포함률 99.5–99.7%).

## V3 자세

윗면 윤곽 픽셀로 직선 방향(`edge_angle`, 잘림 부근 제외)을 구해 축을 잡고, 식별된 부품의 장축 배치를 손실 최소로 고른다. 잘린 한쪽 끝은 보이는 반대편 끝을 기준으로 카탈로그 길이만큼 **완성**해 중심을 낸다. Z = 윗면 − 부품 반두께. 원통은 yaw 0.

## 결과 (dev 100, 기본 자세 vs perception_pose)

기본 자세 = A 이전 리셋 자세, perception_pose = A의 인식용 팔 자세(`env.perception_pose()`). 같은 seed·scene JSON, `~/m2a_data/percept{,_pose}/dev`. 이전(legacy) 열은 1라운드 방식(깊이 단독, 높이 히스토그램 분할)을 같은 데이터에 다시 돌린 값.

| 지표 | legacy 기본 | legacy pose | **plateau 깊이 기본** | plateau 깊이 pose | **최종 hybrid 기본** | 최종 hybrid pose |
|---|---:|---:|---:|---:|---:|---:|
| GT / 가시 / 예측 / TP | 508/425/421/327 | 508/424/399/321 | 508/425/388/387 | 508/424/387/386 | 508/425/388/387 | 508/424/387/386 |
| 재현율 전체 / 가시 | 64.4% / 76.9% | 63.2% / 75.7% | 76.2% / 91.1% | 76.0% / 91.0% | 76.2% / 91.1% | 76.0% / 91.0% |
| 정밀도 | 77.7% | 80.5% | 99.7% | 99.7% | 99.7% | 99.7% |
| 마스크 IoU (TP) | 87.2% | 88.0% | 91.4% | 91.1% | 91.4% | 91.1% |
| 식별 Top-1 / Top-3 | 54.4% / 81.0% | 56.7% / 81.3% | 72.4% / 99.7% | 72.3% / 99.7% | 79.3% / 100% | 80.3% / 100% |
| Top-1 잘린 것 / 안 잘린 것 | - | - | 52.0% / 100% | 51.8% / 100% | 64.1% / 100% | 65.8% / 100% |
| P01/P02 Top-1 (TP 기준 / 전체 기준) | 26.9% / 25.0% | 28.7% / 25.6% | 55.9% / 55.6% | 55.9% / 55.0% | 70.4% / 70.0% | 72.3% / 71.1% |
| 위치 mm p50 / p95 (TP 전체) | 15.9 / 64.1 | 13.7 / 63.0 | 1.0 / 30.8 | 1.0 / 30.9 | 1.0 / 31.9 | 1.0 / 31.0 |
| 위치 mm p50 / p95 (안 잘림) | - | - | 0.4 / 1.0 | 0.4 / 1.0 | 0.4 / 1.0 | 0.4 / 1.0 |
| 위치 mm p50 / p95 (잘림) | - | - | 19.0 / 36.0 | 19.0 / 36.0 | 2.0 / 49.6 | 2.1 / 46.3 |
| yaw ° p50 / p95 (TP 전체, π 대칭) | 13.3 / 67.6 | 13.4 / 68.5 | 0.8 / 81.9 | 0.8 / 80.3 | 0.8 / 85.3 | 0.8 / 79.1 |
| yaw ° p50 / p95 (`pose_reliable` 만) | - | - | 0.7 / 3.3 | 0.7 / 3.1 | 0.7 / 3.3 | 0.7 / 3.1 |
| 술어 일치 part/region/in_tray/on (TP) | 54.4/100/100/100% | 56.7/100/100/100% | 72.4/99.7/100/99.7% | 72.3/100/100/99.5% | 79.3/99.7/100/100% | 80.3/100/100/100% |
| 같은 지표 (미검출=오류) | 35.0/64.4/64.4/64.4% | 35.8/63.2/63.2/63.2% | 55.1/76.0/76.2/76.0% | 54.9/76.0/76.0/75.6% | 60.4/76.0/76.2/76.2% | 61.0/76.0/76.0/76.0% |
| 양성 회수 in_tray / on | 41/44, 2/13 | 41/44, 2/11 | 44/44, 2/13 | 44/44, 2/11 | 44/44, 3/13 | 44/44, 4/11 |
| 전 술어·검출 완전 일치 장면 | 6 | 8 | 12 | 12 | 14 | 15 |

원자료: legacy `raw/depth_dev.summary.json`, `raw/depth_pose_dev.summary.json` / plateau `raw/v2_depth_{reset,pose}.{jsonl,summary.json}` / 최종 `raw/final_hybrid_{reset,pose}.{jsonl,summary.json}` / 추가 `raw/v2_knn_reset.*`, `raw/v2_hybrid_rescue_reset.*`. 매칭은 박스 IoU≥.5 내림차순 일대일. 식별·자세·술어는 TP 조건부. `region/in_tray/on` 술어는 예측 part_id·좌표를 C의 `symbolic_from_gt`에 넣어 만든 값으로 정확도가 TP 조건부(100% 근처)라는 점이 중요하고, 미검출 포함 값은 76%다.

### 구성별 기여 (기본 자세, dev 100)

| 구성 | TP | 정밀도 | Top-1 | P01/P02 Top-1 | 키프레임 ms p50/p95 |
|---|---:|---:|---:|---:|---:|
| 깊이 plateau 단독 (CPU) | 387 | 99.7% | 72.4% | 55.9% | 143.5 / 209.0 |
| + DINOv2-S kNN (`--mode knn`, GPU) | 387 | 99.7% | 79.3% | 70.4% | 220.3 / 379.7 |
| + GDINO tiny 융합 (`hybrid`) | 387 | 99.7% | 79.3% | 70.4% | 553.9 / 704.8 |
| + GDINO 구제 (`--rescue`) | 387 | 99.7% | 79.3% | 70.4% | (미측정) |

**권장 런타임 구성 = 깊이 plateau + DINOv2-S kNN.** GDINO tiny는 이 조건에서 검출·식별을 더 올리지 못하면서 키프레임 지연만 +330 ms 늘린다. 단점: kNN 이득이 시뮬 생성기의 배치 분포(판재가 좌우 구역 가장자리에 놓여 특정 모양으로 잘림)를 학습한 결과일 수 있다(추정). 안 잘린 물체는 kNN 없이도 100%였다.

## perception_pose 효과 (기본 자세 대비)

- 가시 GT 425 → 424. 새로 보이는 물체 0, 새로 안 보이는 물체 1(`raw/compare_pose_v2.json`). **헤드 카메라는 토르소 고정이라 팔 자세는 시야에 영향이 거의 없다.**
- 판재(P01/P02) 길이 편향: 이전 방식 p50 −64.5 mm(기본) vs −64.8 mm(pose) (`raw/compare_pose_base.json`), 새 방식 보이는 길이 −76.4 vs −75.1 mm. 원인은 팔 가림이 아니라 **영상 경계 잘림**: 매칭된 판재의 79.9%(기본)/79.7%(pose)가 경계에 닿는다. 잘리지 않은 판재의 길이 오차는 −3.0 mm.
- 그러므로 팔 가림 보정이 아니라 잘림 표시·카탈로그 완성이 편향 해소 수단이며, 위 표의 잘림 위치 p50이 19 mm(깊이 단독)/2 mm(kNN 식별과 결합)로 줄었다.

## 지연·VRAM (측정 락 `rp_measure.lock`+`rp_gpu.lock`, 1회 285 s 제한, 렌더·파일 읽기 제외)

- 깊이 plateau CPU: p50 143.5 / p95 209.0 ms (EGL 프로세스 비락 실행, 다른 워커와 CPU 공유 중이라 추정 상한).
- 최종 hybrid(GDINO tiny + DINOv2-S, RX 7600 ROCm): 기본 p50 553.9 / p95 704.8 ms, pose p50 598.0 / p95 775.8 ms. VRAM 피크 alloc 1172.0 MiB / reserved 1240.0 MiB(`raw/final_hybrid_*.summary.json`).
- DINOv2-S만(`knn`): p50 220.3 / p95 379.7 ms, VRAM alloc 169 MiB(`raw/v2_knn_reset.summary.json`, 락 없는 비측정 런).
- 키프레임 지연은 다른 워커 부하의 영향을 받는다(이전 라운드 hybrid 490.6 ms와 차이).

## `o3.perceive` 인터페이스 (E 디스패처용)

```python
from m2a.percept.o3 import O3, perceive
state, graph = perceive(env_or_frame)        # 기본: CPU 깊이 + 카탈로그 식별
o3 = O3(detector=GroundingTiny(), embedder=DinoSmall(), gallery=g)   # ROCm 프로세스, 권장은 detector 생략
state, graph = o3.perceive(env)              # env.render('head'), camera_K('head'), T_table_cam('head')만 읽음 (GT 미사용)
```
- `state`: 계약 §5(`objects[oid] = {part_id, region, in_tray, on}` + `reach`). oid는 키프레임 로컬 `p0,p1,…`.
- `graph['objects'][oid]`: `xyz`(T, 물체 중심 m), `yaw`(rad, π 주기), `top3`, `cut`, `cut_fraction`, `pose_reliable`(잘리고 윗면 400px 미만이면 false, 임의 지정), `consistent_parts`, `box_xyxy`, `detection_score`, `source`, `dimensions`, 술어.
- **`graph['obj_pose_T'][oid] = {xyz, yaw, size, part_id, shape}`** (`size`는 카탈로그 `[x,y,z]` 또는 `[반지름,높이]`, `shape`는 box/cylinder). `SkillRunner.run('grasp_lift', arm, obj_pose_T=graph['obj_pose_T'][oid])`가 그대로 받는다. 동일 dict가 `graph['objects'][oid]['obj_pose_T']`에도 있다.
- 스모크: dev 12장면에서 맞는 예측 8개를 `SkillRunner('P-phys')`에 넣었을 때 검증은 모두 통과했고, 결과 코드(COLLISION 5, GRASP_SLIP 3)가 GT-oid 호출과 **8/8 동일**하게 실패했다. 따라서 실패는 인식 자세 오차가 아니라 스킬 쪽(파지·충돌 문제, A 소관)이다. 성공 0/8은 인식 개선과 별개로 확인이 필요하다.

## SAM 3.1 연결에 필요한 것

`v1.SAM31Adapter.segment_text(rgb, prompts) -> (masks bool[N,H,W], scores float[N])`는 `NotImplementedError`. 필요: (1) WSL 환경에 승인 계정 HF 토큰(코드·로그에 남기지 않음)과 gated 스냅샷 다운로드, (2) 해당 transformers/processor 호환 버전과 ROCm 동작 확인, (3) 빈 프롬프트·입력 리사이즈 복원 검증, (4) plateau 제안 대신 SAM 마스크를 `O3._proposals`에 넣고 `top`(윗면)·`cut`을 마스크와 깊이로 계산하는 어댑터. 현재 plateau 분할이 dev 마스크 IoU 91.4%, 정밀도 99.7%라 이득은 실제 카메라나 질감 환경에서 클 것으로 추정.

## 실패 분석 (기본 자세, 미검출 121 = GT 508 − TP 387)

- **헤드 시야 밖 83개(P04 40, P05 23, D01 9, P06 6, P03 5)**: 중심이 영상 밖. 인식 문제가 아니라 카메라 배치 한계(`raw/v2_depth_reset.jsonl`의 `invisible`, 중심 투영 확인).
- **윗면이 안 보임(<20px) 37개**: 세운 다월(P04 14)·캠락(P05 4)·D01(9)·P06(7)·P03(3). 윗면이 영상 경계 밖이거나 측면만 보여 plateau가 없다. 구제도 0건(평평한 윗면 필요). 측면만 보이는 물체는 현 방식으로 검출 불가.
- 기타 1개(P02).
- **식별 불확실(핵심 한계)**: 안 잘린 TP는 Top-1 100%이나 잘린 TP 223개(TP의 57.6%, 대부분 판재)는 길이를 알 수 없어 Top-1 64.1%(kNN 포함). P01/P02 전체 Top-1 70.0%, Top-3 거의 100%. 위치 오차 p95 31.9 mm는 대부분 잘린 판재에서 온다.
- **적층(`on`)**: GT 양성 13 중 위에 놓인 물체 다수가 윗면이 영상 경계 밖이거나 가려 미검출이라(예: seed 10039, 10041) 3/13. `on` 일치율 100%는 거짓 양성이 없다는 뜻이지 회수율이 높다는 뜻이 아니다.
- **yaw p95 79–85°**: 윗면이 작게 보이는 잘린 조각(`pose_reliable=false`)의 축이 틀린다. 신뢰 자세만 보면 p95 3.1–3.3°.
- 정직한 한계: 이 라운드 디버깅 중 dev 일부 장면(10039, 10041 등)을 시각 점검했다. 임계값·가중치는 사전에 임의 지정했고, 잘림 플래그 버그 수정은 train 0–59로 확인했다. dev 지표로 값을 고르지 않았다.

## 남은 문제

1. 잘린 판재의 길이·중심: 실행기가 접근 후 손목 카메라로 재관측하거나 헤드 시점을 바꿔야 확정된다(`consistent_parts`, `pose_reliable` 활용).
2. 헤드 시야 밖 물체 16.3%(83/508) 처리는 계획기/로봇 이동 쪽 설계가 필요.
3. 스킬 단계 실패(위 스모크)는 A/E와 확인 필요.
4. SAM 3.1 연결, 실사·질감 렌더·봉인 test 검증, LoRA 미수행.
5. 프로파일: 깊이 plateau 143 ms 중 역투영 약 40 ms, 법선 계산 약 50 ms가 큰 비중(추정: 프로파일을 부하 중에 쟀음).

## 재현

```bash
# EGL 프로세스 (CPU). 렌더와 모델은 분리.
conda activate robot_percept; source /home/my/work/robot_percept/sim_test/gl_env.sh
nice -n 10 python -m m2a.percept.dataset --split dev --pose perception --root ~/m2a_data/percept_pose
python -m m2a.percept.eval --mode depth --seg plateau --root ~/m2a_data/percept_pose --out ~/m2a_data/percept/raw/v2_depth_pose.jsonl
python -m m2a.percept.compare_pose --parked ~/m2a_data/percept_pose --out ~/m2a_data/percept/raw/compare_pose_v2.json

# ROCm 프로세스 (측정은 이중 락, 1회 5분 이내)
conda activate robot_percept_rocm
export HSA_ENABLE_DXG_DETECTION=1 LD_LIBRARY_PATH=$CONDA_PREFIX/lib HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
flock -w 900 /tmp/rp_measure.lock flock -w 900 /tmp/rp_gpu.lock timeout 285 python -m m2a.percept.eval --mode hybrid --root ~/m2a_data/percept --gallery ~/m2a_data/percept/train_dinov2_gallery.npz --out ~/m2a_data/percept/raw/final_hybrid_reset.jsonl
python -m m2a.percept.eval --mode knn ...   # 권장 구성(GDINO 없음)
python -m pytest tests/m2a -q               # 120 passed
```
