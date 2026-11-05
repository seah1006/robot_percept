# robot_percept

## 서버 (WSL Ubuntu-24.04)

```bash
source /home/user/anaconda3/etc/profile.d/conda.sh
conda activate robot_percept
cd /home/user/work/robot_percept
source sim_test/gl_env.sh
export HOST=0.0.0.0 PYTHONPATH=$PWD
PORT=5091 PERCEPTION=stub python -m web.app
```

http://localhost:5091 에서 G1 선택. ON 응답은 첫 JPEG ready 후 반환하며 cold startup은 별도 수 초가 소요될 수 있습니다. OFF는 worker를 종료합니다. 5080은 기존 사용자 서버로 예약합니다.

## Windows 트래커

Windows Python에 OpenCV, numpy, mediapipe, requests 및 모델이 필요합니다. 최신 tools/teleop_tracker_win.py를 %USERPROFILE%/Documents/sam_camera/teleop_tracker_win.py로 복사합니다. 기본 모델은 같은 폴더 models/hand_landmarker.task 및 models/pose_landmarker_lite.task입니다.

```powershell
python "$env:USERPROFILE/Documents/sam_camera/teleop_tracker_win.py" --url http://localhost:5091 --mode humanoid
# Panda 전용은 --mode panda. 실제 카메라가 분리되어 있으면 --video <녹화.mp4> 사용.
```

## 독립 창 실행기

tools/humanoid_launch.bat -DryRun 으로 명령/경로를 출력합니다. 실제 실행은 -DryRun 없이 사용합니다. -Port 5091, -Python <Windows Python 경로>, -TrackerRoot <트래커 폴더>를 선택할 수 있습니다. 서버와 트래커는 서로 독립된 Windows PowerShell 창에서 실행됩니다. 서버 포트 중복은 거부하며 5080은 금지합니다. 종료는 각 독립 창의 Ctrl+C. 이 구현은 실제 창 실행/생존 시험을 하지 않았고 문법 및 dry-run만 검증했습니다. 트래커는 서버 준비 전 연결 오류가 날 수 있으므로 서버 ready 후 해당 창에서 재실행하세요.

## 검증 / 지연 정의

```bash
pytest -q tests/test_humanoid.py tests/test_smoke.py
flock /tmp/rp_measure.lock -c 'uptime; nvidia-smi; python bench/humanoid_w_runtime.py'
```

/humanoid/status 의 server_latency_ms는 WSL monotonic 기준 수신→최초 servo tick 명령반영→그 스냅샷 렌더완료→JPEG shared-memory 게시의 p50/p95(ms)입니다. 최신 600개 게시된 입력만 포함하며 latest-only로 게시되지 않은 입력은 제외합니다. applied_seq/published_seq와 input_count를 함께 확인하세요. HTTP 전송/브라우저 decode 및 속도·가속 제한에 따른 실제 관절 목표 도달 시간은 포함하지 않습니다. capture_latency_ms는 Windows/WSL wall-clock 차가 포함되어 실측 end-to-end 보장이 아닙니다.

### G1 최초 시작 대기

G1 ON은 첫 렌더가 준비된 뒤 응답합니다. cold start는 환경에 따라 약 4~9초이며, 이 동안 lifecycle lock 때문에 `/humanoid/status`와 `/humanoid/update`도 기다릴 수 있습니다. UI는 전환 중 안내와 선택 비활성화를 표시합니다. 준비 후 스트림 첫 프레임 지연과 cold-start 총시간은 다른 지표입니다.

### G1 전용 실행과 FP 워밍업

G1만 쓸 때는 `RP_PERCEPTION_WARMUP=0`을 권장합니다. FP 등록을 사용하지 않는 세션에서 불필요한 초기 GPU·CPU 작업을 피할 수 있습니다. `PERCEPTION=stub`이면 워밍업은 자동 비활성입니다. FP가 필요한 경우 기본 워밍업을 사용하고 `/status`의 `perception_warmup`을 확인하세요. 운영 코드에는 측정 락이 없으며, `RP_GPU_SERIALIZE=1`은 필요할 때만 GPU 직렬화를 선택하는 옵션입니다.

워밍업 지연·FP lazy-start 적용 전 동시 실행 관측: G1 baseline **31.90fps** → 워밍업 **29.23fps**(33.45초) → 완료 후 **31.87fps**. 워밍업 중 최대 프레임 간격 **1.78초**, 서버 구간 p95 **92.54ms**였습니다. FP와 G1을 함께 쓸 경우 `/status`의 `perception_warmup.state=ready`를 확인한 뒤 G1을 켜는 편을 권장합니다. 수치는 합성 입력·해당 GPU 환경 관측이며 실카메라 결과가 아닙니다.

### 안전 감속

