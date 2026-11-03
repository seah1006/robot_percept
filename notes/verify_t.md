# V-T 검증 (동작 따라하기, 라운드 1) - 포트 5090, 녹화/합성 입력만 사용
verdict: FAIL (라운드 1) - 안전/게이팅/히스테리시스/스모크 PASS, 실시간성(추종 지연, 명령률) FAIL
## 측정 (스크립트 bench/verify_t/*.py, 합성 30Hz 입력, 시스템 load avg ~16 공유 환경)
- 입력 수신률 27~30Hz (서버 /teleop/status hz 29~33). 그러나 로봇 갱신(tick)은 sim 루프(render 포함) 속도에 묶임: /status 프레임 8~9Hz.
- 추종 지연: teleop_target 대비 TCP 최적 지연 1.4s (탐색 상한 도달), RMS 45mm(원) / 73mm(사각, 지연 보정 후); 지연 0 일 때 86~107mm.
- 기대 경로(스케일 매핑) 대비 RMS 46mm(원) / 88mm(사각) (최적 지연 1.45s).
- 관절속도 (status 샘플 기준) 최대 0.68~0.79 rad/s (한도 .65에 근접/약간 초과, 샘플 시간 오차), 한 틱 최대 dq 0.040~0.042rad -> IK 점프 없음.
- 원인: tick 이 sim 루프당 1회, dt=min(.04, 경과) 로 cap -> 루프 < 25Hz 면 시뮬 시간이 벽시계보다 느리게 진행(로봇이 느려짐).
## 안전 PASS
- 손 소실(detected=false): 4.5mm 이후 정지, 이후 0mm 이동. 패킷 중단(stale .3s): 정지(0.8s 내 10mm 이후 0).
- 작업공간 클램프: 극단 입력 시 target [.25,.35,.85] / [.70,-.35,.36] 로 클램프.
- 핀치 히스테리시스: <.28 닫힘, .28~.42 유지, >.42 열림 (12단계 확인).
- 잘못된 입력(-1,2,'a') 400. reset 시 teleop 자동 OFF. OFF 후 /click + pick(mustard 잡음)+place(err 0.8mm, upright 1.0) 정상.
- --replay 61 updates 10.1s 정상 재생, 타겟 이동 확인.
## UI
- 따라하기 모드 패널 펼침/상태/미리보기 표시, JS 에러 0. 단 좌하단 고정 패널이 집기/놓기 버튼을 가림 (screenshot ui_teleop.png).
## 기존 기능
- pytest tests/test_smoke.py: 2 passed. /click OK. FPS 회귀: 공유 부하로 측정 불가 (렌더 11~12 FPS 텔레옵 중 vs 부하 타 프로세스).
## 라운드 2 (재시작 후, 같은 합성 입력)
- verdict: FAIL (추종 속도). status 프레임 11~13Hz, 입력 30Hz 수신.
- 관절속도 최대 0.30~0.31 rad/s (이전 .68~.79) -> 속도 한도 OK, IK 점프 없음(단일 틱 dq .02~.03).
- 그러나 지연 >=1.45s(탐색 상한), 원 RMS 56mm, 사각 RMS 81~99mm.
- 스텝 응답(타겟 +0.14m y 점프): TCP가 약 22 mm/s 등속 램프로만 이동 (5s 후 0.104m). 설계상 오차 클립 .03m*게인4 = 최대 ~120mm/s 여야 함 -> 실제 5배 느림. sim 시간이 벽시계보다 느리거나(RTF<1) 서보 게이팅/게인 문제.

