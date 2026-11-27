# WS-H 보고: 데모 영상 + 로그 뷰어(U1)

조건 표기(영상 자막과 HTML에 모두 들어감): **시뮬레이션, P-gate(GT 보조 weld 파지 근사), O0=GT 인식 / O3=예측 인식**. 이번 영상 3개는 모두 O0, dev seed만 사용.

## 변경 파일 (소유 경로 안, 커밋 안 함, worktree `~/work/rp_m2a_h` 브랜치 m2a/ws-h)
- `m2a/viz/__init__.py`, `captions.py`(한국어 자막 문구, 렌더 없음), `record_episode.py`(녹화+합성+인코딩 호출), `encode_av.py`(PyAV 인코더), `report_html.py`(로그 뷰어), `make_demos.sh`(3영상+HTML 재생성)
- `tests/m2a/test_h_viz.py`(8개), `m2a/notes/wsh_report.md`
- m2a/run, m2a/sim은 수정하지 않았다. 메인에 요청할 훅은 없다(아래 "훅 방식" 참고).

## 훅 방식 (run 코드 무수정)
- `env.step`을 서브클래스로 감싸 시뮬 0.05초마다 front/head/wrist_l/wrist_r 렌더를 캡처(`run_episode(env=...)`로 주입). step을 쪼개 호출하므로 물리는 같은 적분을 따른다.
- `runner_factory` 프록시로 스킬 시작/종료를 표시, `Perturbation` 서브클래스로 교란 직전/직후 프레임을 따로 잡고 배너를 붙인다.
- 자막은 실행이 끝난 뒤 `result['logs']`(episodes/plan)에서 만든다. 계획 #, 액션, 스킬 결과, 재계획 사유(trigger), 교란을 로그 그대로 쓴다.
- 지시 문장: 이 실행들은 자연어 지시 없이 장면 기본 목표로 돌렸다. 자막은 "2단계 준비 (장면 기본 목표, 자연어 지시 없음)"으로 표기한다. 자연어 지시가 기대 목표와 같은 목표로 파싱될 때만 그 문장을 `instr`로 넘기고 자막에 쓴다(L0·L1 장면은 부품 수가 달라 해당 없었음).

## 영상 (`~/m2a_data/demo/`, Windows: `\\wsl.localhost\Ubuntu-24.04\home\my\m2a_data\demo\`)
공통: 1600x900, H.264 yuv420p, 20fps, 1배속(자막 상단에 sim 시각과 배속 표시). 레이아웃: front 큰 화면 + head + 양 손목 카메라 + 계획 패널(완료/진행/대기), 하단 자막, 상단 조건 표기.
| 파일 | 길이 | 장면 | 내용 |
|---|---|---|---|
| `demo_a_L0_B1.mp4` | 15.1초 | dev 10000 L0 standard, B1, O0 | 단품(캠락 o0) 접근 → 파지 → T2에 놓기, 판정 성공 |
| `demo_b_L1_pretray_B4.mp4` | 40.5초 | dev 10047 L1 pretray, B4, O0 | 계획이 다월 o1을 잘못 들어간 트레이 T2에서 꺼내(pick-from-tray) T1에 넣고, 이어 브래킷·짧은 판재를 T3에 담음. 9스킬, 성공 |
| `demo_c_L0_teleport_B4.mp4` | 20.6초 | dev 10001 L0 standard, B4, O0, teleport after_skill=1 | 접근 직후 짧은 판재 o1이 오른쪽 구역에서 왼쪽 구역(목표 캠락 옆)으로 순간이동(시뮬레이션 주입) → 관측 → 재계획 #2 → 재접근·파지·T2에 놓기, 성공 |

대표 프레임 PNG(각 `_start/_mid/_final`, c는 `_perturb/_replan` 추가): `demo_a_L0_B1_*.png`, `demo_b_L1_pretray_B4_*.png`, `demo_c_L0_teleport_B4_*.png`. 메타는 같은 이름의 `.json`.
동일 seed의 배치 결과(`runs/e3-*-a5final`)와 비교: a 성공(3스킬), c 성공(재계획 1, 4스킬, 같은 B1은 GRASP_SLIP 실패)은 일치. b는 배치에서 재계획 1회(GRASP_SLIP 후)였으나 이번 녹화에서는 재계획 0회로 성공(스킬 9개). 녹화 훅이 step을 쪼개 호출하는 것이 원인으로 추정(미확정)이며, 영상은 "녹화 실행 1회의 결과"다.

