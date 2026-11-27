# F: G1 grasp_lift의 LeRobot v3 → ACT

## 구현

- `m2a/data/mask.py`: MuJoCo 물체의 전체 GT 자세(기울기 포함), 부품 치수, 활성 손목 K 및 T_table_cam으로 3D 상자의 투영 볼록 다각형을 rasterize한다. cylinder는 외접 직육면체를 사용한다. 근평면 0.1 mm(임의 지정), 정수 픽셀 중심, 화면 밖/픽셀 없음은 `mask_lost`. RGB에는 마스크를 적용하지 않는다.
- `m2a/data/recorder.py`: 10 Hz, HWC wrist 원본과 별도 uint8 HWC GT 투영 마스크. EE state15는 T xyz/wxyz, 직전 grip 명령, 7개 실측 관절. action7은 T의 위치 델타, 좌곱 축각, grip 명령. 숫자 메타(임의 지정)는 grasp_lift=1, P01~P06=1~6, source=0, sigma_cm=0, P-gate=1. 시뮬 `robot_percept`와 학습 `m2a_lerobot`은 각각 필요한 패키지가 달라 NPZ로 넘긴 뒤 공식 LeRobot 0.4.4 API로 v3 저장한다. RGB H.264는 원본 구도이나 손실 압축이다.
- `m2a/data/auto_demo.py`: standard L0 생성 장면의 목표에 맞춰 초기 관절·접근 yaw·높이·속도를 seed 기반으로 변동(임의 지정). 접근→하강→닫기→상승 오차를 EE 델타 API로 추종한다. 동일 목표 물체의 초기 높이 대비 10 cm 이상과 weld가 20틱 연속(2초, 임의 지정)일 때만 저장. 시뮬 API 기준 a26f31d의 weld는 엄지 대향·접촉 조건을 사용한다. 최종 수집은 메인 지시에 따라 P06(브래킷)만, 목표 100개(임의 지정); P04/P01 등으로 일반화했다고 보지 않는다.
- `m2a/data/train_act.py`: G-B와 동일 fp32, 배치 4, 청크 20, optimizer 100스텝, seed 41(임의 지정). 에피소드 경계를 보존한 action padding과 균일 프레임 샘플링, 스텝 손실·GPU allocator 피크·시간 JSONL, 이어 학습용 상태 저장. 학습 입력에서만 RGB와 GT 투영 마스크를 함께 좌우 반전한다. y 반전은 위치 극벡터 diag(1,-1,1), 회전 축벡터 diag(-1,1,-1), 관절 부호 (1,-1,-1,1,-1,1,-1)(임의 지정, 실제 좌우 시각/동역학 대칭성은 별도 검증 필요). 우측 기준으로 학습하며 왼팔 실행에 inverse mirror를 적용한다.
- `m2a/data/act_executor.py`: 시뮬/ACT 간 고정 binary pipe, 5틱 실행 후 20틱 청크 재계획(임의 지정). dev 10000~10199 중 표준 L0 P06의 첫 30개(임의 지정; 후보 실측 37)에서 생성 장면·초기 자세를 공유한 IK 전문가 대비 성공률/Wilson 95% CI 및 실패 유형을 기록한다.
- `tests/m2a/test_f_data.py`: 정면·회전·화면 밖·근평면 투영, 스키마·mirror, CPU LeRobot 에피소드 왕복.

## 실측 결과 (2라운드, 조건: GT 투영 마스크, P-gate-strict = GT 보조 weld 파지 근사 엄격판)

grasp_mode 표기: 코드 베이스 a26f31d(main 9abfc63 병합 전)의 `P-gate`는 엄격판과 같은 규칙이므로 이 보고의 모든 수치는 **P-gate-strict**다. 데이터셋 NPZ/LeRobot 메타의 숫자 `grasp_mode=1`(코드명 P-gate)이 곧 엄격판이다. 병합 후 완화 `P-gate`와 구분하려면 재수집 필요(미실시). 이 결과는 마찰 파지나 실세계 성능이 아니다.

