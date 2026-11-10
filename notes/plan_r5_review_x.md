# r5 v2 2차 검토 R5-X (Codex, 구현자 관점)

검토일: 2026-11-10. 대상: notes/plan_r5_grounded_picking_cell.md v2. 판정: **수정 필요**. 아래 P0를 v3에 넣으면 구현 가능한 범위다. 실행 성능·설치 성공 판정은 하지 않았다.

## 0. 범위와 근거
- 지정 문서 7개와 지정 코드 8개를 읽고 관련 web/sim_worker.py, web/teleop.py, sim/env.py, sim/objects.py를 추가 대조했다. 브랜치 .git/HEAD는 wip/r2.
- 서버·카메라·모델·pytest·pip 설치·GPU 실행 없음. 사용자 5080 서버에 접속/실행/종료하지 않음. WSL 명령도 실행하지 않고 UNC 파일 읽기와 PyPI/HF 읽기만 수행했다. 저장소 쓰기는 이 파일 하나다.
- 환경 근거는 /home/user/anaconda3/envs/{robot_percept,ai}/lib/python3.12/site-packages 목록과 robot_percept의 dist-info/METADATA. 패키지 import나 실행은 하지 않았으므로 실제 런타임 로드 버전/ABI는 미검증.
- 기존 r3 측정 PASS는 인계 문서의 과거 판정이며 이번 검토가 재검증한 것이 아니다.

## 1. P0: 의존성·worker·VRAM

### 1.1 1차 사실 재확인 및 정정
- 두 env에 transformers/huggingface_hub/tokenizers/safetensors dist-info가 없다. torch 2.14.0+cu130, torchvision 0.29.0+cu130, numpy 2.5.3 dist-info가 있고 constraints와 일치한다.
- **numpy 2.5.2.dist-info와 2.5.3.dist-info가 동시에 존재**한다. 중복 메타데이터만으로 설치가 깨졌다고 단정할 수 없지만, env 복제는 이를 그대로 옮긴다. G0에서 importlib.metadata.distributions 목록·numpy.__version__·numpy.__file__·pip check·설치 report를 함께 기록하고, 충돌이면 검증된 새 env를 만든다. 임의 dist-info 삭제 금지.
- PyYAML 6.0.3 실제 설치. YAML을 피하기 위한 TOML 전환은 불필요하며 safe_load+스키마 검증이면 된다.
- 실제 PyPI JSON 기준 후보:
  - transformers 4.57.6: Python>=3.9, numpy>=1.17, huggingface-hub>=0.34.0,<1.0, tokenizers>=0.22.0,<=0.23.0, safetensors>=0.4.3. torch extra는 torch>=2.2.
  - transformers 4.45.2: Python>=3.8, numpy>=1.17, hub>=0.23.2,<1.0, tokenizers>=0.20,<0.21, safetensors>=0.4.1. torch extra는 상한 없는 torch.
- 따라서 **선언된 메타데이터상 numpy 2.5.3/torch 2.14와 직접 충돌은 없다**. 4.57.6을 G0 첫 후보, 4.45.2를 API 비교 후보로 권장한다. 이는 설치/실행 보장이 아니다. 기본 transformers 설치는 torch를 필수로 요구하지도 않는다. 위험을 resolver 변경, tokenizers 휠, 선택 의존성(sklearn 등) ABI, 모델 API, CUDA/ROCm 커널로 분리한다.
- 복제본에서 constraints를 사용한 dry-run/report 후 실제 설치·pip check·tiny 1회 추론을 실시한다. 버전·가중치 revision·모델 설정·전이 의존성 lock을 함께 남긴다. post_process의 box_threshold/threshold/text_labels 차이는 adapter 안에서 봉인하고 테스트한다. 원본 GroundingDINO 커스텀 CUDA 빌드 대신 HF 경로를 쓰되 disable_custom_kernels 등 실제 선택된 attention 경로도 기록한다.

