# r5 계획서 검토 R5-O (구현자 관점)

검토 대상: notes/plan_r5_grounded_picking_cell.md v1. 검토자 R5-O(Claude), 2026-11-09. 읽기 전용 검토(코드·서버·카메라 실행 없음).
확인 근거: conda env 패키지 조회, perception_stub.py·app.py·realtime.py·teleop.py·teleop_tracker_win.py·sim/env.py·sim/objects.py·sim/control.py·eval/run_benchmark.py 읽기, 웹(라이선스).
동료 R5-C(Sonnet, 사용자·실용 관점, notes/plan_r5_review_c.md)와 합의 결과는 7장.

## 1. Grounding DINO 통합 실현성

### 1.1 transformers 설치·버전 (블로커)
- 사실: `robot_percept`, `ai` conda env 모두 `transformers` 미설치(ModuleNotFoundError). huggingface_hub·tokenizers·safetensors도 없음. rp_constraints.txt에 numpy 2.5.3, torch 2.14.0+cu130, torchvision 0.29.0+cu130, opencv 5.0.0.93 고정.
- 위험: `pip install transformers`가 numpy·torch를 바꾸거나 tokenizers 휠이 없으면 FP·SAM2 env가 깨짐. transformers v4→v5에서 `post_process_grounded_object_detection` 인자명(`box_threshold`→`threshold`, `text_labels`) 등 API 차이.
- 수정안(1단계 0번 작업, 단계 G 시작 전):
  1. `conda create --name rp_gd --clone robot_percept`에서 `pip install "transformers==<X>" -c notes/rp_constraints.txt`로 설치 가능성 확인(설치 로그에서 numpy/torch 변경 0 확인).
  2. 통과한 버전을 rp_constraints.txt에 추가(transformers, tokenizers, huggingface_hub, safetensors 정확 고정).
  3. 가중치는 `IDEA-Research/grounding-dino-tiny` revision(커밋 해시) 고정, `HF_HUB_OFFLINE=1`로 실행 시 네트워크 안 씀. 캐시 경로를 THIRD_PARTY_NOTICES/README에 기록.
  4. HF 구현은 순수 PyTorch deformable attention이라 추가 CUDA 빌드 불필요(원본 IDEA 저장소의 `_C` 빌드 경로는 쓰지 말 것: cu130·cxx20 빌드 고생 반복 위험).
- 집 AMD PC(CPU): 같은 pin으로 CPU torch에서 동작 확인을 별도 항목으로.

### 1.2 VRAM (8GB RTX 2080 SUPER)
- 현재: 유휴 1.16GB 사용(nvidia-smi). SAM2.1 small은 worker 안에서 사용 후 `model.to('cpu')`+`empty_cache`, FP는 상주.
- 추정(측정 전): grounding-dino-tiny(약 172M 파라미터) fp32 가중치 ~0.7GB, 800px 추론 활성 포함 피크 1~2GB. **별도 CUDA 프로세스를 만들면 컨텍스트 ~0.3~0.5GB 추가**되고 GPU 직렬화가 깨짐.
- 수정안: Detector를 **기존 perception worker(_worker)의 새 op 'ground'**로 넣고 SAM과 같은 패턴(호출 후 CPU 오프로드, 상주 여부는 측정 후 결정). 합격 기준에 "DINO+SAM2+FP 순차 실행 시 peak_mb와 nvidia-smi 총사용량 ≤7.0GB" 추가. fp16 autocast는 정확도 영향 측정 후 선택.

### 1.3 추론 지연
- 2080S tiny 1회 지연은 미측정(추정 100~300ms + CPU→GPU 이동 시 수백 ms). "작업 시작 시 1회" 정책이면 충분.
- 모순: 6장 2단계 "실시간 grounding 오버레이"는 3장 "1회(또는 저주파)"와 충돌하고 웹 29.7fps 기준·GPU 직렬화와 경쟁. 수정안: MVP는 **요청 시 1회 + 재탐지 버튼(최대 1Hz)**, 연속 추적(박스 트래커)은 v2. 지연은 cold(첫 로드)/warm 분리 보고, 기존 warmup_async에 ground 워밍업 추가(G1 defer 규칙 그대로).

