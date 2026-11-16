# r5 라운드 공통 규칙 (회사 PC, 2026-11-16~, 부모 1NIgF2z2BvfBSkOh)

먼저 읽기: notes/plan_r5_grounded_picking_cell.md(v3, 10장 사용자 확정, 12장 착수 조건), notes/contract_r5.md(v1.1), notes/HANDOFF_R3.md '11-10 집 PC 세션', notes/TEAM_R3.md(측정 규칙 그대로 적용).

## 환경 (회사 PC)
- WSL Ubuntu-24.04, repo /home/user/work/robot_percept, 브랜치 wip/r2. 커밋은 부모만.
- 기존 env: `source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept; cd /home/user/work/robot_percept; source sim_test/gl_env.sh; export HOST=0.0.0.0 PYTHONPATH=$PWD` (회사 env는 cu130 torch·SAM2·FP 설치됨. 집 원본 env와 다름).
- GPU: NVIDIA RTX 2080 SUPER 8GB, nvidia-smi 있음. 실제 USB 카메라 연결됨(FF Camera) — 카메라는 한 프로세스만, 사용 전 부모에게 슬롯 요청.
- 셸은 PowerShell 7. WSL 명령은 LF .sh + `wsl -d Ubuntu-24.04 -- bash /mnt/c/...` 또는 `wsl -d Ubuntu-24.04 --exec bash -lc '...'`.
- 서버는 Bash yield_ms 장기 실행, 종료는 `ss -ltnp | grep :<포트>` 자기 PID만(pkill -f 금지). 5080은 사용자 서버 예약(켜지 말 것).

- (11-16 12:55 부모 결정) r5 서버·인식(Grounding DINO) 실행 env = **robot_percept_g0c**(원본 복제 + transformers 4.57.6, torch/numpy 줄 불변 확인). 원본 env robot_percept에는 transformers 설치 금지. 기존 r3 측정·회귀는 원본 env 유지.

## 페어·포트
| 페어 | 구현(Codex) | 검증(Claude) | 포트 |
|-|-|-|-|
| CT 계약 코드 | I-CT | V-CT | 서버 불필요 |
| SA 셀 장면 자산 | I-SA | V-SA | 서버 불필요(오프스크린 렌더) |
| G0c 회사 GPU 측정·스크립트 | I-G0 | V-G0 | 서버 불필요 |
| W2 웹캠 보정·평면 투영 | I-W2 | V-W2 | 카메라 슬롯 필요 시 5098/5099 |

## 측정 규칙
- 성능 측정·전체 pytest·수 초 이상 CPU 작업은 `flock -w 900 /tmp/rp_measure.lock -c "..."`, GPU는 measure→gpu 이중 락(`/tmp/rp_gpu.lock`), 보유 5분 이내. 운영 코드는 측정 락 금지.
- 결과에 load·nvidia-smi·동시 작업, 출처 배지([시뮬GT][시뮬인식][실물웹캠][녹화영상]), GT 보조 여부.
- 카메라·얼굴 영상은 저장소에 넣지 말 것.
- (11-16 12:22) 전체 pytest는 **검증자가 묶음 확정 시 1회만**. 구현자는 자기 테스트 파일만(수십 초 이내) 락 안에서. 측정 우선순위: G0 GPU 측정 > 검증 판정 > 구현자 확인. 남의 대기 프로세스는 건드리지 말 것.

- (11-16 12:27) PowerShell 큰따옴표/히어스트링 안의 `$PWD`는 Windows 경로(/mnt/c/Users/USER/.aside/u/0)로 먼저 확장될 수 있음 → WSL 명령은 `export PYTHONPATH=/home/user/work/robot_percept` 절대경로 사용. (이번 full pytest 16 FAIL은 이것이 원인 아님: 전부 SA 신규 test_settled.)

## Gemini 분석가 (G-*, 11-16~, 부모만 호출)
- 호출: `pwsh -NoProfile -File C:\Users\USER\tools\gemini\gemini-ask.ps1 -Name <작업> -Model <ID> -Lines 30 -TimeoutSec <초> -Prompt "..."`. 결과 전체는 `C:\Users\USER\tools\gemini\out\`에 저장, 첫 줄 GEMINI_OK 확인. 읽기 전용(plan 모드).
- 역할: 로그 1차 분류, 저장소 영향 범위·계약 위반 후보 조사, 외부 문서·파라미터 조사, 계획·diff 3번째 의견. **금지**: 파일 수정·커밋·측정/GPU 락·카메라·PASS 판정(결과는 참고 자료, 검증자가 직접 재현해야 근거).
- 모델 규칙: 로그 분류·요약·grep = hydrogen-low/medium · 일반 조사·diff 리뷰 = hydrogen-high(기본) · 어려운 원인 분석·계획 리뷰 = hydrogen-xhigh(yield_ms 백그라운드) · 교차 확인만 argon-high · 형식 변환 = 3.8-flash. carbon 사용 불가.
- 호출 기록(작업 / 모델 / 결과 파일 / 채택 여부):
  - 11-16 12:32 ct-contract-scan / Gemini 4 Argon(당시 스크립트 기본, -Model 옵션 추가 전) / out\ct-contract-scan-1116-123237.md / 후보 10 중 5 재현 확인(V-CT), G3 실결함 1건 신규 발견

## 협업
- 구현↔검증은 message_agent로 직접 루프. 검증 기본 판정 NEEDS WORK, 직접 재현 원자료만 PASS.
- 부모에게는 이정표·PASS/FAIL·결정 필요 사항만.
- 구현자 커밋 금지, 자기 소유 파일만. 공유 파일(web/app.py, web/sim_worker.py, web/realtime.py, web/perception_stub.py, web/static/humanoid.js, index.html)은 이번 라운드 **미변경**(계약 코드는 순수 로직·새 파일).
- ~10분마다 끊길 수 있으니 각자 changes 노트 끝에 재개 지점.
- Codex 한도 시 Claude가 구현 대체 금지, 리셋 대기.