### 1.2 최소 worker 변경안
현재 _worker는 시작 시 torch/FPRunner/sam2를 import하고, call은 fp 모드만 허용한다. segment는 SAM을 CPU로 내리지만 register의 FP runner/scorer/refiner/GL context는 상주한다. op만 추가하면 CPU/Docker 경로가 실패한다.
1. worker 시작 시 순수 메시지 루프만 준비, ensure_detector/ensure_sam/ensure_fp에서 import/생성. torch조차 해당 op에서 불러온다. ready는 모델 준비 완료가 아니라 RPC loop 준비임을 명시.
2. 기존 segment/register/track/drop 계약 불변. ground/segment_box 추가. mode를 오버로딩하기보다 capabilities 집합과 device 설정으로 op별 허용; ground-only에서 register/track은 명시적 unsupported_op. 기존 mode 외부 응답은 호환 유지.
3. FP는 전역 tensor default를 변경하므로 detector/SAM 진입 때 CPU 기본 텐서 및 명시 device를 보장하고, ground→FP→ground 순서 회귀를 둔다. drop은 현재 active만 비우며 FP 메모리를 해제하지 않는다.
4. CPU에서 무조건 torch.cuda.synchronize/autocast('cuda')/peak 조회하지 않는다. GPU일 때만 실행. CPU ms도 동일 반환, peak_mb는 null/별도 cpu RSS.
5. offload/reset/empty_cache는 성공 분기뿐 아니라 finally에. 에러/OOM 시 predictor cache와 GPU tensor 참조까지 제거. 사용자의 FP tracking 중 모델 unload/worker kill 금지.
6. app perception_lock→backend RPC lock 순서를 유지하고 GPU 직렬화는 모든 새 호출에 명시적으로 연결. backend의 RLock은 프로세스 내부 직렬화이지 다른 CUDA 프로세스/렌더러의 GPU lock이 아니다. 측정 락은 운영 코드에 넣지 않는다.
7. 현재 180초 RPC timeout은 worker 연산을 취소하지 않는다. 작업 deadline·cancel token·worker generation을 연결하고 timeout 응답을 늦게 받아도 작업에 반영하지 않는다. 무응답 worker 복구는 안전하게 로봇을 멈춘 후 등록 상태를 무효화한다.

### 1.3 7.0GB 판정
- 7.0GB는 **합격 상한이지 달성 확정값이 아니다**. 1차의 DINO 피크 1~2GB/100~300ms는 추정으로 유지.
- 정의를 7 GiB=7168 MiB 또는 7000 MB 중 하나로 통일. device 전체 사용량(렌더·화면·다른 worker 포함)과 worker allocated/reserved를 별도 기록. max_memory_allocated는 현 코드에서 요청마다 reset되지 않는 누적 최고값이며 CUDA 컨텍스트/GL 메모리를 포함하지 않는다.
- G0 회사 GPU에서 box-only cold/warm, FP loaded→ground, ground→SAM→FP, 반복·예외 후, Panda 화면 활성 조건을 측정한다. 기본 box-only는 FP warmup OFF. FP/SAM 선택 조합은 독립 합격 또는 미지원으로 구분하고 7GiB 초과 시 resident 모델 정책을 줄인다. 집 ROCm 통과가 회사 NVIDIA 상한을 증명하지 않는다.

## 2. P0: G1 인터페이스·payload·설정 고정

다음은 구현 계약 제안이며 기존 코드에 구현됐다는 뜻이 아니다. G1(개발 단계)과 G1(휴머노이드)은 문서에서 구분한다.

~~~python
class Detector(Protocol):
    def detect(self, frame: Frame, queries: list[Query], *,
               deadline: float, cancel: CancelToken) -> DetectionBatch: ...
class Segmenter(Protocol):
    def segment_box(self, frame: Frame, box_xyxy: tuple[float,float,float,float], *,
                    deadline: float, cancel: CancelToken) -> MaskResult: ...
class Localizer(Protocol):
    def localize(self, frame: Frame, det: Detection, *, mask: MaskResult | None,
                 camera: CameraModel, object_spec: ObjectSpec) -> LocalizationResult: ...
