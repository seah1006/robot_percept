# P1c ON 서보 tick 비용 I-S3 1라운드 (2026-11-07)

## 결론
- 기준: `wip/r2` `adf57b3` (사용자 메시지의 `87b4d1b`는 master이며 P1c가 없어, V-S3와 확인 후 P1c 포함 HEAD를 기준으로 사용).
- `collision_avoidance=False` 기본값, monotonic 대기, 운영 락은 변경하지 않았다. 커밋 없음.
- 판단을 바꾸지 않는 계산 중복 제거와 planner 전용 정확 거리 fast path만 구현했다. steps/margin/임계값/재계획 주기는 바꾸지 않았다.
- 비간섭 A/B/A/B에서 sweep p95 `49.87 -> 22.46ms`, twist `71.02 -> 21.13ms`로 감소했으나 4패턴 모두 `<=20ms`를 안정적으로 만족하지 못했다. sweep 개선 배수는 2.22배로 중단 기준 3배 미만이다.
- 따라서 **1라운드에서 추가 최적화를 중단하며 수락 FAIL, 기본 OFF 유지**다. G1 30fps 절대 판정은 tick 기준 실패로 추가 주장하지 않는다.

## 최초 프로파일
원자료: `bench/humanoid_s3_out/profile_before.json`, `*_before.prof`, `*_before_cprofile.txt`. in-process 5초/패턴, 1초 warm-up, cProfile 활성이라 절대 tick은 계측 오버헤드가 포함된다.

| 패턴 | tick p95 | waypoint p95 | collision FK p95/최대 | 비고 |
|---|---:|---:|---:|---|
| sweep | 65.39ms | 60.18ms | 108/110 | 지속 재계획 |
| chest | 1.71ms | 0ms | 1/906 | holding 다수, 단일 tick max 445.48ms |
| jump | 1.77ms | 0ms | 1/503 | holding 다수, 단일 tick max 309.26ms |
| twist | 66.23ms | 60.35ms | 111/240 | 간헐 재계획 |

sweep 단계 p95: retarget 63.76ms, projection 60.25ms, waypoint 60.18ms, collision FK 20.58ms, collision distances 38.56ms, IK 1.53ms, release/brake 1.42ms, integration 0.53ms. 비병목은 IK/release/brake/integration이었다.

sweep cProfile 누적 상위:
- `plan_safe_waypoint`: 7.965s/163회
- `minimum`: 7.669s/16,300회
- `distances`: 5.227s/17,168회
- `forward`: 2.744s/17,168회

직접 경로는 `segment()`에서 49점을 검사한 뒤 escaping 판정용 `samples`에서 같은 49점을 다시 계산하고 start/endpoint도 반복했다. 보통 계획당 약 100회의 minimum/FK였다. microbenchmark에서 기존 minimum 0.338ms, row/normal 할당 없는 정확 거리 계산 0.209ms(1.62배)였으므로 중복 제거와 합쳐 3배 이상 가능하다고 사전 추정해 구현 진행을 결정했다. V-S3에 먼저 공유했고, steps 축소나 캐시 주기 변경 없이 동등 최적화만 하기로 합의했다.

## 구현
변경: `sim/humanoid_collision.py`
1. capsule 순서와 pair index/radius 배열을 초기화 시 캐시해 매 distance 호출의 dict 기반 endpoint/radius 재조립을 제거했다.
2. `minimum_distance()`를 추가했다. `closest_segments_batch`와 동일 수식으로 모든 pair의 정확 거리를 계산하며, 길이 `>1e-9`인 pair의 `previous_normals`도 기존처럼 갱신한다. 퇴화 pair는 기존 normal을 유지한다.
3. direct segment의 49개 gap을 escaping 검사에 재사용했다. start/endpoint는 기존 산술·판정 순서를 보존하려 별도 정확 계산했고, direct segment 마지막 sample의 normal history를 복원했다.
4. waypoint 두 구간도 같은 exact fast path를 사용했다.

변경하지 않음: 48 samples, margin 10mm, waypoint margin, route/argmin/worst, 캐시 임계값, release/brake/CBF, collision monitor, OFF 경로.

## 동등성
원자료: `bench/humanoid_s3_out/equivalence.json`, 기준 모듈 `baseline_humanoid_collision.py`(SHA-256 `56cc4ed2...`). 같은 프로세스에서 구/신 env에 동일 30Hz 합성 입력을 넣고 각 패턴 3초, 150 servo tick/패턴을 비교했다.

- sweep/chest/jump/twist 모두 route/accepted/endpoint_modified mismatch 0
- waypoint, path diagnostics, cmd, qpos 최대 절대차 모두 `0.0`
- 4패턴 최종 `qpos_array_equal=true`, `cmd_array_equal=true`
- planner fast distance와 full distance를 24개 난수 자세에서 `<=1e-12`로 확인
- 동일 선분 퇴화 입력에서 previous normal 비트 유지 테스트 추가
- 기존 OFF 기본/명시 false `np.array_equal` 테스트 포함 관련 4개 테스트 PASS

