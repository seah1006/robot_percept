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