# FPS changes

## Independent verification (V, port 5082)

| Metric | Original baseline | Optimized |
|---|---:|---:|
| Video, one client | 11.4–12.4 FPS | 27.4–28.9 FPS |
| Video, two clients each | 10.8–11.4 FPS | about 28.4 FPS |
| Tracking | 3.8–3.9 FPS | 8.89–11.72 FPS |
| Tracking, 60-second run | not measured | 11.72 FPS, p95 instantaneous 15.3 |
| Mean translation error | about 0.93 mm | 0.92–0.94 mm |
| Mean rotation error | about 1.54 deg | 1.54–1.58 deg |
| Video latency proxy mean | 50–51 ms | about 30 ms |
| Pick/place | success | success in every V run |
| Place error / upright | 1.0 mm / 1.0 | 1.0 mm / 1.0 |
| Post-place reacquire | supported | success in 5.5 s; 1.0 mm / 0.89 deg |
| GPU memory, 60-second tracking | not measured | 4.0 GB to 3.9 GB; no growth |
| Server log errors | 0 | 0 |

V final verdict: PASS, conditional only on clearing the JPEG cache when its idle producer exits. That one-line fix is applied. No other code changed after final verification. Tracking is not guaranteed above 10 FPS under shared-GPU contention: the second 15-second run averaged 8.89 FPS; first 10.98, extended run 11.72. These are sampled instantaneous inference FPS, not guaranteed wall-clock update throughput.

## Implementation

- `sim/env.py`: backward-compatible optional depth and segmentation passes. Default RGB/depth/seg outputs match the original backup exactly (all arrays zero differences). Mode-specific update_scene calls retained for correct segmentation.
- `web/sim_worker.py`: publish cap 18 to 30 Hz; RGB-only idle, RGB+depth tracking, complete synchronized RGB-D-seg on click/reacquire/commands. Refresh segmentation when object transforms move beyond tolerance 1e-5, including uncommanded object motion. Cached object-edge depth filtering retained between segmentation renders. Physics pacing remains independent of the render cap.
- `web/app.py`: JPEG quality 80; shared lazy encoder per GT-overlay variant instead of per viewer; no duplicate encodes for one frame. Stop producer after two seconds without consumers and clear its cache, restart on demand. RGB-only overlay copies. Track polling delay 30 to 3 ms. Full refresh before selection and post-place registration. need_depth intentionally clears on drop/reset and otherwise survives worker status updates.
- `perception/fp_runner.py`: tracking refinement iterations 2 to 1, CPU thread pool 1, cuDNN benchmark enabled, retain CUDA allocator during track only. The scoped empty_cache override is restored in finally on success and failure. This relies on the dedicated, serialized perception process. SAM and registration retain ordinary cache-release behavior. Registration iterations unchanged; refiner already uses fp16 autocast upstream.
- UI language, endpoints, overlays, movement pause, pick/place and reacquisition behavior retained. Port 5080 was never restarted or deployed.

## Profiling and rationale

I baseline: physics 0.107 ms, full RGB-D-seg render 69.10 ms, array copies 0.466 ms, color/JPEG80 2.79 ms. Corrected optional-pass run under shared load: RGB19.45 ms, RGB-D39.49 ms, full103.11 ms. Do not compare the full-pass runs as a speed regression: load varied, while accuracy-equivalence is exact.

Offline saved-frame diagnostic, GT-seeded only to isolate tracking, 25 frames with first three omitted from aggregate: original iter2 + allocator flush 4.30 FPS / 0.782 mm / 1.618 deg; skip flush 5.60 FPS; iter1 8.09 FPS; threads1 + cuDNN + iter1 + retained cache 14.01 FPS / 0.789 mm / 1.619 deg. Tuned crop about33 ms, neural forward17 ms, depth processing4.4 ms. Stage probes synchronize CUDA and can perturb timing.

RGB-D pickle serialization measured0.59 ms; IPC/shared-memory changes deferred because crop and network dominate. No smaller crop, model compilation, or resolution reduction introduced: avoid accuracy risk after meeting the extended-run target. JPEG quality reduction affects display only, not perception input.

## Reproduce

Use the robot_percept conda environment. Source `sim_test/gl_env.sh` and set HOST=127.0.0.1.

- `PYTHONPATH=. python bench/impl/profile_stages.py`
- `bash bench/impl/check_render_equivalence.sh`
- `PYTHONPATH=. FP_INPLANE_STEP=120 python bench/impl/profile_track.py`
- `PYTHONPATH=. FP_INPLANE_STEP=120 python bench/impl/profile_track_tuned.py`
- `bash bench/impl/run_http.sh` starts and cleans up its own port5081 server.
- V regression: `bash bench/verify/run.sh <label> 2` uses5082. Do not benchmark concurrently with another agent on the shared GPU.

Detailed V evidence: `notes/fps_verify.md` and `bench/verify/out/`. Implementation measurements: `bench/impl/*.json`.

Tuning overrides: FP_TRACK_REFINE_ITER=2, FP_CPU_THREADS, FP_CUDNN_BENCHMARK=0, FP_TRACK_KEEP_CACHE=0. To restore all original behavior, use the unmodified `data/backup_fps` backup, not just these tracking switches.
