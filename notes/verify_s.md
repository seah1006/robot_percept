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

## 2026-11-06 P1c 재설계 (집 PC) V-S2
### 기준선 재현 (코드 8aad96e를 git archive로 /tmp/rp_s2base에 분리, 포트 5092, 측정 락 안, load 0.8~1.4, AMD RX 7600/Mesa D3D12, PERCEPTION=stub)
스크립트 bench/verify_s2/ (base_s.py 사본 + job.sh), 원자료 bench/verify_s2/out_b_*.json. 내 독립 캡슐 torso118/upper53/fore45/hand57, status q 20Hz 폴링(500Hz 미관측), 합성 GT는 보조.
| 항목 | 이 PC 재현 | 회사 수치 | 일치 |
|-|-|-|-|
| static OFF 순차 / rest독립 | 1.53/2.10도 평균 0.92 / 평균 0.84 | P1a 1.53/2.10 | 일치 |
| static ON 순차 | 75.5/117.1도, 평균 35.4 | 75.6/117.1, 35.4 | 일치 |
| static ON rest독립 | 77.4/42.0도, 평균 15.5 | 77.4/42.0, 15.7 | 일치 |
| release | 0.64s에 8도 이내, 최종 1.3도 | 0.63s, 1.3도 | 일치 |
| sweep OFF / ON 최소(침투프레임) | -41.6mm(116) / +16.2(0) | -41.1 / +16.8 | 일치(0.6mm 차) |
| chest | -106.0(431) / +16.2(0) | -106.0 / +17.1 | 일치 |
| jump | -106.0(276) / +16.2(0) | -106.0 / +17.1 | 일치 |
| twist | -41.7(433) / +16.2(0) | -41.6 / +17.1 | 일치 |
ON 팔 관절 범위: 4패턴 모두 0.0도 (OFF 88.3/21.5/54.2/3.5) = 동결. fps(ON 22s 창) 32.0~32.5, tick p95 최대 15.3ms(twist ON, 단일 창). 결론: 기준선은 회사와 같다(집/회사 차이 없음). 수락 (a)(b)(d) 미달 상태 그대로.
### I-S2 설계 리뷰 (1차)
rest독립 개선(39.6/4.81)은 진단이며 수락은 순차 기준. 순차 cross 이후 latch 번짐(96.5/15.9) 우선 수정, 3mm margin은 proxy-내캡슐 오프셋과 tracking overshoot 근거 필요, observed jerk 영구 latch 금지·hold 사유 카운터 노출, 경로 샘플 간격<45mm 스윕 확인, fwd60_el100 계속 대상. (I-S2에 직접 전달함)
### 최종 후보 독립 재측정 (I-S2 sha256: collision 56cc4ed2 / env dd1b1139; 작업트리를 /tmp/rp_s2new로 동결 복사, 포트 5092, 락 안, load 0.7~2.5, AMD RX 7600)
원자료 bench/verify_s2/out_n_*.json, 로그 log_n_*.txt. 내 독립 캡슐(118/53/45/57), 실제 status q 20Hz 폴링.
| 기준 | 독립 측정 | 판정 |
|-|-|-|
| (a) static 12자세 ON 순차 / rest독립 | 1.93/2.25도 평균 1.00 / 1.53/2.10 평균 0.89 (OFF 1.53/2.10, 0.92). OFF clearance>=40mm 자세(fwd45/fwd90/fwd90_el60/fwd60_el100/abd*/hum80/up120) 오차 모두 <=2.1도. 얇은 자세 rest/el90/cross도 <=2.2도. 단 wrist_mm_actualS 9.71mm(OFF 1.51, 기준 10mm 직전) | PASS (직접 재현, 손목 오차는 여유 얇음) |
| (b) release chest 3초->abd45 | 0.96s에 8도 이내, 최종 1.0도 (기준선 0.64s) | PASS |
| (c) 4패턴 ON 최소거리(내 캡슐, 20Hz 폴링) | sweep +9.4 / chest +7.7 / jump +1.6 / twist +3.4 mm, 침투 프레임 0 (OFF -41.6/-106/-106/-40.8). jump·twist 마진 얇음. I-S2 자체 500Hz 모니터는 chest 31·twist 35 구간 미인증으로 스스로 (c) 미충족 보고 | 내 캡슐 침투 0 PASS(20Hz 한계), 연속 인증 미충족 -> 조건부 |
| (d) 팔 실제 이동 | 관절 범위 최대 sweep 89.4 / chest 111.5 / jump 23.2 / twist 3.1도 (OFF 88.3/21.5/56.1/3.6). 기준선 0.0도 동결 해소. chest 111.5도는 고정 목표인데 OFF(21.5)보다 큼 -> 안전 경로 우회/진동 원인 미확인(요확인) | 대체로 PASS, twist 3.1도는 OFF와 같음, chest 이상치 |
| (e) 서보 tick p95 <=20ms | 상태 tick_ms_p95 최대 sweep 62.2 / chest 197.1 / jump 207.7 / twist 121.6 ms (OFF 3.9~4.8). I-S2 자체 47.6/47.8보다 나쁨(내 측정은 status 보고값, 렌더 병행) | FAIL |
| (e) G1 30fps·IK | ON 22s 창 fps sweep 33.2 / jump 32.2 / twist 32.2 (chest ON 영상 측정 실패). dyn 파트 30s 창은 MJPEG이 0.2~3초에서 끊겨 무효(ON tick p95 57~196ms), IK p95 0.5~0.6ms는 표본 4~64개뿐 | 판정 불가/불충분 |
| (f) OFF 경로 불변 | 이 라운드 OFF 측정(static OFF 1.53/2.10, 4패턴 OFF 침투 수치)은 기준선과 동일. I-S2의 OFF np.array_equal 테스트는 미확인(내가 pytest 재현 안 함) | 부분 확인 |
최종 판정: NEEDS WORK (P1c 기능 FAIL, 기본 OFF 유지). 핵심 개선(순차/독립 static, release, 팔 동결 해소, 침투 0)은 직접 재현했으나 (e) tick p95 20ms를 62~208ms로 크게 초과하고 연속 인증과 30fps 창 측정이 없어 수락 불가. 부트스트랩 CI: 이번 판정은 단일 반복 측정이며 A/B 차이 주장 없음(CI 미산출). 한계: 20Hz 폴링·근사 캡슐, 합성 입력, 단일 PC.

