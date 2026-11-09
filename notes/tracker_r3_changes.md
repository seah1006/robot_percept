# I-K3 r3 트래커 (2026-11-09)

## 상태
- 구현 완료, 독립 실측 판정 대기. V-T3: uQYJdDaotP8YMpsv.
- 서버/web 수정 0, Documents 복사본 수정 0, 커밋 0, 자체 장시간/성능 측정 0(검증자 슬롯 우선).
- 최종 tracker SHA256: c98c3db3d715330661d12cac9285202611f5b98a8dfec83efbb4d83ddbf98a4e (FREEZE 통보).

## 변경
1. tools/teleop_tracker_win.py: 이미 WS가 성공한 이후 연결이 실패하면 기존에는 raise만 하여 HTTP 우회가 없었다. 이제 임시 HTTP 우회 후 30초 재시도. 404/모듈 부재의 영구 폴백 정책은 유지.
2. transport_events: ws_connected/http_fallback. elapsed_s=transport 생성 후 시간, qpc_s=Windows 공통 perf_counter 시각. ws_failures=폴백 발생 수, ws_connections=성공한 transport 전환 수(내부 WebSocketTransport의 자동 재접속 횟수와 다름). transport_fallback은 이전과 같이 '폴백을 사용한 적 있음' 의미.
3. 300초마다 stdout telemetry: 처리율 window_hz, updates, sent_updates, 누적 network_errors/ws_failures/ws_connections, 현재 transport.
4. preview_post_ms_p95 추가. preview는 HTTP 기본 유지.
5. bench/tracker_r3_company.py: 회사 MP4 loop, humanoid HTTP/WS 교대, raw stdout/stderr/metrics/samples/result 보존. 시작 후 첫 입력 증가+2초 이후 완전한 30초 창의 input_count/preview_count 차이로 수신Hz/preview fps 산출. 누적 상태의 순간 Hz를 판정에 사용하지 않음. 출력 폴더 기존 존재 시 실패(덮어쓰기 없음).
6. --long --seconds 3600: 5분 간격 tracker live PID WorkingSet64 및 --server-pid WSL서버 VmRSS 기록. 서버 tree RSS는 아님. 처리율은 telemetry, 오류/재연결은 이벤트+telemetry와 최종 metrics. 장시간 추이 성능값은 관측 참고만.
7. bench/tracker_r3_recovery.py: localhost forwarding proxy가 10~15초 WS만 끊고 upgrade에 503 응답(404는 영구 폴백이므로 사용 안 함). HTTP는 통과. 55초 창+7초 tracker 실행 후 recovery.json의 실제 QPC return_after_restore_s, within_30s 수집. 실제 장애/복귀가 없으면 PASS 불가. tracker 초기화가 10초 넘으면 fault 이벤트가 없을 수 있으므로 원자료 검사 필수.
8. bench/tracker_r3_slots.sh: async/compact/test_fast × HTTP/WS 3쌍. 한 슬롯 2창(각37초), measure flock 획득/해제, 시작/종료 load+GPU 기록. SERVER는 별도 G1 ON. 5080 금지.
9. bench/tracker_r3_contract.py: 이미 성공한 WS -> HTTP -> WS 계약 8assert.
10. notes/TEAM_R3_schedule.md: V-T3 장시간 일정 기록 자리 생성. 실제 시작은 검증자가 기록.

## 검증 수치
- tests/test_realtime.py: 12/12 PASS, 0.37초.
- 신규 established WS fallback 계약: 8assert PASS.
- compileall 3파일 PASS; slots.sh bash -n PASS.
- 실제 처리율/수신Hz/preview fps/post p95/복구초/1h 누수: 아직 구현자 자체 실측 없음. V-T3 독립 측정으로 판정.

## 영상 선정 확정 (V-T3 정정 수신)
- V-T3 초기 direct detector 사전검출률은 flip을 생략하여 실제 tracker 파이프라인과 달랐음. 초기 final_hand0%/async65.2%는 무효.
- V-T3 실제 tracker 파이프라인 비교: 현재 c98c3db3와 3cf1b19 모두 final_hand 손69.7%/pose100%, async 손1.1%. 회귀 아님. 원자료 bench/verify_t/out_r3/hand_regress/.
- 판정 영상 합의: 주 final_hand(89f, 640x360, 손69.7%/pose100%), 부 compact(179f, 자세 전용), 참고 test_fast(1280x720).
- 코드 비교: 1da4b93도 기본 infer_width640, 640x360 resize, 입력 flip1회, VIDEO 모드, humanoid num_hands2. 3cf1b19와 현재의 추론/검출 경로는 동일(현재 변경은 transport/telemetry/p95뿐). detection_counts는 hold/quality 처리 전 원 result.hand_landmarks에서 집계하므로 hold가 지워서0%가 되는 경로는 아님.
- 회귀가 확인되면 pipeline/frame/resize/model 옵션을 실제 동일 입력으로 분리 검사. 추측만으로 flip/threshold/기본값 변경 금지.

