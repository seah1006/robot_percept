# TASK-GA2: 집기 시행 러너·판정·리포트 (소유: GA2 구현자)

먼저 `TASK-GA.md`(공통 규칙·판정 계약)와 `TASK-GA1.md` 3절(G1GraspEnv API 계약)을 읽을 것.
GA1이 `sim/g1_grasp_env.py`를 **동시에** 만들고 있다. 그 파일은 수정 금지. 아직 없으면 API 계약대로 **가짜 env(FakeEnv)**로 러너·판정·테스트를 먼저 완성하고, GA1 파일이 생기면 실제 env로 연결한다. API 불일치는 GA1 에이전트와 메인에게 메시지.

## 소유 파일
- `tools/m2a_grasp_gate.py` (신규)
- `tests/test_m2a_grasp_gate.py` (신규, FakeEnv 사용, < 30초)
- `notes/m2a/ga2_changes.md` (신규)
- 결과 폴더 `bench/m2a_ga/` (raw jsonl, summary json/md)

## 요구사항
1. **스크립트 집기 시퀀스** (env API만 사용): reset → pregrasp(물체 위 0.10m, 손바닥 아래, 물체 yaw에 맞춘 손 방향) → 하강(물체 높이에 맞게) → `set_hand(1.0)` 서서히(예: 0.5초) → 0.10m 들어 올리기 → 2.0초 유지 → 판정. 단계별 시간 제한.
   - 시퀀스 파라미터(접근 높이, 하강 오프셋, 닫기 속도, 들기 속도)는 `--params` JSON 또는 기본값. **튜닝 시드와 평가 시드를 분리**: 튜닝 seed 0~99, 관문 판정 seed 1000~1019 고정. 판정 시드로 파라미터를 조정하지 말 것(조정 이력은 노트에).
2. **판정 함수** `judge(trace) -> (success: bool, code: str, metrics: dict)`: TASK-GA.md 성공 조건·실패 코드 그대로. trace는 유지 구간 state 샘플(최소 50Hz). env 내부 플래그(weld_active 등)가 아니라 **state의 물체·손바닥·접촉 값으로만** 판정(독립성).
3. **CLI**:
```
python tools/m2a_grasp_gate.py --obj board|dowel|block|all --mode phys|gate|all --seeds 1000-1019 --out bench/m2a_ga/<tag> [--params p.json] [--save-frames N]
```
   - raw: 시행당 1줄 jsonl(seed, obj, mode, success, code, 최대 들림 높이, 유지 시간, 최대 상대 drift, 최대 관통, 접촉 손가락, 소요 시뮬/벽시계 시간).
   - summary: 모드×물체 표(성공 x/20, Wilson 95% CI, 실패 코드 분포), git 커밋·파라미터·mujoco 버전·시드 목록 기록. md도 생성.
   - `--save-frames N`: 처음 N개 시행의 들기 직후·유지 끝 프레임 PNG 저장(검증·보고용).
4. 20회 실행은 측정 락 안에서: `flock -w 900 /tmp/rp_measure.lock -c "..."`, 1회 보유 5분 넘으면 모드·물체별로 나눠 실행.
5. **테스트**: FakeEnv로 judge의 각 실패 코드·성공 경계(정확히 0.05m, 0.03m), Wilson CI 계산, 시드 파싱, summary 집계.

## 완료 보고
- `notes/m2a/ga2_changes.md`: 시퀀스·파라미터·튜닝 이력(튜닝 seed만 사용했는지), 실행 명령, 결과 표, 실패 분석, 미해결.
- 실제 env 연결 후 관문 판정 실행까지 하면 결과 경로 보고. GA1이 늦으면 FakeEnv 완료 상태로 보고하고 대기.
- 최종 답변: 요약 12줄 + 테스트 결과.
