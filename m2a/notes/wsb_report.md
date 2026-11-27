# M2A B 계획층 구현 보고 (2026-11-27)

## 변경 파일·API

- `m2a/plan/__init__.py`, `pddl_gen.py`: typed STRIPS 도메인과 PDDL 생성. `generate_pddl(state, goal, layout)`은 순서를 풀어 쓴 단일 진단용 문제를 반환한다.
- `m2a/plan/planner.py`: `plan(state, goal, layout, *, strict=True, diagnostics_dir=None)`.
- `m2a/plan/verifier.py`: `verify(state, goal, candidate, layout, *, strict=True)`. 계획기·생성기·C 판정기를 import하지 않는다.
- `m2a/plan/parser_ko.py`, `vocab_ko.json`, `instructions_variants.json`: `parse(text)` 및 정답 goal이 명시된 한국어 지시 24개.
- `m2a/plan/b0_script.py`: `plan(state, goal, layout)` 하한선. 기본 팔은 y>0이면 left, 아니면 right(0 동률 임의 지정). §5 기호 상태만 주면 region 대표 y를 쓰고 트레이 내 객체의 y는 트레이 중심으로 추정한다. 실제 위치·쌓임·도달 검증 없이 tabletop pick을 출력한다.
- `tests/m2a/test_b_plan.py`, `m2a/notes/wsb_report.md`, `m2a/notes/wsb_pytest.txt`, `m2a/notes/wsb_plan_ms.csv`, `m2a/notes/wsb_bench.sh`.
- `tests/m2a/__init__.py` 삭제는 기존 공용 테스트 디렉터리 모듈명 충돌 제거를 위한 예외이며, 메인이 별도 통합 커밋 `181659a`로 반영했다. B 작업 트리에서는 커밋하지 않았다.

## 도메인과 계획 방식

- 초안 다섯 액션에 `pick-from-tray`를 추가했다. `clear`로 쌓임 순서를 강제하고, 지역·트레이 reach를 별도로 검사한다. 상태의 `reach`가 우선이고 없으면 layout을 읽는다. 트레이 내 객체는 `in`만 부여하고, 활성화해야 할 위치 미상 객체는 `unlocated:<oid>`로 실패시킨다.
- 양의 전제·목표만 사용한다. 트레이별 목표를 실제 oid로 바꿀 때 모든 정위치 객체를 먼저 예약하고, 나머지는 직접 도달 → 공용 버퍼 경유 → 인계 → 불가 순과 oid 순으로 배정한다. `destination`은 배정된 배치만, `movable`은 목표에 필요한 물체와 위를 막는 물체만 연다. 재고 부족만 `missing` 완화에 쓴다. 닿을 수 없는 재고는 누락 대신 계획 불가다.
- 요청 트레이의 초과/오배치와 전 트레이의 BOM 밖·제외 부품, 금지 트레이 내용물은 `center_zone` 양의 목표로 청소한다. 후속 단계에 쓰는 부품이 선행 트레이에 있다면 먼저 center에 두고 후속 단계에서 배치한다. 요청되지 않은 일반 트레이의 정상 BOM은 다른 목표에 필요하지 않으면 그대로 둔다. 금지 트레이는 새 배치 금지, 기존 물체 회수는 허용한다.
- 엄격 모드는 단계 그룹별로 누적 목표를 순차 해결하고 양손이 비어 있는 상태로 각 문제를 끝낸다. `priority_parts`는 그룹 안에서 트레이에 넣는 순서만 제약하므로 쌓임을 해소할 때 비우선 부품을 먼저 집어 버퍼에 둘 수 있다. 검증기는 oid 배정을 다시 쓰지 않고 액션을 직접 실행하고, 배치 직전의 선행 그룹 완료 여부와 최종 정확 수량을 검증한다. 같은 그룹 안 동치 순서와 이미 들어 있던 정위치 물체는 허용한다.
- pyperplan 2.1 (설치 확인: `python -m pip show pyperplan`, `~/miniforge3/envs/robot_percept/lib/python3.12/site-packages`), Python 3.12.16. A*+hFF, 우선 인계 없이 탐색하고 해가 없을 때만 인계를 연다. 단계별로 인계 없는 해를 더 선호하지만 hFF는 admissible이 아니므로 행동 수 최적성이나 폴백 시 인계 수 최소는 보장하지 않는다. 진단 옵션으로 단계와 탐색 모드별 domain/problem을 남길 수 있다.

## 한국어 지원

`1~2단계 준비해`, `2단계만`, `3단계까지`, `다월은 빼고`, `오른손만 써`, `왼손만 써`, `왼쪽 트레이 쓰지 마`(좌측 T1), `T3 다시 정리해`, `긴 판재부터`. 조사·띄어쓰기·일부 구두점·전각·동의어(예: 목심, 도웰, 긴 보드, 브라켓, 좌측 트레이) 및 지원 템플릿 조합을 받는다. 단계 생략은 전체 단계(임의 지정), 금지 트레이는 요청 단계에서 제거(임의 지정, 대체 배정하지 않음), 재정리는 부족·오배치 교정이고 맞는 부품을 꺼내지 않는다. `다음주에 재고 정리해`, `9단계까지`, `T4 다시 정리해`, `3~1단계`, `오른손만 써, 왼손만 써`, `다월 빼고 다월부터`는 거절한다. 원자료: `m2a/plan/instructions_variants.json`, `tests/m2a/test_b_plan.py`.

