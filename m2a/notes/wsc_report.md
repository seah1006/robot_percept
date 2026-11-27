# M2A 작업자 C: S0 장면 생성과 J 판정

## 변경 범위

- `m2a/scene/{__init__,_geometry,generator,symbolic,judge,preview,cli}.py`, `m2a/scene/situation_mix.json`
- `tests/m2a/test_c_{scene,judge}.py`, `m2a/notes/wsc_report.md`, `m2a/notes/img_c/*.png`
- 메인의 공용 수정 `181659a`와 동일하게 작업 트리의 `tests/m2a/__init__.py` 삭제(패키지명 충돌 방지). 기존 `assets/mujoco_menagerie`는 미수정. 커밋하지 않음.
- 입력 근거: `m2a/CONTRACT.md` §2–5, §8–9, `m2a/config/layout.json`, `m2a/knowledge/m2a_shelf_v1/{parts,steps}.json`, `m2a/common.py`. 검증한 `layout.json` SHA-256: `d76d570ab5aa8f6db3c89cd3c18b03df06ff53fc58cf057c1f9188aa45cf3f9d`. Seed·해시 방식 참고: `sim/cell_scene.py`, `sim/cell_scene_eval.py`. 물리 측정은 하지 않음.

## 생성 규칙(임의 지정)

- **L0**: 1~3단계 중 하나, 그 단계 BOM에서 목표 수량 1개, 다른 물체 1~3개. `stacked`에 한해 목표를 상자형에서 골라 지지면 확보. `pretray`에서는 다른 물체 중 한 개가 동일종 여분이다.
- **L1**: BOM 용량이 충분한 1~2단계를 선택하고 단계별 종류를 최소 한 개 포함하여 목표 4~6개. `missing`은 명목 5~6개 중 한 개를 빼 실제 물체 4~5개를 유지한다.
- **L2**: 2~3단계, 선택 단계의 종류를 최소 한 개 포함하여 명목 목표 6~9개를 뽑고 누락된 유사쌍 P01/P02의 짝 및 비BOM D01을 더한다. 전체 물체 제한 6~10개. 각 단계 최대 수량은 `steps.json` 이하이다.
- **standard**: 최초 트레이는 비어 있다. 일반 초기 배치는 팔 전용 영역을 우선 사용한다. 8회 실패하면 공용 영역도 후보에 포함한다.
- **missing**: 목표 물체 한 개를 제거하고 기대 부족량 기록. L2에서는 P01/P02가 각각 남게 한다.
- **pretray**: 필요 부품 하나는 지정 트레이에, 하나는 부품종이 지정되지 않은 별도 트레이에 미리 넣는다. L0은 목표 한 개를 유지하므로 오투입 물체가 필요종과 같은 여분(*정리 대상*)이다.
- **stacked**: 지지 물체는 목표 부품. xy와 yaw를 공유하고, 위 물체 중심 z를 아래 물체 윗면 + 위 물체 절반 두께로 둔다. 상자형 아래 물체만 허용하고 위 물체 OBB의 각 변이 아래 윗면 경계에서 2 mm 이상 안쪽에 있어야 한다(임의 지정). 부적합 조합은 제외하며, 후보가 없거나 배치가 막히면 다른 조합/구성으로 최대 4회 시도한다(임의 지정). 이 한 쌍만 평면 투영 중첩을 허용한다.
- **reach**: 목표 부품 하나의 지정 트레이 y와 전용 영역 중심 y가 가장 가까운 팔을 기준 팔로 정하고, 해당 부품을 반대 팔만 닿는 영역에 둔다. `allowed_arms`는 두 팔 모두이며 `reach` 표는 레이아웃을 그대로 따른다.
- 레이아웃에서 테이블·영역·트레이 좌표를 읽고 OBB 분리축으로 배치한다. 임의 지정 여유: OBB 간 4 mm, 영역 또는 트레이 내부 경계에서 2 mm. 판재 yaw는 영역 장축 기준 ±15°, 기타는 ±180°(적층 쌍은 공통 yaw, 원통은 직립). 8회 실패 후 경계 슬롯과 기준각 ±1.5° 근방을 우선 시도한다. 최대 전체 재배치 192회, 물체당 180회. 꽉 찬 경우 `ValueError`에 배치를 막은 oid와 부품종을 기록하고, 부분 장면 반환이나 물체 생략은 하지 않는다. 트레이 `wall_thickness`가 있으면 외벽까지 피한다. 테이블 RGB 범위 `[.48,.38,.28]`~`[.62,.52,.42]`, 조명 정수 seed `< 2³¹`. NumPy SeedSequence로 내용/배치/렌더 난수 스트림을 분리한다. JSON 정규화 SHA-256 `scene_digest`는 선택 사용하며 seed 구간은 계약을 따른다.

