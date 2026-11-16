# W2 변경 기록

## 범위
- 카메라 없이 순수 좌표 투영·preview 변환·합성 체커보드 보정·셀 GT 평가만.
- 운영 파일(web/*, teleop_tracker_win.py), 공동 DTO, commit 변경 없음.
- 실제 카메라 실행 0회. 전체 pytest 0회(검증자 전담).

## 구현
1. perception/localize.py: Detection/CameraModel → Localization. OpenCV 왜곡 역보정, 광선-평면 교차, bottom_contact와 top_center 구분. top은 높이 평행평면 교차 후 바닥으로 수직 투영. bottom은 높이 보정 ON/OFF 동일한 것이 정상. 명시 T_base_world 강체 변환 지원; 기본 world=로봇 base. yaw 미관측 null.
2. perception/preview_transform.py: OpenCV pixel-center resize(+0.5/-0.5), center unflip W-1-u, half-open box unflip W-x2/W-x1, UI letterbox offset/scale 역변환, K scaling. 단순 K/2가 아닌 pixel-center principal point 보정 포함.
3. tools/calibrate_camera.py: 오프라인 이미지 또는 명시적 카메라 선택. 실카메라는 확인 플래그, advisory flock, fuser holder 검사. 내부 K/왜곡 및 첫 체커보드 기준 외부 pose, yaml+calibration id. 단독 실행 경로 bootstrap. 이 라운드 실제 캡처 없음.
4. tools/bench_w2.py: eval seeds 100000~100039, mesh GT box 투영. bbox 하단 중심/GT top anchor 별도, 높이 ON/OFF 및 ±2px 코너 극단 잡음. 시뮬 카메라 K로 합성 보드 raster 이미지 생성 후 OpenCV 코너검출부터 보정.

## 재현
```sh
source /home/user/anaconda3/etc/profile.d/conda.sh
conda activate robot_percept
cd /home/user/work/robot_percept
export PYTHONPATH=/home/user/work/robot_percept
flock -w 900 /tmp/rp_measure.lock -c 'pytest -q tests/test_localize_r5.py tests/test_calibrate_r5.py'
flock -w 900 /tmp/rp_measure.lock -c 'python tools/bench_w2.py --seeds 40'
```

## 한계
- [시뮬GT] 인식은 GT projected mesh box. 가림을 반영한 detector/segmentation 점수 아님.
- bbox bottom center는 실제 바닥 접점이 아님. footprint/카메라 시점 편향은 잔존하며 top anchor의 이상적 0 오차는 GT 특징점 기반 수학 검증일 뿐 실제 성능 아님.
- plain 체커보드는 180도 모호성. image top-left endpoint 규칙, 실물 world-board 등록 시 일치 확인 필요. ArUco 기반 world 등록은 이 라운드 미구현.
- 독립 실물 격자 오차·실물 위치 오차·실제 preview FOV/crop 동일 검증은 미실시. 녹화 위치 오차 측정 불가.
- FrameMeta에 mode/FOV/crop 없음: camera 모델 내 값만 보존. 실제 preview 소비 연결 전 해당 필드 계약 확장이 필요. overlay frame은 localizer가 거부.
- 카메라 ownership은 협조 프로세스 lock + Linux fuser 선검사. 비협조 외부 프로세스의 경쟁 획득을 OS 수준 완전 방지하진 않음.

## 재개 지점
- 최종 자기 테스트+40 seed 벤치 exec_session_id=1029. /tmp/w2_bench.log, bench/w2/*.json 확인.
- V-W2=03k6xYxRmHmtXdIL에 검토 요청 완료. 검증 피드백 반영 및 전체 pytest 1회는 검증자.

- 최종 완료: exec1029 exit0, 자기 14 PASS(1.54s), bench/w2/localization.json 및 calibration.json/yaml 생성. 다음은 V-W2 재현/피드백만.

## V-W2 1차 피드백 반영
- V-W2 독립 전체 pytest: 358 PASS(게이트 추가 전 snapshot). 전체 회귀는 이후 재실행하지 않음.
- 자기 추가 시험: 17 PASS / 0 FAIL, 2.31초.
- 박스 높이 ON=OFF는 의도: 하단 접점과 상단 anchor를 구분, bbox만으로 정확한 top 특징점을 알 수 없으므로 임의 보정 안 함. 기존 수치의 GT top ON=0을 실인식 정확도로 주장하지 않음.
- Localizer 기본 거리 3m 이하 / 입사각 10도 이상. 기준은 카메라에서 교차점까지 유클리드 거리, 책상 평면과 광선 사이 각도. 위반 INVALID_INPUT+range_exceeded/grazing_incidence.
- estimate gate: RMS<=0.5px, 추정 board-normal pairwise span>=10도, 보드 중심 정규화 span>=0.03, focal=(0.2~5)*max(image size), principal point 영상 내부, finite K/dist 및 |dist|<=5. 이는 알려진 K 참값 비교가 아닌 퇴화/나쁜 입력 거부이며 독립 오차 검증을 대체하지 않음.
- camera_owner: fuser rc=1만 무소유, rc=0 충돌, 기타 rc fail-closed. fuser 실행 불가 예외 역시 VideoCapture 전에 종료. missing/unavailable unit mock 외 실카메라 실행 없음.
- 게이트 반영 40-seed 재벤치 exec1036. 결과 /tmp/w2_bench.log 및 bench/w2.
- 운영 파일 다른 페어 수정은 W2 소유/수정이 아님.

## 부모 추가 요청: bbox 실제 경로 보정
- 기존 bbox ON=OFF 결과는 과거 snapshot. 새 ON은 박스 중앙 광선이 물체 중간높이(height/2)를 통과한다고 가정하고 평행평면 교차 후 바닥 중심으로 내림. OFF는 기존 하단 중심+책상 평면. 명시 bottom_contact/top_center 의미는 유지.
- 계수 0.5는 기하적 중간높이 가정이며 eval fitting 없음. tuning=1000~1019에서 확인 후 확정, eval=100000~100039는 확정 후 1회.
- 균일잡음은 물체별 100회 u,v 독립 U[-2,2] 평행 박스 이동, 실제GT 위치오차의 pooled p95. 최대이동은 네 극단조합에서 무잡음 보정ON 출력 대비 이동량의 최대. 각 물체집단의 최대이동 p50/p95 별도.
- 원본 synthetic checkerboard의 radial k3 과적합을 새 gate가 거부. 합성3x supersampling 및 시점확대, 보정 distortion model을 k1/k2/p1/p2(k3=0)로 고정. 실물 카메라가 고차 radial 필요하면 별도 모델/독립검증 필수.
- ArUco 외부값·독립 격자점: [blocked: 회사 PC 실카메라]. 이 라운드는 실카메라 사용 금지.
- 재개 지점: exec1040은 측정 락 대기 중(다른 G/K 측정 순번 선행). tuning /tmp/w2_tune.log. 확정 후 eval 1회 필요.

- tuning 완료: 20 seeds/61 objects. 물체별 수치는 bench/w2/tuning/localization.json. analytic bbox midheight(height/2) 방식 고정, eval에서 변경하지 않음. 자기18PASS(2.33s).


- 최종 eval 재개 지점: exec1042, /tmp/w2_eval_final.log, 측정 락 대기(G/K 순번 선행). 최종 snapshot 평가 1회 명령은 이미 제출, 중복 실행 금지. 완료 후 notes/w2_results.md 이전 표 교체와 V-W2 전달.

- 최종완료: exec1042 exit0. 고정방식 eval1회 성공,18PASS(2.31s). notes/w2_results.md 최종표 교체. 재개지점: V-W2 최종독립 판정만 대기, eval 중복실행 금지.
