# V-B 검증 (집 PC, 2026-11-06)

기본 판정은 NEEDS WORK, 직접 재현하고 원자료가 있는 항목만 PASS.
측정 트리: `~/work/rp_vb` (커밋 8aad96e의 별도 worktree, 운영 코드 무수정, 포트 5094). 원자료·스크립트: `bench/verify_b/`.
환경: AMD Radeon RX 7600 (Mesa D3D12, GPU 사용률 카운터는 따로 안 잼 -> N/A), 12 논리코어, PERCEPTION=stub, RP_PERCEPTION_WARMUP=0.
측정은 모두 `flock /tmp/rp_measure.lock` 안(idle fps는 /tmp/rp_gpu.lock 이중), 한 번 5분 이내. 시작 시 load average 1.0~1.6 (다른 에이전트가 5092·5093·rp_s2new 등을 동시에 돌림, 락 안에서만 측정). 일부 구간 load 4.1(sig 1.0초 구간 끝).

| # | 항목 | 판정 |
|---|---|---|
| 1 | 유휴 렌더 2fps / 뷰어 복귀 | **PASS** (직접 측정, 위 조건 한정) |
| 2 | 기동 중 신호 | **NEEDS WORK** (SIGKILL 0.5초 시점에서 worker 잔존 2/42회) |
| 3 | Panda 집기 회귀 (GT 보조) | **PASS** (GT 보조 on, N=20, 회사 수치와 동일) |

## 1. 유휴 렌더 2fps
정의: `web/sim_worker.py` `render_period(status, now)`: 뷰어(`video_viewers>0`), `video_until` 이내, need_depth, teleop, active_command, held_object, phase가 idle/ready 아님 중 하나라도 있으면 1/30초, 없으면 0.5초(=2fps). 25ms마다 재평가. 코드는 렌더만 늦추고 물리·추적·로봇 명령은 늦추지 않는다고 주석에 적혀 있음.

측정(서버 기동 후 ready, `/status`의 `frame_seq` 증가율과 MJPEG `/video` 클라이언트 프레임 수):
| 회 | 유휴 frame_seq fps (5초×2) | 뷰어 연결 후 첫 프레임 | 30fps 근처 도달 | 뷰어 fps(3~8초) | 뷰어 중 frame_seq fps | 끊은 뒤 render_idle=true까지 | 복귀 후 유휴 fps |
|---|---|---|---|---|---|---|---|
| r1 | 2.0, 2.0 | 0.074s | 0.074s | 27.9 | 29.57 | 0.54s | 2.0 |
| m1 | 2.0, 2.0 | 0.064s | 0.064s | 29.45 | 29.26 | 0.54s | 2.0 |
| m2 | 2.0, 2.0 | 0.064s | 0.064s | 29.45 | 29.25 | 0.64s | 2.0 |
| m3 | 2.0, 2.0 | 0.064s | 0.064s | 29.52 | 29.60 | 0.54s | 2.0 |
(r1은 time.time, m1~m3은 time.monotonic 사용. 아래 한계 참고.) "도달"은 연속 10프레임이 0.4초 이내에 들어오는 첫 시점.
결과: 유휴 2.0fps, 뷰어 연결 즉시(<0.1초) 약 29.3~29.6fps, 끊으면 약 0.5~0.65초 뒤 idle로 복귀. 이 PC 값이며 30초 창 ≥29.7fps 개수 기준은 적용하지 않음(동시 작업 중이라 절대 기준은 부모의 조용한 창에서만).
원자료: `idle_fps_r1.json`, `idle_fps_m*.json`(r2, r3 파일은 시계 점프로 오염, 아래).
한계/관찰:
- r2에서 ready_s=95초, r3에서 복귀 시간 -89.8초: `time.time()`이 벽시계 보정으로 점프한 것(이 PC에서 알려진 문제). 스크립트를 monotonic으로 바꾸고 m1~m3을 새로 잼. r2·r3은 판정에서 제외.
- 뷰어 1개, MJPEG 클라이언트는 파이썬 urllib. 브라우저 탭 뷰어는 안 잼.
- 처음 시도에서 `/status`를 10Hz로 폴링하며 기동을 기다렸을 때 60초 동안 ready가 안 보임(SystemExit). 0.5초 간격 폴링에서는 4.5초에 ready. 원인 미분석, 재현 안 함. 폴링 빈도에 따른 기동 지연 가능성이 있어 확인 대상으로만 남김.

