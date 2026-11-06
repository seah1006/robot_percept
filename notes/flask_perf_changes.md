# Flask 성능 개선 기록 (I-F)

## 조건과 F0
- Flask/Werkzeug 유지, 기준 `wip/r2` `cc37144`, PERCEPTION=stub, AMD RX 7600(Mesa D3D12).
- 입력은 합성 사람 랜드마크와 노이즈 JPEG이며 실카메라, MediaPipe 실처리, GT 보조는 없다.
- F0(V-F, Windows Python 3.13.7 urllib3 2.8.0 → WSL): update RTT p95 18.18/19.87ms, 처리율 100%, 30.0Hz. G1 32.00fps, 프록시 p95 30.5/32.6ms, receive→publish p95 48.6/49.9ms. W2 main CPU 20.9/21.8%, tree 87.6/95.5%, 상태 폴링 23.75/23.8 req/s.
- 구현 측정은 `/tmp/rp_measure.lock`, 포트 5093에서 A/B/A/B로 했다. 운영 코드에는 측정 락을 넣지 않았다.

## F1: 저비용 후보
### HTTP/1.1 keep-alive, 폐기
- `WSGIRequestHandler.protocol_version="HTTP/1.1"` 후보를 만들고 urllib3 PoolManager(maxsize=1)에서 실제 peer port를 기록했다.
- 기본 후보와 HTTP/1.1 후보 모두 5회 요청의 peer port가 5회 모두 달라 연결 재사용 0/5였다. 원자료 `bench/flask_perf/out/keepalive_probe.json`.
- Werkzeug 3.1.9 `WSGIRequestHandler.run_wsgi`가 protocol_version과 무관하게 `Connection: close`를 강제한다. 단순 변경은 효과가 없고 내부 run_wsgi 복제는 body drain/413/WebSocket 안정성 위험이 커서 후보를 전부 제거했다.

### 상태 JSON/폴링 프로파일
- F0 응답 p95는 humanoid 6.7~7.0ms, teleop 9.5~9.8ms, app 12.5~13.8ms였다. 표시 필드를 제거하면 UI 동일 조건을 깨므로 JSON 축소는 유지하지 않았다.
- 세 HTTP 폴링은 23.8 req/s였다. 개별 미세 조정 대신 F3 단일 push와 자동 폴백으로 통합했다.

## F2: 트래커 입력 WebSocket
- `flask-sock==0.7.0`, `simple-websocket==1.1.0`의 `/tracker/ws` 추가. 기존 HTTP 엔드포인트는 유지한다.
- text route/data envelope로 JSON 제어 update를 보낸다. HTTP와 WS가 같은 update 검증 함수를 호출한다.
- V-F 1차 Windows 측정에서 binary WS preview가 p50 44ms/p95 48ms, 900개 중 664~668개(약 22Hz)로 회귀했다. JPEG 10KB 축소와 TCP_NODELAY도 효과가 없어 이 경로는 폐기했다.
- 최종 `--transport ws`는 update만 WS, preview JPEG는 기존 HTTP를 유지하는 hybrid다.
- route 상한은 teleop JSON 8192B, humanoid JSON 65536B, JPEG 250000B다. Windows localhost→WSL relay의 큰 프레임 backpressure를 피하려 WS transport cap은 6MB로 두고, 전체 프레임을 drain한 뒤 route에서 413을 응답한다. 5MB binary는 WSL 0.191초, Windows→WSL 0.139초에 413 응답했고 서버가 생존했다.
- Origin 없음(동기 트래커)은 허용하고, Origin이 있으면 Host와 일치할 때만 허용한다. 다른 Origin은 1008로 종료한다.
- 트래커 `--transport http|ws`, 기본 `http`. `websocket-client==1.8.0` 동기 연결을 스레드별로 쓰고 끊김 시 한 번 자동 재연결/재전송한다.