## 계약 확장 및 판정

- 기존 scene 스키마에 `expected.goal`(부족 반영 **전** `m2a.goal.v1` 초안), `expected.missing`(예상 부족 사전), reach 장면에만 `expected.reach={oid, nominal_arm, required_pick_arm}`을 추가했다. `source_text`는 초안의 설명 문구이고 부분 BOM 수량을 표현하는 한국어 파서 입력으로 보장하지 않는다.
- 트레이 내부 객체와 미분류 GT의 `region`은 `null`이다. GT 적층은 실제 수평 도형이 겹치고 두 접촉면의 높이 오차가 5 mm 이내일 때로 추정한다(임의 지정; yaw만 있고 기울기·접촉력 없음). 속도는 J에서만 확인한다.
- J는 `layout.json` `judge`의 중심 xy 마진, 바닥 기준 z 범위, 정착 속도를 사용한다. 초기 레이아웃 값으로 각각 10 mm, 80 mm, 0.02 m/s 미만(계약상 임의 지정). 트레이 `floor_z`는 선택 필드로, 없으면 T좌표의 테이블 상판 `0`이다. 중간에 낙하한 물체도 GT 목록에 남아 있어야 하며 최종 중심 z<0이면 실패한다.
- 목표의 부족량은 전체 GT 수량과 원래 목표를 비교한다. 가용 물체는 이미 올바르게 들어간 수량부터 인정하고 남는 가용량을 목표 단계 순서로 배정한다. 완화된 목표를 기준으로 수량 일치와 `avg_progress`(일치 수량/가용 목표 수량, 분모 0이면 1)를 계산한다. 잉여·비BOM·제외·사용 불가·트레이 내 미정착은 성공에서 제외한다. `per_tray`는 원본 `requested`, 완화 `expected`, 정착 `actual`, 수량 `ok`를 낸다.
- `events=[{"oid":"o0", "tray":"T1", "t_ms":123}]`는 성공한 트레이 투입의 전체 기록으로 사용한다. 최종 기여 물체의 마지막 투입만 사용하며, 앞 그룹 마지막 시각이 뒷 그룹 첫 투입보다 빨라야 한다(동시 신규 투입은 순서 위반). **디스패처 요구사항:** 성공한 모든 투입 이벤트를 누락 없이 남겨야 한다. 기록에 없는 최종 기여 물체를 J는 초기 pretray로 간주한다. 활성 그룹이 둘 이상이고 `events=None`이면 strict 미검증(일반 성공은 독립). 순서 문제는 `strict_violations`에만 기록하여 `strict_success`만 낮추고 `false_completion`은 일반 성공으로 판단한다. `m2a.plan`은 import하지 않는다.

## 검증 결과

```sh
source ~/miniforge3/etc/profile.d/conda.sh && conda activate robot_percept
python -m pytest tests/m2a -q
python -m m2a.scene.cli --split dev --start 10000 --end 10199 -o /tmp/m2a_dev.jsonl
python -m m2a.scene.cli --split test --start 90000  # 플래그 없이 오류 기대
```

