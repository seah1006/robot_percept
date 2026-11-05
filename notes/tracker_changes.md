# I-K tracker r2 (2026-11-03)

## Status
- JSONL v2 humanoid/both record/replay implemented; v1 Panda replay preserved.
- A7 hand hold 150ms + quality flags implemented, I-S pin9ta9lgwPK2eve agreement received.
- A6 camera_acceptance.py: one command launches tracker, produces JSON + Markdown table. --video --dry-run uses independent local HTTP collector (ephemeral loopback port), not the real Flask server. Live mode requires prestarted server/mode ON. No auto camera PASS.
- T bench/tracker_panda_regress.py: mode panda video OFF/ON main FPS mean/drop, reference preview Hz, linked acceptance JSON. Not executed. Warmup/startup affects comparison; validator should exclude startup or extend stable window before final claim.
- Files owned/changed: tools/teleop_tracker_win.py, tools/camera_acceptance.py, bench/tracker_contract.py, bench/tracker_panda_regress.py, notes/tracker_changes.md. humanoid_synth.py unchanged. Documents copy untouched. No commit.

## JSONL format
One JSON object per processed frame, schema="robot_percept.tracker.v2".
- t: seconds from recording start at processing completion; replay uses this cadence.
- capture_t: read/decode completion relative to recording start; capture_at: original Unix wall clock.
- seq: tracker frame sequence; mode: panda/humanoid/both.
- features: original Panda /teleop/update object; humanoid: original /humanoid/update object or null.
- landmarks: first-hand normalized xyz for legacy consumers.
- humanoid.pose: 33 x [x,y,z,visibility], hands.left/right: 21 x xyz, pose2d/hands2d retained.
- Replay sends only requested --mode endpoints. Explicit --mode humanoid or --mode both required for humanoid playback (default panda intentionally preserved). v1 features rows work; v1 cannot invent missing humanoid payload.
- Replay re-bases capture_at/sent_at to current time, preserving recorded capture-to-processing age; original recording object is not mutated.
- Options are server state, not currently changed by tracker. Replay requires same external /humanoid/options/calibration setup; options are NOT snapshotted.
- MP4 remains raw mirrored 640x360 at nominal30fps; JSONL preserves actual timing.

## A7 contract agreed with solver/web
quality.hands.{left,right}: {state: tracked|held|missing, confidence:0..1, age_ms:nonnegative number|null}.
confidence is freshness, NOT detector probability. tracked=1, held linearly decays during <=150ms; expired=missing with no hands entry. Pose absent/upper arm invalid disables hold reuse. No fabricated hands2d on held frames.
quality.upper_body_visible checks all shoulders/elbows/wrists visibility>=.3; hips_visible checks23/24>=.3 independently. Upper-body tracking does not require visible hips. Solver decides safe torso fallback. No automatic neutral motion.
I-S agreed held samples do not refresh palm/finger target; solver keeps torso-local previous valid wrist rotation, freezes finger desired at current command.
I-W preserves optional quality/capture_at/client seq, input_count and capture_latency_ms. Old clients remain valid.

## Measurement and verification
- Windows Python312 scrubbed PYTHONHOME/PYTHONPATH/VIRTUAL_ENV/PIP_PREFIX/PYTHONNOUSERSITE, MSMF transforms0.
- py_compile: 3 files PASS.
- bench/tracker_contract.py: 10 assertions PASS (hold, expiry, absent pose, v2 routes, v1 replay, Panda pipeline OFF).
- load: 10:20:38 8.85/4.68/3.08; 10:21:02 10.07/5.29/3.32.
- Attempted video dry-run under flock /tmp/rp_measure.lock waited60s, tool exit1223 timeout; no successful inference/metrics confirmed. Performance NOT measured, no new30Hz PASS.
- V-W Eh5fPuBB8WlZJE7k notified of bundle and asked direct code review + dryrun. Await feedback.
- 5080 untouched. No own HTTP/Windows tracker intentionally left running; timed-out lock attempt should be checked by validator before measurement.

