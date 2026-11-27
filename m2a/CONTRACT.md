# M2A 구현 계약 v0.1 (2026-11-27, 메인 에이전트)

기획 근거: github seah1006/m2a-vla-proposal `planning/2차_VLA/d_arch2.md`(v2.1), `d_eval2.md`(15~17절 우선).
마감 2026-12-18(임의 지정, 약 3주) → 12주 계획을 **M-min 축소판**으로 압축한다.

## 0. 축소 범위 (3주)
- 1주차(11/27~12/3): 게이트 G-A(G1 파지), G-B(SmolVLA/ACT ROCm 가능성), 계획 코어(PDDL+검증기+템플릿 파서), 장면 생성기·판정 함수.
- 2주차(12/4~12/10): G1 스킬 실행기 + 디스패처(B0-script/B1/B4, O0=GT 인식) 끝까지, 레코더(LeRobot v3)·자동 시연, ACT grasp_lift 1회 학습.
- 3주차(12/11~12/18): 인식 V1~V4(SAM 3.1 또는 GDINO Tiny+SAM2 폴백) O3 연결, dev 평가 + 작은 봉인 test, 데모 영상, 보고.
- 빠지는 것(이번 범위 밖): 실사 트랙 X2, σ 곡선, 시연 수 곡선, LLM 슬롯 파서, teleop 시연 수집, L3 결합.

## 1. 디렉터리·소유권 (작업자는 자기 소유 경로만 수정)
```
m2a/CONTRACT.md                 메인
m2a/config/layout.json          A (초기값은 메인, A가 실측으로 조정 가능. 바꾸면 메인에 알림)
m2a/knowledge/m2a_shelf_v1/     메인 (parts.json, steps.json). 바꿀 필요 있으면 메인에 요청
m2a/plan/                       B   (pddl 생성, pyperplan 계획, 검증기, 한국어 템플릿 파서, B0-script)
m2a/scene/                      C   (장면 생성기 S0, 기하 판정 함수 J, 기호 상태 추출)
m2a/sim/                        A   (G1 조작 환경 S1, 스킬 A2/A3a, 파지 게이트 도구)
m2a/learn/                      D   (LeRobot/SmolVLA/ACT 환경 확인, 측정 스크립트)
m2a/notes/<ws>_*.md             각자 보고서
tests/m2a/test_<ws>_*.py        각자 테스트 (ws = a|b|c|d)
```
- 기존 robot_percept 코드(sim/, web/, perception/ 등)는 **읽기·import만**, 수정 금지(필요하면 m2a/ 아래에 래퍼).
- 공용 코드는 `m2a/common.py`(메인) 하나: 파일 로더만 둔다.

## 2. 좌표계
- **테이블 좌표계(T)**: 원점 = 테이블 윗면 중심, +x = 로봇에서 멀어지는 방향(앞), +y = 로봇 기준 왼쪽, +z = 위. 단위 m, yaw는 +z축 회전 rad.
- 장면 명세·판정·계획은 모두 T 좌표만 쓴다. 월드 변환(`T_world_table`)은 A가 layout.json에 기록.

## 3. 장면 명세 (scene spec, C가 생성 / A가 MJCF로 구성 / B가 기호 상태로 사용)
```json
{
 "schema": "m2a.scene.v1", "seed": 10042, "split": "dev", "level": "L1",
 "situation": "standard",            // standard | missing | pretray | stacked | reach
 "product": "m2a_shelf_v1",
 "goal_steps": [1, 2],               // 이 장면 기본 지시가 다루는 설명서 단계
 "objects": [
   {"oid": "o0", "part_id": "P01", "xyz": [0.05, 0.36, 0.0125], "yaw": 0.3,
    "region": "left_zone", "in_tray": null, "on": null}
   // in_tray: 시작부터 트레이 안이면 "T1" 등, on: 쌓여 있으면 아래 물체 oid. z는 물체 중심 높이(T 좌표)
 ],
 "render": {"table_rgb": [0.55,0.45,0.35], "light_seed": 7}
}
```
- oid는 장면 안에서 고유. part_id는 parts.json의 키. BOM 밖 방해물은 part_id "D01" 등(parts.json `bom=false`).
- 트레이·영역 기하는 layout.json에서만 읽는다(장면마다 바뀌지 않음).

