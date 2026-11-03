# G1 상체 따라하기
시뮬레이션 전용. 로봇 선택에서 Unitree G1을 선택하면 왼쪽 웹캠/스켈레톤, 오른쪽 G1이 표시됩니다. Panda로 돌아가면 G1 worker를 종료합니다. 기존 Panda DOM은 유지합니다.

## 트래커
Windows 환경변수 PYTHONHOME/PYTHONPATH/VIRTUAL_ENV/PIP_PREFIX/PYTHONNOUSERSITE 삭제 후 tools/teleop_tracker_win.py --mode both --url http://127.0.0.1:5091 실행. 사용자 5080 적용/재시작은 부모 담당. 검증은 --video C:\Users\USER\Documents\sam_camera\teleop_round2_async.mp4 --seconds 8 사용. 실제 카메라를 열지 않았습니다.
--mode panda는 기존 한손 TCP 경로, humanoid는 G1만 전송, both는 두 경로. PoseLandmarker Lite + HandLandmarker 2손, 미러 프레임에서 pose 손목과 hand 손목의 최소 거리로 연결. One-Euro로 world pose/양손 필터링. 제어/미리보기는 latest-only 별도 스레드, 스레드별 requests keep-alive. 프리뷰20Hz 제한 제거, 처리 프레임마다 JPEG 전송.

## 매핑
미러 pose LEFT는 robot LEFT. 몸 좌표 x 전방/y 왼쪽/z 위. 허리 ZXY yaw/roll/pitch. 어깨-팔꿈치-손목 방향을 로봇 팔 길이로 정규화. 기본 wrist, 선택 fingertips는 검지/중지 끝 평균 방향. 손바닥 방향 선택은 API /humanoid/options.
MCP는 근위지골의 손바닥 평면 투영과 실제 지골 사이 각도로 굽힘 측정하여 부채꼴 펼침을 배제. Dex3-1 검지에 사람 검지, 중지에 사람 중지/약지/소지 평균. 엄지 MCP/IP와 엄지 끝의 상대 거리로 굽힘/대립. 엄지 빨강/검지 노랑/중지 초록/약지 파랑/소지 보라. 로봇은 3색만 사용. 사람 손바닥 중심은 작은 흰 점.

## 진단과 한계
관절패널 각도/한계 막대/속도, IK 오차/반복/ms/경고 표시. G1 목 관절 없음. 골반 고정, 자기충돌 회피 없음. 손 미감지/입력 .35초 이상은 hold. 관절 속도/가속도 제한은 시뮬레이션 명령 제한이며 실물 안전 보증 아님.
실시간 IK restarts=0, 양팔8회. 팔꿈치 허용오차5mm로 통일. 30fps는 목표이며 실측 미달은 changes 문서에 공개. 합성 스트림은 GT 생성 입력으로 방향/회귀 검증이며 실제 사람 추적 정확도가 아닙니다.

## 11/3 옵션 정정
트래커 기본은 --mode panda이며 이때 Pose를 생성하지 않고 한손만 인식합니다. G1은 명시적으로 --mode humanoid 또는 both를 사용합니다. --infer-width 640(기본)/480/320, --serial(비교용). 손이 있는 녹화본에서는 병렬640 약27.3Hz로30미달. 손목 연결은2x2최소합 전수할당. Pose가 없으면 좌우를 연결할 수 없어 G1 손가락도 hold합니다. 실제카메라가 분리돼 실카메라 검증은 미실시입니다.