### 1.4 시뮬 렌더 도메인 차이
- 사실: sim/objects.py 레지스트리는 mustard(텍스처) + cad_uploads/converted의 CAD(box 계열 4종은 사실상 같은 박스, cup 1종)뿐이고 CAD는 기본 rgba (.25,.6,.85) **같은 파란색**. shadows/reflections 기본 OFF, 640×480.
- 문제: "방해물 포함 N≥100" 장면을 만들 물체 다양성이 없음. 같은 색 박스/컵은 형태만으로 구분해야 해 DINO 성능을 과소평가할 수 있고, "파란 컵" 같은 속성 지시 평가는 불가.
- 수정안: (a) 평가 자산 확장: 색이 다른 primitive(박스·원통·구) + 라이선스 확인된 YCB 일부(모델별 라이선스 표 필수), 물체 6~10종. (b) 렌더 옵션 A/B(그림자 ON/OFF, 조명 무작위) 보고. (c) 프롬프트 규칙 고정: 소문자, "cup . mustard bottle . box ." 형식, 토큰 길이 ≤256. (d) 임계(box/text threshold)는 별도 튜닝 시드에서만 정하고 평가 시드와 분리(데이터 누수 방지).

## 2. 모듈 교체형 인터페이스와 기존 경로의 맞물림 (최소 변경안)

현재 경로: app.py `select_at(x,y)` → `perception.call('segment', click)`(SAM2 + select_candidate) → `call('register', mask)`(FP) → track_loop `call('track')`. PerceptionBackend.call은 `mode!='fp'`면 RuntimeError, _worker는 시작 시 FP·sam2를 import.

최소 변경안:
1. `perception/grounding.py`: `detect(rgb, phrases) -> list[Det(box_xyxy, label, phrase_idx, score)]`. 구현 2개: `GroundingDinoHF`(worker 안), `SimGTDetector`(시뮬 seg 마스크에서 박스 생성, **GT 보조로 표기**, 테스트·상한선용).
2. `perception/segment.py`: `segment(rgb, box, depth=None) -> mask|None`. SAM2는 기존 predictor에 `box=` 프롬프트(SAM2ImagePredictor가 지원), 클릭 경로의 select_candidate는 박스 프롬프트엔 그대로 못 씀(click 필수) → 박스 내 연결성분 선택 함수 별도.
3. `perception/localize.py`: Plane/Depth/FP. Plane·Depth는 numpy만이라 Flask 프로세스에서 실행 가능, FP만 worker.
4. `web/perception_stub.py`: _worker에 op `ground`, `segment_box` 추가, **heavy import를 op별 lazy**로(박스만/CPU 모드에서 FP·nvdiffrast import 실패해도 동작). `call()`의 mode 검사를 op 단위로(`ground`는 `fp|ground` 모드 허용, `register/track`은 fp만). 기존 테스트(warmup·G1 defer)는 회귀 대상.
5. app.py: `select_at(x,y)`를 `select_by_box(det)`/`select_by_click(x,y)`로 분기만 추가(FP register 입력 mask를 grounding 결과로 대체 가능). 기존 /click 계약 불변.
6. 설정: `config/perception.yaml` 대신 PyYAML 의존이 없으면 `tomllib`(표준) 또는 JSON 권장(env에 PyYAML 있는지 확인 후 결정).

## 3. 웹캠 평면 투영 정확도와 원본 프레임 요청

