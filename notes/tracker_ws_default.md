# Windows 트래커 기본 전송 WS 전환

## 목적과 근거
- `notes/verify_t.md`의 V-T 3쌍 교차 측정에서 update `post_ms p95`는 HTTP 21.3~22.7ms, WS 2.27~2.43ms였다.
- 서버 main CPU 차이는 WS-HTTP -2.3%p, 부트스트랩 95% CI [-2.9, -1.6]으로 0을 포함하지 않았다.
- 처리율은 양쪽 모두 100%였고 트래커 Hz·서버 수신 Hz 차이의 CI는 0을 포함했다. 따라서 처리율 개선은 주장하지 않고 전송 지연과 서버 main CPU 감소만 전환 근거로 삼는다.

## 구현
- `tools/teleop_tracker_win.py`
  - `--transport` 기본값을 `ws`로 변경했다. `--transport http`를 명시하면 기존 HTTP `post` 경로를 그대로 사용하고 WS 객체를 만들지 않는다.
  - 404 또는 `websocket-client` 미설치처럼 WS 미지원이 확실하면 경고를 한 번 출력하고 같은 요청을 HTTP로 보낸 뒤 세션을 HTTP로 고정한다. WS 재시도는 트래커 재시작이 필요하다.
  - 연결 거부·timeout 같은 일시 실패는 HTTP로 임시 우회하고 30초마다 WS 복귀를 시도한다. 경고의 오류 요약은 첫 유효 줄 200자 이하로 제한한다.
  - WS가 한 번 성공한 뒤 연결이 끊기면 `WebSocketTransport.request()`의 기존 정책대로 요청 안에서 1회 재연결한다. 두 시도가 모두 실패해도 HTTP로 전환하지 않으며 다음 요청에서 다시 WS 연결을 시도한다.
  - `websocket-client`가 없으면 `python -m pip install websocket-client==1.8.0` 안내를 포함한 경고 후 HTTP로 폴백한다.
  - metrics의 `transport`는 실제 사용 전송(`ws`/`http`), `transport_requested`는 요청값, `transport_fallback`은 폴백 여부를 기록한다. preview는 계속 HTTP다.
- `tools/humanoid_launch.ps1`: 트래커 명령에 `--transport ws`를 명시했다.
- `README.md`: 기본값, 의존성 미설치 폴백, 세션 중 재시도 정책, `--transport http`, V-T 근거를 갱신했다.

## 단위 테스트
- 인자 기본값 `ws`와 명시적 `http` 파싱.
- 일시적 WS 실패 시 HTTP로 같은 요청을 넘기고, 30초 전에는 재시도하지 않으며 30초 뒤 WS 복귀.
- 404는 세션 고정 HTTP, 오류 요약 200자 이하, 재시작 안내.
- `websocket-client` 미설치 안내와 세션 고정 HTTP 폴백.
- 기존 WS 연결 중 끊김의 1회 자동 재연결 테스트 유지.
- 실행: `PYTHONPATH=$PWD python -m pytest -q tests/test_realtime.py -k "windows or ws_mode"`
- 정책 보완 후 관련 테스트 결과: 6 passed, 6 deselected, warning 1개(pytest 플러그인 deprecation).

## V-J 직접 검증
- 원자료: `bench/verify_j/out/`, 상세: `notes/verify_t.md` 끝 V-J 섹션.
- 플래그 없음: master 서버에서 실제 `transport=ws`, post p95 2.18ms, 901/901.
- WS 미지원 서버: HTTP 자동 폴백, 경고 1회, 901/901, 오류 0.
- `--transport http`: WS 측정값 없음, post p95 약 23ms로 기존과 동일.
- 22분 WS 장시간에서 누수 징후 없음, 서버 재기동 재연결 3/3 성공.
- V-J가 직접 실행한 전체 pytest는 93 passed, 5 warnings.
- 최종 판정: **조건부 PASS(스톡 영상·22분 한정)**. 실카메라와 1시간 이상은 미실시다.
- 이후 리뷰 지적에 따라 경고 요약 제한과 일시 실패 30초 재시도 정책을 추가했다. 보완 후 측정 락 안 전체 pytest: **94 passed, 5 warnings, 44.32초**.
