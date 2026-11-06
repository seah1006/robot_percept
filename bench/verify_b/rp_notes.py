from pathlib import Path
import json
root=Path('/home/my/work/robot_percept')
audit={
 'date':'2026-11-06','python':'3.12.16 conda-forge','HAVE_SEM_CLOCKWAIT':0,
 'operating_waits':[
  {'file':'web/humanoid_worker.py','line':127,'period':'1/32s render pacing','impact':'G1 render/publication gap','action':'wait_event monotonic; HEAD already had equivalent wait_monotonic'},
  {'file':'web/humanoid_worker.py','line':135,'period':'startup max 60s','impact':'worker ready response','action':'wait_event monotonic'},
  {'file':'web/humanoid_worker.py','line':'208,217','period':'shutdown max 5s','impact':'render thread stop','action':'join_thread monotonic polling'},
  {'file':'web/humanoid.py','line':113,'period':'100ms watchdog','impact':'worker death detection','action':'existing wait_monotonic alias now shared helper'},
  {'file':'web/app.py','line':85,'period':'warmup cancel max 3s','impact':'G1 reservation response','action':'thread join timeout replaced by join_thread'},
  {'file':'web/app.py','line':'155-161','period':'command poll 50ms, timeout 30/60/180s','impact':'Panda command HTTP/background completion','action':'monotonic deadline + sliced sleep'},
  {'file':'web/app.py','line':'237-251','period':'Panda MJPEG per new frame; frame.jpg max 2s','impact':'Panda stream/frame response','action':'stream uses untimed Event notification; frame.jpg timeout uses monotonic polling'},
  {'file':'web/teleop.py','line':'61-69','period':'preview per new JPEG','impact':'teleop preview MJPEG','action':'untimed Event notification with seq recheck'},
  {'file':'web/perception_stub.py','line':'106-122','period':'RPC readiness poll max 100ms, total 180s','impact':'segment/register/track/warmup response','action':'Queue timed get replaced by Connection.poll selector + get_nowait'},
  {'file':'web/humanoid.py; web/app.py; web/perception_stub.py','line':'process join timeouts','period':'2-3s shutdown','impact':'process cleanup','action':'unchanged; multiprocessing Process.join -> connection.wait(selector + monotonic)'},
 ],
 'bench_waits':[
  {'file':'bench/verify_w/vw_measure.py','action':'ready deadline and thread joins monotonic'},
  {'file':'bench/verify_w/crash_test.sh','action':'ROOT/CONDA_SH/PORT environment defaults'},
  {'file':'bench/humanoid_w_stall.py','action':'stream/poll Event waits use shared helper'},
  {'file':'bench/humanoid_s_render.py','action':'confirmed prior local helper, replaced by shared helper'},
  {'file':'bench/humanoid_w_ab.py','action':'ROOT environment override'},
  {'file':'bench/humanoid_runtime_bench.py','action':'poll Event and thread join use shared helper'},
 ],
 'multiprocessing_basis':{
  'Queue.get_timeout':'potentially affected under semaphore/rlock contention; _multiprocessing.so links sem_timedwait',
  'Connection.poll':'not affected; multiprocessing.connection.wait uses selector.select and time.monotonic deadline',
  'Process.join_timeout':'not affected; Popen.wait delegates to multiprocessing.connection.wait',
  'subprocess_wait_timeout':'not changed; CPython subprocess timeout loop is monotonic',
 },
 'limits':['time.time monkeypatch unit tests do not emulate a kernel CLOCK_REALTIME step','actual clock steps were recorded only in integration windows','HEAD already protected the G1 render pacing path, so A/B does not isolate a new render-loop fix']
}
(root/'notes/humanoid_w_1106_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
section='''

## 2026-11-06 집 PC: monotonic 대기 수정

### 범위와 원인 감사
- conda Python 3.12.16, `HAVE_SEM_CLOCKWAIT=0`. `_multiprocessing.so`도 `sem_timedwait`를 링크한다. `threading.Event/Condition/Lock` timed wait와 `queue.Queue.get(timeout)`은 REALTIME 보정 시 늘어날 수 있고, `multiprocessing.Queue.get(timeout)`도 내부 semaphore/rlock 경합 구간은 같은 위험이 있다.
- 반대로 `multiprocessing.Connection.poll`과 `Process.join(timeout)`은 `selectors.select`와 `time.monotonic()` 경로라 유지했다. `subprocess.Popen.wait(timeout)`과 socket HTTP timeout도 이번 원인의 threading semaphore timed wait로 분류하지 않았다.
- 상세 파일:줄·주기·영향은 `notes/humanoid_w_1106_audit.json`에 기록했다. `sim/`의 G1/Panda 렌더 본문에는 해당 threading timed wait가 없었다.
- 중요한 제한: HEAD 1e51bb6의 G1 render pacing은 이미 `web.shm_channel.wait_monotonic`으로 보호돼 있었다. 이번 변경은 그 구현을 공용화하고 startup/join, Panda MJPEG, teleop preview, app command wait, perception RPC, 측정 하네스의 미보호 경로를 추가 보호한 것이다. 따라서 과거 4.9초 사례를 이번 HEAD A/B의 새 G1 render 개선으로 과장하지 않는다.

### 변경
- `web/monowait.py`: `wait_until`, `wait_event`, `sleep_until`, `wait_for`, `join_thread`. monotonic deadline과 `time.sleep`, 최대 slice 10ms, stop은 매 slice 확인.
- `web/humanoid_worker.py`, `web/shm_channel.py`: G1 pacing/startup/render-thread 종료를 공용 helper로 통일. P1a/P1b/P1c IK·충돌 계산은 수정하지 않았다.
- `web/app.py`: warmup thread join과 Runtime command timeout을 monotonic으로 변경. Panda MJPEG stream은 seq 재확인 후 **timeout 없는 Event 알림 대기**를 사용해 클라이언트당 100~200Hz polling을 피했다. `/frame.jpg`의 기존 2초 응답 한계만 10ms monotonic polling으로 유지했다.
- `web/teleop.py`: preview MJPEG도 seq 재확인 + timeout 없는 Event 알림 대기로 변경했다.
- `web/perception_stub.py`: `multiprocessing.Queue.get(timeout)` 대신 reader `Connection.poll`(selector+monotonic) 후 `get_nowait`을 사용해 추가 10ms polling 지연을 없앴다.
- 하네스: `bench/verify_w/vw_measure.py`, `crash_test.sh`, `humanoid_w_stall.py`, `humanoid_s_render.py`, `humanoid_w_ab.py`, `humanoid_runtime_bench.py`. `ROOT=${ROOT:-$HOME/work/robot_percept}`, `CONDA_SH=${CONDA_SH:-$HOME/miniforge3/etc/profile.d/conda.sh}` 방식 적용.

### 테스트
- `tests/test_monowait.py`: 모의 wall time -4.9s/+92s에서도 50ms monotonic 반환, 사전 stop 즉시 반환, 알림 predicate 지연, render-style stop 50ms 이내를 검사한다.
- 이 monkeypatch는 커널 CLOCK_REALTIME step과 `sem_timedwait` 실패를 직접 재현하지 못한다. 실제 점프 증거는 아래 통합 창의 sleep 기반 probe와 원래 `Event.wait(.05)` probe를 함께 사용했다.
- 최종 `python -m pytest -q`: **73 passed, 5 warnings, 38.21s**. 현재 집 환경 변환물 보완 후 실패 없음.

### 5093 A/B/A/B 실측 (각 30초, 합성 입력, 같은 측정·GPU lock)
결과: `notes/humanoid_w_1106_ab.json`, 원시 JSON/JSONL: `notes/humanoid_w_1106_raw/`.

|창|collision|frames / count fps|max gap|server receive→publish p95|Event.wait max|실제 wall jump|CPU tree|시작 load|
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|A1 HEAD|OFF|961 / 32.033|42.70ms|64.814ms|4806.72ms|±91.96s 16건|280.9%|3.41/4.59/2.96|
|B1 수정|OFF|924 / 30.800|62.25ms|79.336ms|4802.04ms|±91.96s 16건|321.7%|5.45/4.92/3.14|
|A2 HEAD|OFF|936 / 31.200|72.67ms|78.932ms|4811.38ms|±91.96s 14건|292.8%|5.21/4.93/3.23|
|B2 수정|OFF|892 / 29.733|87.01ms|85.013ms|4809.61ms|±91.96s 16건|327.4%|5.32/5.00/3.32|
|B 수정|ON|904 / 30.133|74.17ms|75.278ms|4809.91ms|±91.96s 14건|317.8%|6.46/5.35/3.52|

- 모든 창에서 실제 wall jump가 발생했고 원래 `Event.wait(.05)`는 약 4.80~4.81초까지 늘어났다. 그와 동시에 G1 MJPEG `gap>200ms`는 0건이었다. HEAD render loop도 이미 monotonic 보호 상태였다는 독립 관측과 일치한다.
- 절대 기준은 B1 OFF와 B ON이 fps≥29.7/p95≤80ms 통과, B2 OFF는 fps 29.733 통과지만 p95 85.013ms 실패다. A/B 평균은 부하가 뒤로 갈수록 높아져 수정본 CPU·지연 회귀 여부를 분리하지 못했다. 실패 창을 제거하거나 PASS로 바꾸지 않는다.
- GPU는 전 창 `GL_RENDERER=D3D12 (AMD Radeon RX 7600)`. Windows GPU counter는 이 배치에서 값이 반환되지 않아 사용률은 N/A. 동시 작업으로 부모 5091 서버와 검증자 5092 측정이 존재했고 load가 3.41→6.46까지 상승했다.
- collision OFF/ON 모두 P1c 기능 자체의 안전성/실용성 PASS를 뜻하지 않는다. 기존 결론(P1c FAIL, 기본 OFF 실험 기능)을 유지한다.
- 실제 USB 카메라 장치가 없어 입력은 합성만 사용했다. 실카메라 안전·성능 검증은 **미실시**이며 관련 주장을 하지 않는다.

### 남은 한계
- 이번 환경의 ±92초 보정 주기가 매우 잦아 일반 배포 환경 대표값이 아니다. 시스템 시계는 인위적으로 바꾸지 않았다.
- HEAD에 이미 G1 pacing 보호가 있어, 과거 4.9초 정지의 단일 미보호 호출을 이번 A/B만으로 재지목할 수 없다. 과거 raw watchdog의 `idle_before≈4.907s`, render≈87.7ms, JPEG≈2.8ms는 timed wait stall과 일치하지만, 현재 창은 gap을 재현하지 않았다.
- 수정본 B2 p95 실패와 높은 동시 부하 때문에 성능 최종 PASS는 보류한다. 조용한 창에서 독립 검증자의 A/B와 연결 상태 CPU 결과를 함께 판단해야 한다.
'''
with (root/'notes/humanoid_w_changes.md').open('a') as f:f.write(section)
