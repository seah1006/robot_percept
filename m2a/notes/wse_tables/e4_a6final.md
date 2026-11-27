# E4 dev: P-gate(GT 보조 weld 파지 근사), O3=시뮬 렌더 예측 인식(무질감)

쌍체 부트스트랩은 장면 단위, 10000회 percentile 95% CI (임의 지정).

## O0 dev60: B4r 재시도 허용 vs 고정된 B4(R=3)/B1 기준

원자료: `m2a/notes/wse_runs/e3-main-o0-a5final/result.json` (완료=True, 처리 180개)

[미완료] `m2a/notes/wse_runs/e4-retry-o0-a6final/result.json` 없음

|구성|성공 [Wilson 95% CI]|엄격 성공|avg_progress|거짓 완료|잘못된 missing|PERCEPT_MISS 회차/이벤트|MISID 회차/집기|초기 미검출/오분류|최종 fail_code|
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| B1 | 2/60 [0.9%, 11.4%] | 2/60 | 0.266 | 0 | 0 | 0/0 | 0/0 | 0/0 | {'GRASP_SLIP': 34, 'IK_FAIL': 23, 'TIMEOUT': 1} |
| B4 | 3/60 [1.7%, 13.7%] | 3/60 | 0.266 | 0 | 0 | 0/0 | 0/0 | 0/0 | {'GRASP_SLIP': 31, 'PLAN_VIOLATION': 9, 'TIMEOUT': 1, 'IK_FAIL': 16} |

- 쌍체 **B4−B1**, 60장면: 성공 +0.017 [+0.000, +0.050]; 엄격 성공 +0.017 [+0.000, +0.050]; avg_progress -0.000 [-0.022, +0.025]

## O3 L0 20

[미완료] `m2a/notes/wse_runs/e4-l0-o3knn-a6final/result.json` 없음

원자료: `m2a/notes/wse_runs/e3-b1c-o0-a5final/result.json` (완료=True, 처리 40개)

|O0/O3 구성|쌍|동시 성공|O0만 성공 (요청 정의: 인식 때문에 잃은 성공)|O3만 성공|둘 다 실패|
|---|---:|---:|---:|---:|---:|

O0만 성공은 같은 장면의 순서쌍 기준이며, 개별 사건의 인과 입증은 아님.

O0의 L0 B4는 교란 조건뿐이므로 무교란 O3와 짝지어 계산하지 않음.

## O3 dev60

[미완료] `m2a/notes/wse_runs/e4-dev-o3knn-a6final/result.json` 없음

|O0/O3 구성|쌍|동시 성공|O0만 성공 (요청 정의: 인식 때문에 잃은 성공)|O3만 성공|둘 다 실패|
|---|---:|---:|---:|---:|---:|

O0만 성공은 같은 장면의 순서쌍 기준이며, 개별 사건의 인과 입증은 아님.

[미완료] `m2a/notes/wse_runs/e4-baseline-o3knn-a6final/result.json` 없음