## Commands / remaining
Windows Python312 tools/camera_acceptance.py --video C:\Users\USER\Documents\sam_camera\teleop_final_hand.mp4 --dry-run --seconds 3 --output <tmp>\tracker_acceptance_dryrun.json
Live after reconnection: Python312 tools/camera_acceptance.py --url http://127.0.0.1:5095 --seconds30 --output camera_acceptance.json (real server mode must already be enabled).
Use '--seconds 30' with a space; --seconds30 is not a valid argparse flag.
Real server receive count uses input_count delta; absent counts/latency become null+blocked, never inferred from sends. Preview count currently unavailable from Panda status; moving preview_hz is reference only, not acceptance evidence. Cross-host capture latency includes Windows/WSL wall-clock skew. Video clock is decode/read completion, not sensor exposure. Live camera FPS uses actual capture thread frame count, not CAP_PROP_FPS metadata.

## Resume point
1. Receive V-W review, fix findings directly (no commit).
2. Acquire free measurement lock and low load slot; run3s functional video dryrun, then30/45s humanoid regression ensuring >=99% and count-based30s >=29.7Hz.
3. Add/coordinate server cumulative preview_count with owner if needed; acceptance currently explicit blocked for unsupported counter.
4. Panda bench stable-window/warmup adjustment and V-W actual T rerun; actual camera acceptance remains blocked by disconnected hardware.

## Follow-up (10:40, parent resume)
- Panda bench fixed: OFF warmup5s, first actual preview wait, ON warmup5s, stable measured30s. cumulative receive/preview deltas use actual wall duration; startup excluded. logfile avoids pipe deadlock; env scrub; owned child cleanup.
- camera_acceptance fixed: --warmup2 then complete fixed measurement window, extra5s trailing tracker time; dryrun counts only this window; live status boundaries report actual measured duration. Full window missing => blocked. Local latency samples also filtered to window. Dryrun GET handler no longer produces501 errors.
- Capture timestamp paired atomically with camera frame under camera_lock; video timestamp at decode completion before pacing (not sensor exposure).
- I-W confirms /teleop/status input_count + preview_count implemented and4tests PASS; new server restart needed. A6 reads preview_count from /teleop/status also in humanoid mode.
- Latest compile3 PASS, contract10 PASS. Nonblocking flock attempt10:40:14 exit75 (busy), no inference started. Load10:39:48 2.82/5.07/5.55,10:40:03 2.44/4.84/5.47. V-W running requested review/dryrun, result still awaited.
- Resume: obtain V-W actual dryrun/review result, resolve findings, then low-load slot actual30/45s regression. No physical camera PASS; no new performance PASS. No temp shell retained.

## Video dry-run completed (10:43)
- flock -w900, Windows parent PowerShell env scrub required in addition to WSL env-u. First attempt failed SRE module mismatch; no inference in failed attempt.
- Latest camera_acceptance --video teleop_final_hand.mp4 --dry-run --seconds3: exit0, complete fixed3s window, independent local HTTP collector.
- Received84/3=28.0Hz, preview84/3=28.0fps. Full tracker266/10.018s=26.553Hz; processed266/301=88.372%; sent266, preview266, HTTPerrors0.
- Raw hand detection69.549%, pose100%; local capture-to-arrival p50/p95 151.836/183.251ms; neural p50/p95 36.397/48.043ms.
- Load2.28/4.15/5.15 at launch ->2.96/3.93/4.99 after. No equivalent same-slot baseline. Functional dry-run succeeds but current sample is below >=99%/29.7Hz performance criteria; 3s local-collector test is NOT formal30s real-server acceptance, no regression PASS claimed.
- JSON proof: C:\Users\USER\.aside\u\0\sessions\2026-11-02_1NIgF2z2BvfBSkOh\tmp\tracker_acceptance_dryrun3.json (+ .tracker.json).
- V-W received full numbers/path, review pending. Worker/tracker/collector all exited; lock released, temp shell removed.
- Next: V-W review corrections, controlled baseline-vs-current30/45s real-server run, investigate neural>33ms if repeatable. Physical camera remains untested.

