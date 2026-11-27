# M2A 구현 인계 문서 (최신: 2026-11-27 17:30 KST, 집 PC)

기획: github seah1006/m2a-vla-proposal (발표 PDF/PPT, d_arch2 v2.1, d_eval2 v5). 구현: 이 저장소 `m2a/` 패키지, 브랜치 **m2a/main**.
마감 2026-12-18(임의 지정, 학기말) → 12주 계획을 M-min 축소판으로 압축(계약 `m2a/CONTRACT.md` 0절).

## 1. 지금 상태 (main efe3705 기준)
| 층 | 모듈 | 상태 | 핵심 수치 (조건) |
|---|---|---|---|
| 장면 S0 / 판정 J | `m2a/scene` | V-C 조건부 PASS | dev 200·L2 1,000 생성 실패 0 |
| 계획 L2 / 파서 L1a | `m2a/plan` | V-B 조건부 PASS | pyperplan 2.1, plan_ms p50 약 11ms, 지시 변형 24개 |
| G1 조작 S1 / 스킬 A2·A3a | `m2a/sim` | 개선 중(A4) | 공식 게이트 P-gate P01 18/20, P04 17/20, P06 20/20 (GT 보조 weld 파지 근사). strict: P06만 20/20 |
| 디스패처 A1 / 러너 | `m2a/run` | 검증 중(V-E) | L1/L2 dev 60 B0/B1/B4 모두 0/60 (스킬 층 병목), L0 B1 6/20, 교란 L0 B1 3/20 vs B4 7/20 |
| 인식 V1~V4 / O3 | `m2a/percept` | 검증 중(V-G) | 가시 재현 91.1%, 정밀 99.7%, Top-1 79.3%, 위치 p50 1.0mm (O3 시뮬 렌더, 무질감) |
| 학습 정책 A3b (ACT) | `m2a/data` | 검증 중(V-F) | P06 시연 101, 5000 step, dev 쌍체 IK 8/37 vs ACT 1/37 (P-gate-strict, GT 투영 마스크) |
| LeRobot ROCm G-B | `m2a/learn` | V-D 조건부 PASS | ACT b4 1GiB 141ms/step, SmolVLA b1 3.3GiB 308ms/step (합성 데이터) |

## 2. 다음 할 일 (순서)
1. A4: 스킬 신뢰도(transport_place IK, put_aside 빈 자리, P02/P03/P05 파지, head 카메라 화각, reach 재측정) → `m2a/sim/skill_bench.py` 기준선/최종.
2. A4 병합 후 E 본 배치 재실행(dev 60 × B0/B1/B4 × O0) + O3(실제 `m2a.percept.o3`) 연결 + O3 예측 oid 안정화(MISID).
3. F: A4 이후 P-gate로 시연 재수집 → ACT 재학습(목표선), SmolVLA는 같은 v3 데이터에 task 문장 추가.
4. 봉인 test(seed 90000~90099) 해시 고정 → 9주차 상당 시점에 코드 동결 → test 1회.
5. 데모 영상, 로그 뷰어(U1), 보고서.
6. SAM 3.1: HF 계정(Seah1006)은 facebook/sam3.1 승인됨. WSL에 HF 읽기 토큰 필요(사용자 결정 대기).

## 3. 환경 (집 PC: WSL Ubuntu-24.04, RX 7600 8GB, 12코어, 15GB)
- 시뮬·계획·인식(CPU): `conda activate robot_percept` + `source sim_test/gl_env.sh` (AMD Mesa D3D12 EGL). 
- GPU 모델: `robot_percept_rocm` / 학습: `m2a_lerobot`(robot_percept_rocm 복제 + lerobot 0.4.4 --no-deps). 둘 다 `HSA_ENABLE_DXG_DETECTION=1`, `LD_LIBRARY_PATH=$CONDA_PREFIX/lib`, 학습은 `M2A_TORCHVISION_PYTHON_ONLY=1`.
- 데이터·체크포인트: `~/m2a_data/` (git 밖). 실행 로그: `runs/` (gitignore).
- 측정 락: `/tmp/rp_measure.lock`, GPU `/tmp/rp_gpu.lock` (이중 락, 1회 5분 이내). `pkill -f` 금지.
- `m2a/data/`는 루트 .gitignore `data/` 규칙에 걸리므로 커밋 시 `git add -f m2a/data/*.py`.
- 회사 PC(RTX 2080 SUPER)에서 이어갈 때: `git fetch && git switch m2a/main`, 같은 conda 구성 필요(robot_percept_g0c 등은 회사 기준). LeRobot env는 새로 만들어야 함(m2a/learn/README.md).

## 4. 작업 방식
메인 에이전트가 계약·병합·검증 판정, 구현자(Codex GPT 또는 Claude)는 worktree `~/work/rp_m2a_<ws>`에서 소유 경로만 수정·커밋 금지, 검증자는 다른 모델로 독립 재현(기본 NEEDS WORK). 보고서: `m2a/notes/ws<a..g>_report.md`.