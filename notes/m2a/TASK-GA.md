# TASK-GA: G1 Dex3 집기 관문 (M2A 1~2주차 관문 G-A)

작성: 메인(매니저) 에이전트, 2026-11-26. 기획 근거: m2a-vla-proposal `planning/2차_VLA/d_arch2.md` 3.4절 "파지 물리(게이트 G-A)", `d_eval2.md` 13.1절.

## 목적
현재 `sim/humanoid_env.py`의 G1은 따라하기 표시용(골반 고정, **접촉 전역 비활성** `mjDSBL_CONTACT`, 물체 없음)이라 물체를 집을 수 없다.
이 관문은 **G1 + Dex3-1 손이 MuJoCo에서 테이블 위 물체를 집어 들어 2초 유지할 수 있는지**를 20회 시행으로 판정하고, 안 되면 어느 폴백(P-gate 부착 근사)까지 내려가야 하는지 정한다.

## 공통 규칙 (반드시)
- 작업 위치: WSL worktree `/home/user/work/m2a_g1` (브랜치 `m2a/g1-grasp`). Windows 경로 `\\wsl.localhost\Ubuntu-24.04\home\user\work\m2a_g1`로 파일 편집 가능.
- 다른 worktree(`/home/user/work/robot_percept`, `/home/user/work/rp_test`)는 **읽기만**. 수정 금지.
- **기존 파일 동작 변경 금지**: `sim/humanoid_env.py`, `sim/humanoid_ik.py`, `sim/humanoid_teleop.py`, `web/*`. 재사용은 import·조합으로. 꼭 필요하면 기존 함수에 **기본값이 기존 동작과 같은** 선택 인자만 추가 가능(사유를 changes 노트에 기록).
- Python: `/home/user/anaconda3/envs/robot_percept/bin/python` (mujoco 3.17.0). 실행: `cd /home/user/work/m2a_g1 && source sim_test/gl_env.sh && PYTHONPATH=/home/user/work/m2a_g1 <python> ...` (PYTHONPATH는 리터럴 경로).
- 셸 실행은 PowerShell에서 `wsl -d Ubuntu-24.04 -- bash /home/user/work/m2a_g1/<스크립트>.sh` 처럼 **스크립트 파일로** 실행(인용 문제 회피). 임시 스크립트는 `/tmp/m2a_*`에.
- 수 초 이상 CPU 배치(20회 시행 등)와 전체 pytest는 `flock -w 900 /tmp/rp_measure.lock -c "..."` 안에서, 1회 보유 5분 이내. 운영 코드(sim/ 등)에는 락을 넣지 않는다.
- 커밋·push 금지(메인이 검증 후 커밋). 설치·다운로드·외부 전송 금지.
- 테스트는 **자기 소유 테스트 파일만** 실행. 결과·결정·미해결은 자기 changes 노트에.
- 정직성: 근사(weld)는 근사라고 표기. 수치를 지어내지 말 것.

## 판정 정의 (GA1·GA2 공통 계약)
- 시행 1회: 물체 1개를 테이블 위 기준 위치에서 xy ±3cm, yaw ±30° 무작위(시드 결정적) 배치 → 오른손으로 위에서 접근 → 손가락 닫기 → 10cm 들어 올리기 → 2.0초(시뮬 시간) 유지.
- **성공**: 유지 구간 2.0초 동안 (1) 물체 중심 z ≥ 시작 z + 0.05m, (2) 물체가 테이블·바닥에 접촉하지 않음, (3) 손바닥 사이트(`right_palm_site`) 기준 물체 상대 위치 변화 ≤ 0.03m. 판정은 시뮬 정답 상태로만.
- 실패 코드: `ik_fail`(접근 자세 도달 실패), `no_contact`(닫았는데 손가락 접촉 2개 미만), `slip`(들어 올리다/유지 중 떨어짐), `drift`(상대 위치 변화 초과), `penetration`(손-물체 관통 깊이 > 0.01m), `unstable`(NaN·발산), `timeout`.
- 모드: `phys`(마찰만), `gate`(P-gate: 엄지 + 검지/중지 중 1개 이상, 서로 다른 손가락 2개 이상이 물체와 접촉하고 물체 중심이 손바닥 영역 안일 때만 weld 활성, 손 열면 해제). `oracle`(무조건 weld)은 디버그 전용, 결과표에서 제외.
- 물체 3종(축척 모형): `board` 상자 0.12×0.05×0.025m 0.08kg, `dowel` 원기둥 반지름 0.012 길이 0.08m 0.02kg(눕힘), `block` 상자 0.04×0.04×0.04m 0.05kg.
- 관문 통과선 [가설]: 모드·물체별 12/20.

## 산출물
- GA1: 장면·물리·손 제어 (`sim/g1_grasp_env.py`, `tests/test_g1_grasp_env.py`, `notes/m2a/ga1_changes.md`)
- GA2: 시행 러너·판정·리포트 (`tools/m2a_grasp_gate.py`, `tests/test_m2a_grasp_gate.py`, `notes/m2a/ga2_changes.md`, 결과 `bench/m2a_ga/`)
- 각 TASK 파일 참조: `TASK-GA1.md`, `TASK-GA2.md`.
