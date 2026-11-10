# r5 계약 v1.1 (2026-11-10)

> **v1.1: Claude 설계 대행(D-CT), Codex(I-CT) 확인 대기.** v1(I-CT 작성) 본문을 유지하고 V-CT 지적 C1~C6, 현재 코드 근거 표, 사용자 확정(2026-11-10), G0 측정을 반영했다. 이 문서는 설계 문서이며 코드(perception/interfaces.py·상태 머신·tests)는 I-CT 몫으로 남긴다. I-CT 확인 전까지 v1.1의 신규 숫자·규칙은 "제안"이다.

| 버전 | 일시(KST) | 작성 | 내용 |
|-|-|-|-|
| v1 | 11-10 21:59 | I-CT(Codex) | 1~7장 초안, 현재 근거 표 미완성 |
| v1.1 | 11-10 | D-CT(Claude, 대행) | C1(4.2) C2(4.4) C3(3.1) C4(4.3) C5(4.6) C6(4.7) 반영, 4.9 현재 근거 표 완성(파일:라인), 2.3 G0 결과로 device·perceiving deadline 조정, 5.3·7장 사용자 확정 반영, 오류 코드 3종 추가(STALE_EPOCH, OWNER_CONFLICT, RECOVERY_CHECK_FAILED) |
| v1.1 재검토1 | 11-10 | D-CT(Claude, 대행) | V-CT 재검토 V1(4.6-4 watchdog 상한·종료 실패), V2(4.6-5 draining owner 5 s), V3(4.7 outstanding·재생성 q_hold·DB 영구 실패), V4(4.4 held_object 시 /tasks 409) 반영 |

범위: 계획 v3 P0-2/5/6/7/8 및 worker P0-3/4 접점. 아래는 신규 구현의 규범이며 현재 HTTP/worker 동작을 바꿨다는 뜻이 아니다. 이 변경에서는 공유 운영 코드를 읽기만 한다. [시뮬인식] 기본 GT 보조 없음. [실물웹캠] 인식·위치만, 집기는 시뮬레이션. 카메라/회사 GPU 실측은 미실시.

## 1. 소유 경계와 DTO
G: Detector/Segmenter 어댑터·worker RPC·고정 클래스 사전. W2: 불변 Frame/CameraModel·보정·unflip·Localizer. K: 작업/후보 선택·epoch·단일 executor·DB·로봇 소유. 공동 DTO 변경은 이 문서와 interfaces.py 테스트를 먼저 함께 변경한다. G1 인식과 휴머노이드 G1은 별개다.
perception/interfaces.py가 직렬화 형식의 기준이다. stdlib dataclass만 import하며 이미지/모델 import 금지. schema_version=1. FrameMeta는 frame_id, generation, source, capture_at(UTC Unix 초, 모르면 null), received_at(서버 UTC Unix 초), mirrored, calibration_id(null 허용), width/height, image_origin=top_left, coordinate_frame=image, unit=px, overlay_present를 고정한다. 수신 시각으로 촬영 시각을 조작하지 않는다. Frame은 bytes RGB uint8 HWC 및 선택 depth_m(내부 IPC)로 immutable 소유 복사, REST/DB/WS에는 메타데이터만 둔다.
Detection: detection_id/query_id/canonical_class/score/box_xyxy + 원본 FrameMeta. 박스는 픽셀 경계 좌표 [x1,y1,x2,y2), 0<=x1<x2<=width, 유한값. MaskResult: 동일 frame, RLE counts(0부터 교대, row-major), score, box; mask 크기는 width*height. Localization: xyz_m=책상 위 물체 바닥 중심(world), yaw_rad=null은 미관측, calibration_id/height/method/quality_flags, gt_assist=false. 모델 origin 변환은 object_spec의 고정 offset으로만 한다. 좌표 world(m), OpenCV camera(x우/y하/z전방), yaw rad. CameraModel은 K/distortion/T_world_cam/table plane/보정 영상 크기/crop/FOV/mode 및 검증 오차를 가진다. 카메라/프레임 보정 id 불일치는 CALIBRATION_MISMATCH.
오류: INVALID_INPUT, UNSUPPORTED_OP, MODEL_UNAVAILABLE, NO_DETECTION, AMBIGUOUS, STALE_FRAME, CALIBRATION_MISMATCH, DEADLINE_EXCEEDED, CANCELLED, OUT_OF_MEMORY, INTERNAL_ERROR, **STALE_EPOCH**(명령 owner_epoch < 현재 epoch, 이동 없이 거부), **OWNER_CONFLICT**(arbiter 소유 충돌, HTTP 409), **RECOVERY_CHECK_FAILED**(4.7 조건 불충족, HTTP 409). 실패는 DTO error 필드로 전달하며 성공값으로 위장하지 않는다. Protocol은 deadline(현재 프로세스 monotonic 초)과 CancelToken을 받는다. monotonic 값은 다른 부팅/호스트로 이식 금지.

## 2. worker RPC
### 2.1 envelope·op
기존 (request_id, op, args) / (request_id, ok, result) envelope 유지. ground args={schema_version:1,frame:FrameMeta,rgb:bytes,queries:[{query_id,canonical_class,phrase}],box_threshold:0.35,text_threshold:0.25,deadline:monotonic,cancel_token,owner_epoch}; result={frame:FrameMeta,detections:[Detection],error:null,ms,model_revision,device,peak_mb}. segment_box args={schema_version:1,frame,rgb,box_xyxy,deadline,cancel_token,owner_epoch}; result={mask:MaskResult,error:null,ms,model_revision,device,peak_mb}. 이미지/마스크는 IPC 내부 전용, HTTP에는 opaque frame_id만 받는다. stale epoch/frame 결과는 실행에 사용하지 않는다. 임계값은 유효 범위 [0,1] 검증.
capabilities op는 모델을 로드하지 않고 {schema_version:1,ops:[ground,segment_box],device:cpu|cuda|rocm,device_name,torch_version,accel_version,models:{name:{revision,available,loaded,reason}},segmenter:off|sam2,localizer:plane|depth,fp_available:false} 반환(신규 필드 근거는 2.3). ready는 메시지 루프 준비일 뿐 모델 로드 완료가 아니다. 미지원 op는 UNSUPPORTED_OP. 기존 segment/register/track/drop 호환 유지.