~~~
- Frame: schema_version, source(sim_rgb/webcam_preview/recording), frame_id, generation, received_at, capture_at(null可), width/height, RGB uint8 HWC, depth_m float32 HW optional. 배열은 내부 IPC 전용, REST/DB에 넣지 않는다. image_origin=top_left, mirrored 여부 필수.
- CameraModel: calibration_id, calibrated_size, K, distortion, T_world_cam(카메라→세계, OpenCV x우/y하/z전방), table plane(n,d), workspace frame/단위(m), resize/crop/mirror 변환. sim frame의 K/T와 실물 camera K/T를 섞지 않는다.
- Query: query_id, canonical_class, normalized English phrase. Detection: detection_id, query_id, label, score[0,1], box_xyxy(원본 Frame 픽셀, 반열린 영역), source, frame_id, generation. 유한값/경계/면적 검증. phrase 중복 NMS는 같은 instance만 합치며 같은 범주 두 물체를 하나로 없애지 않는다.
- MaskResult: bool HW(내부), score, frame_id; HTTP 오버레이가 필요하면 RLE 등 별도 제한된 응답. 박스 SAM은 클릭용 select_candidate(click 필수)를 그대로 호출하지 않는다. SAM score+box overlap+component 정책을 고정한다.
- LocalizationResult: xyz_m(바닥 중심/모델 origin 중 기준 명시), yaw_rad nullable, T_world_obj optional, confidence/quality_flags, method, calibration_id, assumed_height_m, gt_assist=false. yaw 미관측인데 0을 정답처럼 쓰지 않는다. grasp에 필요한 모델 origin으로 명시 변환한다.
- RPC 기존 (ident,op,args) 유지: ground 입력 rgb+frame metadata+queries+thresholds, 반환 detections+frame_id+ms+peak_mb+model_revision. segment_box 입력 rgb+box_xyxy+frame_id, 반환 mask+sam_score+ms. 큰 mask/RGB를 DB·WS로 복사하지 않는다.
- REST POST /tasks는 202(task_id,state,version), Idempotency-Key 지원. GET /tasks/id, POST /tasks/id/confirm {candidate_id,frame_id,version}, POST /tasks/id/cancel, POST /cell/estop, POST /cell/reset-stop. 오래된 후보/다른 프레임은 409. 잘못된 지시 422, 소유권 충돌 409, DB 수락 실패 503.

설정 구조(필드 schema_version=1 공통):
- config/perception.yaml: detector{name,revision,device,dtype,thresholds,custom_kernel_policy}, segmenter{off|sam2}, localizer{plane|depth}, max_input_size, timeout, memory policy.
- config/objects.yaml: canonical class→height_m, footprint_m, symmetry, origin offset, grasp bounds/prior, allowed_grasp_modes. instance_id와 class_id 분리.
- config/vocab_ko_en.yaml: aliases→canonical class/English phrase. 미등록어·애매한 목적지는 needs_help, 조용한 추측 금지.
- config/cell.yaml: scene preset, workspace bounds, zones/slots, stage deadlines, retry_max, frame_max_age_s, DB path/retention. 지시 파서는 사전+고정 문법(“A는 왼쪽, B는 오른쪽”)으로 제한. 말/음성 입력이 필요하면 STT는 별도 범위이며 MVP는 텍스트 입력이라고 명시.
- config/camera_calib.json: 위 CameraModel과 실제 캡처/표시 변환·재투영 오차·생성 시각. 비밀/개인 경로 저장 금지. 모든 설정은 시작 시 타입/단위/필수값/미등록키 검증.

기존 클릭 경로는 유지하되 **새 셀 경로와 분리**한다. app.select_at 300줄은 SAM과 GT segmentation overlap으로 이름을 고르고, non-fp는 GT jitter estimate_pose를 사용한다. 이것을 새 DINO 결과에 이어 붙이면 gt_assist=False여도 인식 GT가 누출된다. 새 셀은 검출→canonical class→고정 물체 prior→localizer 경로만 사용한다. GT는 평가 join/점수 산출과 물리 엔진에만, 명령 대상 identity를 GT nearest/overlap으로 보정하면 [GT identity] 보조로 따로 분류한다. FP tracking auto-reacquire가 셀의 선택을 덮지 않도록 generation/owner 검사도 필요하다.

## 3. P0: /tasks와 기존 sim_worker의 실제 접합

### 3.1 현재 구조의 결함
- sim_worker는 FIFO 명령 하나를 꺼낸 뒤 pick_object/place_object를 동기로 완료한다. stop_event도 바깥 while에서만 본다. 따라서 같은 큐의 cancel/stop/shutdown은 **실행 중 동작을 끊지 못한다**.
- ControlAdapter._step_hook는 render/sleep만 한다. Controller._step는 physics step 뒤 hook 호출. 계획 IK 동안은 hook 호출도 없다.
- Runtime.wait는 status.last_command 한 개만 폴링한다. 다음 명령이 결과를 덮으면 완료 유실. wait timeout은 실행 취소가 아니므로 응답 실패 뒤 로봇이 움직일 수 있다.
- 현재 teleop/mode의 active_command/held_object 검사만으로는 perceiving/planning/queued 구간의 race를 막지 못한다. HTTP RLock을 작업 전체에 쥐면 cancel/status까지 막힌다.

