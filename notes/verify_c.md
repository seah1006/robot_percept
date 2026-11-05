# V-C2 최종 검증 (C조 Panda 집기 제어), 2026-11-03~05

판정: **PASS** (gt_assist=on 회귀 열세 없음, 장애물 home 거절 확인). 단 gt_assist=off 는 참고치이며 mustard place 0/20 으로 약함(공개 시 그대로 표기).

## 1. N=20 회귀, gt_assist=on (시드 0..19, 같은 조건)
기준선 = tag baseline-1102 의 sim/ 복사본(bench/verify_c/base, git show 와 diff 동일 확인), 현재 = HEAD+작업트리. 기준선은 return_home 이 없어 home 열은 N/A.
Wilson 95% 하한: 20/20 → 83.9%.

| 스위트/물체 | 기준선 pick / place | 현재 pick / place / home |
|---|---|---|
| single mustard | 20/20, 20/20 | 20/20, 20/20, 20/20 |
| single box | 20/20, 20/20 | 20/20, 20/20, 20/20 |
| single cup | 20/20, 20/20 | 20/20, 20/20, 20/20 |
| multi mustard/box/cup | 20/20 ×3 (all-three 20/20) | 20/20 ×3, home 20/20 ×3 (all-three 20/20) |

home 최대 물체 변위(현재): mustard 0.37 mm, box 0.02 mm, cup 0.0005 mm (<5 mm 기준).
스크립트: 현재는 `tests/test_pick_place.py --trials 20 --suite all` (로그 f_cur_on.log, 결과 f_cur_on_results.json), 기준선은 bench/verify_c/pp.py --root base (f_base.log; 기준선 코드에 gt_assist·home 옵션이 없어 동일 로직의 래퍼 사용).

### 계획 시간 (choose_grasp, 20시드, flock /tmp/rp_measure.lock 안에서 측정, 시작 시 load 1.7~3.5, 타 팀 작업 일부 병행)
| 물체 | 기준선 p50 / p95 / max | 현재 p50 / p95 / max |
|---|---|---|
| mustard | 0.464 / 3.646 / 5.641 s | 0.018 / 0.031 / 0.038 s |
| box | 0.008 / 0.036 / 0.059 s | 0.009 / 0.015 / 0.018 s |
| cup | 0.007 / 0.048 / 0.051 s | 0.009 / 0.019 / 0.023 s |
락 없이 잰 1차(부하 다름): 기준선 mustard 0.629/7.886, 현재 0.020/0.032 로 같은 경향. 모든 물체 계획 성공 20/20. 현재가 더 나쁜 항목 없음(box/cup p50 은 +1 ms 로 잡음 수준, p95 는 개선).

## 2. 장애물 있는 return_home negative (bench/verify_c/home_obstacle.py)
방식: box 집기+놓기 후, 장애물(cup/mustard)을 home 관절 보간 경로의 분율 f 지점의 손 위치(또는 TCP 위 15/25 cm)에 순간이동하고 **매 스텝 kinematic 고정**(처음엔 gravcomp 만 써서 장애물이 떨어져 "COLLIDED" 오판정 나옴, 테스트 결함이라 수정). 독립 모니터로 팔-장애물/팔-테이블 최소 접촉거리와 장애물 변위 측정. 시작부터 겹치는 배치 17건은 제외.

| 케이스 | 건수 | 결과 |
|---|---|---|
| 물체 든 채(gt on) | 2(시드 0,1) | RuntimeError "Cannot return home while object is attached", 이동 없음 |
| 물체 든 채(gt off, weld 없음) | 2 | "Home path intersects table or object after clearance retreat" 거절, 테이블 침투 0 |
| 경로 장애물(cup f=.7/.85/.95, mustard .95) | 7 | 전부 REJECT_EARLY, 장애물 변위 <0.07 mm. f=.7 한 건은 상승 중 접촉 검출로 거절(침투 0.99 mm, 임계 1 mm 직전), 나머지 6건은 사전 경로검사에서 이동 전에 거절 |
합계 11/11 안전(충돌 후 완료 0건). 한계: 우회(detour) 성공 사례는 못 만듦(상승 10 cm 후에도 막히면 거절), 테이블 위 정적 장애물과 시드 2개만 확인, 상승 중 거절은 접촉 1 mm 직전에서 멈추는 사후 검출임.

## 3. gt_assist=off N=20 (참고치, 시드 5개씩 4덩어리, pp.py --gt off)
pick ok 는 폭+양쪽 접촉 기반이라 낙관적. lift>5cm 열이 실제 들림.

| 물체 | pick ok | 실제 lift>5cm | place | home |
|---|---|---|---|---|
| single mustard | 20/20 | 17/20 | **0/20** (오차 중앙값 256 mm) | 20/20 |
| single box | 20/20 | 20/20 | 20/20 (5.4 mm) | 20/20 |
| single cup | 20/20 | 20/20 | 12/20 (60%, CI 39-78) | 19/20 |
| multi mustard | 20/20 | 14/20 | 0/20 | 20/20 |
| multi box | 19/20 | 19/20 | 18/20 | 19/20 |
| multi cup | 19/20 | 19/20 | 15/20 | 19/20 |
multi 세 개 모두 place 성공 0/20 (mustard 때문).
실패 유형: mustard = weld 없이 옆면 파지 후 낙하/미끄러짐(들림 실패 3~6건, 나머지도 놓기 오차 >200 mm); cup = 놓기 오차 ≥20 mm 8건(single); multi 에서 IK "잡을 수 있는 자세가 없습니다" pick 실패 2건(box 1, cup 1). 공개용 문구: "GT 보조 해제 시 box 100%, cup 60~75%, mustard 0%".

## 실패/주의
- FAIL 없음. 주의: on 모드 mustard home 변위 최대 0.37 mm(기준 5 mm 내).
- test_pick_place.py 는 data/c1_check/results.json 을 덮어씀(측정 사본은 bench/verify_c/f_cur_on_results.json).
- 11/5 PC 재부팅으로 첫 off 배치(f_cur_off.log)는 중단, d_* 파일이 최종본.

## 재현
```
wsl -d Ubuntu-24.04 -- bash bench/verify_c/run_5.sh   # 락 안 분할 실행(home 장애물, off, 지연)
python tests/test_pick_place.py --trials 20 --suite all            # on
python tests/test_pick_place.py --trials 20 --suite all --no-gt-assist
python bench/verify_c/pp.py --root bench/verify_c/base --n 20 --gt on --home 0
python bench/verify_c/home_obstacle.py --seeds 0,1
python bench/verify_c/agg.py
```
(환경: conda robot_percept, source sim_test/gl_env.sh, PYTHONPATH=$PWD, OPENBLAS_NUM_THREADS=1; 한 번에 하나씩 실행)