### 2.2 수명·메모리
ensure_detector/ensure_sam/ensure_fp에서만 lazy import. box-only는 FP warmup OFF, SAM 미설치여도 ground 동작. CPU 분기에는 cuda synchronize/autocast/메모리 API 없음(peak_mb=null). FP 이후 CPU tensor default 복원 및 명시 device, ground→FP→ground 회귀 필수. 모든 성공/실패/OOM/cancel 경로 finally에서 일시 tensor 참조·predictor cache 해제/offload/empty_cache(지원 GPU만, rocm 포함), 활동 중 FP 추적 강제 unload 금지. app perception_lock→RPC lock 순서, 기존 worker 한 개 직렬화. 운영 코드에 측정 flock 금지.
VRAM 상한은 장치 전체 peak 7 GiB=7168 MiB. process allocated/reserved, device-wide used, 샘플 간격·cold/warm·렌더 동시 여부를 각각 기록. max_memory_allocated는 요청 직전 reset하고 전후 synchronize하되 device 전체/GL/context를 포함하지 않는다고 명시. CPU/AMD 집 측정은 NVIDIA 회사 합격 증거가 아니다. 미측정은 null, 0으로 합격 처리 금지. 박스만/선택 SAM/FP 조합 별도 판정.

### 2.3 G0 결과 반영: device 값·perceiving deadline (v1.1)
G0 원자료(부모 측정, [시뮬인식], GT 보조 없음, bench/g0/rocm_gpu.json·cpu.json, Grounding DINO tiny rev a2bb814, 640×360 시뮬 RGB 1장, warmup 2·n 20):
| 경로 | 로드 | 첫 추론 | warm p50/p95 | 메모리 |
|-|-|-|-|-|
| 집 RX 7600 ROCm(torch 2.14.0+rocm10.1.0, HIP 7.16) | 18.3 s | 21.1 s | 299 / 306 ms | process max_allocated 1016 MiB, reserved 1098 MiB, device used 샘플 peak 3721 MiB(전 2332, 장치 전체·Windows 포함) |
| 집 CPU 4스레드(torch 2.14.0+cpu, interop 1) | 21.0 s | 3.5 s | 3349 / 3754 ms | null |

device 값 결정:
- 값 집합은 cpu|cuda|rocm 유지. 판정은 torch 문자열이 아니라 빌드로 한다: torch.version.hip이 있고 가속기가 보이면 rocm, torch.version.cuda가 있고 보이면 cuda, 그 외 cpu. ROCm torch는 내부 device 문자열이 "cuda"이므로 torch.device("cuda")를 그대로 보고하면 안 된다(회사 NVIDIA 수치와 섞임 방지).
- rocm도 torch.cuda.* 메모리/동기화 API를 쓴다(G0에서 max_memory_allocated 정상 반환). 따라서 "CPU 분기에만 메모리 API 없음(peak_mb=null)", rocm·cuda는 peak_mb 기록. 결과 DTO의 device에도 같은 값을 넣고 accel_version(hip 또는 cuda 버전)·device_name을 함께 기록한다.
- ROCm on WSL은 HSA_ENABLE_DXG_DETECTION=1과 LD_LIBRARY_PATH=$CONDA_PREFIX/lib가 필요했다. 운영 코드에 하드코딩하지 않고 실행 스크립트/env 문서가 설정한다. hip 빌드인데 장치가 안 보이면 device=cpu로 조용히 떨어지지 않고 models.*.available=false, reason="rocm_device_unavailable(HSA_ENABLE_DXG_DETECTION?)"로 보고하며, CPU 대체는 설정(RP_PERCEPTION_DEVICE=cpu)으로만 한다.

perceiving deadline 조정(v1 단일 180 s → cold/warm 분리):
- cold(해당 worker 프로세스에서 모델 미로드, 또는 같은 device·입력 해상도에서 첫 추론): **180 s 유지**. 근거: ROCm cold = 로드 18.3+첫 추론 21.1 ≈ 39 s, CPU cold ≈ 21.0+3.5 ≈ 25 s(질의 1회). 180 s는 ROCm cold의 약 4.6배로 SAM2 선택 로드(미측정)와 회사 NVIDIA 미측정분 여유를 포함한다.
- warm: **30 s**(device 공통 기본). 근거: CPU warm p95 3.75 s × 질의 최대 4회 ≈ 15 s의 2배. ROCm warm p95 0.31 s에는 과하지만, 해상도가 바뀌면 첫 추론이 다시 21 s 수준일 수 있어(G0의 21 s가 커널 준비로 추정, 해상도 변경 재현은 미측정) ROCm도 30 s로 둔다. 시뮬 카메라 기본은 640×480(web/app.py:16)으로 G0 입력 640×360과 다르다.
- cold/warm 판정은 capabilities.models.*.loaded와 executor가 기억한 (device, width, height) 집합으로 하며, 판정 불가는 cold. device별 양수 override는 config 검증 후만.
- RPC deadline = min(perceiving 잔여, 요청별 상한). 현 perception_stub.py:108의 고정 180 s는 이 규칙으로 대체 대상.
- 회사 NVIDIA 수치는 미측정이므로 cuda는 위 기본값을 잠정 적용하고 W2/G1 회사 측정 뒤 재확정.

