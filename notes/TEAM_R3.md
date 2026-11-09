# r3 라운드 공통 규칙 (회사 PC, 2026-11-09~, 부모 1NIgF2z2BvfBSkOh)

먼저 읽기: notes/HANDOFF_HOME.md 0장(최신 상태)·4장(규칙). 이 문서는 그 규칙 위에 회사 PC 사항만 덧붙임.

## 환경 (회사 PC)
- WSL Ubuntu-24.04, repo /home/user/work/robot_percept, 브랜치 wip/r2 (master는 검증 PASS 커밋만, 부모만 커밋).
- `source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept; cd /home/user/work/robot_percept; source sim_test/gl_env.sh; export HOST=0.0.0.0 PYTHONPATH=$PWD`
- GPU NVIDIA RTX 2080 SUPER 8GB(nvidia-smi 있음), FoundationPose·SAM2·가중치 설치됨(PERCEPTION=fp 가능).
- 셸 도구는 PowerShell 7. WSL 명령은 LF로 저장한 .sh를 `wsl -d Ubuntu-24.04 -- bash /mnt/c/.../x.sh`로 실행(또는 `wsl -d Ubuntu-24.04 --exec bash -lc '...'`).
- Windows 트래커: C:\Users\USER\AppData\Local\Programs\Python\Python312\python.exe (mediapipe 1.2.0, websocket-client 1.8.0). 실행 전 PowerShell에서 PYTHONHOME/PYTHONPATH/VIRTUAL_ENV/PIP_PREFIX/PYTHONNOUSERSITE 제거, cv2 import 전 OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS=0. repo의 tools/teleop_tracker_win.py를 TEMP로 복사해 실행(Documents 복사본은 PASS 후 부모가 동기화).
- 회사 녹화본: C:\Users\USER\Documents\sam_camera\teleop_*.mp4/jsonl (얼굴 포함, 저장소에 올리지 말 것. 결과에는 수치만). 실제 USB 카메라는 분리됨 → 실카메라 항목은 '미실시(카메라 분리)'.
- 서버는 도구 세션 종료 시 같이 죽음 → Bash yield_ms 장기 실행 + bash_interact. 종료는 `ss -ltnp | grep :<포트>` 자기 PID만, pkill -f 금지.

## 포트
| 페어 | 구현 | 검증 |
|-|-|-|
| S (P1c 구조 변경) | 5093 | 5094 |
| T (트래커 회사 판정·장시간) | 5095 | 5092 |
| E (FP 워밍업·평가, GPU) | 5083 | 5084 |
5080은 사용자 서버 예약(현재 꺼짐, 켜지 말 것).

## 측정 규칙
- fps/Hz/지연/CPU% 측정과 수 초 이상 벤치: `flock -w 900 /tmp/rp_measure.lock -c "..."`, GPU 사용 시 measure→gpu 순서 이중 락(`/tmp/rp_gpu.lock`), 한 번 보유 5분 이내(긴 배치는 쪼개서 반복 획득). 운영 코드는 측정 락 사용 금지.
- 예외: 장시간 안정성 시험(1시간 이상, 성능 수치가 아닌 오류·재연결·메모리)은 락 밖 허용. 단 시작/종료 시각을 notes/TEAM_R3_schedule.md에 적고, 그 시간대의 다른 성능 측정은 결과에 '장시간 시험 동시 진행'을 표기.
- (11/9 12:40 변경) 전체 pytest·집계·그림·재계산 등 수 초 이상 CPU 작업도 전부 measure 락 안에서만. 락 밖 허용은 몇 초짜리 단일 테스트·코드 편집뿐(Windows 트래커 측정이 WSL CPU 부하에 민감).
- 결과에 load avg, nvidia-smi, 동시 작업 기록. A/B는 같은 슬롯 교대 + 차이의 부트스트랩 95% CI(0 포함이면 '차이 입증 안 됨').
- GT(정답) 보조 사용은 GT 보조라고 명시.

## 협업
- 구현(Codex) ↔ 검증(Claude)은 message_agent로 직접 주고받으며 지적→수정 루프. 검증자의 기본 판정은 NEEDS WORK, 직접 재현한 증거(원자료 경로)가 있는 항목만 PASS.
- 부모에게는 이정표·PASS/FAIL·사용자 결정 필요 사항만 짧게(숫자 위주).
- 구현자는 커밋 금지. 자기 소유 파일만 수정, 다른 페어 파일이 필요하면 해당 구현자에게 요청.
- 한 번 실행이 ~10분으로 끊길 수 있음 → 각자 changes 노트 끝에 '재개 지점'(실행 중 exec, 명령, 결과 경로)을 항상 갱신.
- 답변·노트는 한국어.