## 2026-11-06 P1c 성능 라운드 (V-S3)
### 1단계: 기준선 재현 (진행 중, 구현 후 재측정 남음)
- 코드: wip/r2 adf57b3(P1c 재설계 포함)를 git archive로 ~/rp_s3/base에 분리. 지시서의 87b4d1b는 master(P1c 재설계 미포함)라 사용하지 않음. /tmp는 중간에 비워져(원인 미확인) $HOME/rp_s3로 옮겨 재실행.
- 조건: 포트 5092, /tmp/rp_measure.lock 안, load 0.2~1.5(I-S3 프로파일과 락 교대), AMD RX 7600/Mesa D3D12, PERCEPTION=stub. 스크립트 bench/verify_s3/(job.sh, run_tick.sh, summ.py, base_s.py 사본), 원자료 bench/verify_s3/out_b_r{1,2}_{패턴}.json, 로그 log_b_*.txt. 내 캡슐 118/53/45/57, status 20Hz 폴링. 패턴당 2회(coll0 OFF -> coll1 ON, 각 24초).
- ON tick_p95 최대(ms), 2회: sweep 62.1/65.2, chest 188.9/201.2, jump 92.6/190.8, twist 111.8/77.3. OFF 4.1~7.1. V-S2: 62/197/208/122. sweep/chest 일치, jump·twist는 반복 간 편차 큼(92~191, 77~112)이라 개선 판정에는 반복 수를 늘려야 함. 기준 20ms 대비 전부 FAIL.
- ON 최소거리 sweep 9.7/9.5, chest 2.7/2.7, twist 3.4/3.8, jump -0.7(침투 1프레임)/1.4mm. jump r1에서 20Hz 폴링 침투 1프레임(V-S2에선 0) 관찰, 경계 수준. ON 관절 범위 sweep 89.4, chest 30.3/66.2, jump 20/30, twist 13/3.0도(반복 편차 큼).
### 2단계: I-S3 프로파일/방향 리뷰
- I-S3 프로파일(cProfile 포함): sweep/twist tick p95 65/66ms, waypoint 60ms, FK p95 약 108~111회, 직접경로 49샘플 FK를 escaping 판정용으로 중복 계산. 제안: gap 배열 재사용 + minimum fast path.
- 내 리뷰(I-S3에 전달): 중복 제거는 판정 불변이나 samples 끝점 비트 차이 주의, previous_normals 갱신 생략은 퇴화 입력에서 판단 변경 가능(기본은 갱신 유지), 근사(steps·간격·조기종료·재계획 빈도·마진) 금지, 동등성 테스트는 실제 4패턴 start/target 시퀀스와 env 궤적을 구 코드와 비교, chest/jump 재계획 스파이크(300~445ms)도 전후 보고. 합의 여부: I-S3 응답 대기(메시지 전달됨).
- 재측정 대기: 구현 sha256과 변경 파일 목록을 받으면 동결 복사 후 같은 run_tick.sh로 4패턴 x 2~3회, static/release/OFF 불변/G1 30fps/pytest 수행 예정. 현재 판정: NEEDS WORK (구현 전).
### 3단계: 구현 후 재측정 (부분, 중단됨)
- I-S3 구현 sha256 collision ba9b376c / tests 85d22a8d를 ~/rp_s3/new로 동결 복사해 측정(포트 5092, 락 안). 락을 I-S3 측정과 교대해 12회 중 3회만 완료한 시점에서 시간 한도로 중단. 원자료 bench/verify_s3/out_n_r1_{sweep,chest,jump}.json.
- 코드 리뷰: 변경은 direct 49 gap 재사용 + minimum_distance(exact, previous_normals 갱신 유지, start/end 호출 뒤 이력 복원) + pair 배열 캐시. 판단을 바꾸는 근사는 발견 못 함(steps, margin, 주기 불변). I-S3 동등성 스크립트(bench/humanoid_s3_equivalence.py)는 구/신 CapsuleModel로 같은 입력 lockstep 3초씩 비교(route, waypoint, path_min, cmd, qpos). 단 3초 창이고 내가 직접 재실행하지 않음 -> 동등성은 미재현.
- ON tick_p95 최대(ms) 신 1회 vs 기준선 2회: sweep 29.4 vs 62.1/65.2, chest 131.0 vs 188.9/201.2, jump 155.3 vs 92.6/190.8. 반복 1~2회라 CI 산출 불가("차이 입증 안 됨"). sweep만 약 2배 개선 경향, 전부 기준 20ms FAIL. ON 최소거리 sweep 9.7, chest 3.4, jump -1.5mm(침투 1프레임; 기준선 jump도 r1에서 -0.7 1프레임), 관절 범위 sweep 89.3, chest 13.4, jump 21.6도(기준선 반복 편차 범위 내). twist 미측정.
- 미수행: OFF 경로 불변 직접 확인, static 순차/rest/release, G1 30초 창, pytest 직접 실행, 잔여 반복. 판정: NEEDS WORK (P1c 기능 FAIL 유지, tick 20ms 미달, 직접 재현 PASS 항목 없음).
- 정리: 5092 리스너, job.sh, run_tick, web.app 잔존 0 확인(00시 20분경).


