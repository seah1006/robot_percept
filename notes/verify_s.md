# V-S 검증 노트 (pair S, r2) - 기준선 (구현 전달 전)
기준: git 1da4b93 스냅샷(/tmp/vs_base, git archive), 포트 5094, 합성 입력(GT 보조), 실카메라 없음. 독립 FK: bench/verify_s/base_s.py가 menagerie G1 xml을 직접 로드해 /humanoid/status의 q로 계산(sim.* 구현 미사용). 부하 load1 5.7~12(타 에이전트 공유).
재현: bench/verify_s/server.sh /tmp/vs_base (5094) -> bench/verify_s/measure.sh TAG [static,dyn,drop,occ,degen,coll] (flock /tmp/rp_measure.lock). 결과 out_base*.json.

## 기준선 수치
| 항목 | 기준선 | 합격기준 | 판정 |
|-|-|-|-|
| P1a FK 방향(12정적자세 대칭) | u1 max 14.85 / u2 max 17.67도, 평균 4.37 | <=8 | FAIL(fwd90 11.3/11.9, up120 14.9/17.7) |
| 손목 위치(rest S 기준 GT) | max 5.97mm | <=10 | PASS |
| 손목 위치(실제 S 기준 GT) | max 19.32mm (fwd90_el60 18.4, cross 14.3, fwd60_el100 13.2) | <=10 | FAIL |
| 좌우차 | 0 (대칭 입력; 비대칭 입력 시험 필요) | <=3 | n/a |
| IK 시간 | p50 1.13 / p95 8.34 / max 16.0ms | p95 <=33 | PASS |
| 로봇 MJPEG 30초 창 | 959프레임/31.59s=30.32fps, max gap 147ms, p99 64ms; tick p95 26ms, render p95 34ms | >=29.7 | PASS(부하 6.7~12) |
| P1b 손 끊김 손목회전 | 샘플간 최대 19.8도(27ms), 33ms환산 24.3도, 손목위치 점프 1.69mm | 기준선 -50% (<=9.9도/샘플) | 기준선 |
| 팔 가림 | 왼팔 hold 이동 0.0mm, 오른팔 259.7mm 정상, left_arm tracking False | hold | PASS |
| 퇴화 입력(케이스별 모드 재시작) | crash: mixed_row_len(pose 행 3/4 혼합, HTTP 200 후 worker crashed). 복귀 실패(정상입력 2초 후 u1 오차, control 3.11도): zeros 68.4, collinear 88.9, zero_arm_len 68.9, hand_degenerate 68.7. 정상: upper_body_only/hip_vis0/same_shoulders/vis_range 3.11 | crash 0 + 복귀 오차 <=control+2도 | FAIL |
| P1c 캡슐(arm r45/hand r50/torso r90mm, 교차 스윕 378샘플) | 최소 -33.5mm(left_upper|right_upper), <0mm 90프레임, <10mm 102프레임 | 임계 미만 0 (임계 >=0mm 제안) | FAIL(기준선) |

주의: 첫 degen/coll 실행(out_base2)은 mixed_row crash 이후 워커가 죽은 채로 이어져 무효. 격리 재실행(out_base3)이 유효. 캡슐 반경은 근사이며 절대값이 아니라 전후 비교용.

## 진행 로그
- I-S 1~3라운드 중간 보고 접수(미검증): A1 원인=고정 rest S와 실제 shoulder 이동(17.9mm); relative_targets 도입으로 합성 11자세 방향 1.5/2.1도, 손목 0.7mm(자체 측정). P1b 손 유실 -99.99%이나 실제 q 속도 2.14배/가속 103배로 자체 FAIL. 독립 재측정은 변경 묶음 수령 후.