## A/B workload-contaminated slot (10:49:17–10:52)
- Acquired measure→gpu dual locks. nvidia-smi initial3%/1606MiB. V-P2 GPU benchmark not in process snapshots, but V-C2 PID69453 home_obstacle.py was running without measurement lock initially, later completed. Other solver diagnostics seen temporarily. Parent explicitly designated this slot relative-comparison only, not absolute acceptance.
- Same server5095/current G1 backend; A=git1da4b93 tracker, B=current tracker; same final_hand.mp4; each35s with first receive+2s warmup then actual30s counter window.
| run | processing% | receiveHz | previewFPS | neural p50/p95 ms | retarget p50/p95 | post p50/p95 ms | load |
|---|---:|---:|---:|---|---|---|---|
| A1 |73.264|19.197|19.231|41.823/67.024|.971/3.317|33.546/83.433|3.97/3.76/4.54|
| B1 |84.872|25.625|25.559|37.515/51.370|.973/2.385|20.782/45.531|6.74/4.47/4.73|
| A2 |86.108|25.880|25.680|36.591/53.767|.828/2.032|19.369/45.503|8.68/5.46/5.06|
| B2 | interrupted | - | - | - | - | - | - |
- B2 interrupted by Windows WinError10048 (socket/ephemeral-port exhaustion) in status monitor. 10Hz×2 urllib polling plus trackerPOSTs/all shared agents can accumulate TIME_WAIT. Server cleanup trap and tracker own-process finally executed. No arbitrary process killed.
- Changed A/B status polling to2Hz, added bounded retry. No tracker behavior changed based on contaminated results; additional quality/hold retarget median cost approx.145ms compared closest A2/B1, NOT isolated causal proof; dominant differences neural/post reflect varying load/network.
- Evidence tmp/tracker_ab.json (3 complete rows, full metrics/GPU/concurrent process snapshots).
- Clean-slot A/B/A/B launched session1032 (flock-w900, GPU-w30); output tmp/tracker_ab_clean.json. Shell bench/tracker_ab_clean_temp.sh; owns5095 only and removes baseline temp on exit. If delegated time limit reached parent should poll session1032, then send V-W result, clean remaining temp shell files. Full absolute acceptance still pending.
- V-W independently confirmed record/replay74/74 exact pose/hands/quality/seq, humanoid mode Panda requests0, tracked/held/missing all observed, dryrunJSON valid. Video capture latency includes pre-pacing decode/FIFO wait, not camera exposure-to-display latency PASS evidence.

## Completed clean-labelled A/B/A/B (10:58:17–11:01:52)
Same single5095 G1 server, same input, dual measure→gpu locks throughout, baseline1da4b93 vs current. Complete4runs, all returncode0, each actual30.13–30.64s count window. Lock held3m35s (<5min);5095 server stopped, baseline/temp shell files removed. bench/tracker_ab.py retained for reuse.
|run|processing%|receivedHz|previewFPS|neural p50/p95 ms|retarget p50/p95 ms|post p50/p95 ms|load|
|---|---:|---:|---:|---|---|---|---|
|A1|82.493|24.497|24.431|37.327/57.066|.858/2.106|17.120/42.495|4.21/4.13/4.60|
|B1|77.926|22.831|22.831|39.750/59.256|1.055/3.176|22.164/58.603|6.16/4.69/4.77|
|A2|78.992|23.662|23.596|40.278/56.389|.882/2.374|19.895/38.437|7.10/5.14/4.92|
|B2|78.211|22.952|22.753|40.615/55.705|1.034/2.677|23.154/47.046|6.40/5.24/4.96|
- A mean80.74263%,24.07956Hz,24.01382preview. B mean78.06851%,22.89115Hz,22.79165preview.
- Processing B-A=-2.67412pp. Receive=-1.18841Hz=-4.93536% relative (or -3.96135pp when normalized to30Hz). Either interpretation of parent2pp threshold => relative regression FAIL. No regression-free PASS claimed.
- Absolute observed criteria all4runs below99%/29.7Hz/29.7fps. Parent adjusted official absolute acceptance to final quiet window; report observed failure, defer final official quiet-window decision.
- Important residual confound: I-S explicitly confirmed history/recovery/physics CPU bench overlapped10:57 onward and was stopped during this slot. A1 ps shows humanoid_s_history.py, A2 shows --reset; B snapshots no active matching task. Windows Aside CPUs also active. V-P2 benchmark not seen; gpu lock held. Load rises4.21→7.10. This is a measured threshold miss, not proof source changes caused entire difference.
- Stage averages of per-run p50: A neural38.803ms vs B40.182ms (+1.380); retarget .870 vs1.044ms (+.174); POST18.508 vs22.659ms (+4.151). Server process_ms median B1.078/1.094 vs A1.199/1.201 => server ingress quality validation not dominant observed bottleneck. JSON median +.018ms, payload~6272→6500 bytes. No isolated ablation proving cause yet.
- Because baseline A also fails absolute criteria, conditional request 'B fail/A pass -> fix' not triggered. Do not remove safe hold/quality or alter pacing without causal evidence. Next if needed: same-slot ablations (disable quality/hold vs current using explicit flags), CPU/HTTP contention profile, repeat after other benches stopped. Parent can elect quiet-window baseline+current final.
- Full evidence tmp/tracker_ab_clean.json and tmp/tracker_ab_clean_summary.json. V-W/parent notified with table and relativeFAIL. No measurement processes left by I-K.

