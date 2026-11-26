# TASK-GA1: G1 집기 장면·접촉 물리·Dex3 손 제어 (소유: GA1 구현자)

먼저 `TASK-GA.md`(공통 규칙·판정 계약)를 읽을 것.

## 소유 파일 (이것만 생성·수정)
- `sim/g1_grasp_env.py` (신규)
- `tests/test_g1_grasp_env.py` (신규)
- `notes/m2a/ga1_changes.md` (신규)

## 요구사항
1. **XML 구성**: `sim.humanoid_env.build_g1_xml`(또는 같은 원본 `g1_with_hands.xml`)을 재사용해 집기용 MJCF를 만든다.
   - 골반 고정(freejoint 제거) 유지. 접촉은 **전역으로 켜되**, 충돌 대상은 **양손(손바닥·손가락) 충돌 geom, 테이블, 물체**만. 몸통·팔·다리 geom은 `contype=0 conaffinity=0`(자기충돌 계속 끔). 비트 설계를 노트에 기록.
   - 테이블(정적 box)과 물체 1개(freejoint)를 추가. 테이블 높이·위치는 **오른팔이 위에서 접근 가능한 위치**로 정하고 근거(도달 확인)를 노트에. 물체 종류·크기·질량은 TASK-GA.md 계약대로.
   - 손·물체 접촉 파라미터(friction, condim, solref/solimp, `opt.cone`, `opt.impratio`, timestep, noslip 등)는 **선택 근거**를 노트에. 리서치 에이전트(R-GRASP)가 메시지로 권장값을 보낼 수 있음.
   - 머리/정면 카메라 1개 이상 유지(렌더 확인용). seg 렌더 쓰면 offsamples=0.
2. **중력 보상 주의**: 기존 env는 `qfrc_applied = qfrc_bias`로 로봇 중력을 보상한다. 물체 freejoint DOF까지 보상하면 물체가 떠 버린다 → **로봇 관절 DOF에만** 적용.
3. **제어 API** (GA2가 이 계약으로 병렬 개발 중. 바꾸려면 GA2 에이전트와 메인에게 먼저 메시지):
```python
class G1GraspEnv:
    def __init__(self, obj: str = 'board', mode: str = 'phys', seed: int = 0, render: bool = False, width=640, height=480): ...
    def reset(self, seed: int | None = None) -> dict: ...        # 물체 무작위 배치(xy ±3cm, yaw ±30°), 팔 휴식 자세, 손 열림. 반환 = state()
    def state(self) -> dict: ...   # {'t', 'obj_pos'(3), 'obj_quat'(4), 'palm_pos'(3), 'palm_quat'(4), 'obj_table_contact': bool,
                                   #  'finger_contacts': list[str] (물체와 닿은 손가락 이름: 'thumb','index','middle','palm'),
                                   #  'max_penetration': float, 'weld_active': bool, 'finite': bool}
    def set_arm_target(self, pos, quat=None, side: str = 'right') -> bool: ...  # 손목/손바닥 목표(월드). 내부에서 sim.humanoid_ik 사용. 도달 불가면 False
    def set_hand(self, closure: float, side: str = 'right') -> None: ...       # 0=열림, 1=닫힘 (Dex3 7관절 고정 시너지)
    def step(self, seconds: float) -> dict: ...  # 시뮬 시간 진행 후 state()
    def object_rest_pose(self) -> tuple: ...     # (pos, quat) reset 직후 정착 위치
    def render(self, cam: str | None = None): ...  # RGB uint8 (render=True일 때)
    def close(self): ...
```
   - `mode='gate'`: TASK-GA.md의 P-gate 조건일 때만 손바닥–물체 weld(equality) 활성, `set_hand(<0.3)`이면 해제. `mode='oracle'`은 디버그용.
   - 접근 각도(위에서 손바닥 아래로)를 쉽게 하는 헬퍼 `pregrasp_pose(obj_pos, obj_yaw, height)` 같은 함수 제공 권장.
4. **테스트** (`tests/test_g1_grasp_env.py`, 빠르게 < 60초):
   - 로드·reset 결정성(같은 seed → 같은 물체 위치), 물체가 테이블 위에 정착(1초 후 낙하·관통 없음), 로봇 몸통–테이블 비접촉, 중력 보상이 물체에 적용 안 됨(물체 정착 z 유지), set_hand 0/1에서 손가락 관절이 범위 내로 이동, gate 모드에서 접촉 조건 없으면 weld 비활성.
5. **스모크**: 한 번 위에서 집기 시도(board, phys)를 스크립트로 돌려 성공/실패와 실패 이유를 노트에 기록(통과 못해도 됨. 사실만).

## 완료 보고
- `notes/m2a/ga1_changes.md`: 파일 목록, XML 수정 내역, 접촉 비트, 파라미터와 근거, 테이블 위치 근거, API 차이(있다면), 스모크 결과, 미해결.
- 최종 답변: 요약 12줄 + 자기 테스트 결과(명령과 통과 수).
