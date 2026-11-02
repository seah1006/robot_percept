# FoundationPose process adapter

Run from `/home/user/work/robot_percept` in conda `robot_percept`:

```bash
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
python -m perception.fp_runner data/sim_scenes/mustard_static --out data/fp_results/mustard_static
python -m eval.pose_metrics data/fp_results/mustard_static data/sim_scenes/mustard_static --mesh data/sim_scenes/mustard_static/mesh/textured_simple.obj --out data/fp_results/mustard_static/metrics.json
```

`FPRunner(mesh_path, est_refine_iter=5, track_refine_iter=2, debug_dir=None)` exposes `register(rgb, depth_m, mask, K)` and `track(rgb, depth_m, K)`. Input RGB uint8, depth float meters planar camera-z, mask bool, intrinsics 3x3. Output 4x4 `T_cam_obj` at the original mesh origin in OpenCV coordinates.

**Process isolation required:** FoundationPose changes default tensor type to CUDA process-wide. Invoke this CLI through a child process, not a shared SAM/web/MuJoCo process. Do not share its object across processes.

Input demo format: `cam_K.txt`, `rgb/*.png`, `depth/*.png` (uint16 millimeters), `masks/*.png`, `mesh/textured_simple.obj`. First-frame mask only used for inference. GT `ob_in_cam/*.txt` is optional and used ONLY for overlays. Results contain matching stems under `ob_in_cam/`, `overlay/*.png` (red predicted box, green GT box), and `runtime.json`. Six-digit sim input stems yield `%06d.txt` output. `--mesh`, `--max-frames`, `--est-refine-iter`, `--track-refine-iter` available.

8GB profile: `FP_INPLANE_STEP=120` (126 hypotheses), refiner/crop chunks 32. Set `FP_INPLANE_STEP=60` to use upstream 252 hypotheses, with higher memory demand. Runtime excludes model initialization; CUDA synchronize wraps each inference. Tracking FPS excludes overlay/file writing. nvidia-smi CSV reflects whole-device memory and may include other agents/desktop.