## 2. 기동 중(ready 전) 신호
방법: 서버를 띄우고 delay 뒤 신호, 서버 종료 시간(exit_s)과 포착한 자손+cwd가 트리인 `web.app/multiprocessing` 프로세스의 소멸 시간(clear_s), 매회 잔존 강제 정리 후 0 확인, 5초 상한 판정. 매 회 포트 5094 비어 있음 확인, /dev/shm 증가 0.
| delay | 신호 | n | 서버 종료 exit_s | clear_s | 잔존 | 5초 초과 |
|---|---|---|---|---|---|---|
| 0.2s | TERM/INT/KILL | 5씩 | 0.02~0.08s | 0.01~0.08s | 0 | 0 (자손 0개 시점, 기본 핸들러로 즉사) |
| 0.5s | TERM | 5 | 3.54~3.84s | 같음 | 0 | 0 |
| 0.5s | INT | 5 | 3.53~3.58s | 같음 | 0 | 0 |
| 0.5s | KILL | 5+12+25=42 | 0.02s | 0.10~0.29s 대부분 | **2건 잔존(15초 대기에도 안 사라져 직접 kill)** | 2 |
| 1.0s | TERM/INT | 5씩 | 3.43~3.63s | 같음 | 0 | 0 |
| 1.0s | KILL | 5 | 0.02s | 2.35~2.42s | 0 | 0 |
| 2.0s | TERM/INT | 5씩 | 2.77~3.32s | 같음 | 0 | 0 |
| 2.0s | KILL | 5 | 0.02s | 1.34~1.44s | 0 | 0 |
| 0.35s/0.7s | KILL | 12씩 | 0.02s | 0.24~0.48s / 2.65~2.91s | 0 | 0 |
- TERM/INT는 20회 이상 전부 5초 안(최대 3.84초), 잔존 0. ready 전엔 `create_app()`이 끝나야 종료 루프가 신호를 보기 때문에 약 3~3.8초 걸림(상한 5초 안이지만 여유 1.2초 정도).
- KILL 0.5초 시점에서 42회 중 2회(4.8%) worker가 사라지지 않음. 포착 자손 수 2(spawn된 manager 계열로 추정, 정체는 확인 못 함: 식별용 25회 재실행에서는 재현 안 됨). 부모 감시 스레드가 설치되기 전에 부모가 죽는 경쟁으로 의심하나 미확정.
- 0.7·1.0·2.0초 KILL의 clear_s 1.3~2.9초는 자손이 부모 사망을 감시해 스스로 종료하는 시간.
- 판정: 잔존 가능성이 실측에서 나왔으므로 NEEDS WORK. 재현 확률이 낮아(2/42) 원인 분석에는 반복 횟수가 더 필요.
원자료: `sig_early_{0.2,0.5,1.0,2.0}.json`, `sig_early_{0.35,0.5,0.7}_kill_*.json`.

## 3. Panda 집기 회귀 (**GT 보조 on**, GT 자세로 grasp/place/home 계산)
방법: `bench/verify_c/pp.py --root ~/work/rp_vb --gt on --n 5 --s0 {0,5,10,15}` 4덩어리 x (단일 물체 3 + multi), 시드 0..19 = N=20. (`tests/test_pick_place.py`는 /home/user 경로가 박혀 있어 경로 치환 사본 `test_pick_place_vb.py`로 latency 20회와 `--suite all --trials 2` 스모크만 실행. 같은 로직의 pp.py로 N=20.) 이 경로는 GT 자세 콜백을 쓰므로 인식 성능이 아니라 제어 회귀 확인임.
| 스위트/물체 | pick | place | home | home 후 물체 최대 변위 | 회사 수치(verify_c) |
|---|---|---|---|---|---|
| single mustard | 20/20 | 20/20 | 20/20 | 2.149 mm | 20/20 x3, 변위 0.37 mm |
| single box | 20/20 | 20/20 | 20/20 | 0.018 mm | 20/20 x3, 0.02 mm |
| single cup | 20/20 | 20/20 | 20/20 | 0.000 mm | 20/20 x3, 0.0005 mm |
| multi mustard/box/cup | 20/20 x3 | 20/20 x3 | 20/20 x3 | 0.016 / 0.018 / 0.000 mm | 20/20 x3, all-three 20/20 |
| multi all-three | 20/20 (home 포함 20/20) | | | | 20/20 |
Wilson 95% 하한 83.9%. 실패 0건. mustard 변위 2.149 mm는 회사의 0.37 mm보다 크지만 기준 5 mm 안(차이 원인 미분석).
장애물 home(`home_obstacle.py`, 시드 0·1): 총 9건 모두 REJECT_EARLY(충돌 후 완료 0건): 물체 든 채 gt on/off 각 1, cup f=.7/.85/.95, mustard .95 (시드 0), cup .85/.95, mustard .95 (시드 1). f=.7 한 건은 상승 중 접촉 검출로 거절, 침투 0.994 mm(임계 1 mm 직전, 회사와 같은 값). 17건은 시작부터 겹쳐 제외(회사와 동일). 회사 11건과 달리 시드 1의 held 케이스는 --no-held 로 안 돌려 9건.
test_pick_place 사본: latency 20시드 median(mustard/box/cup) 0.008/0.005/0.004 s, p95 최대 0.012 s (회사 0.018/0.009/0.009 median; 이 PC가 빠름), 스모크 trials=2 전부 pick/place 성공.
원자료: `bench/verify_b/c/*.json`, `c/summary.txt`, `c/status.log`(각 청크 load), `c/tpp_*.log`.
한계: gt_assist=off(참고치)는 이번 범위가 아니라 안 돌림. 회사와 같은 시드·같은 코드의 확인이라 "차이 입증 안 됨"(A/B 신뢰구간은 해당 없음, 20/20 대 20/20).

## 정리
- 5094 리스너 0, 내 worker 0 확인(남은 rp_s2new 계열 프로세스는 다른 에이전트 것). worktree `~/work/rp_vb`는 남김(data/ 디렉터리, 로컬 링크 포함, 커밋 안 함).