## 11/5 독립 판정: P1a 분기복구 + P1b safety_brake 기본ON (소스 git blob env 55df5957 / ik 881499eb / teleop 40711a8b, I-S 동결본과 일치)
측정: 락 내에서 5094 자체 기동/종료(bench/verify_s/cand_job.sh), load 0.5~2.9, GPU 4~31%, 합성 입력(GT 보조). 원시 json bench/verify_s/out_cand5a..d.json, 로그 log_cand5*.txt.
| 항목 | 기준선(1da4b93) | 현재 | 기준 | 판정 |
|-|-|-|-|-|
| P1a 대칭 12자세 방향 | u1 14.85/u2 17.67 | u1 1.53/u2 2.10 | <=8 | PASS |
| 손목(실제 어깨 GT) | 19.32mm | 1.51mm | <=10 | PASS |
| 비대칭 6쌍x2(리셋 없음) | (현재본 이전 60.0도/93.7mm) | 3.08도/1.59mm, 좌우차 1.75 | <=8/<=10/<=3 | PASS |
| 30초 로봇 MJPEG | 30.32fps (load 6.7~12) | 999프레임/32.5s=30.71fps, max gap 111ms (load 1.5~1.7) | >=29.7 | PASS(절대판정은 부모 조용한 창) |
| IK 시간 | p95 8.34ms | p50 0.44 / p95 1.72 / max 20.0ms | p95<=33 | PASS |
| P1b 기본ON 실제 q 속도비/가속비 | OFF 1.588/2.111 | 0.614 / >=0.791 (status 폴링 하한, I-S 500Hz 0.618/0.784) | <=1.0 | PASS(가속은 하한; 500Hz 상한은 I-S 측정) |
| 손 끊김 손목 회전 최대 변화 | 19.8도 | 0.1도 (-99.5%) | <=9.9 | PASS |
| 퇴화 입력 복귀 | crash 1 + 복귀실패 4 | crash 0, 모두 0.13도(hand_degenerate 0.54), mixed_row/vis_range=400 | control+2 | PASS |
| 토글 정지 자세 | - | Δq 0.1도 | 튐 없음 | PASS |
| 토글 동작 중 OFF->ON | - | v 0.83~0.86, a<=0.06 | <=1.0 | PASS |
| 토글 동작 중 ON->OFF | - | v 2.18/2.10(정상 OFF 약 1.0의 2.1배), a>=3.56/1.73, Δq/poll 18.8~22.0도(OFF 12.1) | <=1.0 | FAIL(2/2) |
지연 증가(I-S 보고): 작은 신호 +32ms, 큰 step +272ms (보고만).

## 11/5 독립 판정: P1a 분기복구 + P1b safety_brake 기본ON (git blob env 55df5957 -> 토글 수정 후 3b519357, ik 881499eb, teleop 40711a8b)
측정: 락 내 5094 자체 기동/종료(bench/verify_s/cand_job.sh), load 0.5~3.9, 합성 입력(GT 보조). 원시 out_cand5a..d / cand6a..c.json, log_cand*.txt.
| 항목 | 기준선(1da4b93) | 현재 | 기준 | 판정 |
|-|-|-|-|-|
| P1a 대칭 12자세 방향 | u1 14.85/u2 17.67 | 1.53 / 2.10도 | <=8 | PASS |
| 손목(실제 어깨 GT) | 19.32mm | 1.51mm | <=10 | PASS |
| 비대칭 6쌍x2(리셋 없음) | (분기복구 전 60.0도/93.7mm) | 3.08도/1.59mm, 좌우차 1.74 | <=8/<=10/<=3 | PASS |
| 30초 로봇 MJPEG | 30.32fps(load 6.7~12) | 999프레임/32.5s=30.71fps, max gap 111ms (load 1.5~1.7) | >=29.7 | PASS(절대판정은 부모 조용한 창) |
| IK 시간 | p95 8.34ms | p50 0.44/p95 1.72/max 20.0ms | p95<=33 | PASS |
| 기본 ON 실제 q 속도비/가속비 | OFF 1.588/2.111 | 0.614 / >=0.791 (폴링 추정, I-S 500Hz 0.618/0.784) | <=1.0 | PASS(가속 상한은 I-S 500Hz) |
| 손 끊김 손목 회전 최대 변화 | 19.8도 | 0.1도 (-99.5%) | <=9.9 | PASS |
| 퇴화 입력 복귀 | crash 1 + 복귀실패 4 | 전부 0.13도(hand_degenerate 0.54), mixed_row/vis_range=400 | control+2 | PASS |
| 정지 자세 토글 | - | 폴링 Δq 0.1도 | 튐 없음 | PASS |
| 동작 중 ON->OFF (수정 전 3b519357 이전 동결본) | - | v 2.18/2.10(OFF 대조 약 1.0의 2.1배), Δq 18.8~22.0도 | 대조 +10% | FAIL |
| 동작 중 ON->OFF (수정본, 4시점) | - | v 0.762~0.765 (OFF 대조 0.78~1.04), Δq 9.2~9.6도 (대조 9.8~12.6) | 대조 +10% | PASS |
| 동작 중 OFF->ON 속도 (수정본) | - | 0.616/0.85/0.987/0.744, 피크 후 단조 감소 | <=1.0 | PASS |
| 동작 중 OFF->ON 가속 | - | 폴링 추정 1.25~2.49이나 ON 무토글 대조도 2.40 -> 시각 지터 과대추정, 독립 판정 불가. I-S 500Hz(40ms 이후 <=0.607) 의존 | <=1.0 | 조건부 PASS |
지연 증가(I-S 보고): 작은 신호 +32ms, 큰 step +272ms (보고만). P1c 미판정.