## POST detail instrumentation / optimisation (11:06)
- Metric semantics: post_ms starts AFTER JSON encode and measures HTTP request/response wall time (includes socket wait and GIL scheduling). It does NOT include visibility/hold/overlay. The earlier+4.151ms is not causal evidence of quality calculation cost.
- Added detail_ms p50/p95/n: visibility, hold_quality, timestamp dictionary, actual camera capture_lock acquisition+read, pose_overlay, panda_features_overlay, hand_overlay, HTTP headers, body, response JSON decode. Existing json_ms/payload_bytes/server_ms preserved.
- Direct urllib3 PoolManager transport now default for humanoid/both, avoiding Requests preparation/cookie/adapter layers; --http-client requests restores old path. Panda default remains requests. Both have independent sender-thread sessions/pools, sameJSON/endpoints, timeout.6s, no automatic retries, status errors still counted. Stdlib fallback remains when requests dependency absent.
- Pure humanoid non-recording now skips Panda feature extraction and first-hand duplicate overlay; generic colored hand overlay remains. Recording still computes legacy Panda features for exact v2 content compatibility. PoseUV conversion vectorized once instead of16conversions/frame; OneEuro constructed only if missing instead of everysetdefault evaluation. Hold/quality unchanged, no sample rate reduction.
- Latest py_compile PASS and tracker_contract10 PASS. New transport performance/functionality pending actual test; NOT declared passed or +1ms target achieved yet.
- ABAB run script bench/tracker_ab_run.sh retained; session1042 waiting measure-w900→gpu-w30. Same35s/2swarmup/30s window, output tmp/tracker_ab_opt.json; server log tmp/tracker_ab_opt_server.log. Parent/V-W informed. If10min limit stops this worker, continue polling1042; do not launch duplicate until session confirmedgone.