### 3.1 정확도 기대치
- 화소 해상도: 1280×720, 수평 FOV ~70°, 카메라-책상 ~0.8m·45° 기울기 가정 시 1px ≈ 1~1.5mm(640 preview면 2~3mm). 보정(체커보드 재투영 <0.5px, ArUco 단일 마커 자세) 오차 2~5mm 수준.
- **지배 오차는 물체 높이 편향**: 45° 시선에서 박스 하단 중심은 물체 바닥 중심이 아니라 앞쪽 가장자리, 마스크 중심은 높이 h의 물체에서 대략 (h/2)·tan(시선각)만큼 밀림 → 60mm 컵이면 ~30mm, 반지름 35mm 편향도 별도. 보정 없이 "중앙값 ≤10mm"는 불가능에 가까움.
- 수정안: 물체별 높이·footprint 사전값(vocab 사전에 함께) → 박스 중심 광선을 z=h/2 평면과 교차, 또는 하단 중심+반지름 보정. 지표는 "보정 전/후" 둘 다. 목표 확정은 1단계 측정 후(계획서 문구 유지).
- yaw: 위에서 본 게 아니라 45° 원근이므로 마스크 PCA는 이미지 평면에서 하면 왜곡 → 마스크 윤곽을 책상 평면으로 역투영 후 minAreaRect. 원통(컵)은 yaw 무의미 → 대칭 물체 yaw 제외 규칙.
- 측정법: 시뮬은 SimEnv의 K·T_world_cam(status에 있음)을 그대로 써서 **기하 알고리즘만** 평가(GT 위치=MuJoCo 물체 pose xy). 실물은 ArUco 기준 인쇄 격자(A3, 십자 표시 좌표 기지)에 물체 바닥 중심을 맞춰 놓고 N≥20 배치×물체별 오차.
- 카메라 모드: 내부 파라미터는 **실제 캡처 모드(MJPG 1280×720)**에서 보정, preview 640×360을 쓰면 K를 0.5배 스케일(같은 화각·크롭인지 확인).

### 3.2 트래커 원본 프레임 요청 (카메라 단일 프로세스)
- 사실: 트래커가 1280×720 캡처, preview는 JPEG q65 HTTP POST `/teleop/preview`(250KB 제한), binary WS는 Windows→WSL 40ms 지연 ACK 회귀로 preview를 HTTP로 유지(teleop_tracker_win.py 207행 주석). 서버→트래커 푸시 채널 없음(트래커는 클라이언트, WS 응답만 존재).
- 수정안(v2): 서버가 tracker WS 응답에 `still_request: <id>` 플래그 → 트래커가 원본 1장을 q90 JPEG로 **별도 HTTP 라우트 `/perception/still`(크기 제한 1MB, capture_at·seq 포함)**로 1회 전송, 서버는 오래된 still 거부. 트래커 PASS 항목(Panda/compact 처리율·수신 Hz) 회귀 재측정 필요.
- **MVP 권고: 트래커 무변경, 기존 preview 프레임(640) 사용**. DINO는 내부에서 짧은 변 800으로 리사이즈하므로 640 입력도 동작, 위치 해상도 2~3mm/px는 높이 편향보다 작음.
- 보정 도구도 카메라가 필요 → `tools/calibrate_camera.py`는 (a) 트래커 정지 상태 단독 실행 또는 (b) 서버의 preview/still을 받아 처리 중 하나를 명시. 회사 USB 카메라는 현재 분리 상태(TEAM_R3) → 2단계는 하드웨어 일정 의존, 시뮬과 녹화본(회사 mp4는 얼굴 포함, 수치만)으로 선행 개발.

