# R2-C(Claude) 검토 및 R2-X(Codex) 합의안 (2026-11-03)

## 1. 질문별 검토 (근거)
1) 빠진 것/과한 것
- 과한 것: A5 Hungarian. 손목 2x2 최소합 전수할당이 이미 구현됨 (humanoid_changes.md:13, humanoid_teleop.md:10, tracker 222-234). 삭제. 엄지 대립 검증만 소항목.
- A1 전제 약함: teleop.py:126-127 에서 E=S+L1*u1, W=E+L2*u2 로 길이 정규화와 방향 목표가 이미 있음. 오차 후보는 iters=8(teleop.py:139), 관절 한계, w_rot .25/w_elbow .35 타협 (changes.md:67-68, elbow 가중치 1이면 손목 14~23mm 악화). R2-X: swivel 1행 치환 시 wrist+rot 6행과 합 7행이 되어 nullspace 정규화가 꺼지는 점 검토 필요. 따라서 "원인 분해 -> 필요 시 swivel" 순서.
- 합격기준은 관절각이 아니라 FK 방향오차(u1,u2): changes.md:46,67 에서 단일 pitch 대비가 coupling 때문에 부정확.
- 빠진 것(자연스러움에 중요):
  a. 손 검출 끊김: 녹화본에서도 손 검출 62/89=70% (changes.md:51). teleop.py:129-133 은 손이 없으면 R_t=None 이라 손목 회전 목표가 on/off -> 손목 튐. 폴백 필요.
  b. 엉덩이 비가시(책상 웹캠 일반): retarget.py:33-34 가 z축을 카메라 위로 가정, teleop.py:103 pitch=0 -> 몸통 기울기 소실. 시험세트에 '상체만 프레임' 필요.
  c. 손목 방향 품질 지표 자체가 없음: rotation weight .25->.1 효과가 거의 0 (changes.md:68) -> 회전 목표가 사실상 약하게 작동. 합성 GT 대비 손목 방향 오차 지표 신설.
  d. 체형 스케일: 방향 기반이라 팔 길이는 안전. 어깨 위치 S는 로봇 고정(teleop.py:36-42), 어깨폭 차이는 저우선. MediaPipe depth(z) 잡음은 개선 불가, 문서화만.
  e. 체감 지연: tau=.06 평활(teleop.py:152)+가속 제한+트래커 loop p50 104ms(changes.md:141). latency_ms(humanoid.py:45)는 Windows sent_at vs 서버 time.time() 시계 차 + '도착'까지만이라 화면 반영/캡처 시각 불포함.
  f. 입력 검증: _finite_list 가 pose 행 길이 3/4 혼재 허용 -> ragged np.asarray 로 worker crash 가능 (R2-X 지적, 코드로 확인).
2) 우선순위: P0 안정성/입력검증 -> P1 자연스러움(A1,A2,A7,A3) -> P2 C/P/T 마무리 -> P3 E(GPU).
3) 합격기준 측정 가능성
- A1: 가능(합성 GT, FK 방향). 관절각 기준은 불가 -> 교체.
- A3 jitter 3mm: 합성 입력은 노이즈 0이라 무의미; 정지 구간 녹화 필요(현재 없음) -> 영상 확보 선행.
- A3 지연 p95 120ms: 캡처~화면은 실카메라 필요(카메라 분리). 지금은 서버 구간만.
- 30fps 판정은 확정 기준(처리율>=99%, 개수기반 30초창 평균>=29.7Hz) 유지; 창 min 은 참고.
4) 소유권: sim/humanoid_{ik,retarget,teleop}.py 한 페어 독점(A1,A2,A7). web/humanoid.py, humanoid_worker.py, shm_channel.py 는 다른 페어(P0,A3,A4). tools/teleop_tracker_win.py 는 A7 트래커측/ T 와 충돌 -> 순차. web/app.py, sim_worker.py 는 T/C 페어, G1 페어는 건드리지 않음(Panda pause 훅 제외).
5) 위험: 측정 간섭(락 필수, 부하<4 기록), 회귀(Panda 29fps, pytest 11 PASS 유지), 5080 사용자 서버 미접촉, 실카메라 미실시 항목 PASS 로 오인 금지.

