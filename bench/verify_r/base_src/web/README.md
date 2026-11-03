# MuJoCo Franka Panda Flask server
MuJoCo는 spawn 프로세스 하나가 독점하고 Flask는 shared memory RGB/depth/seg를 읽습니다.
```bash
cd /home/user/work/robot_percept
source /home/user/anaconda3/etc/profile.d/conda.sh
conda activate robot_percept
source sim_test/gl_env.sh
PERCEPTION=stub PORT=5080 python -m web.app
```
Windows 브라우저: http://localhost:5080

`PERCEPTION=fp`이면 `perception/fp_runner.py:FPRunner`를 별도 프로세스로 구동하며, 없거나 초기화 실패 시 stub으로 fallback합니다.

Endpoints: `/`, `/video`, `/frame.jpg`, `/status`, `/objects`, `/click`, `/robot/pick`, `/robot/place`, `/reset`, `/scene/randomize`, `/cad/upload`.

EGL note: MuJoCo's EGL loader needs `PyOpenGL>=3.1.7`. If the environment still has 3.1.0:
```bash
python -m pip install -c notes/rp_constraints.txt 'PyOpenGL>=3.1.7'
```

## 실제 perception (기본값)
`./run_web.sh` 실행. `PORT=5081 ./run_web.sh`로 별도 테스트 서버 실행.
외부 접속 HOST는 런처에서 0.0.0.0으로 설정합니다. 로컬 전용은
`HOST=127.0.0.1 PORT=5081 PERCEPTION=fp python -m web.app`.
명시적 대안: `PERCEPTION=stub ./run_web.sh` (GT + 노이즈, 실제 인식 아님).

클릭 → SAM2.1 small의 양성 포인트/최고 점수 마스크 → 해당 마스크와
시뮬레이션 seg의 최대 겹침으로 이름만 선택 → 그 이름의 미터 단위 mesh로
FoundationPose register → 새 RGB-D 프레임 비동기 track.
GT는 이름, IoU, mm/deg 평가 및 로봇 성공 판정에만 사용합니다.
집기 계획은 최근 추정 T_cam_obj에 T_world_cam을 곱합니다.
등록 중에도 영상/상태 API는 계속 동작하며, 첫 등록은 모델 로딩 때문에 오래 걸립니다.

GPU 인식 전용 spawn 프로세스에 SAM2 predictor와 물체별 FPRunner가 있습니다.
SAM은 fp16 CUDA inference 후 CPU로 이동하고 임베딩/캐시를 해제하여
8GB VRAM을 FP 등록에 양보합니다. FP는 물체별 mesh/tracking state를 갖고
scorer/refiner를 공유합니다. `FP_INPLANE_STEP=120`, crop/network chunk=32 권장.
실제 인식 실패를 GT 추정으로 조용히 대체하지 않고 API 오류/상태 경고로 표시합니다.

UI: 초록색은 SAM 마스크, EST 축/노란 박스는 추정, GT 축은 평가용입니다.
리셋/랜덤/CAD 변경 시 선택과 추적이 무효화됩니다.
'놓기 위치 클릭'을 누르고 테이블을 클릭하면 depth/K/외부파라미터로
world x,y를 구해 place_object에 전달합니다. 기존 놓기는 기본 위치를 사용합니다.
카메라에 보이는 평평한 테이블을 클릭해야 합니다 (물체/로봇 클릭을 피하세요).
/status.pose: mask_iou, sam_ms, register_ms, tracking_fps, estimate_timestamp,
peak_mb (PyTorch peak allocated), error_mm/error_deg. /status.gpu는 전체 GPU 사용량입니다.

자동 통합 검증: 별도 서버 `HOST=127.0.0.1 PORT=5081 PERCEPTION=fp python -m web.app`
실행 후 `python -m web.test_pipeline`. 기본 /tmp/web-perception-test에 JSON/오버레이 저장.
초기 reset + 랜덤 3회에서 등록/5초 추적/집기/테이블 클릭 놓기와 CAD 업로드를 검증합니다.

### 2026-11-02 실제 검증 (5081, 기존 5080 미중단)
reset + randomize 3회 모두 SAM→FP 등록/5초 tracking/추정 자세 집기/픽셀 놓기 성공.
등록 위치 오차 0.77–1.48 mm, 회전 0.80–1.68°, 추적 4.95–6.29 FPS.
놓기 XY 오차 1.18 / 3.60 / 2.34 / 3.54 mm (요구 20 mm 이내).
SAM IoU 0.985 / 0.978 / 0.153 / 0.977: 한 랜덤 장면의 SAM 마스크 품질은 낮지만 등록/집기는 성공.
CAD 50x30x20mm fillet box 업로드/등록/집기 성공; 위치 1.41mm, 회전 원시오차 179.86°
(대칭 직육면체의 180° 등가 자세, 대칭 보정 metric 아님), IoU 0.690.
PyTorch peak allocated: mustard 3203 MiB / CAD 3518 MiB; 전체 GPU peak는 미계측.
첫 SAM 6.57s / 첫 등록 39.52s는 모델 로딩 포함. 이후 SAM 0.60–0.69s,
등록 2.81–2.84s. 자세오차/IoU는 모델의 입력이 아니라 평가에만 사용.
`web/test_results_fp.json`에 원시 응답 저장. 마지막 bbox/놓기 추적 유지 수정 후에는
stub smoke + reset 무효화 + compile 검증만 수행했으며 전체 FP 시퀀스 재검증은 하지 않았습니다.

제약: 마스크 오버레이는 등록 시 SAM 마스크이며 매 프레임 재분할하지 않습니다.
추정 축/박스만 FP tracking으로 갱신합니다. 심한 가림/추적 실패는 경고와 추정 숨김으로
표시하며 다시 물체를 클릭해 등록해야 합니다. pick 중 카메라 추적 지연은 움직임에 따라 증가합니다.
