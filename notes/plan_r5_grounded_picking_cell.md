# r5 계획서 v2: 자연어 지시 기반 범용 피킹 셀 (Grounding DINO 중심)

작성 2026-11-09 부모(1NIgF2z2BvfBSkOh). v2는 Claude 검토자 R5-O(Opus, 구현)·R5-C(Sonnet, 사용자·실용) 합의 반영(notes/plan_r5_review_o.md, notes/plan_r5_review_c.md). **Codex 2차 검토 대기**(11장).
r4 기구학 시각화(notes/plan_r4_industrial_cobot.md v3)는 v2 범위의 티칭 탭으로 흡수(MVP 제외). 휴머노이드 G1은 보조 데모, P1c 추가 투자 중단(기본 OFF, 회귀만 관리).

## 1. 한 줄 정의와 표현 원칙
작업자가 말로 지시하면 카메라 영상에서 해당 물체를 글로 찾아 위치를 구하고, 로봇이 경로·충돌을 검사해 집어 정리하는 웹 기반 작업 셀.
- 표현 원칙: "인식과 위치 추정은 실물 웹캠, 집기는 시뮬레이션"으로 명확히. "MES 연동"이 아니라 "MES를 흉내 낸 생산 지표", "공장 투입 가능" 같은 표현 금지. 안전 감속은 "시뮬 기능이며 인증 아님".

## 2. MVP 범위 (포트폴리오 컷)
| 포함(MVP) | v2로 미룸 |
|-|-|
| G0 환경·측정, G1 인식 모듈화(박스만 기본, SAM 2.1 선택) | 경량 SAM(MobileSAM·EfficientSAM) 비교 |
| W2 축소판: 카메라 보정, 요청 시 1회 grounding 오버레이(+재탐지 버튼 ≤1Hz), 책상 평면 좌표, 스냅샷 트윈 | 연속 트윈·추적, 원본 1280 still, 손가락 지시, 원격 조종 |
| K 작업 셀: /tasks, 상태 머신, 분류 적재, 이력 DB | FoundationPose·RealSense 정밀 6D 경로 |
| 최소 대시보드 1화면, README, 3분 영상 | r4 티칭 탭, 유일 로봇 교체, LLM 한국어 해석, FP 포함 Docker |
| Docker는 "박스만+시뮬" 이미지만 | |

## 3. 인식 파이프라인 (모듈 교체형)
| 단계 | 역할 | MVP 기본 | 선택/v2 |
|-|-|-|-|
| ① Grounding | 문장 → 박스·라벨·점수 | Grounding DINO(코드 Apache-2.0, HF transformers; **가중치·모델카드 라이선스는 G0에서 직접 확인**) | OWLv2(라이선스 확인 필요), Florence-2(MIT, HF 원격 코드 실행 주의). YOLO-World(GPL-3.0) 제외 |
| ② Segmentation | 박스 → 마스크 | OFF(박스만) | SAM 2.1(기존), MobileSAM·EfficientSAM(Apache-2.0, v2) |
| ③ Localization | 2D → 책상 평면 위치·yaw | 평면 투영 + **물체 높이 사전값 보정**(박스 하단/마스크 중심; yaw는 마스크를 평면으로 역투영 후 계산) | 시뮬 깊이 중심값, FoundationPose(v2) |
| ④ Grasp / ⑤ Execute | 집기 자세 → IK·충돌·안전 감속·실행 | 위에서 집기, 기존 sim/grasp·control 재사용, 로봇 Panda | 유일 협동로봇(v2) |
- **통합 방식**: 새 CUDA 프로세스를 만들지 않고 기존 인식 프로세스(perception worker)에 동작 `ground`, `segment_box` 추가. 무거운 import는 필요할 때만, 모드 검사는 동작별로. 기존 lazy spawn·GPU 직렬화 재사용. **VRAM 상한 7.0GB**. (web/perception_stub.py는 E 페어 소유 → 조율)
- 한국어 → 영어 물체명: 사전 `config/vocab_ko_en.yaml`. 물체 속성 `config/objects.yaml`(이름→높이·바닥 면적·대칭). 화면 입력은 사전에 없는 물체용 보조.