## 4. /tasks 상태 머신·DB·/status/ws 'cell' 누락
1. **로봇 소유권**: 기존 /click·/pick·/place·/reset·/randomize, teleop, G1 모드와 작업 셀이 같은 시뮬 로봇을 씀. 단일 executor + 소유권 락(셀 실행 중 수동 API 409, teleop/G1 ON이면 needs_help 또는 거부) 명시.
2. **취소·비상정지**: `POST /tasks/<id>/cancel`, 전역 stop(실행 중 동작은 안전 정지 후 aborted). 상태에 `cancelled`, `failed`, `aborted` 추가(done/needs_help만으론 부족).
3. **하위 step**: "컵은 왼쪽, 머스터드는 오른쪽"은 물체당 perceive→plan→pick→place 반복. task(1)–step(N) 구조, 부분 성공 표기.
4. **타임아웃·재시도**: 상태별 타임아웃(perceiving 10s, executing 60s 등), 집기 실패 재시도 횟수, needs_help 무응답 타임아웃→failed.
5. **resumed 의미**: needs_help → (선택 확정) → planning으로 복귀를 명시. 원격 조종 개입 후 복귀 시 장면 재인식 필수.
6. **재시작 복구**: 서버 시작 시 DB의 running 작업을 `interrupted`로 마감, 큐 자동 재개 안 함.
7. **목적지 정의**: "왼쪽 상자" 존(이름→xy·크기) 설정 파일, bin 자산을 장면에 추가하면 **기존 Panda 회귀·eval 시드 재현성에 영향** → 셀 전용 장면 프리셋으로 분리.
8. **DB**: SQLite WAL, 단일 writer 스레드(HTTP 스레드에서 직접 쓰지 않기), schema_version, 이미지·프레임 미저장(박스·점수·crop 없음), 보존 기간. 측정 규칙상 DB 쓰기가 fps에 주는 영향 확인.
9. **'cell' 빌더**: realtime.py `StatusSchedule`의 `next`/`active` 키가 robot/teleop/humanoid로 하드코딩 → 'cell' 추가 시 스케줄 수정 필요. 작업 활성 시 5Hz·비활성 1Hz, payload 크기 제한, 검출 오버레이는 frame seq·이미지 좌표 포함(어느 프레임 기준 박스인지).
10. **API 형태**: 202 + task_id, `GET /tasks/<id>`, 멱등 키(중복 제출), `mode=confirm`의 확인 API(`POST /tasks/<id>/confirm {candidate}`).
11. **GT 보조**: sim/control.py `Controller(gt_assist=True)`가 기본 → E2E는 gt_assist off를 주 결과로, on은 별도 표기.

## 5. 합격 기준 측정 가능성·단계 순서·소요

### 5.1 시뮬 GT 장면 N≥100 생성
- `eval/grounding_bench.py`(신규, 웹 서버 미기동, run_benchmark.py 패턴): seed→SimEnv(objects=부분집합, randomize)→render_rgbd(seg 포함)→GT 박스(seg 마스크 bbox, 가림 비율 기록)→지시문 템플릿 생성(범주/색/공간 "왼쪽의")→Detector→판정.
- top-1 정답 정의: 선택 박스와 목표 GT 박스 IoU≥0.5 (가림 >50% 장면은 별도 집계). 방해물 장면 = 같은 범주 또는 유사 범주 동시 존재.
- 통계: top-1 90/100이면 Wilson 95% CI [82.6%, 94.5%]. "점 추정 ≥90%"인지 "CI 하한 ≥85%"인지 기준 명시 필요. CI 하한 기준이면 N≈200.
- 튜닝 시드와 평가 시드 분리, 시드 목록·git hash·가중치 revision을 결과 JSON에.
### 5.2 위치 오차
- 시뮬: 평면 투영 xy vs MuJoCo GT xy(mm), 중앙값·p95, 높이 보정 전/후, 물체별. 깊이 경로(DepthLocalizer)도 같은 장면으로 비교.
- 실물: 3.1의 인쇄 격자 방식. ArUco 자체 자세 오차도 별도 기록.
### 5.3 기타
- 엔드투엔드: gt_assist off 주결과, Wilson CI, 사이클 p50/p95, 실패 원인 분류(인식/계획/집기/놓기).
- 애매 지시: 애매 세트(같은 범주 2개 등)를 생성기로 라벨링해야 정밀도/재현율 계산 가능 → 생성기에 `ambiguous=True` 라벨.
- 성능: ≥29.7fps는 기존 측정 락 규칙(measure→gpu)으로, ground 실행 중 화면 fps 하락도 측정.
### 5.4 순서·병렬화·소요(추정)
| 단계 | 선행 | 병렬 가능 | 추정 |
|-|-|-|-|
| G0 transformers pin·VRAM/지연 측정 | 없음 | W2 보정 도구 작성 | 0.5~1일 |
| G1 인터페이스+worker op+grounding_bench+자산 확장 | G0 | W2, K의 DB/상태머신 단위(목 Detector) | 3~4일 |
| W2 보정+평면 투영(시뮬 기하 먼저) | 카메라 연결 | G1 | 2~3일(+카메라 일정) |
| K 셀 MVP | Detector 인터페이스 고정 | 상태머신·DB는 목으로 선행 | 3~4일 |
| 대시보드 1화면 | K | | 1~2일 |
- 공유 파일(app.py, realtime.py, perception_stub.py)은 G→K 순서로 한 구현자씩. perception_stub.py는 E 페어(FP 워밍업) 소유와 충돌 → 페어 간 소유권 조율 명시.
- Codex 한도(11-09 사례)로 실제 달력은 더 길어짐.

