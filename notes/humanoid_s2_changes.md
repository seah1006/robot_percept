# P1c 자기충돌 회피 재설계 I-S2 기록 (2026-11-06)

## 범위와 결론
- 기준: `wip/r2` 8aad96e, master 452378f, 시작 pytest 85 PASS.
- `collision_avoidance=False` 기본값은 유지했다. 실물 안전 인증이 아니라 MESH 반경 캡슐 근사 실험이다(`physical_stop_certified=False`).
- 구현→검증 2회 상한에서 **수락 기준을 모두 넘지 못했다. 기본 OFF 유지가 최종 결론**이다. 부분 개선을 기본 ON 근거로 사용하지 않는다.
- C2 setpoint p/v/a와 실제 q/qd를 reset/clip하지 않았다. monotonic 대기 코드는 변경하지 않았다. 커밋 없음.

## 원인 분리(후속 과제 1)
원자료 `bench/humanoid_s2_out/static_split_round0.json`, 합성 GT 보조, 실제 q 4초/자세. OFF는 순차 max/평균 2.13/0.93도, rest 독립 2.13/0.85도였다.

| current P1c | max 방향오차 | 평균 | OFF clearance>=40mm 4자세 평균 | holding tick |
|---|---:|---:|---:|---:|
| ON 순차 | 117.11도 | 35.38도 | 58.16도 | 1541 |
| ON 매자세 rest 독립 | 89.40도 | 16.35도 | 13.03도 | 941 |

- rest 독립에서 fwd90 1.8도, fwd90_el60 0.3도, up120 2.1도로 정상화되어 순차 경로/히스토리 영향이 컸다.
- 그러나 fwd45 49.0도, fwd60_el100 13.8도, rest/el90/cross_chest holding이 남아 정적 geometry/제동 과잉도 독립적으로 존재했다.
- 직접 원인: 기존 10mm planning margin이 동적 정착 rest clearance 약 7.5mm보다 커 유효 시작을 infeasible로 취급했고, 전체 reference 위치 지연을 stopping margin에 더한 latch가 안전한 direct 경로도 막았다. 단일 직선 부분 접근에는 우회 경로가 없었다.

## 재설계
- 목표/현재 사이 48샘플 경로 검사. direct가 안전하면 원 목표를 유지한다.
- 직선이 충돌하면 worst sample을 12/20/30mm clearance로 projection하여 2구간을 모두 검증한 중간 waypoint를 선택한다. 작은 clearance에서 안전 목표로 단조 이탈하는 `escape_direct`도 허용한다.
- 최종 planning hard margin은 10mm, 상시 command-velocity CBF margin은 5mm, emergency/release guard는 8mm로 했다.
- release/risk는 실제·reference closing speed, reference acceleration, 관측 reference jerk, normal tracking lag와 planned path minimum을 함께 기록한다. 최소 hold 80ms와 guard 원인 카운터를 추가했다.
- 단일 목표만 캐시하지 않고 시작 상태까지 cache key에 포함했다.
- OFF 회귀 테스트: 기본 옵션 생략과 명시적 `collision_avoidance=False`를 1200 physics step 실행한 qpos/qvel/ctrl/servo cmd가 `np.array_equal`임을 확인했다.

## 1차 결과
원자료 `static_split_round1b.json`. rest 독립 max/평균 39.60/4.81도, clearance>=40mm 4자세 평균 2.71도로 진단상 개선됐지만, 수락 대상인 순차는 max/평균 96.53/15.91도였다. cross_chest 이후 hum80/up120으로 latch가 전파되어 FAIL. V-S2 리뷰에서 순차 우선, 안전 목표 direct 경로면 latch 해제, 3mm margin/jerk false trip/샘플 간격 근거 보강을 요구했다.

## 2차 최선안 결과
### static 12자세
원자료 `static_seq_round2_safety.json`. 순차 max 2.13도, 평균 0.99도, clearance>=40mm 4자세 평균 1.16도. OFF 순차 2.13/0.93도와 유사하다. 자세별 실제 q clearance/최대 방향오차: rest 10.0mm/0.82도, fwd45 45.2/1.38, fwd90 79.4/1.66, fwd60_el100 61.8/0.54, cross_chest 9.38/1.85, hum80 158.8/1.65, up120 73.7/2.13. cross_chest는 91 tick holding이 있었지만 다음 자세로 고착 전파되지는 않았다.