## 3. GT identity 방화벽
현재 코드 근거(이번 변경 전): web/app.py:283 RGB/depth/GT seg/objects 수집; :299 stub mask=GT segmentation; :300-303 GT overlap 최대로 name 선택·GT pose 추출; :305 이름으로 GT registry mesh 선택; :307 gt_pose로 stub estimate; :309/316 GT mask·pose 오차 평가; :337 gt_assist 기본 true. web/perception_stub.py:8-10 GT pose+seed 7 jitter. web/sim_worker.py:149/152 GT name registry bounds/object_pose_fn; :151 기본 GT assist true. gt_assist=false만으로 identity 누출은 없어지지 않는다.
새 E2E는 select_at/estimate_pose/objects/GT seg 호출 금지. 고정 vocab_ko_en.yaml alias→canonical_class/영문 phrase, objects.yaml class→height/footprint/symmetry/origin/grasp prior, 버전·해시를 평가 시작 전에 동결. 미등록·모호 지시는 needs_help. 검출 instance_id는 frame_id+query_id+검출 index에서 만들며 simulator body name과 같게 만들지 않는다. 후보는 동일 클래스에서 score 내림차순, tie는 x1,y1,detection_id 순. 복수 후보면 사용자 confirm(candidate_id,frame_id,version), 자동 평가는 사전에 선언한 top-score 정책만 허용. GT nearest/overlap으로 재선택 금지. class NMS는 동일 물체 중복만 제거, 같은 클래스 여러 물체 보존.
실행은 관측 좌표+고정 prior로 접근한다. sim body identity가 필요한 부착/물리 로직은 접촉 기반으로만 하거나 별도 [시뮬GT][GT identity 보조] 실험으로 분리. 정답은 추론 완료 후 별도 evaluator에서만 join하여 점수 산출, 제어 루프 역유입 금지. 측정에 gt_assist와 identity_assist 각각 저장. GT jitter/stub 성공을 인식 E2E 성공으로 보고하지 않는다.

### 3.1 legacy 선택/추적과 셀 선택의 분리 (C3)
현재: track_loop(app.py:106-147)는 rt.selected/rt.generation만 보고 non-fp에서 GT pose+jitter(app.py:129)를 rt.estimate에 쓴다(:131-133). pause 조건은 phase/held_object/active_command뿐(:118)이라 queued/perceiving/planning 중엔 계속 돈다. select_at(app.py:293-317)은 성공 시 generation+1 후 rt.selected/estimate/mask를 교체(:313-314)하고, reacquire_after(:318-330)는 place 뒤 자동으로 select_at을 부른다.
규칙:
1. 셀 후보·Localization은 rt.selected/rt.estimate/rt.mask를 쓰지도 읽지도 않는다. 셀 전용 슬롯 cell_candidate={task_id,step_id,candidate_id,frame_id,cell_generation,version,localization}에만 저장하고, pick/place 명령 payload는 이 슬롯에서만 만든다.
2. owner: legacy 선택 상태(rt.selected 등)의 쓰기 권한은 arbiter owner.kind ∈ {none, manual}일 때만 있다. 셀이 소유를 획득하는 transaction 안에서 arbiter가 rt.drop()과 같은 효과(generation+1, selected/estimate/mask=None)를 적용한다. 진행 중이던 track_loop 결과는 기존 generation 비교(app.py:123-124, :132)로 버려진다.
3. owner.kind=cell(모든 비종결 상태와 stopping 포함) 동안: /click(select_at)·reacquire_after는 OWNER_CONFLICT 409, track_loop는 perception_lock을 잡기 전 owner를 확인해 건너뛴다(추론 RPC도 호출 금지). /robot/pick의 rt.estimate 경로도 409.
4. cell_generation은 셀 전용 단조 증가 카운터(재촬영·confirm·재인식마다 +1). 셀 결과 commit은 (task_id, step_id, cell_generation, owner_epoch) 모두 일치할 때만 하고 불일치는 폐기·이벤트 기록. rt.generation과 공유하지 않는다.
5. 셀 terminal 후 owner 해제 시 legacy 선택은 비어 있는 상태로 시작(이전 셀 후보를 legacy로 넘기지 않음). 자동 reacquire 금지는 셀 경로 전체에 적용되며 legacy 수동 place의 reacquire_after는 [시뮬GT] 기능으로 유지한다.
테스트(I-CT): 셀 owner 중 track_loop가 estimate를 1회도 쓰지 않음, select_at 409, generation 경합 시 셀 슬롯 불변.

## 4. 명령·정지·지속성
### 4.1 실행 구조
단일 웹 프로세스, CellExecutor 스레드 1개, MuJoCo 소유 sim_worker 1개, SQLite writer 1개. gunicorn multiworker/reloader 중복 실행 금지. ControlArbiter 짧은 mutex로 owner/task/epoch/inflight 원자 변경; manual/click place/pick/place/reset/randomize/CAD/teleop HTTP·WS/humanoid mode도 같은 arbiter. 추론/planning/queued에서도 소유 유지, 긴 HTTP lock으로 stop/status 차단 금지. 로봇 이동 명령의 inflight는 셀 전체에서 최대 1개.