## 6. 빠진 것·과한 것·라이선스

### 빠진 것
- transformers 미설치·pin(1.1), 평가 자산 다양성(1.4), 높이 편향 보정(3.1), 로봇 소유권·취소(4), GT 보조 기본 ON(4.11), perception_stub의 E 페어 소유 충돌(5.4).
- 한국어→영어 사전 미등록 단어 처리(needs_help로 보내기), DINO가 같은 물체에 여러 phrase를 붙일 때 중복 제거(NMS, phrase별 최고 1개).
- 'person' 제외: 필터일 뿐 프레임은 서버로 전송됨 → 표기·저장 OFF(R5-C 의견과 동일).

### 과한 것
- 5단계 r4 티칭 탭, 손가락 지시, 원격 조종 연결, 연속 트윈, FP/RealSense 실물 6D → v2.
- Docker: FP·nvdiffrast·cu130 포함 이미지는 과함 → "박스만 + 시뮬(CPU 가능)" 이미지로 한정.
- 조합별 마스크 IoU 표(박스만/MobileSAM/SAM2.1): MobileSAM·EfficientSAM은 새 의존성 → MVP는 박스만 vs SAM2.1 둘만, 경량 SAM은 v2.
- 유일 로봇 교체는 5단계 이후 유지(Panda 시작).

### 라이선스 (웹 확인, 11-09)
| 모델 | 코드 | 가중치/모델카드 | 비고 |
|-|-|-|-|
| Grounding DINO | Apache-2.0 (IDEA-Research/GroundingDINO, HF transformers 구현도 Apache-2.0) | HF `IDEA-Research/grounding-dino-tiny` 모델카드 라이선스는 구현 시 revision과 함께 재확인·기록 | 학습 데이터 출처는 별도 |
| OWLv2 | Apache-2.0 (google-research/scenic) | HF google/owlv2-* Apache-2.0로 알려짐, 모델카드 재확인 필요 | transformers 네이티브 |
| Florence-2 | MIT (HF microsoft/Florence-2-large LICENSE 확인) | MIT | HF 저장소가 `custom_code`(trust_remote_code) → 원격 코드 실행 위험, 사용 시 revision 고정 또는 transformers 네이티브 구현 여부 확인 |
| MobileSAM | Apache-2.0 (ChaoningZhang/MobileSAM LICENSE 확인) | Apache-2.0 | |
| EfficientSAM | Apache-2.0 (yformer/EfficientSAM 확인) | Apache-2.0 | |
| YOLO-World | GPL-3.0 | | 계획대로 제외 |
- YCB 자산을 쓰면 별도 라이선스 표기. 저장소에 가중치 커밋 금지(다운로드 스크립트+해시).