## preview +3~9ms 조사
- 코드: preview HTTP route는 JPEG bytes를 수용/저장 후 짧은 JSON 응답; update WS 옵션과 preview HTTP 전송 자체는 분리되어 있음. 현재 서버 수정 없음.
- 기존 notes/flask_perf_changes.md의 증거: binary WS preview p50~44/p95~48ms, 900 중664~668개(~22Hz), JPEG10KB/TCP_NODELAY에도 개선 없었음. 따라서 preview WS 옵션 재도입은 현재 근거 없음.
- 기존 HTTP p95 차이 +4.20ms, bootstrap95%CI [+2.81,+6.50]는 동일 HTTP 경로에서 WS update 공존/slot 영향과 분리되지 않음. 이번에는 preview_post_ms_p95 계측을 추가했으나 새로운 원인 실험은 미실시. 원인 규명은 [blocked] 추가 교차 실측 필요. 기존 delayed ACK 설명을 확정 원인으로 주장하지 않음.
- 장시간 metrics는 기존 리스트 누적 방식이라 RSS 증가에 샘플 보존 비용이 포함됨. 누수와 구분 필요.

## 재현 명령
Windows Python312 환경변수 PYTHONHOME/PYTHONPATH/VIRTUAL_ENV/PIP_PREFIX/PYTHONNOUSERSITE 제거 후:
- 교차(권장): WSL `bash bench/tracker_r3_slots.sh 'C:\Users\USER\AppData\Local\Temp\rp_t3_NEW' http://127.0.0.1:5095` (flock 내부 실행).
- 개별: `python bench/tracker_r3_company.py --url http://127.0.0.1:5095 --out <새폴더> --seconds 30 --order http,ws --videos <async.mp4>` (바깥 WSL measure 락 필요).
- 복구: `python bench/tracker_r3_recovery.py --url http://127.0.0.1:5095 --out <새폴더> --video <async.mp4>` (바깥 WSL measure 락 필요).
- 장시간: `python bench/tracker_r3_company.py --url http://127.0.0.1:5095 --out <새폴더> --long --seconds 3600 --server-pid <WSL PID> --videos <async.mp4>` (락 밖, schedule 실제 시작/종료 기록).
- 계약: `PYTHONPATH=$PWD python bench/tracker_r3_contract.py`.

## 재개 지점
- 실행 중인 구현자 서버/벤치 exec 없음. 5095 사용하지 않았음.
- V-T3에 FREEZE 및 명령 전달 완료. 검증자는 5092.
- 다음: final_hand 회귀 아님 확인 완료. V-T3의 bench/verify_t/r3_{run.sh,cross.py,win_run.ps1}로 5092 독립 교차/복구/1h 결과 대기. tracker TEMP vt3 사본 c98c3db3. 하네스 지적 수신 후 수정. tracker 수정은 재-FREEZE 협의 후.
- 회사 실카메라: 미실시(카메라 분리).

## V-T3 중간 실측 수신 (최종 판정 아님)
- 조용 슬롯 final_hand: HTTP 처리율98.89/99.78%, WS100/100%; post p95 HTTP23.5/21.8ms, WS6.6/4.1ms; 수신Hz29.68~29.81; neural p9536~43ms. 기준 미달창 존재하므로 절대PASS 아님.
- E eval 락밖 CPU91%/RSS7.7GB 동시 진행 슬롯은 오염으로 폐기, 재측정 대기. I-K3 락밖CPU 작업0 유지. 장시간은 최종 성능슬롯 이후 V-T3 실행 예정.
- 지표 해석: processed_input_ratio=count/(floor(processing_seconds*source_fps)+1)는 시간슬롯 충족률. video cap.read는 순차이며 source_queue max2 포화 시 put 재시도하여 프레임을 버리지 않음. neural이33ms를 넘으면 백프레셔/처리지연, 이후 pacing sleep0으로 따라잡음. seconds 종료 시 아직 처리 못한 due 시간슬롯이 unprocessed_source_slots이며, MP4 원본 프레임 실제 드롭 수와 다름(video dropped_frames=0). 종료 직전 다음 추론 선제 submit으로 선독/추론 완료했으나 count에 집계되지 않은 프레임이 있을 수 있음. update/preview latest-only 송신큐는 덮어쓰므로 송신 누락 가능, sent_updates와 실제 서버count로 별도 확인.