### 3.2 최소 설계
1. CellExecutor 스레드 1개가 task/step만 진행하고, MuJoCo는 기존 sim_worker만 소유한다. executor→rt.send(pick/place) 구조 재사용. DB writer는 별도이며 로봇 executor 역할을 맡기지 않는다.
2. ControlArbiter의 짧은 mutex로 owner(task/manual/teleop/humanoid), epoch, command_inflight를 원자적으로 갱신. /click(place 포함), pick/place/reset/randomize/CAD rebuild, teleop mode 및 HTTP/WS update, humanoid mode 전환 모두 거친다. 휴머노이드는 별 로봇이지만 MVP에선 GPU/장면 우선권 때문에 모드 상호배제를 정책으로 명시한다.
3. 각 command에 cid, task_id, step_id, owner_epoch, deadline를 넣고 worker가 stale epoch/expired command를 실행 전 거부. accepted→running→completed 결과를 cid별 bounded store/별도 result queue로 전달. status.last_command는 UI용 호환 필드로만 유지.
4. FIFO 밖 mp.Event(cancel/estop)와 공유 cancel 대상/epoch를 둔다. Controller의 매 physics step 전(또는 hook 재배치), phase 경계, IK 반복 경계에 checkpoint. raise 제어 예외 후 arm target을 현재 qpos로 hold, 속도/제어 상태 안정화, 그리퍼는 무조건 열지 않음. held_object/attachment를 보존하고 recovery_required 표시. 시뮬 정지일 뿐 실제 하드웨어 안전기능 아님.
5. 취소 요청 즉시 terminal로 바꾸지 않고 cancel_requested/stop_requested 플래그와 stopping substate를 표시. worker 정지 ACK 이후 cancelled, E-stop/crash는 aborted. deadline 초과도 같은 정지 경로. ACK 전 owner 해제 금지. 비응답이면 watchdog가 해당 자식 PID만 종료하고 sim 재생성·수동 복구 후 재개, 자동 재시도 금지.
6. estop은 latch 유지: 새 task/teleop/manual movement 차단. 명시 reset-stop→복구 점검→새 epoch. 중단 직후 자동 home/reacquire/open 동작 금지.

### 3.3 상태와 지속성
- queued→perceiving→planning→executing, 물체 step마다 반복, 전부 완료→done. ambiguous/low_confidence→needs_help. confirm→프레임/장면 유효성 검증→perceiving 또는 planning. 재촬영/수동 개입 후에는 perceiving 필수.
- failed를 terminal에 추가: 재시도 소진/도달 불가/확인 timeout은 정상 실패이며 cancelled나 crash aborted와 구분. 부분 완료는 task.steps에 결과를 보존한다. executing 중 needs_help로 이동하려면 먼저 정지 ACK.
- state timeout은 monotonic deadline, DB에는 UTC timestamps+elapsed 기록. CPU cold load는 10초를 넘을 수 있으므로 1차 예시값을 공통 고정하지 말고 backend/device별 구성. needs_help 전체 대기 deadline도 별도.
- 시작 시 이전 boot_id의 비종료 작업(queued/needs_help 포함)을 aborted(reason=server_restart)로 원자 마감. 큐·확인·움직임 자동 재개 금지. 진행 중 물체는 시뮬 재시작과 함께 사라질 수 있음을 이력에 남김.
- SQLite: WAL, writer thread 전용 connection, bounded write queue, busy_timeout, schema migration, task+step+event+command 테이블. 변경 version CAS와 event_seq. HTTP 202는 task 수락 transaction commit ACK 뒤에만 반환. DB 쓰기 실패 시 실행 시작 금지, 실행 중 실패면 정지 요청. 읽기는 별도 read connection, 종료 시 flush/join. 단일 writer는 “단일 웹 프로세스” 조건에서만 보장되므로 다중 gunicorn worker 금지.
- WS cell builder를 next/active/builders 모두 추가하고 schema_version/event_seq/owner/stop_latched 제공. active 5Hz, idle 1Hz 등 하나로 고정. 추론·DB 쿼리를 WS tick에서 직접 수행하지 말고 cached snapshot 반환.
- 필수 단위/통합 시나리오: pick 중 cancel/estop, IK 중 deadline, queued cancel, 늦은 결과/중복 confirm, 동시에 manual/teleop/task, DB full/queue full, worker crash/restart, cancel 후 자동 place/home 방지. 무GPU mock으로 대부분 구현 가능.