### 4.2 명령·ACK·epoch (C1)
명령={command_id UUID(전체 32hex),boot_id,task_id,step_id,owner_epoch,op,payload,deadline}. worker는 dispatch 직전·모든 checkpoint에서 epoch/deadline/cancel/stop 검증. accepted/running/terminal ACK는 command_id별 저장, 중복 id+동일 payload는 기존 결과, 다른 payload면 409. epoch 불일치·기한 경과는 이동 없이 거부(STALE_EPOCH/DEADLINE_EXCEEDED 터미널 ACK). result store는 DB 보존, in-memory bounded cache는 미ACK/진행 항목을 evict하지 않으며 full이면 수락 거부.
epoch 규칙:
- **epoch 증가 주체는 웹 프로세스의 ControlArbiter 한 곳뿐**이다. sim_worker·perception worker·HTTP 핸들러·CellExecutor는 epoch를 읽기만 한다. 현재 epoch는 arbiter mutex 안에서 DB cell.epoch(CAS)와 공유 슬롯(mp.Value 'q', FIFO 밖)에 함께 쓴다.
- 증가 시점: owner 획득/해제, cancel 수락, estop, executing deadline, **ACK timeout(아래)**, reset-stop 성공, 새 boot. 한 task의 연속 명령은 이 사건이 없으면 같은 epoch를 쓴다.
- ACK timeout 처리: 현재 Runtime.wait(app.py:158-164)는 시간 초과 시 {"error":"command timeout"}만 돌려주고 command_q의 명령은 그대로 남아 나중에 실행될 수 있다. 신규 규칙에서 accepted ACK가 송신 후 2 s 안에 없거나 terminal ACK가 명령 deadline까지 없으면 대기 측은 직접 아무것도 바꾸지 않고 arbiter.expire(command_id)를 호출한다. expire는 mutex 안에서 ① 공유 슬롯 epoch+1과 해당 cid 취소 플래그를 **먼저** 게시(안전 우선, 멱등) ② 같은 값을 DB에 commit(event command_expired) ③ task는 상태·owner 유지, 이동 명령이었으면 stopping=true.
- 늦게 꺼내진 명령: worker가 dispatch 직전 owner_epoch < 공유 epoch를 보고 이동 없이 STALE_EPOCH 터미널 ACK. 이미 실행 중이었다면 다음 checkpoint에서 hold 후 stopped ACK(4.3).
- expire 후 owner 해제 조건은 그 cid의 터미널 ACK(STALE_EPOCH/stopped/완료) 수신 + DB commit ACK. stop_ack_timeout(4.6) 안에 없으면 watchdog 경로. DB commit 실패 시 stop_latched·recovery_required=true, owner 유지.
- 자동 재전송·재시도 없음. 같은 의도는 새 epoch·새 command_id로 사람이 다시 요청한다.

### 4.3 정지 전달·checkpoint·지연 상한 (C4)
FIFO 밖 mp.Event+대상 command/epoch 공유 슬롯으로 stop/cancel 전달. 취소/timeout은 요청 플래그일 뿐 terminal 아님. checkpoint: perception RPC 전후, IK 호출 경계·경로 샘플·phase 전환, 매 physics step 이전(Controller._step→step_hook, sim/control.py:72-81), gripper 및 place/home 직전. 정지 시 현재 qpos를 ctrl에 써서 hold, 목표/속도 안정화, 그리퍼 ctrl·held_object·weld 보존(open_gripper는 detach를 부르므로 control.py:142 정지 경로 호출 금지). stop latch는 신규 이동 전부 차단.
IK 내부 checkpoint: solve_ik(sim/ik.py:57, max_iters 160×restarts 10=최대 1600 반복)와 choose_grasp(sim/grasp.py:113-152)는 step_hook을 부르지 않는다. v1.1은 **sim/ik.py 내부 수정 없이 호출 경계 checkpoint를 필수**로 한다: control.py:110(move_cartesian 경유점마다), :260, :301, :304(place yaw 후보마다), grasp.py:129/132/147/151(seed·후보마다). 내부 콜백 추가 여부는 I-CT 판단(추가 시 상한 강화).
정지 지연 정의: stop/cancel 공유 슬롯 set 시각 → worker가 hold ctrl을 쓴 시각(monotonic, worker 기록).
집 PC 측정(D-CT, 11-10, robot_percept env, mustard 장면, flock 내, load 0.67, [시뮬GT] 타이밍만):
| 구간 | 측정 |
|-|-|
| solve_ik 도달 불가(1600 반복 소진) | 339 / 343 / 383 / 370 / 385 ms (N=5, max 385) |
| solve_ik 도달 가능 | p50 1.0 ms, max 2.4 ms (N=20) |
| choose_grasp(mustard) | 8.0~8.7 ms (N=3) |
| physics step(_step, hook 없음) | p50 0.038 ms, max 0.156 ms (N=200) |
상한(집 PC 기준, 합격 판정용):
- IK·grasp 계획 구간: **≤ 500 ms**(호출 1회 최대 385 ms + 30% 여유). 내부 콜백(반복 32회마다 등)을 넣으면 ≤ 50 ms.
- 이동·gripper·home physics 구간: **≤ 100 ms**(step 0.16 ms + render_hook 1회(35 step마다, sim_worker.py:20) + 실시간 pacing sleep. render 시간은 미측정이므로 구현 시 측정해 이 값을 확정하거나 낮춘다).
- 회사 PC 수치는 미측정. 다른 PC에서 상한을 넘으면 내부 콜백 추가가 조건.
테스트(I-CT): solve_ik를 0.4 s sleep 가짜로 바꾼 상태에서 stop→hold ≤ 0.5 s+5 ms, 위 호출 지점 각각의 checkpoint 호출 수 검증, hold 이후 ctrl·qpos 변화 없음.

### 4.4 자동 open/home 적용 범위와 held_object (C2)
현재: pick 실패 시 자동 open_gripper(sim_worker.py:154-155), place 뒤 자동 return_home(:164-168), place 성공 후 held_object=None(:163).
범위 규칙:
- "자동 open/home/reacquire 금지"는 **stop/cancel/estop/deadline 요청이 관측된 뒤의 경로**(정지 경로)에만 적용한다. 정지 경로에서는 그리퍼를 움직이지 않고 home으로 가지 않으며 다시 인식하지 않는다.
- 정상 경로(정지 요청 없음)에서 계획된 동작은 허용하되 각각 명시 phase와 직전 checkpoint를 둔다:
  - pick 실패 open: phase pick.fail_open. 직전 checkpoint에서 정지 요청이 있으면 open 생략·hold. 양쪽 손가락 접촉이 남아 있으면(control.py:_finger_contact_body) open하지 않고 failed+held_object=접촉 물체로 보고(놓치기보다 쥔 채 정지).
  - 셀 경로의 home은 place 명령에 포함하지 않고 **별도 명령 op=home**(step)으로 낸다. place 성공 터미널 ACK와 DB commit 뒤 executor가 새 command_id로 보낸다. place와 home 사이 cancel은 home을 내지 않는 것으로 끝난다.
  - legacy /robot/place(app.py:339-346)는 호환을 위해 place 안 home을 유지하되 sim_worker.py:164 직전에 checkpoint를 둔다.