## 13:06 이후 preview 조사 인계 (새 성능 측정 없음, FREEZE 유지)
### 확정 근거와 미확정 원인 구분
1. 상대 회귀와 경로 오버헤드는 다른 수치다. verify_f 최종 유효 J/JG/I2 측정에서 HTTP 폴백 preview p95는 기준 대비 +3.0ms CI[+0.4,+5.6], hybrid는 +9.1ms CI[+4.8,+13.0]. 앞선 F2/H 계열은 worker 잔존66개/5092 relay CLOSE_WAIT 오염 기록이 있어 최종 판정 근거로 쓰지 않는다.
2. 유효 후속 3창: Windows 송신 preview HTTP p95 23.77/22.89/24.74ms, WSL 내부 송신 3.62/3.73/3.67ms. 각각 preview100%, G1 약32fps. Windows↔WSL 경로/송신기 환경을 포함한 차이가 크다는 증거이나, 동시 동일호스트 A/B가 아니므로 이 차이 전부를 relay 단일 원인이나 +3~9ms 상대 회귀 원인으로 단정할 수 없다. 당시 Windows Python3.13.7/urllib3 2.8.0과 WSL Python3.12의 차이도 교란이다.
3. HTTP 연결 재사용 부재는 확인된 구조적 비용: flask_perf_changes F1 peer port5/5 변경, Werkzeug run_wsgi가 Connection:close 강제. PoolManager(maxsize1)이어도 매 요청 연결 생성/종료 비용이 남는다. 단 HTTP 기준선에도 동일하므로 상대 회귀 +3~9ms 자체를 설명했다는 주장은 불가. protocol_version만 HTTP/1.1로 바꾸는 패치는 효과 없었고 미적용.
4. 현재 서버 accept_preview는 JPEG SOI/EOI/길이 검사+Condition 안 bytes 포인터 교체/카운터증가/notify_all만 한다. JPEG 디코딩·렌더·재인코딩은 이 route에서 하지 않는다. mutex는 status/preview getter와 공유하나 코드만으로 경합 비용을 확정할 수 없다.
5. tracker preview_encode_ms와 preview_post_ms는 분리되어 있다. post_ms에는 HTTP 연결/송수신 및 스레드 스케줄링 지연이 포함되고 JPEG imencode 자체는 제외된다. 기존 detail_ms http_headers/body는 humanoid update만 계측하므로 preview 병목 위치를 그 값으로 추론하면 안 된다. 이번 preview_post_ms_p95는 총시간만 신규 제공.
6. binary WS p50~44/p95~48ms 및 ~22Hz 회귀, JPEG10KB/TCP_NODELAY 실패는 기존 오염 F2 진단에서 나온 보조자료이므로 확정 원인 증거로 사용하지 않는다. 다만 개선 입증이 없는 옵션을 재도입할 근거도 없어 기본 HTTP 유지가 최소위험이다. tracker 주석의 delayed ACK 단정은 검증되지 않은 과거 가설이며 실제 원인 확정 아님(FREEZE 중 문구 수정 안 함).
### V-T3 후속 최소 분리 실험 제안(기존 필수 슬롯 우선)
- 동일 Python/urllib3/동일 JPEG/동일 부하, Windows localhost vs WSL IP 직접 접근 vs WSL 내부를 교대 30초창으로 비교. WSL IP 변경은 OS/서버 설정 없이 도달 가능할 때만. 각 슬롯 measure 락/5분 이내.
- inference 없이 preview만30Hz, preview+HTTP update30Hz, preview+WS update30Hz를 교대하여 WS 공존/MediaPipe 부하를 분리. headers/body/connect/전체 RTT, 응답 Connection 헤더/peer port를 수집. CI가0을 포함하면 차이 입증 안 됨.
- 새 서버 계측/preview WS/WSGI 내부 수정은 부모 승인 후에만. 현재 조사 결론은 '경로·연결 비용 근거 있음, +3~9ms 원인 미규명'. 새 측정/서버 변경0으로 V-T3 슬롯 방해하지 않음.
### 재개 지점 갱신
- 13:06 사용자 실카메라 테스트 종료/5080 정지는 부모 공지 수신 정보. 이후 V-T3 실카메라 수락 예정이며 과거 카메라 분리 상태를 현재 상태로 단정하지 않는다.
- V-T3가 final_hand 재측정·실카메라·WS 최악위상·1h 순차 진행. I-K3 CPU 작업/서버/측정0, FREEZE c98c3db3 유지. V-T3 지적 수신 시 수정 루프.