## 4. P0/P1: 장면·GT 평가·평면 투영

### 4.1 장면 자산과 N≥100
- “물체 3종으로 N≥100 장면 불가”는 과도한 표현이다. pose/조명/배치로 100장 생성은 가능하나 의미·색·동일범주 방해물 다양성이 부족한 것이다.
- sim/env.reset은 x=.45~.66,y=±.23 범위와 물체 반경+25mm 간격을 사용하며 300회 실패 시 예외. 6~10개를 한 장에 전부 넣는 안은 부적합. 자산 종류 6~10개 중 장면당 2~4개를 먼저 쓰고 reachable/reject 사유를 기록한다.
- 현재 object_names 중복은 금지. 같은 범주 2개 시험에는 class_id와 고유 instance_id 분리 및 같은 mesh를 공유하는 복수 등록이 필요. primitive도 grasp bounds/collision/mass/색/이름 명세가 있어야 한다. 자산 생성물은 사전 오프라인 생성해 runtime registry가 파일을 새로 쓰지 않게 한다.
- 새 eval/grounding_bench.py를 권장. 기존 run_benchmark는 단일 대상·GT nearest-centroid click·FP pose 평가용으로 유지. 새 하네스는 frame→queries→detector→selection을 GT 없이 실행하고 GT visible seg bbox와 사후 매칭한다.
- manifest에 분리된 tuning/eval scene seeds, generator version, 자산 hash/라이선스, model revision, config hash, git dirty/source hash, thresholds, prompt templates, source/GT 보조를 고정한다. scene seed만 바꿔 동일 이미지/프롬프트가 유출되지 않게 장면 hash도 점검.
- N≥100은 독립 장면 수. 한 장에 여러 질문은 trial 수와 scene 수를 따로 보고하고 CI 상관성에 주의한다. 클래스/방해물/가림/애매/무대상 세트를 층화. 무검출·timeout·장면 생성 실패를 조용히 버리지 않으며 rejection 생성 수와 평가 누락 분모를 공개한다.
- 정답 IoU≥.5+목표 query/instance의 top-1 일치, GT bbox는 visible/amodal 중 정의 고정(visible 권장), 가림·화면 이탈 정책 기록. 위치 오차는 성공 검출 조건부와 전체 성공률을 같이 보고한다.
- 90/100 Wilson 95% CI 약 [82.6,94.5]는 맞음. **N≈200이면 CI 하한 목표가 자동 달성되는 것은 아님**. 90% 관측 시 180/200 하한은 약85%, 95%인 190/200은 약91%. 목표 하한과 기대 성공률을 먼저 고정해 N 산정. 점추정+CI 병기는 현재 MVP에 적절.

### 4.2 W2의 추가 누락: mirror·overlay·프레임 신선도
- tracker 303~304/374줄은 **cv2.flip(frame,1) 후 640×360**. 이후 손·자세 도형을 덧그린 frame을 preview로 전송한다(418~448줄). 단순 K 0.5배만 적용하면 좌우와 ArUco 검출/좌표계가 틀어질 수 있다.
- tracker 무변경 MVP는 서버가 JPEG를 unflip하여 보정/검출/위치 계산, UI 박스는 역변환한다. calibration도 같은 unflip·resize·crop 경로를 사용한다. 손/도형 없는 정적 장면을 전제하고, 오염 없는 raw preview는 후속 개선으로 분리한다. 왜곡 파라미터는 영상 좌표와 같은 기준이어야 한다.
- teleop preview 저장소는 JPEG+seq뿐이며 capture_at 없다. 서버 get_latest_preview()에 raw/seq/received_at를 같은 mutex로 복사해 제공(웹 파일만 변경). 신선도는 서버 수신 시간 기준이며 실제 촬영시간을 보증 못한다. tracker 무변경으로 capture_at 계약을 달성했다고 쓰지 않는다.
- frame/K/T/calibration_id/generation을 하나의 immutable snapshot으로 고정. 현재 sim.frame() 복사와 status metadata 복사는 원자적 한 묶음이 아니므로 동기 capture 명령의 결과에 frame_seq/K/T를 결합하는 개선 필요. 정적 셀에서는 움직임 금지 후 capture ACK로 보완 가능.