## OFF->ON 가속 최종 (I-S 500Hz npz 독립 재계산, bench/verify_s/check_npz.py, env blob 3b519357)
npz(bench/humanoid_s_out/20261105T045230Z_*): 정확 30Hz 입력/500Hz 물리, qd를 직접 2ms 차분해 계산(캡은 내 정의, npz vmax/amax와 일치).
- 전환 40ms 이후 max 가속비 0.598/0.597/0.599/0.380 (t0.3/0.6/0.9/1.2) -> <=1.0 PASS.
- 첫 40ms max(right_shoulder_pitch) 0.635/1.255/1.525/1.164 vs 동관절 OFF 대조 4.09/6.42/6.78/7.76 (OFF 대조 이하 4/4).
- 전환 후 속도 최대 0.617/0.716/0.800/0.565 (<=1.0), 단조 수렴. r0/r1 동일(결정적).
- 판정: 부모 안(40ms 이후 <=1.0, 첫 40ms는 OFF 대조 이하) PASS / 엄격 '전 구간 <=1.0'은 t0.6/0.9/1.2 첫 스텝 스파이크로 FAIL(최대 1.525). 기준 확정은 부모.

## P1b 최종 확정 (부모 결정)
OFF->ON 판정 기준: 전환 후 첫 40ms는 같은 관절·같은 step의 OFF 대조 이하, 40ms 이후 가속비 <=1.0. 근거(부모): OFF 상태 잔류 응답은 물리적으로 즉시 제거할 수 없고, 스파이크 1.16~1.53은 단일 physics step이며 동관절 OFF 대조 4.09~7.76보다 훨씬 작음.
측정: 첫 40ms 최대 0.635/1.255/1.525/1.164 (OFF 대조 이하 4/4), 40ms 이후 0.598/0.597/0.599/0.380 -> PASS. 엄격 기준(전환 구간 모든 순간 <=1.0) 적용 시 t0.6/0.9/1.2에서 FAIL, 최대 1.525 (참고 기록).
P1b = PASS (확정). 다음: P1c 통합 묶음 판정(캡슐 최소거리 >=0mm 프레임 0, 실제 q·연속 경로, 30fps·IK p95 영향).

## P1c 독립 판정 (구 snapshot: env 3e37f4bd / teleop 30aa2f64 / collision 0c4309e5 / ik 881499eb, collision_avoidance 기본 OFF, 옵션 ON으로 측정)
측정: 락 내 5094 자체 기동/종료, load 1.1~3.2, 합성 입력. 캡슐은 내 독립 정의(arm45/hand50/torso90mm, torso 축=pelvis->양어깨중점, 손 W->palm+9cm, 13쌍), status q 20Hz 폴링(500Hz 미관측). I-S 이후 소스 변경(mesh profile/제동 latch)으로 이 판정은 구 snapshot 범위.
| 패턴(24s) | OFF 최소/0mm미만 | ON 최소/0mm미만/5mm미만 | 비고 |
|-|-|-|-|
| 기본 교차 스윕 | -25.1mm / 90프레임 (기준선 -33.5/90) | +5.6mm / 0 / 0 (10mm미만 4) | I-S 5.688과 일치 |
| chest(가슴 밀착 고정) | -90.0 / 429/429 | +45.1 / 0 / 0 | ON에서 팔 관절 범위 0.0도(rest에서 전면 hold) |
| jump(0.6s마다 rest<->교차) | -90.0 / 209 | +45.1 / 0 / 0 | ON hold, 관절 범위 0.0도 |
| twist(교차+몸통 비틀기) | -25.8 / 426/426 | +0.5 / 0 / 5mm미만 11(10mm미만 14) | 마진 얇음, 팔 16도 이동 |
성능(ON): 30초 로봇 MJPEG 1033프레임/32.47s=31.78fps (max gap 84ms), IK p95 1.22ms, tick_ms_p95 p95 15.9; chest ON 21.98s 창 31.76fps, jump ON 31.86fps (OFF 대조 31.9/30.31). 판정: 침투 0·30fps·IK 영향 PASS(구 snapshot, 근사 캡슐 한정). 주의: chest/jump ON은 접근 없이 전면 hold(I-S 확인: 의도된 보수 fallback, 최대접근 미구현), 사용자 경고 UI 미연결, 기본 OFF, physical_stop_certified=False(긴급정지 인증 아님), twist 마진 0.5mm.