held_object(정지 시점, worker가 접촉으로 판정해 stopped ACK에 포함):
| 정지 시점 | 그리퍼 | held_object | 비고 |
|-|-|-|-|
| pick open~reach(접촉 전) | 현 ctrl 유지 | null | |
| pick grasp~lift | 현 ctrl 유지(닫힘 유지) | 양쪽 접촉이면 그 물체, 아니면 null | weld 있으면 유지 |
| place transport~lower(release 전, control.py:320 이전) | 닫힘 유지, open 금지 | 이전 값 유지(접촉 재확인, 끊겼으면 null+event object_lost) | weld 유지 |
| place release 중(open 진행) | 그 위치에서 ctrl 고정 | 접촉 판정 결과 | possibly_dropped event |
| place retreat 이후·home 중 | 열림 유지 | null | home 재시도 안 함, 팔은 home이 아닐 수 있음 |
held_object 값은 시뮬 접촉 판정(3장 "접촉 기반")이며 인식 결과로 보고하지 않는다. 다음 셀 계획은 현재 qpos에서 시작할 수 있어야 한다(home 가정 금지). **held_object가 null이 아니면 POST /tasks는 409 OWNER_CONFLICT(reason=held_object)로 거부**한다(place 전용 task·지시문 파서 특례 없음, V4). 정리는 사람만: legacy 수동 /robot/place(owner manual) 또는 /reset 후 새 task. teleop은 기존처럼 held 시 거부(teleop.py:33)하고 arbiter 검사도 추가.

### 4.5 상태·deadline
상태: queued→perceiving→planning→executing→done, step 반복 executing→perceiving. ambiguous→needs_help; 유효 confirm은 planning, 재촬영/수동 개입은 perceiving. done/cancelled/aborted/failed는 terminal. 각 비종료 상태에서 cancelled/aborted/failed 가능하나 executing 이탈은 stopped ACK 필수. queued/perceiving/planning/needs_help timeout→failed, executing timeout→aborted(정지 ACK 이후). 기본 deadline 초: queued 30, **perceiving cold 180 / warm 30(2.3)**, planning 60, executing 180, needs_help 300, **stopping 중 stop_ack_timeout 3(4.6)**. 상태 진입마다 monotonic 재설정, device별 config 검증된 양수 override 가능. executing timeout 직후 stopping=true, state/owner 유지. terminal에는 deadline 없음. timeout unit helper는 ACK 없으면 executing을 그대로 반환. UI/API도 이를 따라야 한다.
worker stopped ACK와 DB terminal commit ACK 둘 다 전까지 owner 유지. 무응답은 watchdog가 확인된 자기 PID 종료→재생성→recovery_required; 늦은 결과는 epoch로 폐기, 자동 재시도 없음. 시뮬 기능이며 안전 인증 아님.

### 4.6 cancel·estop·deadline 우선순위와 멱등 (C5)
요청 플래그 cancel_requested, estop(stop_latched), deadline_expired는 단조(한 번 true면 terminal까지 안 내려감). 모든 처리는 arbiter mutex + tasks.version CAS로 직렬화하며 같은 tick의 경합은 CAS를 먼저 이긴 쪽만 적용, 진 쪽은 no-op.
1. **terminal 사유는 먼저 commit된 요청(event_seq 최소)이 정한다.** cancel→cancelled, deadline→failed(비executing) 또는 aborted(executing), estop→aborted(estop). 뒤에 온 요청은 이벤트로만 기록하고 사유를 바꾸지 않는다.
2. **estop의 셀 효과는 우선순위와 무관하게 항상 적용**: latch 설정·epoch+1·신규 이동 차단은 즉시(긴 DB 대기 전에 공유 슬롯 게시). 예: cancel 후 estop → task는 cancelled, 셀은 stop_latched=true. estop 후 cancel → aborted(estop) 유지, cancel은 202 no-op.
3. 이중 cancel: cancel_requested가 이미 true면 version과 무관하게 202 {state,cancel_requested:true}, 새 event·epoch 증가 없음. terminal이 cancelled면 200 현재 상태, 다른 terminal이면 409. 처음 cancel의 version 불일치는 409.
4. stopping 중: 상태 deadline은 더 이상 terminal을 만들지 않고(이미 정지 요청 중) **stop_ack_timeout 3 s**만 돈다(4.3 최악 정지 지연 0.5 s의 6배). 초과 시 watchdog(상한 합계 7 s, V1): ① ss/proc로 자기 자식 PID 확인 ② SIGTERM→join 2 s ③ 살아 있으면 SIGKILL→join 2 s ④ 종료 확인되면 task aborted(worker_unresponsive), stop_latched·recovery_required=true, worker 재생성(장면 reset 상태로 시작, 이전 물체 유실 가능 event). ⑤ SIGKILL 후에도 종료 확인 실패(좀비·D state)면 task는 **aborted(worker_unkillable)로 terminal 처리**(task 장부가 영구 stopping에 묶이지 않게)하되, 셀은 stop_latched·recovery_required=true, owner={kind:recovery}, 공유 epoch+1로 모든 이동 명령 거부, 새 worker 생성 금지. 이 상태의 복구 경로는 **서버 재시작뿐**(4.8)이며 reset-stop은 409. 프로세스 종료 확인 전 terminal은 ⑤의 경우만 예외.
5. 비executing 상태(queued/perceiving/planning/needs_help)의 cancel/estop: 로봇 이동이 없으므로 cancel_token 설정 후 task terminal(cancelled/aborted)은 즉시 commit 가능하고 늦게 오는 RPC 결과는 epoch로 폐기. 단 **owner 해제는 perception RPC lock이 풀린 뒤**(V2): owner를 {kind:draining}으로 두고 RPC 반환(정상·CANCELLED·오류)을 기다린다. worker는 cancel_token을 전처리/모델 forward/후처리 경계에서 확인한다(forward 자체는 중단 불가, warm 1회 ROCm p95 0.31 s·CPU p95 3.75 s). 대기 상한 **5 s**, 넘으면 자기 perception worker PID만 종료(로봇 없음, 안전)→lock 해제→owner 해제, 다음 RPC에서 lazy 재생성(cold 재적용). 다음 task는 그동안 queued에 머물며 queued deadline 30 s 안에 들어온다(5+2 s).
6. estop은 terminal task에도 셀 latch를 건다. reset-stop 전까지 POST /tasks는 503이 아니라 409 OWNER_CONFLICT(latched)로 거부.
테스트(I-CT): 위 1~6의 순서 조합(cancel→estop, estop→cancel, cancel×2, deadline→cancel, cancel→deadline, stopping 중 deadline, ACK 없음→watchdog)을 가짜 시계로 고정.

