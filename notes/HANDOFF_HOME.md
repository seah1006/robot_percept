# robot_percept 인계 문서 (2026-11-05 회사 → 집, 2026-11-06 집 PC 갱신)

저장소: https://github.com/seah1006/robot_percept (public)
- `master`: 독립 검증 PASS된 커밋만 (최신 a9f2c26). 태그 `baseline-1102`, `humanoid-30fps-pass`.
- `wip/r2`: 진행 중인 r2 작업 전체 스냅샷 (검증 미완 포함). **집에서는 이 브랜치에서 이어서 작업.**

## 0. 2026-11-06 집 PC 세션 갱신 (이 섹션이 최신. 아래 1~2장은 11-05 기록)

### 완료 (master 반영)
| 커밋 | 내용 | 근거 |
|-|-|-|
| 970a681 | r2 라운드 병합(P1a, P1b, W, monotonic 대기, UI 확인). P1c는 기본 OFF 실험, 트래커 절대 판정·FP 워밍업 defer는 미검증으로 명시 | notes/humanoid_w_changes.md, notes/verify_w.md |
| 16e49a8 | F 라운드: Flask 유지 성능 개선. 트래커 update `/tracker/ws`, 브라우저 상태 `/status/ws` push(폴링 자동 폴백). update p95 15~17ms→2.3ms, 서버 main CPU 약 -11%p. 트래커 기본 `--transport http` | notes/flask_perf_changes.md, notes/verify_f.md |
| 452378f | G 라운드: 서버 종료 시 worker 잔존 수정(부모 신호 정리 5초 상한, 자식 부모 PID 감시, Manager 감시). 60/60 잔존 0 | notes/shutdown_changes.md, notes/verify_g.md |
- 11-05 남은 일 1~4번은 위로 처리됨. 5번(FastAPI)은 사용자 결정으로 하지 않음(Flask 유지).
- G1 4.9초 정지: 집 PC에서 HEAD의 G1 렌더 루프는 이미 monotonic이라 재현 안 됨. Panda/teleop/perception/하네스의 timed wait를 monotonic으로 바꿈(개선 근거는 코드 리뷰와 모의 테스트).

### 남은 일
1. P1c 재설계(자세별 rest 시드 분리, release 방향 기반). 집 PC에서 진행 예정.
2. 짧은 검증: 유휴 렌더 2fps 독립 재측정, 서버 기동 중(ready 전) 신호, Panda 집기 회귀(GT 보조).
3. 트래커 MediaPipe 실처리 절대 판정(처리율 ≥99%, ≥29.7Hz): Windows Python 3.12 + mediapipe + 30fps 사람 영상 필요. 통과 후 트래커 기본 ws 전환 검토.
4. 알려진 한계: Windows→WSL preview HTTP p95 +3~9ms(처리량 동일, WSL 내부 3.6ms). 원인 미규명.
5. 회사 PC 필요(CUDA): SAM2/FoundationPose, FP 워밍업 defer 재측정, E 평가(FP N30, 추정 자세 집기), 실카메라 수락.

### 집 PC 환경 (회사와 다른 점, 3장 설치 외 추가로 필요했던 것)
- GPU AMD Radeon RX 7600: `sim_test/gl_env.sh`의 `MESA_D3D12_DEFAULT_ADAPTER_NAME=AMD`(로컬 전용, skip-worktree). nvidia-smi 없음 → GPU 기록은 GL_RENDERER로.
- 경로 /home/my/work/robot_percept, conda는 ~/miniforge3(Python 3.12.16, HAVE_SEM_CLOCKWAIT=0). sudo 비번 필요.
- Panda 장면/테스트용: `pip install imageio gdown`, FP 데모 데이터 중 mustard0만(`gdown 1AwV9sESDKMgXGUu2n1o0Pc4x2JGYdVB3` → downloads/demo_data/mustard0), `python sim_test/build_scene.py`로 panda_mod.xml을 이 PC 경로로 재생성(로컬 전용, skip-worktree), CAD 샘플 변환용 `.venvs/cad`(cadquery 2.8.0, coacd) 후 `tools/stp_to_mesh.py ... --collision coacd`로 box_fillet·cup 변환. 이후 pytest 전부 통과.
- PowerShell에서 WSL 명령은 `wsl -d Ubuntu-24.04 --exec bash -lc '...'`(--exec 없으면 바깥 셸이 $변수 확장).
- WSL 벽시계가 약 5초마다 ±92초 점프(systemd-timesyncd active, 동기화 no). 측정 창마다 14회 정도 겹침.
- Windows→WSL 5092 중계에 CloseWait가 쌓여 막힌 적 있음(5094로 우회). WSL 재시작으로 풀릴 가능성.
- WSL 안에 사용자 openclaw gateway(:18789) 상주. 건드리지 말고 측정 시 CPU만 기록.
- Windows: Claude Code·Codex에 agency-agents 개발 7개 부서(131개) 전역 설치(~/.claude/agents, ~/.codex/agents, WSL ~/.codex/agents).