## 2. 합의 우선순위 (R2-C + R2-X, 1차 왕복 후 제안; R2-X 최종 회신 시 아래 '이견' 갱신)
| # | 항목 | 담당 | 소유 파일 | 정량 합격 기준 | 예상 | 병렬 |
|---|---|---|---|---|---|---|
| P0 | 입력 검증(pose 행 길이 통일, ragged 방지) + status enabled/state 불일치 + cold start 후 video 연결 | G1-web 페어 | web/humanoid.py, humanoid_worker.py | 혼재 행 payload 400 응답/worker 생존; off 상태 enabled=false; 모드 ON 후 video max_gap<=200ms(3회) | 0.5일 | 병렬 |
| P1a | A1 원인분해 후 팔 정확도 | G1-IK 페어 | sim/humanoid_ik.py, humanoid_teleop.py | FK 방향오차 u1,u2<=8도(양팔), 손목위치<=10mm, 좌우차<=3도; IK p95<=33ms 유지 | 1~1.5일 | 순차 시작 |
| P1b | A7 손 검출 끊김 폴백 + 상체만 프레임 케이스 | 같은 IK 페어(retarget) + 트래커 부분 | sim/humanoid_retarget.py, teleop.py, (tracker 폴백 최소) | 62/89 영상: 손목 회전 프레임간 최대 각변화 baseline 대비 -50%; hips 비가시 입력에서 waist roll/yaw 오차 측정치 보고 | 1일 | P1a 후 |
| P1c | A2 자기충돌: 양팔 동시 후검사 + 명령->실측 중간경로 | 같은 IK 페어 | sim/humanoid_ik.py, humanoid_env.py | 합성 동작 세트에서 캡슐 최소거리<임계 프레임 0; fps>=29.7 유지 | 1일 | P1a와 같은 파일, 순차 |
| P1d | A3 지연: 서버 구간 계측(도착->해당 상태 렌더 프레임), 시계 오프셋 보정 | G1-web 페어 | web/humanoid*.py | 서버 구간 p95<=80ms 수치 보고; 캡처->화면 120ms 는 실카메라 후(미실시) | 0.5일 | P1a와 병렬 |
| P1e | 정지구간 녹화 확보 + jitter | 사용자/카메라 연결 후 | - | 손목 jitter std<=3mm(영상 확보 시) | 대기 | 보류 |
| P2 | C N=20+원위치 복귀 negative, P r5 84클릭 독립 재확인, T 새 트래커 재측정(메인 FPS 하락<10%) | C/P/T 기존 페어 | control/perception/tracker | 기존 기준 | 각 0.5~1일 | G1과 병렬, 측정 락 직렬. T 는 tracker 변경(P1b) 후 |
| P3 | E: FP N30, 매트릭스 N20 | E 페어 | eval | GPU 락, nice 19 | 야간 | 마지막 |
| P4 | 원클릭 런처, README, .gitignore | 엔지니어링 | scripts, README | 서버+트래커 1명령 기동 | 0.5일 | 병렬 |
| 삭제 | A5 Hungarian(이미 구현), 엄지 대립은 소항목 | | | | | |
| 카메라 | A6 실카메라 수락 스크립트 | G1-web | tools | 연결 후 1명령: 30fps/검출률/지연 | 0.5일 | 실행은 연결 후 |

## 3. R2-X 회신 반영 (2차 왕복 후 확정)
- 합의: A1 원인분해 선행, 기존 길이정규화 재구현 금지, 주지표는 FK 방향/위치. swivel은 1 scalar 팔평면 잔차로 구체화하되 straight-arm 특이점 폴백 필수. wrist 허용범위 우선인 계층 태스크 권장(가중치 타협 지양).
- A2: 접촉 ON이 아니라 torso+상완/전완 소수 캡슐 signed distance + 해석적 최근접점 Jacobian, 활성 쌍만 barrier. 양팔 후보 qfull 동시 결합 후 명령 궤적/실측 q 사후 거리 검사 + 안전 정지(무조건 중립 이동 금지). 14DOF QP는 후속. 소요: A1 진단 0.5d+개선 1~2d, A2 프로토 1d+하드닝 2~3d+독립검증 1d (표의 A2 1d는 과소, R2-X 수치 채택).
- 추가 확정 항목(P0): pose 3/4 혼재 행 ragged crash, 영/공선 랜드마크로 torso/palm 퇴화 방어, A4 enable/disable 동시 호출 lifecycle race 및 재시작 시 잔류 sample/frame/cache 리셋.
- 소유권 확정: sim solver/servo(A1,A2,A7 hold) 한 페어 순차 / web runtime(P0,A3 서버구간,A4) 다른 페어 병렬 / tools/teleop_tracker_win.py 단독 owner 1명(A3 트래커측, A6, T, A7 트래커 폴백) 순차.
- R2-X 최종 추가(수용): capture→화면 120ms는 소프트웨어 최초 반영과 운동학 응답(속도/가속 제한)을 분리 측정. A2 '충돌 0프레임'은 capsule surrogate 한정이며 actual q·command 경로 검사, hold도 관성 충돌 가능하므로 감속 마진 필요. A7은 속도/가속 상한+actual q 비교 추가, hips fallback은 정확도 보장이 아니라 graceful 동작으로 명시. 코드부채: (1) teleop.py:122 가려짐 시 flag만 false이고 이전 des를 향해 계속 이동(hold 문구와 불일치), 손 None이면 손가락도 이전 des 유지 (2) reset_state:49 B0 초기화하면서 calib_seen 보존 → 보정 복원 안 됨 (3) tracker record/replay는 Panda features만, humanoid replay 무시 → A6 전 record v2(pose/hands/seq/capture ts) (4) G1 crash 시 Panda render_pause 해제 경로 없음. 이 4개는 P0/P1b에 편입.
- 남은 이견: 없음. 수치 임계(P1b -50%, A3 서버 80ms)는 baseline 측정 후 확정 조건으로 양측 동의.