## 2026-11-09 r3 P1c 구조 변경 (V-S3, 회사 PC, 포트 5094, 측정 락 안)
### 기준선 HEAD cab9e7f (git archive ~/rp_vs3/base; collision ba9b376c / env dd1b1139)
인프로세스 하네스 bench/verify_s/r3_inproc.py(실시간 페이싱, 렌더 스레드 없음, 24s) + 500Hz qpos npz(bench/verify_s/r3raw/raw_b0_*), 내 독립 캡슐 118/53/45/57 재계산(r3_recalc.py, 로그 log_b0_recalc.txt). load 0.6~1.1.
| 패턴 | ON tick p95 / max / >40ms 개수 / rtf | 500Hz 최소거리(OFF) | 침투 | monitor 미인증 |
|-|-|-|-|-|
| sweep | 32.95 / 74.5 / 14 / 0.85 | +9.53mm (-40.2) | 0 | 0 |
| chest | 2.97 / 332.8 / 24 / 0.86 | +1.83 (-106.0) | 0 | 58 |
| jump | 59.5 / 266.6 / 63 / 0.71 | +2.10 (-106.0) | 0 | 8 |
| twist | 32.6 / 269.1 / 41 / 0.89 | +3.59 (-61.7) | 0 | 79 |
팔 후반 12s 관절 범위(ON/OFF, 도): sweep 89.4/88.1, chest 0/0, jump 0/54.2, twist 0/0. OFF tick p95 5.5~6.4ms, max<=17.7.