### 데이터 (원자료 `~/m2a_data/`)
- 수집 `f_p06_spool/attempts_*.jsonl`, NPZ 101개. 부품 P06(브래킷)만, 목표 100(임의 지정) 초과 101. 총 시도 366회 중 성공 저장 101회 = **27.6%** (이전 파일럿 40/127 = 31.5% 포함). 실패: GRASP_SLIP 259, IK_FAIL 6. 이전 40개 NPZ는 스키마(wrist 256²×3, mask 256²×1 uint8, state 15, action 7), 프레임 60~72(평균 66.3), 성공 판정(10 cm 상승·weld 2초 유지) 확인 후 포함.
- LeRobot v3 `f_p06_lerobot/`(변환 로그 `f_p06_convert.log`): 101 에피소드, 6689 프레임, 10 Hz. 팔은 `meta/m2a_arms.json`(우 대표 / 좌 미러 학습).
- 시연 시드는 train 0~4999 중 P06 대상 장면(시드 약 1500까지 사용). 평가 dev 10000~ 와 분리.

### 학습 (ACT, m2a_lerobot, ROCm, fp32)
- 설정(임의 지정): 배치 4, 청크 20, 5000 step, seed 41, AdamW 기본 lr(LeRobot ACT 기본), 좌우 반전 증강, 이중 락, 1회 ≤290 s 4번에 나눠 이어 학습. 로그 `f_p06_train_{0..3}.log`, 체크포인트 `f_p06_act/{training_state.pt,policy/}`.
- 손실: 첫 10 step 평균 49.3(첫 111.8) → step 1597 최근10평균 1.98 → 3160 1.37 → 4718 0.87 → 5000 **0.83**. 총 학습 시간 795 s(실행 4회 합), step 중앙값 0.133 s. VRAM peak allocated 1.06 GB / reserved 1.15 GB.
- 수정(속도): 기존 코드는 샘플당 H.264 seek+청크의 마스크 20행 재독으로 약 2.4 s/step(5000 step 불가). wrist 영상 전체 디코딩과 parquet 열 1회 로드 후 메모리에서 청크를 만들도록 바꿔 0.14 s/step. 청크 끝 패딩 규칙은 LeRobot과 동일(마지막 행 복제, is_pad).

### dev L0 쌍체 평가 (P06 37장면, dev 10000~, 같은 장면·같은 초기 관절 섭동)
원자료 `f_p06_dev.jsonl`, `f_p06_dev.summary.json`, `f_p06_eval.out`. ACT 추론은 CPU(2 스레드), 10 Hz 관측→20틱 청크 중 5틱 실행 후 재계획(임의 지정), 최대 110 틱.

| 방법 | 성공 / 회 | Wilson 95% | 실패 유형 |
|---|---:|---|---|
| EE 델타 IK 전문가(grasp_lift) | 8 / 37 (21.6%) | 11.4%~37.2% | GRASP_SLIP 27, IK_FAIL 2 |
| ACT (5000 step, 시연 101) | 1 / 37 (2.7%) | 0.5%~13.8% | GRASP_SLIP 18, TIMEOUT 15, LIFT_SHORT 3 |

- 쌍체 차이(ACT−IK) = −18.9%p, 장면 부트스트랩 95% CI [−35.1, −5.4]%p(10000회, seed 41 임의 지정). CI가 0을 포함하지 않으므로 **IK가 낫다는 차이는 입증됨**(n=37). 쌍 분포: 둘 다 성공 0, IK만 8, ACT만 1, 둘 다 실패 28.
- 실패 분석: ACT는 22/37에서 그리퍼를 닫았으나(≥0.85) weld가 붙은 경우는 4건뿐이고 평균 최대 상승 0.7 cm(IK 6.6 cm). 즉 병목은 **파지 위치·자세 정밀도**(닫을 때 엄격 접촉 조건 미충족)이며, TIMEOUT 15건은 좌팔 11건으로 접근 단계에서 헤맴(좌우 미러 가정 미검증 가능성, 추정). IK 자체도 엄격판에서 21.6%라 상한이 낮고, IK 실패의 대부분(27/37)이 GRASP_SLIP이므로 학습 신호(시연)가 성공 샘플만이라도 정책이 이 정밀도를 재현하지 못했다. 좌/우 성공은 IK 좌 6·우 2, ACT 좌 1·우 0.
- 한계: 한 부품, 시연 101개, 모델 1개 seed, 1회 학습. M-min("ACT grasp_lift 1회 학습 + dev L0 평가") 충족, 성능 주장은 못 함. 추정: 시연 수 부족, 접근 오차 누적, 미러 가정.