## 시나리오 (b)에 대한 한계
- stacked(pick-from-top으로 위 물체를 치우는) 장면은 A5 최종판 배치에서 성공이 없어(L1/L2 B4 3/60, 성공 3건은 reach/standard/pretray) 영상으로 만들지 못했다. (b)는 pretray로 대체: "목표와 무관한 트레이에 이미 들어간 부품을 먼저 꺼내는" 계획 장면이다. stacked 영상은 A 쪽 스킬 개선 후 같은 명령으로 재생성 가능.
- (c)의 재계획 #2는 계획 액션 내용이 #1과 같다(교란 물체는 목표 밖 부품이었고 위치만 바뀜). 달라진 점은 관측으로 교란 물체의 새 위치가 반영된다는 것. O0는 GT를 읽는 것이므로 자막은 "재인식"이라 쓰지 않고 "관측 → 재계획"으로 표기했다.

## 로그 뷰어 (`report_html.py`)
- 입력 `runs/<id>/{config,result,episodes,plan}`, 출력 정적 HTML(CSS만, 스크립트·외부 링크 없음, 테스트로 확인). 내용: 조건 표기 배너, 메타(관측/스킬 판/커밋/seed), config×level×상황 성공 표, fail_code 분포 표(config별), 재계획 사유 표, 에피소드별 펼침(계획 액션 한국어+원본, 재계획 사유, 스킬별 성공/실패와 reason_code, 교란 표시, 대표 프레임 썸네일·mp4 링크). `--demo-dir`로 thumbs 연결(같은 seed/level/상황/config와 교란 유무가 일치하는 항목만).
- 생성: `~/m2a_data/demo/report_e3_main.html`(180 에피소드, 365KB), `report_e3_l0pert.html`(40), `report_e3_b1c.html`(40). 헤더 수치는 로그 재집계값이며 e3-l0pert는 B1 7/20, B4 11/20으로 표시됨(로그 원자료 기준).
- 직접 확인: 로컬 http.server(5091)로 브라우저에서 열어 표·재계획 표·펼침 상세·썸네일 렌더링을 확인(썸네일 16개 요청 200). file:// 로는 브라우저 정책상 못 열어 http로 확인했다. 사용자는 파일을 그냥 더블클릭해서 열면 된다(상대 경로 이미지 링크, 같은 폴더).

## 인코딩 방법
설치 없이: `m2a_lerobot` env의 PyAV 15.1(libx264 포함)을 subprocess(`nice -n 10`, 스레드 2)로 호출(`encode_av.py`). robot_percept env에는 av가 없고 Windows 쪽 ffmpeg는 찾지 않았다. 프레임은 임시 JPEG 시퀀스로 쓴 뒤 인코딩 후 삭제(실패 시 `<name>_frames/`로 남김). 세 mp4를 PyAV로 다시 디코딩해 코덱/해상도/프레임 수를 확인했다(h264, 1600x900, 301/809/411프레임, 15.05/40.45/20.55초). 중간 프레임(c의 9초 지점: 재계획 #2의 파지 실행 중)도 PNG로 꺼내 육안 확인.

## 테스트
- `tests/m2a/test_h_viz.py` 8개(자막 문구, 조건 표기 필수 문구, 재계획·교란 전 자막, HTML 표·외부자원 없음, 썸네일 링크, PIL 합성 무렌더) 통과.
- `python -m pytest tests/m2a -q`: 183 passed, 1 skipped (20초, nice 10).

## 남은 문제
1. stacked(위 물체 치우기) 영상 없음(위 사유). 스킬 개선 후 `make_demos.sh`의 b 줄을 stacked seed로 교체.
2. O3 영상 없음: `observation` 옵션은 자막만 바꾼다. 이번 3개는 O0이며 O3 연결(percept) 후 `--observation O3`와 해당 perception 주입이 필요(record는 현재 OraclePerception 기본만 사용).
3. 녹화 실행과 배치 로그가 완전히 같은 물리 경로가 아닐 수 있음(b 재계획 횟수 차이). 영상에는 "녹화 1회 결과"로만 쓸 것.
4. 지시 문장은 자연어 지시 없이 기본 목표를 풀어 쓴 것. 발표용으로 한국어 지시 문장을 화면에 넣으려면 `--instr`를 지원하는 장면 선택이 필요(현재 미지원, 필요하면 추가).
5. 손목 카메라 화면은 손가락 시점이라 처음 보는 사람에게는 직관적이지 않을 수 있음(발표 시 head+front만 크게 쓰는 변형 가능).
6. 이 세션 중 Bash 도구가 간헐적으로 `AsideWindowsSandboxHelper.exe ENOENT`로 실패했다(재시도 시 복구). 결과물에는 영향 없음.