### 자체 A/B (WSL 내부, G1 OFF, 각 10초 A/B/A/B)
| 경로 p95 ms | HTTP A1/A2 | Hybrid B1/B2 | B-A 평균, bootstrap 95% CI |
|---|---:|---:|---:|
| humanoid update | 3.732 / 3.600 | 1.967 / 1.439 | -1.963 [-2.161,-1.765] |
| JPEG preview(모두 HTTP) | 3.647 / 3.664 | 3.102 / 3.061 | -0.574 [-0.603,-0.545] |
- 각 슬롯 300/300 성공, 오류 0. 원자료 `bench/flask_perf/out/quick_ab.json`, CI `quick_ab_ci.json`.
- V-F hybrid 3쌍 분리 측정(Bhttp→Bws+poll): update p95 -17.64ms CI[-20.47,-16.13], 서버 main CPU -2.50%p CI[-2.8,-1.9], 처리율 100%.
- preview는 900/900 처리로 30Hz를 회복했지만 p95는 +4.20ms CI[+2.81,+6.50] 증가했다. transport는 동일 HTTP이므로 슬롯/WS 공존 영향이 남은 한계이며 절대값 24~25ms는 F0 범위(14~26ms) 안이다.

## F3: 브라우저 상태 push와 폴백
- `/status/ws` 한 연결에서 기존 payload를 `robot`, `teleop`, `humanoid` 타입으로 전송한다.
- robot 3Hz, 활성 teleop/humanoid 10Hz, 비활성 1Hz다. `web/monowait.py`의 monotonic `sleep_until`만 사용한다.
- push 이벤트는 `*-push`로 분리했다. app 렌더 후 기존 `robot-status`를 한 번만 발행해 focus.js 호환을 유지하며 재귀하지 않는다.
- 연결 실패/종료 또는 2.5초 무수신이면 기존 세 폴링이 자동 재개된다. UI 렌더 코드는 동일하다.
- 상태 연결 상한은 8개다. 9개 동시 연결에서 8개만 데이터를 받았고, 24회 열고 닫은 뒤 서버 스레드 수는 28→28로 누수 없음.

### 자체 A/B (G1/teleop OFF, 각 10초 A/B/A/B)
| 방식 | 빈도 | 서버 main CPU |
|---|---:|---:|
| 기존 HTTP 폴링 | 23.0 req/s / 23.0 req/s | 7.3% / 6.9% |
| 단일 push | 4.9 msg/s / 4.9 msg/s | 2.5% / 2.7% |
- 자체 G1 OFF CPU push-poll 차이 -4.5%p, bootstrap 95% CI[-4.8,-4.2].
- V-F G1 ON 3쌍 분리 측정(Bws+poll→Bws+push): main CPU -5.37%p CI[-5.8,-4.7], tree CPU -7.93%p CI[-9.3,-5.4], 요청/메시지 빈도 -9.79/s CI[-9.80,-9.78].
- 분리 측정은 `VF_TRANSPORT=ws VF_STATUS=poll`(F2)과 `VF_TRANSPORT=ws VF_STATUS=push`(F3 증분) 조합을 사용한다.

## 테스트와 한계
- 관련 단위 테스트와 이벤트 재귀·hybrid 경로 회귀 테스트를 포함했다. 최종 전체 pytest는 측정 락 안에서 81 passed, 5 warnings.
- 실제 Flask smoke: 정상 update, 잘못된 JSON 400, 250001B JPEG와 5MB binary 413, 오류 후 연결 생존, status 세 타입, cross-origin 종료, 8연결 상한, 24회 종료 누수 없음.
- 브라우저 실화면 확인은 구현 서브에이전트의 UI 금지 제약으로 V-F에 요청한다.
- 실제 카메라·MediaPipe 포함 절대 판정은 미실시다.

## 의존성
- 서버: `flask-sock==0.7.0`, `simple-websocket==1.1.0`.
- 측정 및 Windows 트래커: `websocket-client==1.8.0`.
- conda env `robot_percept`에 pip 설치했고 `notes/rp_constraints.txt`와 README에 고정했다.