### 4.3 투영·높이·yaw·트윈 구현
- cv2.undistortPoints로 (u,v)→정규화 광선 q. c=T_world_cam[:3,3], r=R_world_cam*q. plane n·X+d=0에서 가정 feature 높이 h_ref를 반영한 평면 n·X+d=h_ref에 대해 t=(h_ref-d-n·c)/(n·r), X=c+t*r. |n·r|≈0, t≤0, workspace 밖은 거부. 바닥 중심 추정으로 변환 후 모델 bounds origin offset을 적용.
- bbox center는 기본 h_ref≈height/2의 휴리스틱, bottom-center는 높이0인 “앞쪽 가장자리”라 중심 보정 footprint가 별도로 필요. 두 방식 혼용 금지, 방법별 bias를 보고한다. mask pixel이 전부 같은 높이에 있다는 가정도 틀리므로 plane inverse-PCA yaw는 근사이며 yaw quality/unknown 필요. 원통 yaw 제외, 비대칭 물체 yaw 오차 별도 평가.
- 60mm/45°→30mm는 h_ref=h/2 가정의 예시이지 보정 보증치 아님. 시뮬 GT pose xy와 메쉬 중심/바닥 origin 불일치부터 정규화한다. 실물은 알려진 바닥 중심 격자 배치와 독립 측정점으로 평가(보정에 쓴 marker 오차만 보고 끝내지 않음).
- snapshot twin은 실물 desk 좌표→시뮬 world의 T_sim_desk 및 scale=1을 설정, bounds/reachability 검사 후 셀 장면에서 한 번 배치. 현재 sim_worker에는 batch set_object_poses 명령이 없으므로 새 명령·idle/owner 검사·scene generation 증가·settle/ACK가 필요. 이것이 W2 누락 공수다.
- zone은 단순 좌/우 xy 외에 slot capacity·footprint·occupied 정책 필요. MVP는 목적지 2개 표시 구역+정해진 단층 슬롯으로 한정. 실제 벽 있는 bin/높이 적재는 경로/충돌/놓기 높이 수정이 필요해 후속으로 둔다.
- 계획의 “위에서 집기+기존 grasp 재사용”은 모순: plan_grasps는 높이>70mm이면 side 우선. MVP strict top-down 필터를 넣고 허용 물체 높이/폭을 제한하거나 기존 top/side 자동 선택이라고 문구를 고친다. 컵/병 top-down 가능 여부는 실측 전 확정하지 않는다.
- gt_assist OFF도 물리 충돌 엔진의 실제 geometry/contact 사용까지 없앤다는 뜻은 아니다. 알려진 셀 자산 기반 충돌검사와 GT perception/pose 보조를 구분해 설명한다.

## 5. 일정·집 PC 분리·라이선스

### 5.1 일정
- v2 합계 9.5~14 인일은 인터페이스/정지 큐/GT 분리까지 이미 해결됐다는 낙관 추정이다. 3페어 병렬이면 2~3주 달력은 가능하지만 카메라·ROCm/GPU·회귀·Codex 한도에 여유가 없다. 단독 2~3주는 빠듯하다.
- 권장: 계약/G0 1~2일, 인식/장면/평가 4~6일, W2 3~4일, K 5~7일, 통합/회귀/영상/Docker 2~3일의 작업량. 병렬의 총합을 달력 일정으로 합산하지 말 것. 3페어 기준 10~15 작업일+2~3일 예비를 명시한다.
- 병렬 시작: G는 detector mock·자산 생성기, W는 순수 localizer+보정, K는 fake command executor+DB/FSM. 첫 0.5~1일에 타입/오류코드/frame·owner epoch 계약부터 합의.
- 공유 파일 순서: E의 perception_stub 상태 인계→G가 worker 변경, W가 sim_worker snapshot/배치 명령→K가 arbiter/cancel/result queue→app/realtime 결선→UI 한 명. sim/control.py·sim/grasp.py·sim/env.py·sim/scene_builder.py·web/teleop.py·web/humanoid.py도 공유 파일 목록에 추가. localize 소유자는 G 또는 W 중 한 명으로 정한다.
- 기존 S/T/E 미완 평가는 r5 필수 회귀와 신규 범위를 분리. P1c 추가 투자는 중단 상태 유지하되 OFF baseline이 비교 기준. 전체 pytest·회귀/통계 집계는 TEAM_R3 측정 락 준수.

