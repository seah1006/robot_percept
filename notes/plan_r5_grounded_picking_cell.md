# r5 계획서 v1: 자연어 지시 기반 범용 피킹 셀 (Grounding DINO 중심)

작성 2026-11-09 부모(1NIgF2z2BvfBSkOh). 사용자 결정: "실용성 + 로보틱스" 방향, SAM 2.1에 얽매이지 않고 Grounding DINO(텍스트→영역 grounding)를 인식의 중심으로. r4 기구학 시각화(notes/plan_r4_industrial_cobot.md v3)는 이 계획의 **티칭·디버깅 탭(5단계)**으로 흡수·축소한다. 휴머노이드 G1은 보조 데모로 유지(P1c 추가 투자 중단, 기본 OFF 실험 기능).

## 1. 한 줄 정의
작업자가 말로 지시하면 카메라 영상에서 해당 물체를 글로 찾아 위치·자세를 구하고, 로봇이 경로·충돌을 검사해 집어 정리하는 웹 기반 작업 셀(실물 웹캠 ↔ 시뮬레이션 디지털 트윈 포함).

## 2. 왜 이 방향인가
- 로보틱스: 개방형 인식 → 위치·자세 → IK·경로·충돌 검사·안전 감속 → 실행이 한 흐름으로 보인다.
- 실용성: 새 품목을 재학습 없이 이름으로 지시, 좌표·코드 없이 말로 지시, 애매하면 사람 확인(human-in-the-loop), 생산 지표 기록(MES/SCADA 흉내). 유일로보틱스 카탈로그의 취출·팔레타이징·스마트팩토리 연동과 결이 같다.
- 백엔드 강점: 작업 지시 API·작업 큐·WebSocket 실시간·작업 이력 DB·지표 대시보드.

## 3. 인식 파이프라인 (모듈 교체형)
| 단계 | 역할 | 기본 | 대안(라이선스) |
|-|-|-|-|
| ① Grounding | 문장 → 박스+라벨+점수 | Grounding DINO (Apache-2.0, HuggingFace transformers) | OWLv2, Florence-2 (검토 시 라이선스 확인). YOLO-World는 GPL-3.0이라 기본 제외 |
| ② Segmentation(선택) | 박스 → 마스크 | OFF(박스만) | SAM 2.1(기존 클릭 선택 개선 재사용), MobileSAM·EfficientSAM(경량) |
| ③ Localization | 2D → 3D 위치/자세 | 웹캠: 책상 평면 투영(박스 하단 중심 또는 마스크 중심, yaw는 마스크 PCA/최소 사각형) | 시뮬 RGB-D: 깊이 중심값, 정밀: FoundationPose(CAD 필요, 기존 경로) |
| ④ Grasp | 위치 → 잡기 자세 | 위에서 집기(top-down) | 물체별 규칙, 기존 sim/grasp.py 계획 재사용 |
| ⑤ Execute | IK·충돌·안전 감속·실행 | 시뮬 로봇(Panda 또는 유일 협동로봇) | 산업용(YMX) 비교 |
- 인터페이스: `perception/grounding.py`(Detector), `perception/segment.py`(Segmenter, None 허용), `perception/localize.py`(PlaneLocalizer / DepthLocalizer / FPLocalizer). 조합은 설정(`config/perception.yaml`)으로 고른다.
- 한국어 지시 → 영어 물체명: 1차는 사전(`config/vocab_ko_en.yaml`), 필요 시 LLM 선택 옵션.
- GPU: Grounding DINO는 작업 시작 시 1회(또는 저주파 재탐지) 실행, 이후 추적은 경량. SAM2·FP와 동시 상주하지 않도록 기존 lazy spawn·GPU 직렬화 정책 재사용(8GB). 집 AMD PC는 CPU 모드(느림 표기).

## 4. 실제 웹캠 연결 (디지털 트윈)
- 카메라 1개를 한 프로세스만 연다 → 기존 Windows 트래커가 캡처·송신(미리보기 640×360 30fps, 인식 요청 시 원본 1280×720 1장)하고 서버가 손 추적·물체 인식에 같이 쓴다.
- 보정 1회: 체커보드로 내부 파라미터, 책상 위 ArUco 마커로 카메라↔책상 외부 파라미터(`tools/calibrate_camera.py`, 결과 `config/camera_calib.json`, 개인 영상은 저장소 미포함).
- 실물 → 시뮬: 검출 물체를 책상 평면 좌표로 변환해 시뮬레이션에 같은 배치로 생성, 실물을 옮기면 트윈도 갱신(저주파).
- 손으로 지시: 기존 손끝 좌표(MediaPipe)로 가리킨 물체 선택(선택 기능).
- 개인정보: 'person' 검출은 대상에서 제외, 프레임·영상 저장 기본 OFF.
- 정밀 6D 실물 자세는 깊이 카메라(RealSense 등)가 있을 때의 확장(교수님 가이드에 pyrealsense2 포함, 학교 장비 대여 확인).

## 5. 작업 셀 (백엔드)
- `/tasks` API: `{"instruction": "컵은 왼쪽 상자, 머스터드는 오른쪽 상자", "mode": "auto|confirm"}` → 파싱 → 계획(물체·목적지 매칭) → 실행 큐.
- 상태 머신: queued → perceiving → planning → executing → done / needs_help(애매·저신뢰·실패) → (사람 확인 또는 원격 조종) → resumed.
- 작업 이력 DB(SQLite): 지시문, 검출 결과(박스·점수), 선택 근거, 계획, 결과, 사이클 타임, 실패 원인.
- 실시간: `/status/ws`에 'cell' 빌더(작업 큐·현재 단계·검출 오버레이).
- 대시보드: 성공률(Wilson CI), 사이클 타임 분포, 실패 원인 상위, 최근 작업 타임라인.

