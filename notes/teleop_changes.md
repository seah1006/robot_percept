# T round1 변경 및 현재 검증 상태
- 신규: sim/teleop.py, web/teleop.py, web/static/teleop.js, tools/teleop_tracker_win.py, tests/test_teleop.py, notes/teleop.md.
- 기존: web/app.py Blueprint 등록 2줄, web/sim_worker.py import/init, 명령 시 모드 해제, tick 호출. UI script hook은 I-F가 추가.
- smoke 2 passed (18.83초). Tasks API 실제 카메라 인식 및 JPEG preview HTTP 업로드 확인.
- 녹화: Windows Documents/sam_camera/teleop_test_fast.mp4/.jsonl, 61프레임 11.2초, 5.44Hz, 네트워크 오류0. 약30Hz 목표 미달. 전체 CPU/GPU 공유 환경에서 수집한 수치이며 FPS하락10% 미만은 아직 독립 검증되지 않음.
- Windows localhost IPv6 fallback 지연을 피하기 위해 tracker는 localhost를127.0.0.1로 정규화. MSMF HW transforms 비활성화.
- V-T 최종 PASS 대기. V-C에 worker thin hook 회귀 리뷰 요청.

## Round2
- V-T round1: safety PASS, realtime FAIL (1.4s lag); corrected servo to run on simulation clock at50Hz inside500Hz physics step loop, independent of render wall-time truncation.
- Camera capture latest-frame thread drops stale frames; inference/record640x360; asynchronous JPEG preview uploads avoid control-path blocking.
- Compact recording179frames11.14s=16.07Hz, no network errors. Later async-preview rate measurement pending.
- UI moved to normal document flow, avoiding pick/place button overlay.
- smoke + API regression3passed8.30s.

## Round3
- V-T round2 still slow; corrected accumulated joint position command integration (previously each tick restarted at measured q). Integrated commanded trajectory remains .65rad/s-limited, gain8, Cartesian error clip.06m.
- /teleop/status now exposes rtf, sim_time and servo_ticks.
- Clean synthetic30Hz FPS benchmark (before round3 gain change): baseline median19.45FPS; teleop18.9FPS =2.83% reduction.
- Control HTTP upload now latest-only asynchronous thread as well, so inference never waits for HTTP. JPEG sender separate latest-only thread.

## Round4 안전 안정화
- 모든 measured-q hold를 jointlimits로 clip, worker tick exception은 teleop만 비활성화하여 시뮬레이션 crash 방지.
- 명령-실측 관절 lead±.04rad antiwindup, 명령속도 .45rad/s, gain4, qvel damping .6.
- tests/test_teleop.py:4000step square/circle actual qvel<=.65rad/s + out-of-limit hold regression 통과 (2passed8.72s).
- 최종 HTTP sender trust_env=False로 Windows proxy lookup 제외, 제어/preview latest-only 별도 스레드. 무손 입력 송신 약24.8Hz; 실제 손 live 측정은18.05Hz까지 확인. 손20Hz 달성은 아직 검증되지 않음.
- 검증용 hand-positive JSONL: Windows Documents/sam_camera/teleop_round2_async.jsonl (89/89detected). 기존 MP4는 skeleton이 포함되어 재인식에 부적합할 수 있음. 최신 tracker는 raw640x360 MP4를 기록하고 skeleton은 미리보기에만 그려서 재현성 개선. MP4는30fps, 정확한 녹화 시간 간격은 JSONL replay 사용.
- V-T round4 최종 PASS 대기.

## Round4 V-T PASS / Round5 UI
- V-T control/safety PASS: step1.2s no overshoot, circle RMS5mm lag.4s, square RMS36-43mm lag.5-.6s. handloss/stale hold<=1mm; reset/pick/place 회귀없음.
- Round5: NEW web/static/teleop.css, own teleop.js 비교모드, MJPEG preview endpoint, telemetry preview_hz/cameraK/Twc/neutral/origin. 기존 #video-wrap을 이동 후 복귀하여 클릭 이벤트 유지. Mobile stack, Motion fade/slide, target/trail projection, inversemapped handworkspace, nohand 안내.
- 기본 front 영상 기준 handx→world+y→viewer-right 방향 일치. cv2.flip 한 번만 적용.
- UI/영상/FPS V-T 검증 대기.