### 5.2 집 PC
- 이번 읽은 저장소/패키지는 회사 /home/user 환경이다. 집 /home/my 환경에서 ROCm 지원/버전을 이번 검토로 확인한 것이 아니다.
- **rp_constraints.txt는 torch==2.14.0+cu130/torchvision==0.29.0+cu130으로 ROCm/CPU 설치에 그대로 쓸 수 없다.** 공통 pins(numpy/웹/transformers)와 backend별 cuda/rocm/cpu overlay를 분리한다. ROCm torch2.14 wheel 존재·Python3.12·RX7600 gfx1102·WSL·드라이버 조합을 G0에서 공식 지원표와 실제 wheel로 먼저 확인한다. Linux/Windows 표 등재나 타 GPU 이슈 close만으로 WSL 지원 확정 금지.
- 기존 집 env/skip-worktree 파일 보존. ROCm 시험은 별도 env에서 0.5~1일 timebox, 실패 시 CPU+mock으로 계속 진행한다. HSA_ENABLE_DXG_DETECTION=1만으로 지원이 보증되는 것은 아니다. FP(nvdiffrast/pytorch3d CUDA)는 집 G0 대상 제외.
- GPU 없이 가능한 것: DTO/config/parser/localizer 단위, 자산·시드 manifest, mock detector 기반 FSM/DB/취소/소유권, UI, CPU Docker. MuJoCo 렌더는 소프트웨어/헤드리스 가능성 확인 후 별도 실행 검증하며 이번 검토에서는 실행하지 않았다.
- 회사만 확정할 것: NVIDIA VRAM/지연, SAM/FP 회귀, E 미완 평가, 실카메라/회사 녹화본. 녹화에 보정판이 없으면 위치 오차 미측정이라는 기존 합의 유지.

### 5.3 라이선스·과한 범위
- HF IDEA-Research/grounding-dino-tiny README의 license: apache-2.0을 이번에 직접 확인했다. 최종 가중치 revision의 카드/라이선스 파일·가중치 hash를 THIRD_PARTY_NOTICES에 남기는 G0 게이트는 유지. 카드 tag 확인만으로 학습 데이터 권리까지 보증하지 않는다.
- 사용하지 않는 OWLv2/Florence/MobileSAM/EfficientSAM 라이선스를 지금 전부 확정할 필요는 없다. 도입 시 코드·가중치·dependency·remote-code revision을 각각 확인. YCB 전체를 단일 허가로 취급하지 말고 항목별 출처 확인. 직접 만든 primitive로 시작하면 자산 법적 비용을 줄인다.
- SAM·MuJoCo 로봇/mesh·texture·Docker 배포 dependency도 notices 범위다. FP 없는 이미지에서조차 worker의 startup FP import가 남지 않도록 smoke test 필요. 모델은 git에 커밋하지 않고 checksum 검증 downloader 또는 사용자 cache mount.
- 빠진 것: API 입력 길이/유한값·NaN 검증, task/DB queue 한도·보존, 로컬/LAN 공개 시 origin/CSRF/접근 정책, calibration 유효성, frame stale 판정, bin capacity, failed 종료 상태. 대시보드·CI 계산은 DB snapshot 기반 단순 구현으로 제한한다.
- 과한 것: 새 경량 SAM·다중 detector 비교, raw still 프로토콜·연속 추적, 실제 하드웨어 안전/원격제어, 6D/LLM/STT, 벽 있는 다층 bin. MVP에서 제외 유지.

