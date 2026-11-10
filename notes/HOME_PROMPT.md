# 집 Aside 인계 프롬프트 (2026-11-09 작성, 최신)

아래 블록을 집 Aside에 그대로 붙여 넣는다.

```
robot_percept 프로젝트를 이어서 진행해줘. 답변은 처음부터 끝까지 한국어로.

## 저장소와 먼저 읽을 문서
- https://github.com/seah1006/robot_percept , 작업 브랜치 wip/r2 (master는 독립 검증 PASS 커밋만).
- 순서대로 읽어: notes/HOME_PROMPT.md(이 문서), notes/HANDOFF_R3.md(11-09 상태·남은 일·방향 변경), notes/plan_r5_grounded_picking_cell.md(현재 계획서 v3, 12장 착수 조건), notes/plan_r5_review_o.md·notes/plan_r5_review_c.md(Claude 1차)·notes/plan_r5_review_x.md(Codex 2차), notes/TEAM_R3.md(작업 규칙), notes/HANDOFF_HOME.md 0장·3장(집 PC 환경 차이와 설치).

## 프로젝트 방향 (11-09 확정)
"자연어 지시 기반 범용 피킹 셀": 작업자가 말로 지시하면 Grounding DINO로 글에 맞는 물체를 찾고(분할은 선택: 기본 박스만, SAM 2.1 등 교체 가능), 실물 웹캠은 책상 평면 투영(+물체 높이 보정)으로 위치를 구해 시뮬레이션에 같은 배치를 만들고, 로봇(Panda)이 IK·충돌 검사·안전 감속을 거쳐 집어 정리한다. /tasks 작업 지시 API·상태 머신·이력 DB·대시보드로 생산 지표를 보여준다. 표현 원칙: "인식과 위치 추정은 실물 웹캠, 집기는 시뮬레이션", "MES 흉내 지표", "공장 투입 가능" 같은 과장 금지.
- r4(유일 산업용·협동로봇 기구학 화면)는 r5의 v2 범위(티칭 탭)로 흡수. 휴머노이드 G1은 보조 데모, P1c(G1 자기충돌)는 추가 투자 중단 권장(기본 OFF 유지, 회귀만 관리).

## 시작할 때 할 일
1. 이 PC 확인: 집 PC(AMD RX 7600, CUDA 없음, /home/my/work/robot_percept, miniforge, Python 3.12.16)인지. 저장소가 있으면 git pull로 wip/r2 최신화(로컬 skip-worktree 파일 sim_test/gl_env.sh(AMD)·panda_mod.xml 유지), 없으면 HANDOFF_HOME.md 3장대로 설치. flask-sock==0.7.0, simple-websocket==1.1.0 필요.
2. 전체 pytest를 측정 락 안에서 돌려 환경 확인(회사 기준 104 passed 근처).
3. 나한테 아래 '사용자 확인 6개'를 한 번에 물어봐(각 권장 답 포함). 답 전에도 확정 안 된 것과 무관한 작업은 진행해.

## 사용자 확인 6개 (계획서 10장, 괄호는 검토자 권장)
1) 작업 셀 로봇 Panda로 시작, 유일 로봇은 v2? (예)
2) 실물 물체: 머그컵·작은 박스·캔/병 3개 + 목적지 상자 2개, 투명·반사·작은 물체 제외? (예)
3) 깊이 카메라는 MVP에 불필요? (예)
4) P1c 중단 동의? (예)
5) 통계: N≥100 점추정+Wilson CI 병기 vs N≈200 CI 하한 기준
6) 보정판(체커보드·ArUco)을 함께 찍은 얼굴 없는 새 녹화 가능?

## 이어서 할 작업 (순서)
1. **Codex 2차 검토**: 계획서 v2를 Codex 검토자(R5-X)에게 맡겨 notes/plan_r5_review_x.md를 받고, 필요하면 Claude 검토자와 1회 이상 왕복 → 지적을 반영해 계획서 v3로 커밋.
2. **G0(환경 시험)**: conda env를 복제해서 `-c notes/rp_constraints.txt`로 transformers 설치 시험(torch·numpy 고정 깨지지 않게), Grounding DINO 버전·가중치 리비전 고정, 가중치·모델카드 라이선스 직접 확인, 집 PC는 **ROCm 시험부터**: 기존 env는 그대로 두고 ROCm 전용 env(예 robot_percept_rocm)를 새로 만들어 ROCm용 torch 2.14 설치 → `HSA_ENABLE_DXG_DETECTION=1`(WSL에서 /dev/dxg로 GPU 인식) → torch.cuda.is_available()·작은 행렬 연산 확인 → Grounding DINO 1회 실행해 GPU 지연·VRAM 측정. 근거: ROCm 7.14/10.x 호환표에 RX 7600(gfx1102) 등재(Linux·Windows), ROCm 7.2.1 WSL 표에는 없었음, RX 7600 XT WSL 이슈(ROCm/ROCm #6119) 완료 처리. FoundationPose(nvdiffrast·pytorch3d CUDA 확장)는 ROCm 대상 아님 → 회사 PC 몫. ROCm이 안 되면 CPU 지연만 측정하고 회사 PC로 GPU 측정을 넘김. 설치 재현 스크립트(성공/실패 로그 포함) 커밋.
3. **집 PC에서 가능한 MVP 작업**(GPU 불필요): 인식 모듈 인터페이스(perception/grounding·segment·localize, config/objects.yaml·vocab_ko_en.yaml), 시뮬 장면 자산 확장(색·형태가 다른 물체), 평가 하네스 확장(튜닝/평가 시드 분리, 출처 배지), 작업 셀 K(/tasks·상태 머신·로봇 소유권 락·취소/비상정지·상태별 타임아웃·재시작 시 aborted·SQLite 단일 쓰기 스레드·셀 전용 장면), 대시보드 1화면. 카메라가 있으면 W2 보정 도구(tools/calibrate_camera.py).
4. 회사 PC 몫(손대지 말고 남겨): Grounding DINO GPU 지연·VRAM(≤7.0GB) 측정, SAM2/FoundationPose 경로, r3 E 평가 배치 330회 재개, 회사 녹화본·실카메라 판정.

## 작업 방식
- 구현은 Codex 서브에이전트, 검증은 Claude 서브에이전트(기본 판정 NEEDS WORK, 검증자가 직접 재현한 원자료만 PASS). 서로 task id를 알려 message_agent로 직접 지적→수정 루프, 나한테는 이정표·PASS/FAIL·결정 필요 사항만 숫자 위주로. 동시 서브에이전트 ≤8. subagent_wait에 여러 작업을 한꺼번에 걸지 마(내 메시지를 못 읽음). 각자 changes 노트 끝에 재개 지점 기록.
- Codex가 사용량 한도에 걸리면 Claude로 구현을 대신하지 말고 리셋까지 대기(대략 재개 시각 알려줘). 계획 검토처럼 구현이 아닌 일은 Claude로 대신해도 되지만, 나중에 Codex 확인을 받아.
- 구현자 커밋 금지. 검증 PASS 후 부모(너)가 커밋, 검증 미완은 wip/r2 스냅샷. master에는 PASS만 cherry-pick.

## 규칙
- 프로세스 종료는 `ss -ltnp | grep :<포트>`로 자기 PID만. pkill -f 금지.
- 서버는 도구 세션 종료 시 같이 죽으니 Bash yield_ms 장기 실행 + bash_interact.
- 성능 측정, 전체 pytest, 집계·재계산 등 수 초 이상 CPU 작업은 `flock -w 900 /tmp/rp_measure.lock -c "..."` 안에서(GPU면 measure→gpu 이중 락), 한 번 보유 5분 이내. 운영 코드에는 측정 락 금지.
- 에이전트 동시 작업 중엔 같은 슬롯 A/B 교대 + 차이의 부트스트랩 95% CI로 회귀 판정, 절대 기준은 마지막 조용한 창에서 한 번.
- 결과에는 출처 배지([시뮬GT][시뮬인식][실물웹캠][녹화영상])와 GT 보조 여부를 밝혀.
- 내가 5080(또는 로컬 서버)으로 직접 테스트한다고 하면 모든 에이전트 성능 측정을 멈추고, 끝나면 전원에게 재개 공지.
- 저장소에 얼굴 영상·카탈로그 PDF·대용량 원시 데이터 넣지 마. 공개 저장소다.
- 작업 끝나면 wip/r2에 커밋·push하고 notes/HANDOFF_R3.md(또는 새 HANDOFF 문서)에 상태·재개점을 갱신해.
```