## 4. 실제 웹캠 (W2 축소판)
- 트래커는 MVP에서 **변경하지 않음**: 기존 미리보기 프레임(640×360, HTTP, 250KB 제한) 사용. 원본 프레임 요청은 v2(바꾸면 트래커 PASS 항목 재측정 필요).
- 보정: `tools/calibrate_camera.py`(체커보드 내부 파라미터, 책상 ArUco 외부 파라미터) → `config/camera_calib.json`.
- 평면 투영 오차의 주원인은 물체 높이 편향(45° 시야에서 60mm 컵이면 약 30mm 추정) → 높이 보정 전/후를 모두 보고.
- 카메라가 없을 때: 녹화 mp4 + 시뮬 조합 허용, [녹화영상] 배지로 구분. 단 기존 회사 녹화본엔 보정판이 없어 **위치 오차는 '측정 불가'**, 선택·오버레이만 검증. 보정판을 함께 찍고 얼굴이 나오지 않는 구도로 새 녹화하면 위치 오차도 측정 가능.
- 개인정보: 'person' 제외는 검출 결과 필터일 뿐 프레임은 서버로 전송됨을 명시. 프레임 저장 OFF, DB에는 박스·점수만.

## 5. 작업 셀 (K)
- `/tasks`: `{"instruction": "...", "mode": "auto|confirm"}` → 파싱 → 물체·목적지 매칭 → 다단계 실행(물체별 집기·놓기).
- 상태 머신: queued → perceiving → planning → executing → done / needs_help / cancelled / aborted. **상태별 타임아웃**, **취소·비상정지**, **서버 재시작 시 실행 중 작업은 aborted 처리**.
- **로봇 소유권 락**: /tasks, 수동 API, teleop, G1이 동시에 로봇을 못 쓰게.
- **셀 전용 장면**(목적지 구역 정의, 기존 Panda 장면 회귀 보호). **장면 자산 확장**: 현재 시뮬 물체 3종(mustard·box·cup, CAD 2개는 같은 파란색)으로는 방해물 장면 100개 이상 불가 → 색·형태가 다른 물체 추가.
- 이력 DB: SQLite, **쓰기 스레드 1개**. 지시문, 검출(박스·점수), 선택 근거, 계획, 결과, 단계별 시간, 실패 원인.
- 실시간: `/status/ws`에 'cell' 키 추가(현재 robot/teleop/humanoid 고정 구조 수정 필요, web/realtime.py 공유 파일).
- 대시보드 1화면: 성공률(Wilson CI), 사이클 타임 분포, 실패 원인 상위, 최근 작업.

## 6. 단계·순서·소요
| 단계 | 내용 | 완료 조건(시연) | 추정 |
|-|-|-|-|
| G0 | (집 PC) ROCm 전용 env로 RX 7600 GPU 시험(HSA_ENABLE_DXG_DETECTION=1, torch 2.14 ROCm 빌드, Grounding DINO·SAM2 대상, FP 제외). env **복제본**에서 `-c notes/rp_constraints.txt`로 transformers 설치 시험(torch 2.14·numpy 2.5.3 고정 유지), 버전·가중치 리비전 고정, 라이선스 확인, VRAM·지연(첫 로드/재사용) 측정 | 설치 재현 스크립트, 측정표 | 0.5~1일 |
| G1 | perception worker 통합(ground, segment_box), 모듈 인터페이스, 장면 자산 확장, 평가 하네스(튜닝/평가 시드 분리) | 시뮬 장면에서 문장→물체 선택, 지표 표 | 3~4일 |
| W2 | 보정 도구, 요청 시 오버레이, 평면 좌표+높이 보정, 스냅샷 트윈 | 실물 물체 → 시뮬 배치, 위치 오차(보정 전/후) | 2~3일(+카메라 일정) |
| K | /tasks·상태 머신·락·DB·셀 장면·분류 적재 | "A는 왼쪽, B는 오른쪽"이 끝까지 실행, needs_help 확인 후 재개 | 3~4일 |
| D | 대시보드 1화면, README, 3분 영상, 박스만 Docker | 원클릭 실행·시연 | 1~2일 |
순서: G0 → G1 → (W2 보정 도구 병행) → K → D. 공유 파일(web/app.py, web/realtime.py, web/perception_stub.py, web/static/humanoid.js, index.html)은 한 번에 한 구현자.