## 2026-11-05 재부팅 후 재측정 완료
- 과거 tracker_ab_opt.json 존재: tmp/tracker_ab_opt_before1105.json으로 보존. 과거 session1042와 서버 재사용 안함.
- bench/tracker_ab_run.sh와 동일 스크립트, 신규5095 G1서버, 동일영상, measure→gpu 이중락13:06:46~13:10:21(3분35초). 전4run exit0, HTTP오류0. 5095 own서버 종료/기준트래커 임시본/AB실행 임시sh 정리 완료.
|실행|처리율%|서버수신Hz|previewfps|neural p50/p95 ms|POST p50/p95 ms|
|---|---:|---:|---:|---|---|
|A1|82.017|24.698|24.665|39.699/53.204|16.378/33.055|
|B1|92.959|28.060|28.027|35.806/44.658|12.456/23.947|
|A2|100.000|30.169|30.136|29.219/43.983|10.916/23.505|
|B2|100.000|29.993|29.993|28.244/40.551|9.298/23.540|
- A평균 처리91.00856%/수신27.43326Hz/preview27.40035fps; B평균96.47954%/29.02625Hz/29.00975fps.
- B-A 처리+5.47098pp, 수신+5.80679%(30Hz정규화+5.30997pp). 부모 '-2pp 이내' 상대판정 PASS, 회귀 없음.
- POST p50 평균 A13.64685→B10.87740ms, -2.76945ms. '+1ms 이내' 목표충족.
- 절대관측: A2/B2 처리≥99%,수신≥29.7Hz,preview≥29.7fps 전부충족. A1/B1 미달, B평균도미달. 공식절대최종PASS는 부모가 조용한 창에서 측정할 때까지 보류.
- load run별2.39/3.72/3.26/3.55, GPU7%1571MiB/33%1855/30%1800/20%1663. V-P2 GPU벤치 미관측. 다른 성능벤치 프로세스는 flock대기명령만 관측, Windows Aside CPU 영향은 배제 못함.
- 세부B2 p50: visibility .0117ms, hold/quality .0086ms, timestamp .0039ms, poseoverlay .2089ms, handoverlay .2792ms, HTTP헤더8.8386ms/body .3280ms/응답JSON .0352ms. 안전로직 유지. POST증분을 quality계산으로 설명할 증거없음; HTTP준비경량화와 중복후처리 제거를 함께 적용한 총체A/B라 개별최적화 기여는 분리확정하지 않음.
- 증거: C:\Users\USER\.aside\u\0\sessions\2026-11-02_1NIgF2z2BvfBSkOh\tmp\tracker_ab_opt_1105.json, tracker_ab_opt_1105_summary.json, tracker_ab_opt_1105_server.log. V-W/부모에표전달.

## Panda 뷰어 기준선 재개 지점 (11/5)
- session1006 실행 중: bench/tracker_panda_viewer_run_1105.sh, measure-w900→gpu-w30 별도슬롯 대기. 원본 bench/verify_w/panda_viewer_base.sh 수정 안함; 포트5092→5095 임시치환하여 자기서버만 측정. Panda OFF + /video뷰어, warmup6초/측정30초, curl42초.
- 로그예정: 위tmp/tracker_panda_viewer_1105.log (+tracker_panda_viewer_server_1105.log). 완료후 V-W/부모에 mean/min/max/n 및 load/GPU 전달.
- 10분제한 전에 미완료면 부모가 bash_interact session1006 폴링. 세션이없을때만 해당run sh 재실행(기존프로세스중복 금지). wrapper trap이 자기5095 PID만 종료/뷰어임시sh삭제. 측정대기중wrapper파일 삭제금지.
- 커밋/5080/Documents복사본 미접촉.

## Panda 뷰어 기준선 완료 (11/5 13:11:43)
- session1006 exit0. 별도이중락13:11:02~13:11:43(41초), 자신의5095서버 G1OFF/Panda따라하기OFF, /video뷰어 연결. 원본V-W스크립트 포트만 임시치환(소유파일수정없음).
- warmup6초+30초/status 샘플: fps mean28.48/min13.3/max29.6/n136. 이는 status fps 산술평균 기준선이며 MJPEG실수신개수 기반fps가 아님. 최소값하락 원인단정하지 않음.
- load2.11/2.25/1.19→2.31/2.28/1.25, GPU9%1544MiB→7%1848MiB. V-P2실행없고 다른벤치flock대기명령만관측.
- 증거tmp/tracker_panda_viewer_1105.log 및tracker_panda_viewer_server_1105.log. 자신의5095 PID종료,뷰어timeout종료,임시뷰어sh삭제,락해제 확인. V-W/부모에결과전달완료.
- 이번11/5요청: ABAB 상대회귀없음PASS,POST증분목표충족; 절대최종quietwindow만별도대기. Panda뷰어기준선지원완료. 커밋/5080/Documents미접촉.