## P1c 새 snapshot 재판정 (env 84ad62e1 / teleop d65b91e2 / collision 4fe062a0 / ik 881499eb, 새 MESH 반경 torso118/upper53/fore45/hand57로 내 캡슐 재계산), load 1.7~4.8
| 패턴 | OFF 최소/0mm미만 | ON 최소/0mm미만 | ON 관절 범위(어깨·엘보 max) |
|-|-|-|-|
| sweep | -41.1mm / 113 | +16.8 / 0 | 0.0도 (OFF 88.3) |
| chest | -106.0 / 411 | +17.1 / 0 | 0.0 (OFF 20.5) |
| jump | -106.0 / 257 | +17.1 / 0 | 0.0 (OFF 60.2) |
| twist | -41.6 / 422 | +17.1 / 0 | 0.0 (OFF 3.6) |
ON 최소 +17mm 상수 = rest 자세 clearance: 팔이 전혀 움직이지 않음(동결). ON 상태 P1a: static 12자세 방향 max 121.5/132.1도(평균 64.6), 비대칭 max 101도·좌우차 68도, 안전목표 복귀(release) 8도 이내 도달 실패(최종 34.2도) -> 기능 FAIL. 성능(ON): dyn 29.84fps(load 4.8 오염 가능), IK p95 1.90ms; jump ON 21.51fps/tick p95 54ms(OFF 26.53, load 4.45 오염) 조용한 창 재측정 필요. 구 snapshot(3e37f4bd...)은 침투 0 + twist 16도 이동. 기본 OFF라 P1a/P1b 운영 판정은 영향 없음. P1c 판정: FAIL(새 snapshot), 수정본 대기.

## P1c 방향성 마진 snapshot (env 3a49949f / ik fcd3fb9e / teleop 191db4b9 / collision 996ebffd), 새 반경 내 캡슐, load 0.9~1.3
- 성능 최적 snapshot(env 28979bfb/teleop ad91f64a): ON static 평균 64.6도, release 실패 -> FAIL.
- 방향성 마진(teleop 191db4b9): release PASS (0.63s에 8도 이내, 최종 1.3도). static ON 12자세 max 65.3/42.0도, 평균 20.0도 -> FAIL.
- 자세별(OFF clearance -> ON 오차): 추종 OK abd45(110mm)/abd85(161)/fwd90_el60(78)/abd60_el90(138)/hum80(159); 얇은 clearance hold 정당 rest(7.5)/el90(13.7)/cross_chest(4.9); 과잉 보수 의심 fwd45(45.3mm, 31.4도)/fwd90(79.3, 44.0)/fwd60_el100(62.4, 18.9)/up120(73.7, 62.8).
- I-S 자체 런타임: actual -0.9494mm 침투, uncertified 77구간, FPS 29.283/gap 2.612s FAIL.
- 판정: P1c FAIL (기본 OFF 유지). 다음: 자세별 rest 시드 시험으로 경로 vs 정적 마진 분리, 침투/렌더 gap 제거 후 STATOPT=1 static,release -> 4패턴+fps(조용한 창).

## P1c 마지막 두 후보 (STATOPT=1 collision_avoidance 켠 static 12자세 + release, 새 반경 내 캡슐)
| snapshot (blob) | static 방향 max u1/u2 | 평균 | release |
|-|-|-|-|
| env d6049a4c / teleop 893eb6c6 / ik fcd3fb9e / collision 996ebffd (이력 순차) | 83.3 / 117.1도 | 45.2도 | 0.65s, 최종 1.3도 |
| 같은 snapshot, 자세마다 rest 시드 | 77.4 / 42.0도 | 15.7도 | - |
| 최종 후보 env 0cd1b0ba (+ teleop 893eb6c6) | 75.6 / 117.1도 | 35.4도 | 0.63s, 최종 1.3도 |
I-S 보고(미독립): 최종 후보 runtime actual +12.185mm 침투 0·미인증 0, ON 32.02fps; 단 팔 최대 이동 4.33도 후 holding 고착(앞선 방향성 후보 30.86도에서 퇴행).

## 최종 상태 (부모 결정, 2라운드 상한)
- P1a PASS: 대칭 12자세 방향 1.53/2.10도, 손목 1.51mm, 비대칭 3.08도·1.59mm·좌우차 1.75도, IK p95 1.72ms, 30초 창 30.71fps(load 1.5~1.7, 절대 판정은 부모 조용한 창).
- P1b PASS (OFF->ON 기준: 첫 40ms OFF 대조 이하 + 이후 가속비 <=1.0; 엄격 전 구간 <=1.0이면 최대 1.525로 FAIL, 참고): 기본 ON 속도/가속비 0.614/>=0.791(I-S 500Hz 0.618/0.784), 손 끊김 0.1도(-99.5%), 퇴화 복귀 0.13도·mixed_row 400, 토글 ON->OFF 속도 0.76(OFF 대조 0.78~1.04).
- P1c FAIL, 기본 OFF 실험 기능으로 마감: 켜면 침투는 0이지만 팔이 거의 안 움직이거나(static 평균 35~45도 오차) 안전 목표를 추종하지 못함. 한계: rest clearance 약 7.5mm에서 정지 마진이 큼, clearance 45~79mm 자세도 추종 실패, 20Hz 폴링·근사 캡슐 기준, physical_stop_certified=False. P1a/P1b에는 영향 없음.
