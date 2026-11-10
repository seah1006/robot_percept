# robot_percept 인계 문서 r3 (2026-11-09 회사 PC → 집)

이 문서가 최신. 이전 기록은 notes/HANDOFF_HOME.md(11-05~11-07). 공통 규칙은 notes/TEAM_R3.md + HANDOFF_HOME 4장.
브랜치: `wip/r2`(이 커밋 포함, 작업 브랜치). `master`는 3cf1b19 그대로(오늘 새로 master에 올린 것 없음).

## 11-10 집 PC 세션 (최신, 이 절부터 읽을 것)
환경: 집 PC(RX 7600, WSL Ubuntu-24.04), wip/r2 pull 후 전체 pytest **104 passed**(65s, 측정 락). 부모가 HOME_PROMPT 진행.

**사용자 확정 6개** → 계획서 10장 아래 '사용자 확정 (2026-11-10)'. 요약: Panda로 시작·유일 v2 / 실물 3개+상자 2개 / 깊이 카메라 불필요 / **P1c 중단 동의** / N≥100+Wilson CI / 보정판 새 녹화 어려움(녹화 기반 위치 오차 '측정 불가'). 집에 웹캠 없음 → **W2 실촬영·보정은 회사 PC(11-11~)**.

**Codex 사용량 한도**: 11-10 22:00경 I-G0·I-CT·I-SA 모두 정지, "Try again in ~2389 min" → **재개 약 11-12(목) 13:50 KST**. 규칙상 구현은 대기, 설계·검증만 Claude.

| 항목 | 판정 | 근거·수치 |
|-|-|-|
| G0 ROCm(RX 7600 gfx1102, WSL) | 동작 확인(V-G0 재현), 스크립트 NEEDS WORK | env robot_percept_rocm: torch 2.14.0+rocm10.1.0, HIP 7.16. **HSA_ENABLE_DXG_DETECTION=1 + LD_LIBRARY_PATH=$CONDA_PREFIX/lib 필수**(없으면 libgomp.so.1 ImportError — install_rocm.sh·probe에 누락, Codex 수정 대상) |
| G0 Grounding DINO tiny GPU [시뮬인식] GT보조 없음 | 측정 재현 | rev a2bb814(apache-2.0, HF API 확인), transformers 4.57.6, 640×360 N=20: p50 299/p95 306ms(V-G0 296/317), 첫 추론 21s(재현 7.7s, 캐시), 로드 18s, 프로세스 max_alloc 1016MiB, 장치 peak 샘플 3721MiB(기준 2332, Windows 포함). AMD 값은 회사 NVIDIA 합격 증거 아님 |
| G0 CPU | 측정 재현 | env robot_percept_cpu(torch 2.14.0+cpu), 4스레드 p50 3349/p95 3754ms(loadavg 6), V-G0 재측정 3049/3301ms |
| G0 의존성 | 확인 | 원본 env robot_percept freeze 해시 불변(torch 없음 — PERCEPTION=stub). 복제 env robot_percept_g0에 transformers 4.57.6 -c 설치 OK. backend별 constraints: notes/constraints/{common,cu130,rocm,cpu}.txt. numpy dist-info 중복은 집 env에 없음(단일 2.5.3) |
| G0 검출 품질 메모 | 결함 기록 | 'a blue cube' 0.49가 책상 전체 박스(오검출, 장면엔 빨간 큐브만). G1에서 임계·프롬프트 조정 |
| 계약 notes/contract_r5.md v1.1 | **문서 PASS**(V-CT) | Codex v1(61줄) → Claude D-CT 설계 대행 보완(205줄), C1~C6·V1~V4 반영. **Codex 확인 대기**: warm 30s, 정지 ACK 3s, 정지 지연 상한 IK 500ms/physics 100ms, 셀 home 별도 명령, 오류코드 3개·SQLite 컬럼 추가, solve_ik 콜백 여부 |
| 장면 자산 확장(I-SA) | 미착수 | Codex 한도로 산출물 없음 |

**재개 순서 (Codex 복귀 후)**
1. I-G0: install_rocm.sh·probe에 LD_LIBRARY_PATH 반영, tools/g0/bench_gpu.py(부모 임시 작성) 정식화, notes/g0_results.md 작성, 멱등 재실행 → V-G0(notes/verify_g0.md 재개점) 판정.
2. I-CT: notes/contract_r5_changes.md 재개점대로 perception/interfaces.py·셀 상태 머신(가짜 시계)·tests/test_contracts_r5.py, 전체 pytest → V-CT(notes/verify_contract_r5.md E·F).
3. I-SA: 셀 장면·물체 ≥8종·config/objects.yaml·vocab_ko_en.yaml·시드 생성기 → V-SA(notes/verify_scene_r5.md).
4. 회사 PC: W2 보정 도구·실카메라, Grounding DINO cu130 GPU 지연·VRAM ≤7.0GiB, SAM2/FP, r3 E 330회.

