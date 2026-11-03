# 물체 포커스 뷰 (F)

- `/click`으로 물체 선택 후 Motion 글래스 카드 표시. 확대 뷰 / 3D 모델 탭, 한글 자세/크기/정답 비교/IoU/상태/집기 모드.
- `web/focus.py` Blueprint. app.py는 create_app 등록 한 줄만 추가 (P와 협의).
- `/focus.jpg`: 요청 시에만 생성, 현재 추정 bbox 투영(마스크 fallback), 30% padding, 배경 dim 및 윤곽선. 최대 480px JPEG. 125ms 서버 캐시로 여러 클라이언트 공유. 클라이언트 약 6.7Hz, 숨김/3D 탭에서는 요청 중지.
- `/focus/status`: `T_world_cam @ T_cam_obj_est` 추정 월드 회전/위치, RPY, mm 크기 및 mesh URL. 기존 `/status` 3Hz 갱신에 연동.
- `/objects/<name>/mesh/<path>`: 실행 중 registry object mesh 부모 디렉터리 안으로 resolve containment 검사, OBJ/MTL/이미지 확장자만 허용. 절대 경로 입력/디렉터리 탈출/심볼릭 링크 탈출 거절.
- three.js 0.160.1 + OBJLoader/MTLLoader/OrbitControls 로컬 배포, MIT LICENSE 포함. 추정 방향(정답 회전 사용 안함), 월드 axes, 조명, 궤도/확대/자동회전. reset 시 GPU mesh 자료 해제.
- 테스트: `python -m pytest -q tests/test_smoke.py`: 2 passed (기존 경고 1개).
- FP 서버 5087 최초 모델 초기화가 수 분 걸려 실물 FP 포커스 스크린샷은 미완료. UI 경량 모드와 V-F 독립 검증 진행 중. FPS <10% overhead 기준은 V-F 측정 결과 참조. commit 하지 않음.

## V-F round2 PASS
FP mustard textured 3D and STEP cup crop/model/info verified. Reset/randomize hide, JS errors zero, traversal404. Frame_seq FPS: crop4.0/s versus disabled3.76/s, no degradation (GPU contention). Screenshots: session tmp/if/focus_*.png. Outline is estimated bbox hull (mask fallback), not current segmentation; disclosed in UI. Minor: extreme zoom may clip model; symmetric cup yaw error can be large; large textures have initial load latency.