## 6. R5-O와의 왕복·이견 해소
- R5-O(task ZTHqcfHTVxg0iTo5)에 최초 질의→회신 수신: transformers 버전은 1차 미확정, VRAM/지연은 추정, FIFO cancel의 중단 가능성은 1차 미검증임을 확인했다.
- 이어 실제 코드 근거로 out-of-band stop/ACK, last_command 유실, GT identity 누출, numpy 중복 metadata, ROCm pin 분리, top-down/side 모순, mirror/overlay 누락을 전달했다. 회신 결과는 아래에 덧붙인다.
- 1차 큰 방향(worker 통합·lazy import·snapshot MVP·평면 높이 보정·독립 seed·GT OFF)은 유지한다. 다만 “cancel API/락만 추가”, “K 절반은 큐 재사용으로 해결”, “3종이면 100장 생성 불가”, “N≈200이면 원하는 CI 하한 충족”으로 해석하면 구현/통계상 틀리므로 위 조건으로 정정한다.

## 7. v3 반영 체크리스트
1. [P0] transformers 후보4.57.6/대안4.45.2 메타데이터 근거, 실제 설치/ABI 미검증과 numpy 중복 확인, backend별 constraints 분리.
2. [P0] Detector/Segmenter/Localizer DTO·frame/mirror/calibration·오류 계약 및 G/W 소유자 확정.
3. [P0] worker lazy imports/capabilities/CPU 분기/finally offload/FP 전역 tensor default 회귀.
4. [P0] 7GiB 정의·device 전체와 process별 측정 분리, box-only FP warmup OFF, optional 조합 별도 합격.
5. [P0] GT overlap identity 및 GT jitter 경로를 새 E2E에서 분리, 고정 class prior/instance 선택 계약.
6. [P0] 단일 executor+worker 명령 epoch+cid 결과저장, FIFO 밖 stop/cancel, step/IK checkpoint, ACK 전 owner 유지.
7. [P0] stop latch/hold/recovery, failed 상태·재확인·deadline·restart abort 범위, DB commit ACK와 단일 process 조건.
8. [P0] preview mirror/unflip·overlay·received_at 한계, immutable capture+metadata, snapshot twin batch 배치 명령.
9. [P1] 높이/feature anchor·origin/좌표 변환, yaw unknown·대칭 정책, strict top 또는 side 허용 문구.
10. [P1] 장면당 물체 수/instance 등록·seed/hash 분리·평가 분모/무대상·가림·CI 기준, 자산/가중치 notices.
11. [P1] 목적지 단층 slot/capacity, 공유 파일 확대·변경 순서, 2~3주 병렬 조건과 예비일.
12. [P1] 집 ROCm timebox/지원표+wheel 검증, CPU+mock 대체 및 회사 측정 잔여 항목 분리.

재개 지점: 부모가 본 P0를 v3에 반영한 뒤 계약/G0부터 착수. 본 검토는 구현 착수 승인(PASS)이나 설치/성능 검증 결과가 아니다.

## 8. R5-O 최종 회신과 합의 확정
- R5-O가 sim_worker/app/tracker/grasp와 numpy dist-info를 직접 재확인하고 위 핵심 P0를 전부 수용했다. 별도 stop Event+checkpoint+ACK/epoch/cid 결과 보관, 새 E2E의 GT identity 분리, transformers 후보와 위험 정정, YAML 유지/ROCm overlay, strict top 정책, preview unflip+UI 역변환+수신시각 구분에 이견 없음.
- 추가 합의: q65/640 보정 손실을 줄이려면 트래커를 정지하고 단독 보정 도구에서 1280 원본 촬영. 카메라 단일 소유를 지키며 실제 캡처 모드/FOV/crop 동일 확인→K preview 스케일→unflip/좌표 변환을 검증하고 독립 격자점으로 평가한다. 원본으로 보정했다고 preview의 위치 정확도가 보장되는 것은 아니다.
- numpy 중복 메타데이터는 임의 삭제하지 않고 진단 뒤 깨끗한 검증 env 복구. strict top 경계는 코드 그대로 h<=70mm, side 우선은 h>70mm이다.

## 9. 직접 확인한 외부 메타데이터 출처
- https://pypi.org/pypi/transformers/4.57.6/json (requires_python/requires_dist)
- https://pypi.org/pypi/transformers/4.45.2/json (requires_python/requires_dist)
- https://huggingface.co/IDEA-Research/grounding-dino-tiny/raw/main/README.md (license apache-2.0, 모델 사용 예시)
확인일 2026-11-10. 현재 main 카드의 확인이며 특정 가중치 revision의 법적/실행 검증을 대신하지 않는다.