## 오늘 상태 요약 (11-09)
에이전트 구성: S(I-S3 Codex / V-S3 Claude), T(I-K3 Codex / V-T3 Claude), E(I-E3 Codex / V-E3 Claude). 13:32 Codex 사용량 한도 → 사용자 지시로 Claude 검증자도 정지. 모든 측정 프로세스 정리됨.

| 항목 | 판정 | 핵심 수치·근거 |
|-|-|-|
| E: FP 워밍업 정책(defer / 워밍업 중 G1 ON 취소 / 사용자 선택 보호) | **PASS (경로당 N=3, 9/9)** | G1 31.4~32.0fps, max gap ≤109.7ms, OFF 후 재워밍업 29.5~39.8s, 첫 클릭 2.31~2.70s. notes/verify_e.md r3, bench/verify_e/r3/out/ |
| E: 결함 후보 | 미수정 | 워밍업 취소 직후 상태가 잠깐 `failed`(running→failed→deferred_g1) 노출 |
| E: 평가 330회(FP N30 파일럿 + gt/fp×assist on/off N20) | NEEDS WORK(진행 중) | 40/330 완료(pose 40/40). V-E3가 mustard 30개 독립 재계산 30/30 일치. 하네스 수정: FP 평가가 구형 SAM argmax 쓰던 버그, 분모 계획 N 고정·missing_trial. 재개: `bash bench/eval/r3_matrix.sh --resume --out bench/eval/r3_gpu_1109a`(measure→gpu 락, 청크 ≤240s). notes/eval_r3_changes.md |
| T: Panda 모드 트래커 | **PASS** | 6창 처리율 100%, 수신 29.94~30.02Hz, Panda 화면 하락 ≤0.1fps |
| T: compact(자세 전용) 절대 판정 | **PASS** | 6창 처리율 100%, 수신 29.99~30.04Hz; ws vs http: post p95 −18.6ms, 서버 CPU −6.0%p |
| T: final_hand(손+자세) | NEEDS WORK | ws 100/100%, http 98.89/99.78%(이 PC neural p95 36~43ms라 http는 99% 경계). 조용한 6창 재측정 미완 |
| T: WS 일시 실패 후 복귀 | 조건부 PASS | 20.1s / 7.6s, 차단 중 HTTP 유지·오류 0. 최악 위상(≈30.6s) 미시험(bench/verify_t/r3_rec_one.sh) |
| T: 실카메라 수락(1회, 카메라 앞 사람 거의 없음) | NEEDS WORK(근소 미달) | 카메라 29.29fps, 처리율 98.80%, 수신 29.64Hz, 손 1.3%/자세 100%. bench/verify_t/out_r3/cam4/ |
| T: 1시간 장시간 | 미실시 | |
| T: preview HTTP +3~9ms | 원인 미규명(알려진 한계) | Werkzeug Connection:close·재사용 0 확인(기준선도 동일). notes/tracker_r3_changes.md |
| T: 트래커 수정 | 반영(wip/r2) | WS 성공 후 실패 시 HTTP 우회 못 하던 버그 수정, 회사 녹화본 판정 하네스(bench/tracker_r3_*) |
| S: P1c 자기충돌(기본 OFF) | NEEDS WORK | 아래 |

### S: P1c 상세
- 구조(구현 완료): 10Hz subprocess planner(PID 100ms watchdog, 사전 기동·더미 계획 후 `planner_ready`), 서보는 최신 계획 + 국소 3FK 후검사, ready 전엔 빠른 투영 fallback, 조기 FK refresh(미인증 구간 제거), 종료 시 자손 잔존 0(자체·V-S3 1차).
- c4(V-S3 직접): tick p95 sweep 12.8/chest 8.2/jump 13.1/twist 7.7ms, 침투·미인증 0, 복귀 2.33s/1.4°. 문제: jump 8초 후 영구 hold, up120 손목 33.3mm, chest t=0.31s 42ms 1회.
- c5(현재 작업트리, collision 6be22eb6 / env 444b9d74 / teleop bb163931, 작은 clearance 회복 escape + release/brake 임계 1e-4 통일): jump hold 해소(후반 354.9°, 최소 +6.5mm, 침투 0). 그러나 **정적 회귀**(hum80 방향 45.0/78.5°·손목 238.7mm, up120 23.4°·86.1mm), chest 41.9ms 재현, 서버 tick p95 창 최대 sweep 27.4/chest 22.5/jump 21.3ms. 30s fps jump 31.95/twist 32.02 PASS(sweep/chest 미완). 전체 pytest 104 PASS.
- 원인 가설(미확정): collision waypoint가 task IK seed를 덮는 coupling → cross_chest 이후 hum80 분기 오염. 진단 결과 `bench/humanoid_s4_out/c6_seed_diagnose/result.json`(미검토).
- 재개점: notes/humanoid_s4_changes.md(13:05), notes/verify_s.md r3 끝(남은 측정 목록·명령).