전체 pytest: **96 passed, 5 warnings, 45.96s** (기준 94 + 새 테스트 2).

## 비간섭 A/B/A/B 자체 측정
원자료: `bench/humanoid_s3_out/{A1,B1,A2,B2}/profile.json`, `ab_summary.json`. A=adf57b3 별도 worktree, B=최적화, 각 5초/패턴+1초 warm-up, cProfile OFF, 동일 측정 락 안, load 약 0.79~1.00. 차이는 B-A p95 bootstrap 95% CI, 10,000회(seed 20261107).

| 패턴 | A p95 | B p95 | 배수 A/B | B-A p95, bootstrap 95% CI | A max -> B max | 판정 |
|---|---:|---:|---:|---:|---:|---|
| sweep | 49.87 | 22.46 | 2.22x | -27.41ms `[-28.62,-25.06]` | 162.53 -> 147.15 | 개선 입증, 20ms FAIL, 3배 미만 |
| chest | 1.37 | 1.35 | 1.01x | -0.02ms `[-0.09,+0.06]` | 363.82 -> 293.04 | p95 차이 입증 안 됨, 스파이크 잔존 |
| jump | 1.78 | 1.34 | 1.32x | -0.44ms `[-2.77,-0.02]` | 297.11 -> 160.19 | p95 통과, 스파이크 잔존 |
| twist | 71.02 | 21.13 | 3.36x | -49.89ms `[-143.59,-18.64]` | 234.12 -> 73.47 | 개선 입증, 20ms FAIL |

B 개별 반복은 sweep 22.61/20.40ms, twist 21.78/19.34ms였다. 즉 조용한 반복 하나에서는 twist만 20ms 아래였고 sweep은 두 번 모두 실패했다. chest/jump는 holding 때문에 p95가 낮지만 재계획 tick max가 각각 293/160ms로 남는다.

## 안전/범위 판정
- 4패턴 구/신 cmd와 qpos가 비트 동일해 이 3초 비교 구간의 최소거리, chest 진동, twist 이동, 500Hz monitor 결과는 변경되지 않는다.
- static 순차/rest와 release는 알고리즘 판단 동등성 및 기존 테스트 외에 I-S3가 별도 장시간 재측정하지 않았다. V-S3 독립 재측정 대상으로 넘긴다.
- G1 30fps는 tick 기준을 넘지 못해 I-S3 절대 수락 측정을 생략했다. 성능 개선을 기본 ON 근거로 쓰지 않는다.

## 다음 대안 (이번 라운드 밖)
1. planner 계산을 별도 스레드/주기로 분리하고 마지막 검증 경로를 servo에서 사용. 시간 지연과 stale 경로 안전 여유를 수치화해야 하며 판정 변경이라 별도 합의 필요.
2. capsule endpoint FK를 MuJoCo full kinematics 대신 선택 체인 전용 FK로 계산. 동일 결과 검증 비용이 크지만 48 sample 자체는 유지 가능하다.
3. 보수적 swept bound/BVH로 안전하게 먼 구간을 배제. argmin/path_min 변경 가능성이 있어 연속 안전 여유와 동등성 규격을 새로 정의해야 한다.
4. 근사 형상 pair 축소/샘플 수 감소는 현재 동등성 원칙상 금지. 별도 안전 분석 없이는 사용하지 않는다.


## V-S3 최종 독립 판정
원자료 `bench/verify_s3/out_n_r1_*.json`, 기준선 `out_b_r1/r2_*.json`. V-S3 시간 한도로 신 코드 반복은 1회만 완료해 CI는 계산할 수 없으며, 성능 차이는 **입증 안 됨**으로 판정했다.

| 패턴 | 신 ON status tick p95 최대 | 기준선 2회 | 독립 최소거리 |
|---|---:|---:|---:|
| sweep | 29.4ms | 62.1 / 65.2ms | +9.7mm |
| chest | 131.0ms | 188.9 / 201.2ms | +3.4mm |
| jump | 155.3ms | 92.6 / 190.8ms | -1.5mm, 침투 1프레임 (기준선도 -0.7mm 1프레임) |
| twist | 59.0ms | 111.8 / 77.3ms | +3.6mm |

- OFF는 4~5.5ms로 기준선과 유사했다.
- 팔 범위는 기준선 편차 안이었다.
- 동등성 mismatch 0, pytest 96 PASS, 코드 리뷰에서 판단 변경 근사는 발견하지 못했다.
- static/release/G1 30초는 V-S3가 직접 재현하지 못해 PASS가 아니다.
- 전 패턴 ON p95 20ms 초과, jump 1프레임 proxy 침투가 있어 최종 **NEEDS WORK**. 3배 미만 중단 규칙에 따라 추가 최적화 중단 권고, 기본 OFF 유지.