- 작업자 C 테스트 **30 passed**, 환경의 `dash/testing/plugin.py` Pytest 10 예정 호환성 경고 1건. 판정의 기하/정착/누락/거짓완료/순서/낙하와 생성의 결정성/seed 검증/상황별 불변식/GT 역추출을 확인했다.
- 기본 JSONL 모드에서 L0→L1→L2 순환, `situation_mix.json`의 가중치 `40/15/15/15/15`(임의 지정 가설)로 seed당 하나 선택한다. dev 200줄, 서로 다른 200 seed, 생성 실패 **0**. 관측 상황: standard 70, missing 32, pretray 42, stacked 27, reach 29. 선택은 정확한 할당량이 아닌 seed별 가중 표본이다.
- 물체 수 1~10개별 장면 수: `5, 24, 17, 64, 15, 9, 17, 40, 7, 2`. L0(67): `1:5, 2:24, 3:17, 4:21`, L1(67): `4:43, 5:15, 6:9`, L2(66): `7:17, 8:40, 9:7, 10:2`.
- 추가 생성 점검: dev 200 seed × 3 난이도 × 5 상황 = **3,000회, 실패 0회**(기하·상황 불변식 전체 검사는 기본 200장면 pytest). 봉인 구간은 플래그 없는 CLI가 거절함을 확인했고 실제 test 장면은 생성하지 않았다.
- 미리보기: `m2a/notes/img_c/{standard,missing,pretray,stacked,reach}.png` (L2, dev seed 10047). 위에서 본 이미지 5장으로 영역·트레이 경계, 좌/우 배치, oid 라벨 및 적층 한 쌍을 시각 검토했다. PNG는 아래 A 확정 기하 기준으로 다시 생성했다. PNG에 사용한 Pillow는 기존 환경에 설치되어 있었다(13.0.0, `conda list`).

## A 확정 기하 교차 확인

- 원자료: 작업자 A가 메인을 통해 공유한 기하(T 좌표). 원본 `m2a/config/layout.json`은 수정하지 않고 임시 `tmp/ws-c/a_layout.json`으로 주입했다. 측면은 `left_zone=[-.20,-.05,.24,.46]`, `right_zone=[-.20,-.05,-.46,-.24]`, 공용은 `[-.22,-.14,-.12,.12]`, 트레이 x=`-.01`, y=`.16/0/-.16`, 내부 `.24×.13`, `floor_z=.004`, `wall_thickness=.006`이다. 측면 판재는 y 장축(기준 yaw π/2)으로 전환한다.
- A 기하의 기본 dev 200장면 실패 0, 물체 수 분포는 위와 동일. L2의 dev 200 seed × 5 상황 **1,000/1,000 성공(100%)**; 6~10개별로 `31, 250, 532, 127, 60`장면이며 각 상황에서 200개씩 성공했다. 64회 한도에서는 10개 장면 두 건을 못 채웠고(10049/reach, 10139/standard), 192회 한도에서 둘 다 생성됨을 확인했다. 그보다 좁거나 배치 불가능한 영역에서는 예외를 반환한다(테스트 포함).
- 앞서 공유된 중간 축소 예시(측면 최대 |y|=.40, 트레이 x=-.01, 임의로 축소한 공용 영역)에서도 당시 전체 23개 테스트 및 dev 3,000 조합 생성 실패 0을 확인했다. A 확정 기하와는 다른 임시 예시이다.

## 남은 문제

- 병합된 A의 최종 `layout.json`이 이 임시 입력과 동일한지 확인하고 통합 dev 평가를 수행해야 한다. 배치 기하와 GT 기반 합격 판정만으로 실제 파지/도달/적층 동역학을 보장하지 않는다.
- strict 평가 전에 디스패처가 합의한 성공 투입 로그를 빠짐없이 남기는지, 모든 초기 oid(낙하 포함)가 최종 GT에 남는지 연동 확인이 필요하다. 테스트 split 해시 동결은 후속 작업이다.

## V-C P2 반영 (병합 전)

- 생성기 `layout=None`은 기본 `m2a/config/layout.json`을 사용하고 CLI `--layout PATH`는 입력 JSON을 한 번 읽어 전체 범위에 넘긴다. `symbolic(spec, layout)`, `symbolic_from_gt(gt_objects, layout, parts)`, `judge(gt_objects, goal, layout, ...)`는 기존처럼 명시적 레이아웃을 받는다.
- 일반 실패 `violations`와 순서 전용 `strict_violations`를 분리했다. 골든 해시 5건은 이동 가능한 고정 테스트 레이아웃과 NumPy 2.5.3을 기준으로 잡았다. 해시가 바뀌면 실패 메시지에 기준·실행 NumPy 버전이 나온다.
- `python -m pytest tests/m2a -q`: **30 passed**, 기존 환경 경고 1건. 기본 및 A 임시 레이아웃 각각 dev **200/200**과 L2 dev 200 seed × 5 상황 **1,000/1,000** 생성, 실패 0. 각 L2 행렬의 stacked 200건에서 상자형 받침과 OBB 여유를 확인했다. A 기하의 `stacked.png`도 새 규칙으로 재생성했다.