G1의 **안전 감속(실제 로봇 한계 준수)**은 기본 ON입니다. `/humanoid/options`의 `safety_brake` boolean 또는 화면 체크박스로 바꿀 수 있고, `/humanoid/status`에서 현재 값을 확인할 수 있습니다. OFF는 **반응 빠름·한계 초과 가능** 모드입니다. 한계 준수는 검증 세트 범위의 결과이며 모든 동작의 안전을 보장하지 않습니다.

전체 프로젝트 단위 테스트: 환경 활성화 후 `python -m pytest -q`. 루트 `pytest.ini`는 `tests`와 `eval/tests`를 수집하며 벤더·데이터·백업 복사본은 제외합니다. `web/test_pipeline.py`는 5081 전용 서버가 필요한 수동 통합 스크립트이며 pytest 테스트 함수가 아닙니다. `test_env`의 `rtree` 미설치는 별도 환경 의존성 실패로 보고하며 테스트를 건너뛰지 않습니다.

현재 정책은 G1 ON 동안 FP 워밍업을 `deferred_g1`로 미루고, 첫 실제 FP RPC 전까지 worker·CUDA 초기화도 하지 않습니다. G1 OFF 후 워밍업을 완료합니다. 11/5 재측정은 기준 **31.83fps**, 지연 구간 **32.00fps / 최대 gap 61.69ms**, 완료 후 G1 복귀 **31.97fps / 최대 gap 65.63ms**였습니다. 이는 실제 워밍업과 G1을 동시에 돌린 수치가 아니라, GPU 작업을 G1 OFF까지 미룬 정책의 결과입니다.

사용자 선택 물체 또는 실제 인식 요청 때문에 워밍업 취소가 거절되는 경우에는 해당 서버 FP 자식 프로세스의 CPU 우선순위를 nice 19로 낮춥니다. 이 우선순위는 서버 재시작까지 유지될 수 있습니다. `RP_PERCEPTION_CPU_THREADS=1`은 FP CPU 스레드를 줄이는 선택 옵션입니다. CPU 완화는 GPU 커널의 선점이나 무중단 렌더를 보장하지 않으므로, 이 경우에는 여전히 FP ready 후 G1 ON을 권장합니다.

워밍업 취소 정책 적용 전, nice 완화만 사용한 경로 관측(nice 10→19, FP CPU threads 1): G1 기준 **31.83fps** → 실제 겹침 **23.52fps / 최대 gap 197.00ms** → 완료 후 **30.47fps**였습니다. CPU 완화 적용은 확인됐지만 겹침 중 30fps·서버 지연 목표는 충족하지 못했습니다. 따라서 **G1 ON 중에는 워밍업 지연 정책을 사용하고, 이미 워밍업이 시작됐다면 ready 후 G1 ON**을 권장합니다.

현재는 선택 물체와 실제 인식 요청이 없는 **워밍업 전용 작업**에 한해, G1 ON 준비 시 FP worker를 중단하고 thread join·queue 정리를 확인합니다. 시작 reservation으로 재생성 경쟁을 막고, G1 OFF 후 자동으로 새 worker를 만들어 다시 워밍업합니다. 사용자 선택이나 실제 인식 RPC는 강제 중단하지 않습니다.

11/5 취소 정책 실측: ON 요청에서 ready 응답까지 **2.92초**(cold start), 응답 후 첫 1초 **33fps / 최대 gap 38.92ms**, 이후 30초 **31.97fps / 57.60ms**. OFF 후 자동 재워밍업 **35.01초**, 첫 실제 클릭 **HTTP200·ok / 2.43초**. 첫 1초 회복 기준은 ON ready 응답 이후이며 cold-start 총시간과 구분합니다.

### 자기충돌 회피 실험 진단

`collision_avoidance`는 **기본 OFF인 실험 옵션**이며 안전 감속과 독립입니다. 화면 체크박스 또는 `/humanoid/options` boolean으로 명시적으로 켭니다. 캡슐 근사 proxy 판단이므로 실제 충돌 안전을 보장하지 않습니다.

`/humanoid/status`의 `collision_state`는 `clear`(목표 수정 없음), `avoiding`(목표 수정·부분 접근), `holding`(브레이크 래치·안전 접근 불가)입니다. `holding`은 즉시 완전 정지를 뜻하지 않습니다. `collision_status`에 이유와 가드 진단, `profile_ms`와 `profile_counts`에 servo 단계 시간·FK 호출 수를 제공합니다(`servo_profile`은 호환 묶음).

진단은 새 추적 입력이 없어도 50Hz servo tick마다 갱신됩니다. API 상태 게시 15Hz, 화면 조회 10Hz는 렌더 부하를 위해 유지합니다. 실험 ON일 때 경고와 진단 펼치기를 표시하며 OFF에서 자동 활성화하지 않습니다.