### 테스트
- `tests/m2a/test_f_data.py`: robot_percept 3 passed 1 skipped(lerobot 없음), m2a_lerobot 4 passed(왕복 포함, 7.46 s). 전체 `python -m pytest tests/m2a -q`: **114 passed, 1 skipped**(`f_tests_full.log`).
- 변경: `act_executor.py`에 `summarize`(Wilson+쌍체 부트스트랩), 워커의 torchvision import 우회 수정. `train_act.py` 메모리 로딩.

### SmolVLA 확장에 필요한 것
- 같은 v3 데이터 재사용(task 문장 포함). 영상 키/통계 정합, 마스크를 보조 영상으로 넣을지 별도 비교, 더 많은 시연(여러 부품·노출 변화), 실제 인식 마스크로 교체, 지연 측정, 1주차 측정상 메모리 여유 확인. ACT가 접촉 정밀도에서 막혔으므로 VLA 이전에 시연 증가와 파지 자세 데이터 정제가 선행되어야 함.

### 남은 문제
- 완화 P-gate 재수집·재평가(병합 후), 시연 수 증가 대비 곡선, 좌우 미러 검증(좌팔 TIMEOUT 편중), 실행 청크 길이 변화, 추론 GPU 평가(지금은 CPU), 커밋은 메인이 `git add -f m2a/data`.
- 수집 코드 `auto_demo.py`는 `--part` 등 이전 라운드 수정 포함(미커밋).
## 3라운드: 4부품 언어 조건 VLA (오른팔)

- 베이스 `182469d` (`m2a/main`). **GT 투영 마스크, P-gate(GT 보조 weld 파지 근사)** 사용. 실물 마찰 파지나 인식 성능으로 해석하지 않는다. test seed 사용 안 함.
- 왼팔 train seed 0의 성공한 전문가 궤적 43개 표본: EE xyz/관절 왕복 최대 `5.94e-8`(각 항 원 단위), 회전 `7.60e-8 rad`, 축각/위치 action 왕복 `0`. `S=diag(1,-1,1)`에서 `SRS`와 미러 quaternion의 오차 `7.60e-8 rad`, 오른팔 FK 대조 위치 `1.0e-5 m`, 회전 `3.35e-16 rad`(각 최댓값). 원자료 `~/m2a_data/f3/mirror.jsonl`. 손목 영상 정렬, 접촉 및 폐루프 동역학 대칭성까지 입증하지 못했으므로 오른팔만 수집·학습·평가한다. 미러 구현 변경 없음.
- 현재 main `SkillRunner`에서 관측 10 Hz, 명령 관절 표적 FK와 실측 EE의 차이를 xyz/좌곱 축각으로 6차원 기록하고, 손 제어 명령을 profile grip 스칼라에 대응시켜 7차원으로 기록한다. 전문가 성공 + 추가 2초 weld 유지 확인; 학습 시 같은 시연만 사용. 관절 명령을 EE 제어로 재생할 때의 동등성은 별도 입증하지 않았다.
- 시연 목표 임의 지정: 부품별 100개, 총 400개; train 표준 L0에서 오른팔·P03/P04/P05/P06, 방해물 0~2개, source=0, 4개 영어 task, 에피소드마다 베이스 해시·장면 digest 메타 기록. LeRobot v3의 `meta/tasks.parquet`로 저장. 드라이버 `~/m2a_data/f3/driver.log`, 시연 원자료 `spool/attempts_*.jsonl`, 변환 `convert.log`, 데이터 `lerobot/`.
- 학습 임의 지정: same-data fp32, seed 41, SmolVLA base 고정 revision에서 b1/50청크/1200 step 목표(vision freeze + expert only, 10 denoise 유지), ACT b4/20청크/3500 step 목표. 256² wrist RGB, 별도 3채널 GT 투영 마스크, 15차원 state 공통. SmolVLA만 영어 문장; 양쪽 action 7. ROCm 이중 락에서 295초 타임아웃 및 체크포인트 이어 학습. 로그 `~/m2a_data/f3/{smolvla,act}/train_*.log`, 정책·optimizer 체크포인트 각각 동일 폴더 `policy/`, `training_state.pt`.
- dev는 부품당 20장면, 세 방법에 동일 장면·초기 관절 섭동, 최대 110틱·5틱 재계획(임의 지정). 오른팔 자연 생성 장면이 P06 18, P04 12개여서 동일 dev 시드 구간 내 표준 L0 목표 부품을 지정해 생성한 장면을 모자란 수만큼 추가한다. 세 방법 모두 대상 weld와 5.5 cm(임의 지정) 상승을 2초 유지해야 한다. IK는 스크립트 전문가, 학습 정책은 목표 OID를 EE 제어기에 넘기지 않아 weld 후보 지정으로 답을 누설하지 않는다(근접 물체의 GT synergy 및 P-gate 접촉 판정은 유지). 첫 weld OID로 마스크 제거, 문장 교란, 마스크 교란을 구분; 양 입력 일치 조건만으로 언어 grounding을 주장하지 않는다. 원자료 `~/m2a_data/f3/dev_*.jsonl`, `dev.summary.json`. 지연은 첫 호출 워밍업을 빼고 정책 프로세서·pipe·동기화 포함 왕복으로 집계한다.
- CPU 테스트: `python -m pytest tests/m2a -q` **151 passed, 1 skipped**, 26.02 s(`~/m2a_data/f3/tests.log`). 부품별 dev 20개·계약 범위, 쌍체 통계와 불완전 쌍 제외, 미러 왕복 테스트를 추가했다.

