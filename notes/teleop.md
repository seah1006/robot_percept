# USB 카메라 따라하기 (시뮬레이션 전용)

Windows USB 카메라는 WSL에 전달하지 않습니다. Windows에서 MediaPipe Tasks 손 추적을 실행하고 WSL Flask 서버로 특징과 스켈레톤 미리보기를 전송합니다. 실제 로봇 연결 기능은 없습니다.

## 실행
1. WSL: `source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept; cd /home/user/work/robot_percept; source sim_test/gl_env.sh; HOST=0.0.0.0 PORT=5080 PERCEPTION=stub python -m web.app`
2. Windows PowerShell: PYTHONHOME/PYTHONPATH/VIRTUAL_ENV/PIP_PREFIX/PYTHONNOUSERSITE 환경 변수를 지우고 다음 실행:
   `& C:\Users\USER\AppData\Local\Programs\Python\Python312\python.exe C:\Users\USER\Documents\sam_camera\teleop_tracker_win.py --url http://localhost:5080`
   소스는 `tools/teleop_tracker_win.py`. 최초 실행 시 Google 공식 hand_landmarker.task 모델을 Documents/sam_camera/models에 다운로드합니다. opencv, numpy, mediapipe Tasks API 필요. requests가 있으면 keep-alive 사용.
3. 웹의 왼쪽 아래 `따라하기 모드` 펼치기. 손을 펴고 `시작`, `기준 자세`로 중립 보정.
4. 미러 화면의 좌우/상하가 TCP 좌우/높이를 조절합니다. 손을 가까이/멀리 이동하면 깊이를 조절합니다. 엄지/검지를 모으면 그리퍼 닫기, 펼치면 열기. 전체 몸/팔 관절 모방이 아닌 한 손 TCP 조작입니다. yaw는 고정해 손 떨림을 줄입니다.

## 안전
- TCP 작업공간: x .25~.70, y -.35~.35, z .36~.85m. DLS 서보 50Hz, 관절 명령 변화 .65rad/s 제한. 로봇의 동적 속도 자체를 하드웨어 수준으로 보장하지는 않습니다.
- 0.3초간 새 손 입력이 없으면 현재 관절 위치 유지. 자동 재추적 시 기존 기준으로 다시 움직입니다.
- 중지, reset/randomize/pick/place 등 명령은 따라하기를 끕니다. 물체를 잡은 상태나 명령 실행 중에는 시작하지 못합니다.
- 작업공간 제한은 충돌 회피 계획기가 아닙니다. 테이블 위 물체와 부딪힐 수 있습니다. 집기/놓기는 모드를 끄고 사용하세요.
- 카메라는 프로세스 하나만 사용하세요. 기존 win_cam_sender를 동시에 켜면 카메라 열기가 지연/실패할 수 있습니다.
- HTTP는 인증 없는 로컬 개발용입니다. 공용망에 노출하지 마세요.

## 재현 / 녹화
`python teleop_tracker_win.py --url http://localhost:5089 --record C:\Users\USER\Documents\sam_camera\teleop_test --seconds 10`
MP4(재인식을 위한 원본 640x360, 스켈레톤 없음)와 JSONL이 저장됩니다. 스켈레톤은 웹 미리보기에만 표시됩니다. MP4는30fps로 인코딩되므로 실제 촬영 간격을 정확히 재현하려면 JSONL replay를 사용하세요.
`python teleop_tracker_win.py --video C:\Users\USER\Documents\sam_camera\teleop_test.mp4 --url http://localhost:5090`
`python teleop_tracker_win.py --replay C:\Users\USER\Documents\sam_camera\teleop_test.jsonl --url http://localhost:5090`
JSONL 한 줄: `{"t":0.033,"features":{"detected":true,"x":0.5,"y":0.5,"scale":0.15,"pinch":0.6},"landmarks":[[0.1,0.2,0.0]]}`. detected=false는 손 없음. 원본 영상이 아닌 특징 재생은 카메라/MediaPipe 없이 가능하지만 OpenCV/numpy 필요.

API: POST /teleop/mode {enabled:bool}, POST /teleop/calibrate, POST /teleop/update {detected,x,y,scale,pinch,sent_at}, POST /teleop/preview JPEG, GET /teleop/preview.jpg, GET /teleop/status. Status Hz는 최근 2초 입력 빈도, latency_ms는 Windows 송신~서버 수신 벽시계 시간으로 전체 영상 지연은 아닙니다.


## 비교 화면 (Round5)
- 시작하면 왼쪽 `내 카메라 · 손 추적`, 오른쪽 `로봇 시뮬레이션`이 같은 높이로 배치됩니다. 작은 화면은 위/아래. 가운데 배지에 입력 Hz, 송신 지연, 손 감지, 집게 상태가 표시됩니다. 중지하면 원래 영상 위치로 복구되며 물체 클릭/포커스 뷰의 기존 DOM과 이벤트는 유지됩니다.
- 카메라는 Windows tracker의 cv2.flip(frame,1)에서 한 번만 셀피 좌우반전합니다. 웹 CSS는 추가 반전하지 않습니다. 미러 화면 손 x 증가 → world y 증가(.7m/화면폭). 기본 `front` 시뮬 카메라는 world +y를 영상 오른쪽으로 투영하므로 두 화면의 보는 사람 기준 좌우 방향이 같습니다. 다른 시뮬 카메라 시점에서는 투영 방향이 달라질 수 있습니다. 기본 front 시점을 사용하세요.
- 손 영역 경계는 기준 자세와 TCP x/y/z clamp 중 화면 x/y에 해당하는 한계를 역매핑합니다. 깊이(scale) 제한은 이 2D 경계로 표시하지 않습니다. 초록 점은 손 중심. 로봇 쪽 초록 십자점과 짧은 선은 카메라 보정행렬로 투영한 TCP 목표/최근 목표 궤적입니다.
- 손 미감지 안내는 즉시 표시되며, 서보는 마지막 입력 이후0.3초에 정지합니다. 배지 지연은 전체 영상/로봇 지연이 아닌 송신→서버 수신 시간입니다.
- 미리보기: `/teleop/preview.mjpg` MJPEG, Windows JPEG 업로드 목표20fps. 최신 프레임만 유지하며 재인코딩하지 않습니다. `/teleop/status`의 preview_hz는 최근2초 서버 수신 미리보기 빈도입니다. 가려진/꺼진 비교 화면은 MJPEG 연결을 닫습니다.
- 성능 검증: notes/verify_t.md 및 notes/teleop_changes.md. 손 입력30Hz는 환경에 따른 목표이며, 초기 실제 hand-positive live 추적18.05Hz까지 확인했습니다. 비동기 HTTP 개선 후 hand-positive20Hz는 아직 별도 검증 대기입니다.
