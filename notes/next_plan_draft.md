# robot_percept 다음 작업 계획 (초안 v0, 부모 작성)

프로젝트: 개인 프로젝트. 가상 로봇만 사용(실제 카메라/로봇 연동 안 함). 교수님 참고 MD(ROBOT_PERCEPT.md): SAM2.1 + PyTorch3D + FoundationPose + Flask/pyrealsense2/trimesh/cadquery(STP 업로드). 강의 PDF 15p 응용: SAM mask → FoundationPose 6DoF → depth → grasp → 로봇 좌표.
현재 상태(WSL ~/work/robot_percept): MuJoCo Panda SimEnv, grasp planner(top/side/top-cap, 20/20 mustard/box/cup/multi), grasp-assist weld(시뮬 기법), Flask 웹(SAM2 small 클릭 mask → FP register → track 10~20fps, 추정 자세로 pick, 놓기 위치 클릭, 놓은 뒤 재인식, CAD STP 업로드), 영상 28fps, 모션 UI(Magic UI/Motion 참고), FP 시뮬 정확도 ~1mm/1.5°.
알려진 문제: SAM2 클릭 mask IoU가 가끔 11% 수준(자세는 정확), 놓은 뒤 로봇이 어색한 자세로 머묾, 머스터드 grasp planning p95 4s, 추적 FPS 여유 작음(공유 GPU 시 8.9), 서버는 Aside 세션에 묶여 있음(run_web.sh 존재), 평가가 시나리오별로 흩어져 있음.

## 우선순위 초안
P1 인식 품질: SAM2 mask 개선(박스/다중점 프롬프트, base_plus 모델, mask 후처리, depth 일관성 검사) + 실패 시 재시도/사용자 안내. 목표 IoU 중앙값 > 0.85.
P2 체계적 평가(보고서 핵심): eval/run_benchmark.py — 물체(mustard/box/cup) × 랜덤 장면 N=30 × 조건(GT 자세 / FP 추정 / depth 노이즈 / 조명·텍스처 랜덤) → 등록 오차, 추적 오차(이동 중), 집기 성공률, 처리시간. 표·그래프 자동 생성.
P3 강건성: depth 노이즈 모델(D405 유사), 조명/텍스처 domain randomization, 부분 가림 시나리오.
P4 기능/UX: 놓은 뒤 home 복귀, 여러 물체 연속 정리(task queue), GT 표시 토글, CAD 업로드 → FP 등록까지 E2E, 에러 메시지 개선.
P5 엔지니어링: git 저장소, README/설치 스크립트, pytest 회귀 테스트, 설정 파일(config.yaml), 로그 정리.
P6 산출물: 보고서(구조도, 단계별 결과, 평가표, 한계: grasp-assist weld 명시), 데모 영상(브라우저 녹화), 발표 자료.

## 진행 방식 초안
각 단계마다 구현자(Codex) + 검증자(Claude 별도 세션) 교차 검증, 포트 분리(5081/5082), 사용자 5080 유지, 백업 후 진행, 합격 기준 사전 합의.