## 1. 현재 상태 (r2 개선 라운드)

| 항목 | 상태 | 근거 |
|---|---|---|
| R 휴머노이드(G1) 따라하기 30fps | PASS, master 커밋 | notes/humanoid_changes.md, notes/verify_r.md |
| P SAM2 클릭 마스크·FP 등록·워밍업 | PASS, master 커밋 | notes/perception_changes.md, notes/verify_p.md |
| C Panda 집기 N=20 회귀·장애물 home | PASS, master 커밋 | notes/control_changes.md, notes/verify_c.md |
| P1a 팔 정확도(실제 어깨 기준 목표 + IK 분기 복구) | PASS (wip/r2) | notes/humanoid_s_changes.md, notes/verify_s.md |
| P1b 안전 감속 safety_brake (기본 ON, 화면 토글) | PASS (40ms 기준) (wip/r2) | 같은 파일. OFF→ON 첫 40ms는 OFF 대조 이하, 이후 가속비 ≤1.0 |
| P1c 자기충돌 회피 | **FAIL → 기본 OFF 실험 기능으로 마감** | notes/humanoid_teleop.md 한계 섹션 |
| W 웹 안정성(잘못된 payload 400, 동시 ON/OFF, worker 복구, 첫 끊김 ≤200ms), 유휴 렌더 2fps, FP lazy spawn·워밍업 취소 | 보고 수치 PASS, 독립 최종 재측정 남음 | notes/humanoid_w_changes.md, notes/verify_w.md |
| K 트래커 최적화(Pose+Hand 병렬, QPC 시계, urllib3) + humanoid 녹화/재생 + 카메라 수락 도구 | 상대 회귀 없음 PASS, 절대 판정 남음 | notes/tracker_changes.md |
| G1 화면 4.9s 정지 | **원인 특정, 수정 미적용** | 아래 2-1 |

## 2. 남은 일 (순서대로)

1. **G1 화면 정지 수정**: WSL 벽시계(REALTIME)가 ~4.9s 역행하는데, conda Python 3.12.14 빌드가 `HAVE_SEM_CLOCKWAIT=0`이라 `threading.Event.wait(timeout)`이 벽시계 기준으로 동작 → 렌더 스레드(`render_stop.wait`)와 측정 하네스 대기가 동시에 ~5s 멈춤. 실제 렌더 88ms, JPEG 2.8ms로 정상. 수정: web/humanoid_worker.py 등 렌더/게시 루프와 bench 하네스의 timeout 대기를 `time.monotonic()` 데드라인 + `time.sleep` 기반으로 교체(정지 신호는 짧은 sleep 간격으로 폴링). 같은 슬롯에서 OFF 대조와 재측정.
2. **조용한 창 최종 측정**(다른 작업 전부 정지): G1 30초 창 ≥29.7fps(개수 기반), 서버 지연 p95 ≤80ms, 트래커 처리율 ≥99%·수신 ≥29.7Hz(녹화본 30fps 페이싱), `bench/verify_w/vw_measure.py`·`crash_test.sh`로 P0 재측정, 워밍업 defer 경로 재측정.
3. **브라우저 UI 육안 확인**: Panda/G1 전환, 안전 감속 체크박스·경고 문구, 충돌 회피 실험 토글(기본 꺼짐)·주의 문구, 전환 중 안내.
4. PASS 항목을 master에 커밋·push, Windows 트래커 복사본(Documents/sam_camera) 동기화.
5. (선택, 사용자 결정 대기) FastAPI + WebSocket 전환을 별도 단계로. 성능 이득은 대부분 WebSocket(트래커 30Hz POST의 HTTP 헤더 ~9ms, 브라우저 폴링 3개)에서 나옴. 기준선 측정 → 같은 경로 이식 → Pydantic → WebSocket → bench/verify_* 회귀.
6. (나중) E 평가 FP N30·추정 자세 집기 매트릭스, 실카메라 수락 테스트(`tools/camera_acceptance.py`), P1c 재설계(자세별 rest 시드 분리, release 방향 기반).

## 3. 집 환경 설정

전제: Windows + WSL Ubuntu(24.04 권장) + NVIDIA GPU. 경로는 집 환경에 맞게 바꿀 것.