## 라운드 3 (command 적분 수정 후) - FAIL (안정성)
- 스텝 응답 개선: +0.14m 점프를 ~0.7s에 도달, 오버슈트 ~8% (0.151), 정착 0.140. (이전 22mm/s 램프 해결)
- 하지만 사각 경로 10s: 상태 샘플 기준 관절속도 최대 2.58 rad/s, 한 샘플 dq 0.27 rad (한도 .65), RMS 124mm(최적 지연 .25s) -> 불안정/점프.
- 이어서 worker crash: state=crashed, ValueError: Arm target outside joint limits at sim/teleop.py:17 `self.env.set_arm_target(self.env.arm_qpos())` (측정 q가 한계를 살짝 벗어나면 hold 호출이 예외). 서버 sim_time 12.9 에서 정지. rtf 0.95, servo_ticks 805.
- 요청: hold/target 은 clip(q, limits) 후 전달, 예외는 worker 를 죽이지 않도록 teleop.tick try/except -> teleop_enabled=False; command 적분은 측정 q 와 괴리(windup) 제한 (|command-q|<=0.1rad), 속도 .65 rad/s 보장 테스트 추가.

## 라운드 4 - 동작/안전 PASS (새 서버 5090)
- 스텝: +0.14m 를 ~1.2s 에 정착, 오버슈트 없음(0.1399). rtf 1.0, servo_ticks 증가, error None.
- 원 경로: 최적 지연 0.4s, RMS 5.0mm(기대 경로) / 5.4mm(target). 사각: 지연 0.5~0.6s, RMS 36~43mm (코너 둥글림).
- 관절속도(프레임 타임스탬프 기준): p50 .26-.29, p95 .55, max .63-.68 rad/s (샘플링 오차 포함, 한도 근처). 한 샘플 dq<=.11rad. 크래시 없음.
- 손 소실: 0.2mm 이후 정지. stale: 1mm 후 정지. 핀치 히스테리시스 OK. 잘못된 값 400. 작업공간 클램프 OK (x .25~.70, z .36~.85, y +-.35 도달/수렴). reset 시 teleop OFF. OFF 후 click+pick(mustard)+place err .8mm OK.
- 남은 항목: 라운드5 UI(나란히 비교 레이아웃, 방향 일치, 프리뷰 fps), 실제 손 영상 replay, 메인 FPS 회귀.

## 라운드 5 (UI 나란히 비교) - 판정: 조건부 PASS (UI/방향/안전 PASS, FPS 회귀·프리뷰 fps FAIL/미달)
- 레이아웃: 켜기 -> 좌 '내 카메라·손 추적'(스켈레톤, 초록 작업공간 박스) | 중간 배지(손 없음/Hz/전송 ms/집게/카메라 FPS) | 우 로봇 시뮬레이션(동일 크기). 420px 폭에서 위/아래 스택 OK. 끄기 -> #video-wrap 원위치, 이후 물체 클릭 선택/포커스 뷰 정상, 켠 상태에서도 포커스 패널 유지. JS 오류 0.
- 방향: 합성 입력 x+.15 -> TCP 이미지 u +51px(오른쪽), y-.15(손 위) -> v -50px(위). 일치.
- 손 있는 jsonl replay(teleop_round2_async.jsonl): 입력 11->20Hz, detected True, 집게 닫힘/열림 반영, 목표 이동. mp4 재처리는 스켈레톤이 그려진 영상이라 손 미검출(0 hands) -> 영상 입력 경로는 jsonl 로 검증.
- 프리뷰: status preview_hz 11~14Hz (목표 >=15 미달, 공유 부하 하 측정), tracker 영상 처리 13~19Hz.
- 메인 FPS(브라우저 닫고 /status fps 평균, 공유 부하 노이즈 큼): OFF 14.3/17.0, ON idle 19.0/12.5, ON +30Hz 입력 10.6/9.0 -> 입력 스트리밍 시 -26%/-47% (목표 <10% 미달). 서보 틱(50Hz, 야코비안)·status 직렬화 비용 의심. 요청: tick 비용 프로파일/ status 갱신 분리.
- 서버 5090이 가끔 외부 요인으로 종료됨(원인 불명, 로그 에러 없음).
- 스크린샷: tmp/vt/ui_on_focus.png, ui_on_hand.png, ui_mobile.png (얼굴 포함 녹화 프레임 - 공유 주의).