## 7. R5-C와의 합의·이견
1회 왕복 완료(R5-O 지적 7개 송부 → R5-C 전부 수용 + 보탬 5개 → R5-O 단서 2개 회신).

합의:
- MVP 컷: 1단계(G) + 2단계 축소(보정, 요청 시 1회 grounding 오버레이, 평면 좌표, 트윈은 스냅샷 1회 생성) + 3단계(K) + 최소 대시보드 1화면 + 박스만·시뮬 Docker/README/3분 영상. v2: 손가락 지시, 원격 조종 연결, 연속 트윈·연속 추적, still 원본 프레임, FP/RealSense 실물 6D, r4 티칭 탭, 유일 로봇 교체, LLM 한국어 해석, MobileSAM/EfficientSAM.
- 순서: G0(pin·측정) → G1 → W2(보정은 G와 병행) → K(Detector 인터페이스 고정 후, 상태머신·DB는 목으로 선행).
- R5-O 1~7(transformers pin 선행, worker op 통합·op별 lazy import, 실시간 오버레이 삭제, 평가 자산 확장, 높이 편향 보정, MVP는 트래커 무변경 preview 사용, /tasks 누락 항목) 전부 수용.
- 통계: 기본은 N≥100에 점 추정+Wilson CI 병기, "CI 하한 기준(N≈200)"은 사용자 선택 사항.
- 실물 2단계는 카메라 일정 의존 → '녹화 mp4 + 시뮬' 대체 경로를 MVP 완료 조건에 허용하되 [녹화영상] 배지로 분리. **단서(R5-O)**: 기존 회사 녹화본은 체커보드/ArUco가 없어 보정 불가 → grounding 선택·오버레이만 검증, 위치 오차는 '측정 불가' 표기(보정 판을 함께 찍은 얼굴 없는 새 녹화면 가능).
- 위치 오차 목표는 높이 보정 후 측정치로 확정. 높이 사전값은 1차로 vocab 설정(물체명→높이·footprint·대칭), UI 입력은 미등록 물체 보조(R5-C 제안 + R5-O 단서).
- 모든 지표에 [시뮬GT]/[시뮬인식]/[실물웹캠]/[녹화영상] 배지, GT 보조 상시 표기, 체감 지표(지시→오버레이/집기 시작/완료 p50/p95), 실패 케이스 갤러리(R5-C).
- Docker는 박스만+시뮬 이미지 한정. 'person' 제외는 필터일 뿐(프레임 저장 OFF, DB엔 박스·점수만), 안전 감속은 시뮬 기능이며 인증 아님.

이견: 없음.

## 8. 계획서 v2 반영 요청 요약(부모용)
1. 6장 1단계 앞에 G0 추가: transformers 등 pin(env 복제본 검증), 가중치 revision 고정, VRAM·지연(cold/warm) 측정.
2. 3장 인터페이스: Detector는 perception worker의 op로, call() mode 검사 op 단위, heavy import lazy. perception_stub.py 소유권(E 페어) 조율.
3. 6장 2단계 "실시간 grounding 오버레이" → "요청 시 1회 + 재탐지(≤1Hz)".
4. 7장: 정답 정의(IoU≥0.5), 튜닝/평가 시드 분리, 통계 기준, 위치 오차 높이 보정 전/후, VRAM ≤7.0GB, gt_assist off 주결과, 애매 세트 라벨.
5. 5장: 소유권 락, 취소/정지, task–step, 타임아웃, 재시작 복구, 목적지 존·셀 전용 장면 프리셋, StatusSchedule 수정, SQLite 단일 writer.
6. 4장: MVP는 트래커 무변경(preview), still 라우트는 v2, 보정 도구의 카메라 사용 방식 명시, 카메라 분리 상태 반영.
7. 9장 위험 추가: 의존성 설치로 env 파손, 평가 자산 부족, 높이 편향, 공유 파일 소유권.
8. 라이선스 표(6장 표) THIRD_PARTY_NOTICES에 반영, Florence-2는 custom_code 주의.