## 4. 목표 명세 (goal, B 파서 출력 / B 검증기·C 판정 입력)
```json
{
 "schema": "m2a.goal.v1",
 "trays": {"T1": {"P01": 2, "P04": 2}, "T2": {"P02": 2}},   // 트레이별 부품 종류:개수
 "allowed_arms": ["left", "right"],
 "unusable_trays": [],
 "step_order": [["T1"], ["T2"]],      // 엄격 성공용 순서(앞 그룹 완료 후 다음)
 "excluded_parts": [],                // "다월은 빼고" → ["P04"]
 "source_text": "1~2단계 준비해"
}
```
- 장면에 부품이 모자라면(missing) 계획기가 goal을 완화하고 `missing` 목록을 출력한다: `{"P04": 1}`.

## 5. 기호 상태 (symbolic state, C의 `scene.symbolic(spec or gt)` 출력 / B 입력)
```json
{"objects": {"o0": {"part_id":"P01","region":"left_zone","in_tray":null,"on":null}},
 "reach": {"left": ["left_zone","center_zone","T1","T2","T3"], "right": ["right_zone","center_zone","T1","T2","T3"]}}
```
- reach는 layout.json `reach` 표(A가 IK로 실측해 갱신)에서 온다.

## 6. 계획 형식 (B 출력)
```json
{"schema":"m2a.plan.v1","planner":"pddl_pyperplan","ok":true,
 "actions":[["pick","right","o3","right_zone"],["place","right","o3","T1"],
            ["pick-from-top","left","o5","o2","left_zone"],["put-aside","left","o5","center_zone"],
            ["handover","right","left","o3"]],
 "missing":{"P04":1}, "plan_ms": 42, "reason": null}
```
- `ok=false`면 `reason`(예: "unreachable:o4", "goal_unsat").

## 7. 스킬 API (A 구현, 2주차 디스패처가 사용)
`run(skill, arm, oid, target) -> {"ok":bool, "reason_code":str|None, "internal_done":bool, "t_ms":int}`
- skill ∈ {reach_pregrasp, grasp_lift, transport_place, put_aside}; reason_code ∈ {IK_FAIL, GRASP_SLIP, TIMEOUT, COLLISION, None}.

## 8. 판정 (C 구현, 시뮬 GT만 읽음, 계획·스킬 코드와 독립)
`judge(gt_objects, goal, layout, reported_missing=None, internal_done=None, events=None) -> dict`
- gt_objects: `{oid: {"part_id","xyz","yaw","lin_speed"}}` (T 좌표)
- 부품 ∈ 트레이: 중심 xy가 트레이 내부 사각형(여유 margin) 안 + z가 트레이 바닥~바닥+0.08 + lin_speed < 0.02 m/s (모두 임의 지정, dev 파일럿 후 동결)
- 출력: `success, strict_success, avg_progress, false_completion, per_tray, violations[]`
- B의 **검증기**(계획을 기호적으로 실행해 목표 도달 판정)와 C의 **판정**(물리 결과 판정)은 서로 import 금지.

## 9. seed 구간
train 0~4999 / dev 10000~10199 / test 90000~90099. test seed는 `--final-test` 플래그 없이는 생성기가 거부(봉인은 2주차에 해시 고정).

## 10. 공통 규칙 (robot_percept notes/HANDOFF_HOME.md 4장 + 추가)
- 구현자는 커밋 금지(작업 트리에만 남김). 메인이 검증 PASS 후 커밋·병합.
- 측정(수 초 이상 벤치, fps/지연/VRAM)은 `flock -w 900 /tmp/rp_measure.lock`, GPU는 그 안에서 `/tmp/rp_gpu.lock` 이중 락, 1회 5분 이내.
- `pkill -f` 금지. 포트가 필요하면 구현 5091/5093/5095, 검증 5092/5094.
- 사실·실측은 원자료 경로와 함께, 추정은 "추정", 내가 정한 값은 "임의 지정". GT 보조 결과는 GT 보조라고 표기.
- 답변·보고서는 한국어.