<!-- F3 MEASURED START -->
### 실측 (원자료 `~/m2a_data/f3/`)

| 부품 | 저장 / 시도 | 성공 필터율 | 저장 시연의 방해물 0/1/2 |
|---|---:|---:|---|
| P03 | 60 / 81 | 74.1% | 31/16/13 |
| P04 | 53 / 57 | 93.0% | 24/18/11 |
| P05 | 54 / 67 | 80.6% | 27/18/9 |
| P06 | 59 / 62 | 95.2% | 20/27/12 |

전체 LeRobot 변환 아직 미완료.

스모크(본 실험 아님): 4 에피소드/324 프레임, `pilot/convert.log` 및 `pilot/lerobot/meta/tasks.parquet`.

smolvla 스모크: 2 step, 손실 0.1129→0.07694, peak allocated/reserved 3.29/3.44 GiB, 실행 131.5 s(`pilot/smolvla/train_0.log`).

act 스모크: 2 step, 손실 106.2→89.76, peak allocated/reserved 0.99/1.07 GiB, 실행 61.4 s(`pilot/act/train_0.log`).

smolvla: 전체 데이터 체크포인트 완료치 없음.

act: 전체 데이터 체크포인트 완료치 없음.

전체 데이터 dev 평가(쌍체 성공, 실패 및 언어 분석·추론 지연) 아직 미실측.
<!-- F3 MEASURED END -->

### 남은 문제

- 시연 EE 라벨을 시뮬 EE 델타 제어로 실제 재생하는 오차, 왼팔 영상 및 접촉 동역학 대칭성, 학습 시 항상 제공된 마스크를 제거·교란했을 때 생기는 분포 밖 효과. 언어 대조는 소수 탐색 표본이며, 아무 물체에도 weld되지 않으면 언어 vs 마스크 우위를 판정할 수 없다.
- 4개 소량 시연의 명령 재생 진단: 기록 상대 EE action을 순서대로 그대로 재생하면 0/4 성공(3/4 weld), 명령의 EE 표적을 복원해 매 틱 실측 자세 기준으로 재계산하면 2/4 성공(P04·P06, 3/4 weld). 직접 재생 위치오차 p95 5.30~8.71 cm, 표적 재계산 p95 1.15~1.26 cm(각 시연 내). 현재 전문가의 연속 관절 제어와 학습 정책의 10 Hz EE 실행이 동등하지 않으며 파지 정밀도 병목이 남아 있음을 보여준다. 샘플 4개이므로 일반화 금지. `pilot/replay.jsonl`, `pilot/replay_retargeted.jsonl`.
- 2라운드는 P06 한 부품·P-gate-strict, 3라운드는 P-gate·다부품이므로 라운드 간 수치 차이를 학습 구조의 인과효과로 해석하지 않는다.