## 테스트와 실측

- WSL Ubuntu-24.04 / conda `robot_percept`: `python -m pytest tests/m2a -q` → **68 passed, 1 warning** (P2 회귀 포함) (`m2a/notes/wsb_pytest.txt`, 기존 Dash pytest 훅 deprecation). PDDL 계획이 독립 검증기를 통과하고, B0는 standard 통과 / stacked, pretray, reach, excluded, unusable 실패. 독립 검증기가 전제 위반, 잘못된 트레이, 금지 팔·트레이, 허위 missing, 단계·우선순위 역전을 거절했다.
- 실측 절차: 11개 성공 fixture × 30회(반복 횟수 임의 지정), 각 fixture 한 번 워밍업 후 측정, `PYTHONHASHSEED=0`(임의 지정), 공용 측정 락 `flock -w 900 /tmp/rp_measure.lock`, 300초 timeout. `plan_ms`는 목표 변환/PDDL 쓰기/파싱·접지/검색 합계 wall time이고 verifier·fixture 작성·물리 실행은 제외. 아래 p95는 inclusive percentile이다. 재현용 fixture: `tests/m2a/test_b_plan.py`, 원자료: `m2a/notes/wsb_plan_ms.csv`.

| fixture | n | 최소 ms | 중앙 ms | 평균 ms | p95 ms | 최대 ms | 행동 수 / 인계 / 치우기 |
|---|---:|---:|---:|---:|---:|---:|---|
| 전체 | 330 | 6.350 | 12.829 | 15.634 | 40.836 | 82.352 | 12~20 / 0~2 / 0~2 |
| standard | 30 | 9.039 | 14.038 | 15.046 | 23.905 | 26.114 | 16 / 0 / 0 |
| missing | 30 | 7.780 | 11.277 | 11.494 | 15.987 | 16.583 | 14 / 0 / 0 |
| pretray | 30 | 9.627 | 14.483 | 14.369 | 17.675 | 19.281 | 18 / 0 / 2 |
| stacked | 30 | 29.872 | 42.255 | 42.650 | 51.842 | 82.352 | 20 / 0 / 2 |
| reach | 30 | 8.769 | 12.687 | 13.753 | 20.065 | 34.795 | 20 / 0 / 2 |
| handover | 30 | 10.206 | 15.674 | 15.872 | 22.695 | 27.536 | 18 / 2 / 0 |
| one_arm | 30 | 6.350 | 9.746 | 9.443 | 11.444 | 13.371 | 16 / 0 / 0 |
| excluded | 30 | 7.358 | 11.871 | 11.152 | 13.829 | 14.447 | 14 / 0 / 1 |
| unusable | 30 | 6.683 | 9.570 | 9.742 | 12.513 | 20.200 | 12 / 0 / 2 |
| priority | 30 | 10.523 | 14.616 | 15.816 | 24.784 | 33.335 | 18 / 0 / 1 |
| strict | 30 | 8.760 | 12.919 | 12.639 | 16.294 | 19.966 | 16 / 0 / 0 |

재실행: WSL `bash m2a/notes/wsb_bench.sh` (B 작업 경로 기준).

## 계약 확장 요청과 남은 문제

1. §4에 선택 `priority_parts: [part_id, ...]`와 그룹 내 배치 순서 의미를 명시 요청. §6에 `['pick-from-tray', arm, oid, tray]`를 추가하고 디스패처에서 처리해야 한다. §5의 `in_tray != null → region=null`, 위치 미상 `region=null`도 문서 반영 권장. B가 계약 원본을 편집하지 않았다.
2. 결과는 계약 fixture 기반 기호 검증이지 GT 장면/동역학 검증이 아니다. 용량·충돌·IK/인계의 물리 성공은 미검증. center 버퍼는 용량 무제한 모델이며 한 물체 위에 직접 올라간 물체 한 개만 허용한다(다단 스택은 지원, 분기·트레이 내 스택은 미지원). oid는 결정적으로 탐욕 배정하므로 복합적인 reach 교차/스택 또는 더 큰 문제에서는 실행 가능한 전역 대체 배정을 놓칠 수 있다.
3. V-B의 대형 장면(물체 22개, 3단 방해물 탑 2개, 구성 임의 지정) 단일 실측은 `plan_ms` 966 ms였다(원자료: 세션 `tmp/v-b/t3.out`). 소형 fixture 통계로 대형 장면의 지연을 가정하지 않는다.
4. 다른 목표도 동일 부품을 여러 트레이에 요구할 때 기존 정위치 개체를 먼저 보존한 뒤 순서대로 남은 재고를 배정한다(계약 내 임의 지정); 독립 검증은 같은 총 부족량의 동치 분배를 허용한다. C의 물리 judge 및 디스패처와의 연동은 다음 단계에서 확인해야 한다.

## 면접 설명

수량 목표를 구체 물체와 양의 STRIPS 목표로 바꿔 표준 플래너로 풀었습니다.
쌓임과 도달 제약은 도메인에 넣고, 양팔 인계는 버퍼 경유로 풀 수 없을 때만 탐색했습니다.
플래너와 구현을 공유하지 않는 검증기로 정답뿐 아니라 일부러 망가뜨린 행동도 테스트했습니다.