```bash
# WSL
git clone https://github.com/seah1006/robot_percept.git ~/work/robot_percept
cd ~/work/robot_percept && git checkout wip/r2
conda create -n robot_percept python=3.12 -y && conda activate robot_percept
pip install mujoco==3.17.0 numpy==2.5.3 flask==3.1.3 opencv-python==5.0.0.93 requests urllib3 scipy trimesh open3d rtree pytest -c notes/rp_constraints.txt
# G1 모델 원본(필수): MuJoCo Menagerie (회사 기준 커밋 f3b6013)
git clone https://github.com/google-deepmind/mujoco_menagerie.git assets/mujoco_menagerie
source sim_test/gl_env.sh   # MUJOCO_GL=egl + WSLg D3D12. GPU 이름(MESA_D3D12_DEFAULT_ADAPTER_NAME)을 집 GPU에 맞게
export HOST=0.0.0.0 PYTHONPATH=$PWD
python -m pytest -q          # 68 pass 기대
PORT=5091 PERCEPTION=stub RP_PERCEPTION_WARMUP=0 python -m web.app   # http://localhost:5091 → 로봇 선택 G1
```
- G1/휴머노이드만 할 때는 위로 충분(SAM2/FoundationPose 불필요, `PERCEPTION=stub`).
- SAM2·FoundationPose(PERCEPTION=fp)가 필요하면 `notes/downloads.md`(가중치·데모 데이터 Google Drive ID), `notes/fp_compat.md`, torch 버전은 `notes/rp_constraints.txt` 참고. pytorch3d·nvdiffrast 빌드 필요.
- Windows 트래커: Windows Python 3.12 + `pip install mediapipe opencv-python numpy requests urllib3`. 모델 `hand_landmarker.task`, `pose_landmarker_lite.task`를 `%USERPROFILE%\Documents\sam_camera\models\`에. 실행 전 PowerShell에서 PYTHONHOME/PYTHONPATH/VIRTUAL_ENV/PIP_PREFIX/PYTHONNOUSERSITE 제거, cv2 import 전 `OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS=0`. 카메라가 없으면 `--video <녹화.mp4>`(녹화본은 저장소에 없음, 얼굴 포함이라 비공개).

## 4. 작업 규칙 (지금까지 합의된 것)

- 구현은 Codex(gpt 계열) 서브에이전트, 검증은 Claude(sonnet) 서브에이전트. 둘이 task id로 직접 주고받으며 자가 피드백, 부모에게는 이정표만. 동시 서브에이전트 ≤8. 긴 대기는 subagent_wait에 여러 작업을 한꺼번에 걸지 말 것.
- 구현자는 커밋 금지. 독립 검증 PASS 후 부모가 master에 커밋. 미완 작업은 wip/r2 스냅샷.
- 프로세스 종료는 `ss -ltnp | grep :<포트>`로 자기 PID만. `pkill -f` 금지. 사용자 서버 포트(회사 5080)는 함부로 끄지 말 것.
- 포트: 구현 5091/5093/5095, 검증 5092/5094.
- 도구 세션이 끝나면 백그라운드로 띄운 서버가 죽음 → 서버는 Bash yield_ms 장기 실행으로.
- 성능 수치(fps/Hz/지연/CPU%) 측정과 수 초 이상 벤치는 `flock -w 900 /tmp/rp_measure.lock` 안에서, GPU 벤치는 measure→gpu 순서 이중 락(`/tmp/rp_gpu.lock`), 한 번 5분 이내. 운영 코드는 측정 락 사용 금지. 결과에 load·nvidia-smi·동시 작업 기록.
- Windows 트래커는 WSL nice가 안 먹으므로 트래커 측정 중엔 WSL 배치도 측정 락 안에서.
- 에이전트 동시 작업 중엔 상대 비교(같은 슬롯 A/B/A/B, -2%p 이내)로 회귀 판정, 절대 기준은 마지막 조용한 창에서 한 번.
- 30fps 판정은 개수 기반(30초 창 ≥29.7). 입력이 30fps면 30Hz가 상한이므로 처리율 ≥99%로 판정.
- 시뮬 결과 중 정답(GT) 보조를 쓴 건 GT 보조라고 밝히고, 추정만 쓴 결과는 따로 보고.
- (2026-11-06 추가) A/B 비교는 반복 창/샘플로 차이(B-A)의 부트스트랩 95% 신뢰구간을 함께 보고. CI가 0을 포함하면 "차이 입증 안 됨", 개선 주장 금지. 기존 -2%p 상대 기준과 병행.
- (2026-11-06 추가) 검증자의 기본 판정은 NEEDS WORK. 구현자의 자체 측정·"문제 0건" 보고는 확인 대상일 뿐이고, 검증자가 직접 재현한 증거(원자료 경로)가 있는 항목만 PASS.
- 답변은 한국어.