### 4.7 reset-stop 합격 조건 (C6)
POST /cell/reset-stop {version,confirmed:true,scene_confirmed:true,held_object_ack}은 아래를 모두 만족할 때만 commit, 하나라도 실패하면 409 RECOVERY_CHECK_FAILED {failed:[항목]}이고 latch 유지:
1. 모든 task terminal, 모든 이동 명령이 터미널 ACK+DB commit ACK 완료, sim_worker active_command 없음, **arbiter outstanding 집합(송신했으나 터미널 ACK 없는 command_id) 비어 있음**. mp.Queue.empty()는 근사이므로 쓰지 않는다(V3-③). latch/epoch+1 이후 worker는 큐를 계속 꺼내 이전 epoch 명령을 이동 없이 STALE_EPOCH ACK로 비우므로 outstanding이 0이 되는 것으로 drain을 확인한다.
2. worker 생존·ready, boot_id 동일, owner.kind≠recovery(4.6-4⑤면 reset-stop 불가, 서버 재시작만).
3. qpos hold: 정지 시 기록한 q_hold(DB cell.q_hold_json) 대비 모든 팔 관절 |q−q_hold| ≤ 0.02 rad(control.py:393 home 불변식과 같은 값), 0.5 s 관찰 창(250 step) 동안 max |qvel| ≤ 0.05 rad/s.
4. 그리퍼: 정지 후 그리퍼 ctrl 불변, 손가락 폭 변화 ≤ 2 mm. 자동 open 없음.
5. held_object: worker 접촉 재판정 값이 정지 ACK 값과 같고, 요청의 held_object_ack(물체 이름 또는 null)와 같아야 함. 접촉이 끊겼으면 held_object=null로 갱신하고 이 요청은 실패(사람이 다시 확인).
6. scene_confirmed:true는 사람이 화면으로 장면을 확인했다는 표시. GT 물체 변위(control.py:392-393의 5 mm 기준)는 [시뮬GT] 진단 로그로만 남기고 합격 판정·제어에 넣지 않는다.
7. 성공 시 하나의 transaction에서 stop_latched=false, recovery_required=false, epoch+1, owner=null, version+1, event reset_stop; commit 뒤 arbiter mutex 안에서 공유 슬롯 epoch·latch 게시. commit과 게시 사이 프로세스가 죽으면 재시작 규칙(4.8)이 latch를 다시 건다.
worker 재생성 후(V3-①): q_hold가 없으므로 재생성 worker가 ready 직후 기록한 초기 qpos(env reset 직후 home)를 q_hold로 DB에 저장하고 3·4번은 이 값과 그 시점 그리퍼 폭 기준으로 판정한다. 장면이 reset되어 held_object=null이 되므로 held_object_ack는 null이어야 하며, 사람이 event objects_reset_by_respawn을 확인했다는 뜻으로 scene_confirmed:true가 필요하다.
DB 영구 실패(V3-②): commit이 계속 실패하면 reset-stop은 503이고 latch 유지. 이때 복구 경로는 **서버 재시작뿐**이며 재시작 후 4.8 마감과 정상 DB에서 다시 reset-stop을 거친다.
reset-stop은 팔을 움직이지 않는다(home 이동 없음). home이 필요하면 reset-stop 뒤 사람이 별도 명령으로 낸다.

### 4.8 재시작
이전 boot_id의 모든 nonterminal(queued/needs_help 포함)을 aborted/server_restart로 단일 transaction 마감, terminal 불변. 진행 큐/확인/동작 자동 재개 금지. 이전 물체 유실 가능 이력, latch/recovery_required 설정, 새 boot/epoch. DB 오류/queue full은 신규 실행 금지; 실행 중이면 정지 요청. 202/confirm/cancel 수락 ACK는 해당 event/상태 CAS transaction commit ACK 이후. worker terminal ACK 뒤 DB 실패면 owner를 풀지 않고 복구 진입.