## 9. 2차 합의 (Codex R5-X, notes/plan_r5_review_x.md)
왕복 2회 완료, 이견 없음. R5-X 지적은 R5-O가 코드로 직접 확인함(web/sim_worker.py 123·127·152·162행, web/app.py Runtime.wait, tools/teleop_tracker_win.py 303·374·418~438행, sim/grasp.py TOP_MAX_H, robot_percept env site-packages의 numpy dist-info).

1차 합의를 정정·보강한 내용:
1. **취소·정지(4장 2번 정정)**: sim_worker는 `command_q.get_nowait()` 후 pick_object/place_object를 끝까지 동기로 실행하고, stop_event는 바깥 루프에서만 검사함. cancel을 같은 FIFO에 넣으면 진행 중인 동작을 못 멈춤 → 별도 mp.Event + Controller step_hook/IK 경계에서 협조적으로 중단, worker ACK가 올 때까지 owner 유지. 명령에 owner/epoch 토큰을 넣음.
2. **결과 유실**: `Runtime.wait`는 `last_command` 하나만 폴링해서 후속 명령이 덮어쓰면 결과가 사라지고, timeout이 나도 큐 실행은 취소되지 않음 → 결과를 cid별로 보관.
3. **GT 경로 재사용 금지**: 기존 select_at은 SAM 마스크와 GT seg 겹침으로 물체를 식별하고, non-fp estimate_pose는 GT에 지터를 더한 값임 → 셀 E2E에서 재사용 금지. 쓰면 GT 보조로 표기.
4. **G0 의존성(1.1 정정)**: transformers 4.57.6이 1차 후보, 4.45.2가 비교 후보(PyPI 메타데이터상 고정 numpy/torch와 선언 충돌 없음, 실행은 G0에서 검증). 위험 서술은 "resolver/ABI/선택 import 위험"으로 고침. numpy 2.5.2·2.5.3 dist-info가 중복돼 있으니 임의로 지우지 말고 import/version/file + `pip check`로 진단한 뒤 검증 env에서 복구. ROCm/CPU는 공통 pin + backend overlay로 분리. PyYAML 6.0.3이 설치돼 있으니 YAML 설정 유지(2장 6번 정정). Grounding DINO tiny HF README의 apache-2.0 메타태그는 R5-X가 직접 확인함.
5. **집기 일관성**: plan_grasps는 h≤0.07이면 top, h>0.07(>70mm)이면 side 우선 → 계획서의 "top-down + 기존 grasp 재사용"과 모순. strict top 필터를 쓰거나 MVP 물체에서 70mm 초과는 빼고, 판단은 높이 사전값으로.
6. **W2 preview(3.1·3.2 정정, P0)**: 트래커는 `cv2.flip(frame,1)` 후 640×360으로 줄이고, 손·자세 그림을 frame에 직접 그린 뒤 JPEG q65로 보냄. 1차의 "K 0.5배"만으로는 틀림 → 좌우 반전 역변환(u'=W-1-u) 필수. MVP에서 트래커를 바꾸지 않으려면 서버에서 unflip하고, 손·사람이 없는 장면으로 한정하고, UI 박스는 역변환. 서버에 received_at+seq를 기록(실제 촬영 시각이 아님을 명시). 깨끗한 원본은 v2 still 경로(트래커 변경 + 회귀 재측정).
7. **보정 캡처**(R5-O 제안, R5-X 조건부 동의): 체커보드/ArUco 보정은 트래커를 멈춘 상태에서 단독 도구로 1280 원본을 캡처. 조건: 캡처 장치·모드·FOV·crop이 같은지 확인, K는 preview 배율과 mirror/unflip 변환을 반영, 독립 격자점으로 검증.