### 후보 c4 = I-S3 최종 동결 (collision 75b68ce5 / env 294d0bc1 / teleop bb163931 / tests d0fdfa30, 내가 git hash-object로 일치 확인; ~/rp_vs3/c4)
인프로세스 24s, load 0.8~1.5, 락 안. 원자료 r3raw/raw_c4_*, log_c4.txt, log_c4_recalc.txt, log_c4_traj.txt.
| 패턴 | tick p95 / max / >40ms | 500Hz 최소거리 | 침투 | 미인증 | 후반 12s 경로(ON, 도) |
|-|-|-|-|-|-|
| sweep | 12.8 / 19.6 / 0 | +9.69mm | 0 | 0 | 179 (OFF 178) |
| chest | 8.2 / 42.0 (t=0.31s 1회) / 1 | +8.91 | 0 | 0 | 0.4 (진동 없음, 6s에 정지) |
| jump | 13.1 / 31.7 / 0 | +6.49 | 0 | 0 | 0.3 (OFF 935) |
| twist | 7.7 / 22.6 / 0 | +8.99 | 0 | 0 | 0.4 (OFF도 고정목표) |
- 기능 문제: jump ON은 t=8s 이후 완전 정지(rest 자세 근처), 교차/rest 교대 미추종 -> '팔이 실제로 움직임' FAIL. chest는 right_shoulder_pitch -113.7도 수렴, 범위 122.5도(OFF 104).
- 서버 경로(5094, ON): static 12 대칭 방향 max 7.52/7.72도(up120 7.72, 8도 직전), 손목 max 33.3mm(up120; 나머지 11자세 <=9.73, cross_chest 9.73) -> 방향 PASS(여유 얇음) / 손목 FAIL. release chest->abd45 2.33s에 8도 이내, 최종 1.4도 PASS. out_c4_stON.json.
- 미실시: 4패턴 30초 fps 서버 창, 비대칭 12, OFF 회귀(P1a/P1b), planner 종료/kill -9/ON-OFF 반복. 사유: 12:5x 부모가 사용자 카메라 테스트 동안 새 성능 측정 중단 공지 -> 체인 중단(체인 r3_chain.sh 중단, 5094 미기동 확인). I-S3 자체 30fps(31.9~32.0, 957~961프레임/30s)는 미재현.
- 판정(c4): NEEDS WORK. 근거: jump 영구 hold, up120 손목 33mm, chest 스파이크 42ms 1회(40 초과), 직접 재현 못한 항목 다수.