### 4.9 현재 근거와 신규 계약 차이 (HEAD 2859663, D-CT 직접 확인)
|현재 근거(파일:라인)|신규 계약과 차이|
|---|---|
|web/app.py:156-157 send: uuid4().hex[:10], command_q.put, epoch/deadline/owner 없음|UUID 전체+boot/task/step/owner_epoch/deadline, arbiter 경유(4.2)|
|web/app.py:158-164 wait: last_command.id 폴링, timeout은 "command timeout" 반환만, 큐 명령 잔존|arbiter.expire: epoch+1 게시, cid별 ACK, 늦은 명령 STALE_EPOCH(4.2)|
|web/app.py:106-147 track_loop: rt.selected/generation 기준, :118 pause는 phase/held/active만, :129 non-fp GT jitter|셀 owner 중 미실행, 셀 슬롯 분리(3.1)|
|web/app.py:293-317 select_at: :299 GT seg mask, :300-302 GT overlap 이름, :307 GT jitter, :313-314 generation+1·selected 교체|셀 owner 중 409, 새 E2E 호출 금지(3, 3.1)|
|web/app.py:318-330 reacquire_after: place 후 wait 180 s→select_at 자동|셀 경로 금지, legacy만 [시뮬GT](3.1)|
|web/app.py:333-337 /robot/pick: rt.estimate 사용, gt_assist 기본 True|셀 명령은 Localization에서, gt_assist/identity_assist 명시 false(3)|
|web/app.py:339-346 /robot/place, :347-352 reset/randomize: 소유 검사 없음|arbiter 소유·latch 검사(4.1, 4.6)|
|web/app.py:366 CAD add_object wait 60 s|같은 expire 규칙(4.2)|
|web/app.py:371-379 status_payload: GT 대비 error_mm/deg|cell 키 추가, GT 오차는 [시뮬GT] 표기(6)|
|web/perception_stub.py:8-11 estimate_pose: GT pose+rng(7) σ1.5 mm|새 E2E 금지, [시뮬GT] 전용(3)|
|web/perception_stub.py:19,26-29 worker 시작 시 torch/FP/SAM2 import|ensure_*에서만 lazy import(2.2)|
|web/perception_stub.py:42-45,58 SAM device='cuda'·autocast cuda 고정|cpu/cuda/rocm 분기(2.3)|
|web/perception_stub.py:74-75 cuda synchronize·max_memory_allocated 무조건|cpu는 peak_mb=null, rocm/cuda만 기록(2.3)|
|web/perception_stub.py:93-94 fp 모드 아니면 RPC 거부|ground/segment_box/capabilities는 모드와 독립(2.1)|
|web/perception_stub.py:108 RPC 대기 180 s 고정|deadline 인자=min(상태 잔여, 상한), cold/warm(2.3)|
|web/sim_worker.py:122-123 stop_event는 바깥 루프 첫 줄만|FIFO 밖 stop/cancel, 모든 checkpoint(4.3)|
|web/sim_worker.py:127-133 FIFO get_nowait 후 바로 실행|dispatch 직전 epoch/deadline/latch 검사(4.2)|
|web/sim_worker.py:141,143 reset/randomize가 held_object=None, owner 무관|arbiter 소유 필요, latch 해제 아님(4.7)|
|web/sim_worker.py:151,161 gt_assist 기본 True|셀 명령 필수 필드, 기본 false(3)|
|web/sim_worker.py:152,162 object_pose_fn=GT 이름 pose|GT 보조/evaluator 전용(3)|
|web/sim_worker.py:154-155 pick 실패 자동 open|정상 경로만, 정지 경로 금지(4.4)|
|web/sim_worker.py:163-168 place 후 held=None·자동 home|셀은 home 별도 명령, legacy는 직전 checkpoint(4.4)|
|web/sim_worker.py:172-178 last_command 단일 슬롯 덮임, finally active=None|cid별 ACK, stopped+commit ACK 전 owner 유지(4.2)|
|sim/control.py:110,260,301,304, sim/grasp.py:129-152 solve_ik hook 없음|호출 경계 checkpoint, 지연 ≤500 ms(4.3)|
|sim/control.py:72-81 _step→step_hook|physics checkpoint 지점, ≤100 ms(4.3)|
|sim/control.py:142 open_gripper가 detach|정지 경로 호출 금지(4.3, 4.4)|
|web/teleop.py:33 active_command/held만 검사|queued/perceiving/planning도 arbiter 소유(4.1)|
|web/teleop.py:7,53-58 preview={jpeg,seq}, capture_at 없음|legacy preview 메타 고정(5)|
|tools/teleop_tracker_win.py:303,374 flip; :418,430-438 손·자세 overlay; :446 imencode q65; :448 pending; capture_at은 update payload(:36)에만|unflip·overlay_present=true·capture_at=null(5)|
|web/realtime.py:70-84 StatusSchedule next/active 3종 고정, :112 builders 3종|type=cell 추가, 기존 호환(6)|

## 5. W2 프레임·보정
tools/teleop_tracker_win.py:303/374 좌우 flip, :418-438 손·자세 overlay, :446-448 encode 후 preview. web/teleop.py:53-58는 JPEG/seq만 수신하며 촬영시각 없음. update capture_at와 preview JPEG는 원자 연결되지 않으므로 합치지 않는다. legacy preview는 capture_at=null, overlay_present=true, mirrored=true, 수신시각만 기록하며 오버레이 없는 촬영이라고 보고 금지. clean capture를 확보할 때까지 정밀 실물 E2E는 blocked(legacy preview 실험은 오버레이 오염 한계 표기). 트래커 수정은 별도 승인 범위이며 이번 변경은 없음.
픽셀 중심 unflip: u'=W-1-u, v'=v. 박스 반열린 경계: [W-x2,y1,W-x1,y2]. UI 역변환은 letterbox offset 제거→표시 scale 역변환→unflip, 출력 overlay는 역순; center와 edge 공식을 혼용하지 않는다. 보정 frame과 원본 unmirrored 좌표만 localizer에 입력. immutable bytes+metadata 원자 snapshot(frame_id/generation/capture/received/mirror/calibration/mode/FOV/crop/overlay/hash) 보존. 추론 도중 latest preview를 다시 읽지 않는다. 스냅샷 트윈은 검증된 물체 전체 batch 명령 하나(전체 성공 또는 거부).
보정: 트래커 종료→카메라 단독 소유 단독 tool 1280 원본 체커보드 K/distortion→책상 ArUco T_world_cam/plane→실제 640 preview capture mode/FOV/crop 동일 확인→스케일·unflip 검증→보정에 쓰지 않은 독립 격자점 오차 보고. 높이 보정 전후 별도; 원본 보정이 preview 정확도 보장하지 않음. mismatch는 CALIBRATION_MISMATCH, 보정 id 없는 실물 localization 거부.