### 3라운드 설계 변경: EE 델타 → 절대 EE 목표

서보 명령 증분과 실측 EE 변화가 일치하지 않아 기존 동작 그대로 재생하면 0/4 성공이었다. `ee_target_table_rotvec_v1`은 **테이블 T 좌표의 목표 위치 3 m + T축 기준 절대 회전 벡터(축×각) 3 rad + grip [0,1] 1**이다. 절대 목표는 `(p_meas + dp, Rot(dr)·R_meas)`에서 복원했다. 실행은 매 0.1 s에 `p_goal−p_current`, `log(R_goal·R_current⁻¹)`을 기존 IK API에 넘긴다. 이 보정은 목표 물체 피드백이 아니므로 기록된 목표열은 개루프로 재생된다. 시뮬 공용 API는 변경하지 않았다. 좌우 증강은 이번 절대 데이터에서 사용하지 않는다. 새 NPZ/LeRobot/정책 메타에 행동 의미 및 문자열 `grasp_mode` 기록; 시연·평가 CLI에서 `--grasp-mode P-gate|P-gate-strict` 명시. 해당 실험은 **GT 투영 마스크, P-gate(GT 보조 weld 파지 근사)** 조건이다.

재생 게이트 기준: 각 부품의 원 전문가 성공 중 처음 10개(임의 지정), 해당 물체 weld + 5.5 cm 이상 상승을 20틱 연속 유지, 부품별 ≥80% 필요. 제어기에 목표 oid를 넘기지 않는다. 원자료 `~/m2a_data/f3/absolute/recovered_*.{jsonl,summary.json}`.

| 부품 | 원 전문가 성공 | 절대 목표 복원 재생 | 통과 |
|---|---:|---:|---|
| P03 | 10/10 | 6/10 (60%) | 아니요 |
| P04 | 10/10 | 10/10 (100%) | 예 |
| P05 | 10/10 | 9/10 (90%) | 예 |
| P06 | 10/10 | 10/10 (100%) | 예 |


절대 스키마 변환 스모크 1에피소드/81프레임 완료(`absolute/schema_pilot/convert.log`); Parquet에서 `grasp_mode: string` 값 `P-gate`, `action: float[7]` 확인. 이 스모크로 학습하지 않았다.

P03은 10 Hz 절대 목표 서보로 다시 수집한다. 원래 IK 계획에서 목표열을 복원해 우선 그대로 재생하고, 실패 시 사전 고정한 그립 정착 시간 및 z 오프셋 변형(임의 지정)을 시도한다. 성공한 행동열과 그 실행 중 관측을 저장한 뒤, 새 reset에서 독립 개루프 재생한다. 나머지 부품은 복원한 목표를 사용한다. 혼합 데이터셋의 최종 재생 게이트에 모두 통과하기 전에는 학습하지 않는다. 이전 델타 파이프라인/보고 PID `8234`/`10515`와 확인된 직계 자식만 종료했고 네 원 수집기는 유지했다. 상단의 델타 스모크는 회귀 진단이며 본 실험의 모델 결과가 아니다.

<!-- F3 ABS STATUS START -->
### 실측 (원자료 `~/m2a_data/f3/absolute/`)

- `native_P03` 개루프 검증: P03 10/10 (통과).
- CPU 회귀 테스트 `153 passed, 1 skipped` (`tests.log`).

| 부품 | 저장 / 시도 | 성공 필터율 | 저장 시연의 방해물 0/1/2 |
|---|---:|---:|---|
| P03 | 41 / 42 | 97.6% | 21/10/10 |
| P04 | 100 / 112 | 89.3% | 44/33/23 |
| P05 | 100 / 123 | 81.3% | 42/43/15 |
| P06 | 100 / 107 | 93.5% | 39/40/21 |

전체 LeRobot 변환 아직 미완료.

smolvla: 전체 데이터 체크포인트 완료치 없음.

act: 전체 데이터 체크포인트 완료치 없음.

전체 데이터 dev 평가(쌍체 성공, 실패 및 언어 분석·추론 지연) 아직 미실측.
<!-- F3 ABS STATUS END -->