### 후보 c5 (collision 6be22eb6 / env 444b9d74 / teleop bb163931 / tests 3d73db1e, 해시 직접 일치; ~/rp_vs3/c5) 부분 측정 — 부모 지시로 13:3x 중지
인프로세스 24s(락 안, load 0.85~3.5; jump는 동시 eval.r3_batch GPU 일부) + 서버 5094 경로. 원자료 r3raw/raw_c5_*, raw_c5b_*, out_c5_*.json, log_c5*_recalc.txt.
| 항목 | 결과 |
|-|-|
| jump ON (인프로세스) | p95 15.5 / max 30.5 / >40 0, 500Hz 최소 +6.51mm 침투 0 미인증 0, 후반 12s 경로 354.9도·범위 41.6도 (c4는 0.3도 동결, OFF 935도) -> 영구 hold 해소(부분 추종) |
| sweep / twist | p95 10.3 / 9.2, max 24.6 / 20.2, 최소 +9.47 / +9.05mm, 침투 0 미인증 0 |
| chest | p95 9.3, max 41.9 (t=0.34s 1회, c4와 동일 재현) -> 초기 스파이크 40ms 초과 미해결; 최소 +9.55mm 침투 0 |
| 서버 status tick_ms_p95(200샘플 창)의 최대 | sweep 27.4 / chest 22.5 / jump 21.3 / twist 12.7 (렌더 병행; 20ms 초과 -> 서버 경로 기준이면 FAIL 여지) |
| 서버 MJPEG fps | jump 959프레임/29.99s=31.95, twist 961/29.98s=32.02 (>=29.7 PASS). sweep 714/22.46s, chest 750/23.48s는 창이 30s 미달(원인: 벽시계 time.time() 기반 종료, 이후 monotonic으로 수정) -> 30s 창 재측정 필요 |
| 정적 12 ON 순차 (settle 3.2s) | **회귀**: hum80 u1/u2 45.0/78.5도 손목 238.7mm, up120 23.4/7.3도 손목 86.1mm (c4: hum80 2.4도/4.5mm, up120 7.7도/33mm). 나머지 10자세 <=2.2도, <=9.79mm. release 2.17s/최종 1.4도 PASS |
| planner lifecycle (1차, 카운트 기준 오류로 시간값 무효) | web.app+mp 4+planner 1: mode ON 시 planner 1 추가, mode OFF/옵션 OFF 시 planner 소멸, 6회 ON/OFF·3회 옵션 토글에서 프로세스 수 증가 없음, shm 44->59(실행 중)->44(종료 후). TERM·kill-9·kill-9 초기: cwd 기준 잔존은 계측 서브셸 1개뿐(=실제 0), 종료 시간은 측정 오류로 무효 -> 재측정 필요 |
판정(c5): NEEDS WORK (정적 회귀 hum80/up120, chest 초기 42ms, 서버 경로 tick p95 창 최대 >20, 미실시 항목 다수).

### 재개 지점 (V-S3, 부모 중지 지시로 중단)
정리 완료: 5094 닫힘, r3_* 체인/잡/서버/planner 자식 종료(r3_cleanup.sh). 동결 트리 ~/rp_vs3/{base,c3,c4,c5}.
남은 측정(c5 또는 새 동결 c6):
1. 정적 12 ON: SETTLE=8 재측정(서버 RTF 저하로 3.2s 내 미수렴 여부 분리): `bash bench/verify_s/r3_chain2.sh /home/user/rp_vs3/c5 c5` (stON8, sweep/chest 30s 창 포함; 락 필요, 약 6분).
2. 비대칭 12자세 ON/OFF: `bash bench/verify_s/r3_srv_job.sh TREE TAG "STATOPT=1" asym` (OFF는 STATOPT=0).
3. OFF 회귀 P1a/P1b: `r3_srv_job.sh TREE TAG "STATOPT=0" static,asym` 및 `dynv,degen`, 기준값은 이 문서 앞의 PASS 표.
4. planner lifecycle 재측정: `bash bench/verify_s/r3_life.sh TREE TAG` (BASHPID 보정 완료).
5. chest 초기 스파이크: 인프로세스 `bash bench/verify_s/r3_ip_job.sh TREE TAG "chest" 24` 반복(>40ms는 t~0.3s).
6. I-S3 시드 진단: bench/humanoid_s4_out/c6_seed_diagnose/result.json (생성 확인, 내용 미검토); 가설 = collision waypoint가 task IK seed를 덮어 hum80/up120이 순차 실행에서만 어긋남. I-S3 인프로세스 sim-시간 기준에서는 hum80 1.85도/up120 1.67도로 재현 안 됨 -> 서버 RTF/settle 차이 분리가 우선(1번).
