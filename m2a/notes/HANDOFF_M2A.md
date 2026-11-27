# M2A 구현 인계 문서 (최신: 2026-11-28 01:00 KST, 집 PC)

기획: github seah1006/m2a-vla-proposal (발표 PDF/PPT, d_arch2 v2.1, d_eval2 v5). 구현: 이 저장소 `m2a/`, 브랜치 **m2a/main**.
마감 2026-12-18(임의 지정, 학기말) → 12주 계획을 M-min 축소판으로 압축(계약 `m2a/CONTRACT.md` 0절).

## 1. 지금 상태 (main 399093e 이후)
모든 성공률은 시뮬레이션, P-gate(GT 보조 weld 파지 근사) 조건.
| 층 | 모듈 | 핵심 수치 |
|---|---|---|
| 장면 S0 / 판정 J | `m2a/scene` | dev 200·L2 1,000 생성 실패 0 (V-C 조건부 PASS) |
| 계획 L2 / 파서 L1a | `m2a/plan` | pyperplan 2.1, B+C 연동 dev 200/200 verify (V-B 조건부 PASS) |
| G1 조작·스킬 | `m2a/sim` | 공식 게이트 P01 17·P02 17·P03 20·P04 19·P05 20·P06 20 (/20). skill_bench 1사이클 주변0 120/192, 주변3 98/192 (A5). A6 실험 스킬은 회귀로 미병합(브랜치 stash) |
| 디스패처·러너 | `m2a/run` | O0 A5판: L0 B1 15/20, B1c 15/20; 교란 L0 B1 7/20 vs B4 11/20; L1/L2 dev 60 B0 4, B1 2, B4 3, B4r 3 (/60). 병목 = 스킬(GRASP_SLIP·IK_FAIL). 결과 `m2a/notes/wse_runs/` |
| 인식 V1~V4 / O3 | `m2a/percept` | 새 head 카메라: 재현 전체 84.4%, 정밀 94.5%, Top-1 73.2%, P01/P02 43.9%, 위치 p50 0.6mm (V-G PASS는 옛 카메라 기준) |
| 학습 정책 | `m2a/data` | 2라운드 ACT(델타 행동) dev IK 8/37 vs ACT 1/37 (V-F 조건부 PASS). 3라운드: 행동을 **절대 EE 목표**로 바꿈(델타 재생 0/4 → 절대 재생 게이트 P03 10, P04 10, P05 9, P06 10 /10), 시연 400개 LeRobot v3 변환 완료. SmolVLA/ACT 학습·평가는 F4 진행 중 |
| LeRobot ROCm | `m2a/learn` | ACT b4 1GiB, SmolVLA b1 3.3GiB (합성) |
| 데모·뷰어 | `m2a/viz` | 데모 3종 mp4(`~/m2a_data/demo/`), 정적 HTML 로그 뷰어 |

## 2. 다음 할 일
1. F4: 학습 데이터 memmap화 → SmolVLA·ACT 학습 → dev 쌍체 평가(IK vs ACT vs SmolVLA, 언어 대상 지정).
2. E4: O3 dev 60 {B1,B1c,B4}·재관측 ablation·O0 vs O3 병목 분해 표(`m2a/notes/wse_tables/e4_a6final.md`).
3. 스킬 층 추가 개선 여부 결정(현재 병목). 놓은 뒤 P04 쓰러짐, 미부착 SLIP.
4. 봉인 test(seed 90000~90099) 해시 고정 → 코드 동결 → test 1회(사전등록 구성).
5. 보고서·발표: 기획서 대비 결과, 한계(P-gate 근사, 시뮬 전용, 무질감 렌더).
6. SAM 3.1: HF 계정(Seah1006) 승인됨, WSL HF 토큰 필요(사용자 결정 대기).

## 3. 환경 (집 PC: WSL Ubuntu-24.04, RX 7600 8GB, 12코어, WSL RAM 15GB)
- 시뮬·계획·인식(CPU): `conda activate robot_percept` + `source sim_test/gl_env.sh`.
- GPU 모델: `robot_percept_rocm` / 학습: `m2a_lerobot`. 둘 다 `HSA_ENABLE_DXG_DETECTION=1`, `LD_LIBRARY_PATH=$CONDA_PREFIX/lib`, 학습은 `M2A_TORCHVISION_PYTHON_ONLY=1`.
- 데이터·체크포인트 `~/m2a_data/`(git 밖), 실행 로그 `runs/`(gitignore, 요약은 `m2a/notes/wse_runs/`).
- `m2a/data/`는 루트 .gitignore `data/`에 걸리므로 커밋 시 `git add -f`.
- **운영 교훈(2026-11-28)**: (1) 메모리 15GB를 넘으면 OOM으로 Ubuntu 배포판 전체가 재시작되고 모든 백그라운드 작업이 죽는다(F3 학습이 영상 전체를 RAM에 올려 발생). 긴 작업은 `systemd-run --user --unit=<이름> -p MemoryMax=<N>G ...`로 띄워 OOM이 그 유닛에만 머물게 한다. (2) 서브에이전트가 nohup/yield로 띄운 프로세스는 그 에이전트 세션이 끝나거나 배포판이 재시작되면 죽을 수 있다 → systemd 유닛 사용. (3) 평가 배치는 작업 트리 병합과 섞이지 않게 고정 커밋 worktree(`~/work/rp_m2a_eval`)에서 돌린다.

## 4. 작업 방식
메인 에이전트가 계약·병합·검증 판정, 구현자(Codex GPT 또는 Claude)는 worktree `~/work/rp_m2a_<ws>`에서 소유 경로만 수정·커밋 금지, 검증자는 다른 모델로 독립 재현(기본 NEEDS WORK). 보고서: `m2a/notes/ws<a..h>_report.md`.