### 5.3 사용자 확정 반영 (2026-11-10)
- [녹화영상]은 선택·오버레이 검증에만 쓴다. 보정판 포함 새 녹화가 어려우므로 **녹화 기반 위치 오차는 '측정 불가'**로 표기하고 지표 값은 null+reason="no_calibration_target_in_recording". 0이나 시뮬 수치로 대체 금지.
- 집 PC에는 웹캠이 없다. W2 실촬영(보정 도구 촬영, 실물 위치 오차, 실카메라 판정)은 **회사 PC**(11-11 예정). 집에서는 카메라 없이 되는 순수 로직(unflip·평면 투영·높이 보정 변환)과 시뮬 검증만 하며, 그 결과는 [시뮬GT] 또는 [시뮬인식]으로 표기하고 [실물웹캠] 근거로 쓰지 않는다.
- calibration_id 없는 실물 localization 거부 규칙은 그대로이므로 회사 보정 전 [실물웹캠] 위치 지표는 모두 미측정(null).

## 6. API·WS·SQLite 초안
POST /tasks {instruction,source,frame_id?,schema_version:1}, Idempotency-Key 필수(동일 key/다른 body=409); commit ACK 후 202 {task_id,state:queued,version:1}. GET /tasks?limit=50&after=cursor, GET /tasks/id(steps/events/commands 요약); POST /tasks/id/confirm {candidate_id,frame_id,version}는 stale/다른 frame/version 409; POST /tasks/id/cancel {version}는 cancel_requested만 commit 후 202(멱등 규칙 4.6), worker stopped 전 terminal 표시 금지. POST /cell/estop은 event 즉시 전달+latch(긴 DB 대기 전에 전달), durable ACK 실패 503이더라도 latch 유지. POST /cell/reset-stop {version,confirmed:true,scene_confirmed:true,held_object_ack}는 4.7 검증 후 commit. 잘못된 schema=400, 미등록 지시=422/needs_help(구문 유효 시), owner 충돌·latch=409 OWNER_CONFLICT, 복구 조건 실패=409 RECOVERY_CHECK_FAILED, DB/queue unavailable=503. 이미지 base64/GT identity 입력 금지.
/status는 기존 키 유지하고 cell 키 추가. /status/ws는 기존 {type,data} envelope에 type=cell 추가(data는 /status.cell와 동일). cell={schema_version:1,event_seq,boot_id,task_id,state,version,owner:{kind,id,epoch},command_id,stop_latched,recovery_required,cancel_requested,stopping,deadline_at,held_object,error,source_badge,gt_assist:false,identity_assist:false}. active5Hz/idle1Hz, cached snapshot만 읽기(WS tick DB/추론 금지). StatusSchedule next/active/builders 모두 추가가 후속 구현 조건.
SQLite schema v1 초안(UTC 시각 문자열, JSON은 이미지 없이 DTO 메타만):
~~~sql
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=3000;
CREATE TABLE tasks(task_id TEXT PRIMARY KEY, boot_id TEXT NOT NULL, idempotency_key TEXT UNIQUE NOT NULL, request_hash TEXT NOT NULL, state TEXT NOT NULL, version INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deadline_at TEXT, payload_json TEXT NOT NULL, error_json TEXT);
CREATE TABLE steps(task_id TEXT NOT NULL REFERENCES tasks(task_id), step_id TEXT NOT NULL, state TEXT NOT NULL, candidate_json TEXT, result_json TEXT, PRIMARY KEY(task_id,step_id));
CREATE TABLE commands(command_id TEXT PRIMARY KEY, task_id TEXT REFERENCES tasks(task_id), step_id TEXT, boot_id TEXT NOT NULL, owner_epoch INTEGER NOT NULL, payload_hash TEXT NOT NULL, status TEXT NOT NULL, deadline_at TEXT, result_json TEXT, stopped_ack INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL);
CREATE TABLE events(event_seq INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT REFERENCES tasks(task_id), command_id TEXT, type TEXT NOT NULL, at TEXT NOT NULL, payload_json TEXT NOT NULL);
CREATE TABLE cell(singleton INTEGER PRIMARY KEY CHECK(singleton=1), boot_id TEXT NOT NULL, epoch INTEGER NOT NULL, stop_latched INTEGER NOT NULL, recovery_required INTEGER NOT NULL, owner_json TEXT, held_object TEXT, q_hold_json TEXT, version INTEGER NOT NULL);
PRAGMA user_version=1;
~~~
writer 전용 connection+bounded queue, 별도 read connection. 상태 update WHERE version=expected와 event insert는 동일 transaction. migration은 시작 시만, 실패하면 시작 거부. 결과 삭제는 terminal+ACK+보존 기간 후만, owner/inflight 삭제 금지. shutdown flush/join. (v1.1: commands.status에 stale_epoch·expired 값 추가, cell에 held_object·q_hold_json 추가.)

## 7. 검증 경계
이번 추가는 순수 계약/테스트만. 실제 worker 중단·DB full·owner 경합·GPU cleanup·실물 보정 통합 PASS는 후속 K/G/W2 검증 필요. tests/test_contracts_r5.py가 DTO roundtrip/unflip/전이/timeout/restart 계약을 고정한다(I-CT 작성 예정, v1.1 시점 미작성).
통계(사용자 확정 2026-11-10): 선택 정확도·E2E 성공률 등 비율 지표는 **N≥100 점추정 + Wilson 95% CI 병기**(예: 90/100 → 82.6~94.5%). CI 하한 기준(N≈200)은 쓰지 않는다. N<100 결과는 "예비"로만 표기하고 합격 근거로 쓰지 않는다. 분모(대상 없음·가림 포함)와 시드/해시를 결과에 함께 저장.
4.3의 정지 지연 상한과 2.3의 deadline은 집 PC 수치 기반 잠정값이며 회사 PC에서 재측정 후 확정한다. 집 AMD/CPU 수치는 회사 NVIDIA 합격 증거가 아니다.