## 7. 합격 기준 (검증자가 직접 재현한 원자료로만 PASS)
- **출처 배지**: 모든 지표에 [시뮬GT] [시뮬인식] [실물웹캠] [녹화영상].
- **Grounding 선택 정확도**: 정답 = 지시 대상과 IoU ≥0.5, 평가 시드는 튜닝과 분리, 장면 N≥100(방해물 장면 별도), 점추정+Wilson 95% CI 병기(예: 90/100 → 82.6~94.5%). CI 하한 기준(N≈200 필요)은 사용자 선택.
- **영역 품질**: 박스 IoU, (선택 시) 마스크 IoU와 처리 ms.
- **위치 오차**: 시뮬 평면 투영 중앙값·p95(mm), 실물은 ArUco 기준점으로 보정 전/후. 목표값은 G0~W2 측정 후 확정.
- **엔드투엔드(시뮬)**: 주결과는 **GT 보조 OFF**, 성공률(Wilson CI)·단계별 시간 p50/p95(지시→오버레이→집기 시작→완료), GT 보조 ON은 참고. **오인식 실패 사례 갤러리**.
- **애매한 지시**: 확인 요청 정밀도/재현율, 확인 없이 잘못 집은 비율.
- **자원·성능**: VRAM ≤7.0GB, Grounding 1회 지연(회사 GPU / 집 CPU), 웹 화면 ≥29.7fps, 기존 Panda·G1·트래커 회귀 없음, 전체 pytest 통과.
- **표기**: 근사·비제휴 문구, 모델별 라이선스 표(THIRD_PARTY_NOTICES 갱신), 시뮬/실물 분리 서술.

## 8. 팀·파일
| 페어 | 구현(Codex) | 검증(Claude) | 범위 |
|-|-|-|-|
| G(인식) | I-G | V-G | perception/grounding·segment·localize, perception worker 동작 추가, config/, bench/eval 확장, 장면 자산 |
| W2(웹캠) | I-C | V-C | tools/calibrate_camera.py, 평면 투영·높이 보정, 스냅샷 트윈 |
| K(셀) | I-K | V-K | web/cell*.py, DB, /tasks, 락, 대시보드 |
측정 규칙은 notes/TEAM_R3.md(측정·전체 pytest는 측정 락 안).

## 9. 위험
| 위험 | 대응 |
|-|-|
| transformers 설치가 torch·numpy 고정을 깸 | G0에서 env 복제본으로 먼저 시험, 실패 시 대안(별도 경량 env + IPC) 검토 |
| 시뮬 렌더 도메인 차이로 정확도 저하 | G1 측정, 프롬프트·임계 조정, 실물은 유리 |
| 8GB GPU 공존 | 기존 worker 통합, 박스만 기본, VRAM ≤7GB 기준 |
| 평면 높이 편향 | 높이 사전값 보정, 전/후 보고 |
| 범위 과다 | MVP 컷 고정, v2 목록 분리 |
| 라이선스·개인정보 | 가중치 라이선스 확인, GPL 제외, 프레임 미저장 |

## 10. 사용자 확인 (검토자 권장 답)
1. 작업 셀 로봇: **Panda로 시작, 유일 로봇은 v2** (권장)
2. 실물 물체: **색·형태가 뚜렷한 3개(머그컵, 작은 박스, 캔 또는 병) + 목적지 상자 2개**, 투명·반사·작은 물체 제외 (권장)
3. 깊이 카메라: **MVP엔 불필요**, 생기면 v2 확장 (권장)
4. P1c 중단: **동의 권장**(기본 OFF 유지, 회귀만)
5. (추가) 통계 기준: 점추정+CI 병기(N≥100) vs CI 하한 기준(N≈200)
6. (추가) 보정판을 함께 찍은 얼굴 없는 새 녹화 가능 여부(위치 오차 측정용)

## 11. 검토 상태
- 1차(완료): Claude R5-O·R5-C 합의, 이견 없음.
- 2차(대기): **Codex 검토** — 16:55경 사용량 리셋 예상. 결과 notes/plan_r5_review_x.md. Codex 지적 반영(v3) 후 구현 착수.
