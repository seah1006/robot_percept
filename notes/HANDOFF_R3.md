# robot_percept 인계 문서 r3 (2026-11-09 회사 PC → 집)

이 문서가 최신. 이전 기록은 notes/HANDOFF_HOME.md(11-05~11-07). 공통 규칙은 notes/TEAM_R3.md + HANDOFF_HOME 4장.
브랜치: `wip/r2`(이 커밋 포함, 작업 브랜치). `master`는 3cf1b19 그대로(오늘 새로 master에 올린 것 없음).

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

## 남은 일 (우선순위)
1. S: c6 seed 진단 결과 검토 → IK seed 분리(collision waypoint와 task IK warm start 분리) 수정 → 정적 12자세(대칭·비대칭, 방향 ≤8°, 손목 ≤10mm) 회복, chest 첫 tick ≤40ms, 서버 tick p95 ≤20ms, 30fps 4패턴, OFF 회귀(P1a/P1b), 종료 누수 → V-S3 판정. 통과 전 기본 OFF.
2. E: 평가 배치 330회 재개 → V-E3 recompute3.py 재계산·결정론 확인. 워밍업 취소 시 `failed` 순간 노출 수정.
3. T: final_hand 조용 6창, 실카메라 수락 재측정(사람이 카메라 앞에 있는 조건 포함), WS 최악 위상, 1시간 장시간.
4. r4 신규: 유일 YMX-1210(산업용) + YBL-A612(협동) 기구학 시각화 — notes/plan_r4_industrial_cobot.md(v3, Claude 검토자 R4-C·R4-O 합의 반영), notes/yuil_specs.md.
   - **착수 전 필수: Codex 2차 검토 미실시**(11-09 Codex 사용량 한도). 계획서 12장의 지시문으로 Codex 검토자(R4-X)를 띄워 notes/plan_r4_review_x.md를 받고, 지적을 v4에 반영한 뒤 구현(I-A Codex / V-A Claude) 시작.
   - 사용자 확인 필요(계획서 11장): 로봇 조합 유지 여부, YBL E·F 정면도 확인, 진행 순서(B0·A·B는 r3와 병행, 화면 연결은 P1c 동결 이후), STEP(CAD) 문의 여부.
5. PASS 항목만 master에 cherry-pick·push(검증 근거 커밋 메시지에).

## 집 Aside용 프롬프트
```
robot_percept 프로젝트를 이어서 진행해줘. 답변은 처음부터 끝까지 한국어로.
- 저장소: https://github.com/seah1006/robot_percept, 작업 브랜치 wip/r2(master는 검증 PASS 커밋만).
- 먼저 wip/r2의 notes/HANDOFF_R3.md(최신 상태·남은 일), notes/TEAM_R3.md(규칙), notes/HANDOFF_HOME.md 0장·3장(집 PC 환경 차이와 설치), notes/plan_r4_industrial_cobot.md, notes/yuil_specs.md를 읽어.
- 이 PC가 집 PC(AMD GPU, /home/my/work/robot_percept, miniforge)인지 확인하고, git pull로 wip/r2 최신화(로컬 skip-worktree 설정 유지), pytest(측정 락 안)로 환경 확인. flask-sock==0.7.0, simple-websocket==1.1.0 설치 필요. 집 PC는 CUDA가 없으니 FP/SAM2·E 평가 배치·실카메라·회사 녹화본 항목은 회사 PC 몫으로 남겨.
- 집에서 할 일: HANDOFF_R3 남은 일 1번(S: P1c IK seed 분리·정적 회귀 수정)과 4번(r4 유일 로봇 기구학 시각화 — 먼저 계획서 12장대로 Codex 2차 검토를 받고 시작). 
- 작업 방식: 구현은 Codex 서브에이전트, 검증은 Claude 서브에이전트(기본 판정 NEEDS WORK, 직접 재현한 원자료만 PASS). 서로 task id로 직접 소통, 나한텐 이정표와 결정 필요 사항만. 동시 서브에이전트 ≤8, subagent_wait에 여러 작업을 한꺼번에 걸지 마. Codex 한도에 걸리면 Claude로 구현 대체하지 말고 리셋까지 대기(검증만 진행 여부는 나한테 물어봐).
- 규칙: 구현자 커밋 금지(PASS 후 부모가 커밋), 프로세스 종료는 ss -ltnp로 자기 PID만(pkill -f 금지), 서버는 Bash yield_ms 장기 실행, 성능 측정·전체 pytest·수 초 이상 CPU 작업은 flock -w 900 /tmp/rp_measure.lock 안에서(한 번 5분 이내), 에이전트 동시 작업 중엔 같은 슬롯 A/B 상대 비교, 절대 기준은 마지막 조용한 창. GT 보조는 GT 보조라고 밝혀.
- 내가 5080으로 직접 테스트한다고 하면 모든 에이전트 성능 측정을 멈추고, 끝나면 전원에게 재개 공지.
```