## 6. 단계와 완료 조건
| 단계 | 내용 | 완료 조건(시연) |
|-|-|-|
| 1. 인식 모듈화 | Grounding DINO 추가, ①②③ 교체형 구조, 시뮬 GT로 평가 하네스 확장 | 시뮬 장면에서 문장→물체 선택, 조합별 지표 표 |
| 2. 실제 웹캠 | 보정, 실시간 grounding 오버레이, 책상 평면 디지털 트윈 | 실물 컵·상자 → 시뮬 배치 일치, 위치 오차 측정 |
| 3. 작업 셀 MVP | `/tasks`, 상태 머신, 분류 적재, 이력 DB | "A는 왼쪽, B는 오른쪽" 지시가 끝까지 실행 |
| 4. 대시보드·사람 개입 | 지표 화면, needs_help 확인 UI, 원격 조종 연결 | 애매한 지시에서 후보 확인 후 재개 |
| 5. 티칭 탭·배포 | r4 축소판(FK·행렬·특이점·IK, 경유점 티칭·경로 미리보기), Docker, README·3분 영상 | 원클릭 실행, 시연 프리셋 |

## 7. 합격 기준 (검증자가 직접 재현한 원자료로만 PASS)
- Grounding 선택 정확도(시뮬 GT, 장면 N≥100, 방해물 포함): top-1 ≥90%, 방해물 장면은 별도 보고.
- 영역 품질: 박스 IoU·마스크 IoU를 조합별(박스만 / MobileSAM / SAM 2.1)로 보고, 속도(ms)와 함께 표.
- 위치 오차: 시뮬 평면 투영 중앙값·p95(mm), 실물 웹캠은 ArUco 기준점으로 측정(목표 중앙값 ≤10mm는 1단계 측정 후 확정).
- 엔드투엔드(시뮬): 지시→완료 성공률(Wilson CI)·사이클 타임 p50/p95, GT 보조 사용 여부 분리 보고.
- 애매한 지시: 확인 요청 정밀도/재현율, 확인 없이 잘못 집은 비율.
- 성능: 웹 화면 ≥29.7fps 유지, Grounding 1회 지연 측정(회사 GPU/집 CPU 각각), 기존 Panda·G1·트래커 회귀 없음, 전체 pytest 통과.
- 표기: 근사·비제휴 문구, 모델별 라이선스 표(THIRD_PARTY_NOTICES 갱신).

## 8. 팀·파일
| 페어 | 구현(Codex) | 검증(Claude) | 범위 |
|-|-|-|-|
| G(인식) | I-G | V-G | perception/grounding·segment·localize, config/perception.yaml, bench/eval 확장 |
| W2(웹캠·트윈) | I-C | V-C | tools/calibrate_camera.py, 트래커 원본 프레임 요청, 트윈 동기화 |
| K(셀·대시보드) | I-K | V-K | web/cell*.py, DB, /tasks, 대시보드 UI |
- 공유 파일(web/app.py, web/realtime.py, web/static/humanoid.js, index.html)은 한 번에 한 구현자, 순서 조율. 측정 규칙은 notes/TEAM_R3.md.
- 1단계(G)를 먼저, 2단계(W2)는 보정 도구부터 병행, 3단계(K)는 1단계의 Detector 인터페이스 고정 후.

## 9. 위험
| 위험 | 대응 |
|-|-|
| 시뮬 렌더 화면에서 Grounding 정확도 저하(도메인 차이) | 1단계에서 측정, 필요 시 프롬프트·임계 조정, 실물 웹캠은 오히려 유리 |
| 8GB GPU에 Grounding+SAM2+FP 동시 상주 | lazy spawn·직렬화, 박스만 모드 기본 |
| 웹캠만으로 높이·기울기 불명 | 책상 평면 가정 명시, 정밀은 깊이 카메라 확장 |
| 한국어 지시 해석 | 사전 우선, 애매하면 확인 요청 |
| 범위 과다 | 단계별 시연 가능 산출물, 5단계 r4는 축소판 |
| 라이선스 | Apache·MIT 계열 우선, GPL 모델 제외, 표로 관리 |

## 10. 사용자 확인 필요
1. 로봇: 작업 셀 기본 로봇을 Panda(기존)로 시작하고 유일 협동로봇(YBL-A612)은 5단계 이후 교체? 아니면 처음부터 유일?
2. 실물 데모 물체: 책상에 올릴 실제 물체 2~3개(예: 컵, 상자, 병) 선정.
3. 깊이 카메라(RealSense 등) 대여 가능 여부.
4. P1c(G1 자기충돌) 작업 중단(기본 OFF 실험 기능 유지)에 동의?

## 11. 검토 상태
- 1차: Claude 검토자 2명(R5-C 사용자·실용 관점, R5-O 구현 관점) 상호 검토 진행 예정.
- 2차: **Codex 검토 대기**(11-09 Codex 사용량 한도, 약 16:50 리셋 예상). 결과 notes/plan_r5_review_x.md. 구현은 Codex 검토 반영 후 시작.