### release와 4패턴 실제 q
원자료 `dynamic_gate_round2.json`, MESH 캡슐 proxy, 합성 입력, 실제 q를 2ms마다 `CollisionPathMonitor`로 검사.

| 패턴 | actual min | penetration checks | 미인증 구간 | 팔 최대 범위 | servo tick p95 |
|---|---:|---:|---:|---:|---:|
| sweep | +9.372mm | 0 | 0 | 97.57도 | 47.64ms |
| chest | +2.878mm | 0 | 31 | 44.15도 | 1.62ms |
| jump | +5.801mm | 0 | 0 | 15.63도 | 10.18ms |
| twist | +3.386mm | 0 | 35 | 39.67도 | 47.83ms |

- 팔은 네 패턴 모두 실제로 움직여 이전 0~4도 고착은 벗어났다.
- chest 3초→abd45는 3.10초에 8도 이내, 최종 1.03도로 복귀했다.
- exact check 침투는 0이지만 chest/twist의 motion-bound 미인증 구간 31/35가 있어 기준 (c)의 미인증 0을 충족하지 못했다.
- 48샘플 planner 비용으로 sweep/twist servo tick p95가 47.64/47.83ms라 20ms 기준을 실패했다. 따라서 G1 30fps·IK p95 렌더 측정을 추가해도 전체 수락은 불가능하며, 2회 상한에 따라 추가 튜닝/측정을 중단했다. 30fps와 별도 IK p95는 미판정이다.
- static을 5mm margin으로 낮춘 중간 시도는 순차 cross에서 실제 clearance +0.55mm까지 소진되고 다음 자세가 고착되어 폐기했다. 최종안은 10mm planning margin이다.

## 회귀와 파일
- 전체 `python -m pytest -q`: **87 passed, 5 warnings, 45.39s**. 기존 85에 planner/OFF-byte-equality 테스트 2개 추가.
- 원자료: `bench/humanoid_s2_out/`.
- 측정은 `/tmp/rp_measure.lock` 안, 각 실행 5분 이내. 포트 5093/5095 및 사용자 5080은 사용하지 않았다. AMD RX7600 환경이나 이번 in-process 비렌더 측정은 GPU를 사용하지 않았다.
- 최종 소스 SHA-256은 `bench/humanoid_s2_out/source_sha256.txt` 참고.

## 남은 한계/후속
1. 48 FK 경로 샘플을 broadphase+적응형 swept bound로 바꾸어 tick p95를 20ms 아래로 낮춰야 한다.
2. chest/twist의 실제 q 구간을 연속 인증하도록 monitor bound/refresh를 강화하되 캡슐 근사 한계를 유지해 표기해야 한다.
3. 이후에만 30fps/IK p95와 V-S2 독립 4패턴 재측정을 수행한다.
4. 모든 기준 독립 PASS 전에는 기본 ON 금지. 현재 최선안도 실사용 권장/실제 충돌 안전 인증 대상이 아니다.

## V-S2 최종 독립 판정
동결 소스 `collision 56cc4ed2` / `env dd1b1139` 기준 독립 재측정(`notes/verify_s.md`, `bench/verify_s2/`):
- static 순차 방향 max 1.93/2.25도, 평균 1.00도; rest 독립 1.53/2.10도 PASS.
- chest 3초→abd45는 0.96초에 8도 이내, 최종 1.0도 PASS.
- 독립 캡슐 20Hz 최소거리: sweep +9.4mm, chest +7.7mm, jump +1.6mm, twist +3.4mm, 관측 침투 0.
- 그러나 status tick p95가 ON 62/197/208/122ms(OFF 4~5ms)로 20ms 기준을 크게 실패했다.
- chest 고정 목표에서 관절 범위 111.5도로 우회/진동 이상이 있었고, twist 팔 범위는 3.1도로 OFF와 동일했다. wrist 오차도 9.71mm로 10mm 기준 직전이었다.
- 독립 최종 판정 **NEEDS WORK**, 기본 OFF 유지.