## 오늘 바뀐 규칙 (notes/TEAM_R3.md)
- 전체 pytest·집계·그림·재계산 등 수 초 이상 CPU 작업도 measure 락 안에서만(락 밖 pytest가 Windows 트래커 측정을 오염시킨 사건).
- Windows 트래커 측정은 WSL 측정 락이 Windows 실행 종료까지 감싸야 함.
- 사용자가 5080·실카메라로 직접 테스트할 땐 모든 성능 측정 중지 공지 → 끝나면 재개 공지(공지 누락 주의: 6명 전원에게).
- 백그라운드(nohup) 측정은 무효 사례 있음(트래커 미실행 + stale metrics 재사용) → stale 파일 삭제·로컬 복사본 사용.

## 저장소에 없는 것
- `bench/verify_s/r3raw/`(V-S3 500Hz 원시 npz 122MB): 용량 때문에 .gitignore, 회사 PC에만. 요약 JSON·스크립트(bench/verify_s/*)로 재생성 가능.
- 회사 녹화본(Documents/sam_camera/teleop_*.mp4, 얼굴 포함), 유일 카탈로그 PDF(저작권) — 수치만 notes에.


## 방향 변경 (11-09 오후)
- 프로젝트 방향: **자연어 지시 기반 범용 피킹 셀**(Grounding DINO 중심, 분할·위치 모듈 교체형, 실물 웹캠 평면 투영 디지털 트윈, /tasks 작업 셀·대시보드). 계획서 notes/plan_r5_grounded_picking_cell.md(v2, Claude 검토 합의 반영).
- r4 기구학 시각화는 r5의 v2 범위(티칭 탭)로 흡수. P1c(G1 자기충돌)는 추가 투자 중단 권장(사용자 확인 대기).
- **착수 전: Codex 2차 검토(notes/plan_r5_review_x.md) → v3 반영 → G0(transformers env 복제본 설치 시험)부터.**

## 남은 일 (우선순위)
1. S: c6 seed 진단 결과 검토 → IK seed 분리(collision waypoint와 task IK warm start 분리) 수정 → 정적 12자세(대칭·비대칭, 방향 ≤8°, 손목 ≤10mm) 회복, chest 첫 tick ≤40ms, 서버 tick p95 ≤20ms, 30fps 4패턴, OFF 회귀(P1a/P1b), 종료 누수 → V-S3 판정. 통과 전 기본 OFF.
2. E: 평가 배치 330회 재개 → V-E3 recompute3.py 재계산·결정론 확인. 워밍업 취소 시 `failed` 순간 노출 수정.
3. T: final_hand 조용 6창, 실카메라 수락 재측정(사람이 카메라 앞에 있는 조건 포함), WS 최악 위상, 1시간 장시간.
4. r4 신규: 유일 YMX-1210(산업용) + YBL-A612(협동) 기구학 시각화 — notes/plan_r4_industrial_cobot.md(v3, Claude 검토자 R4-C·R4-O 합의 반영), notes/yuil_specs.md.
   - **착수 전 필수: Codex 2차 검토 미실시**(11-09 Codex 사용량 한도). 계획서 12장의 지시문으로 Codex 검토자(R4-X)를 띄워 notes/plan_r4_review_x.md를 받고, 지적을 v4에 반영한 뒤 구현(I-A Codex / V-A Claude) 시작.
   - 사용자 확인 필요(계획서 11장): 로봇 조합 유지 여부, YBL E·F 정면도 확인, 진행 순서(B0·A·B는 r3와 병행, 화면 연결은 P1c 동결 이후), STEP(CAD) 문의 여부.
5. PASS 항목만 master에 cherry-pick·push(검증 근거 커밋 메시지에).

## 집 Aside용 프롬프트
최신 프롬프트는 **notes/HOME_PROMPT.md** (r5 방향 반영). 아래 이전 버전 대신 그것을 쓴다.
