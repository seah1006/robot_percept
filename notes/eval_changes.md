# E evaluation harness change log

## Implemented
- `eval/run_benchmark.py`: headless SimEnv, seeded randomized single-object scenes. CAD objects explicitly registered from converted OBJ + CoACD parts with add_object_from_mesh. No server/web imports.
- `eval/harness/worker.py`: sequential SAM2 and FoundationPose RPC in spawned process. Simulator parent never imports torch/FP. SAM uses visible GT-mask centroid snapped to visible pixel only to choose click; highest model score chooses candidate, not GT IoU. Benchmark supplies object identity. This is oracle click placement, not automatic detection.
- Motion adapts exporter push-object logic to explicit target; 5 frames default, 8 physics steps per frame. Fixed-step offline experiment, not real-time streaming/drop-frame evaluation.
- Metrics reuse pose_metrics.evaluate_pair; exact object diameter from convex-hull pairwise max. ADD-S threshold <= 10% diameter for box/cup/mustard pilot yaw ambiguity policy; all ADD values and raw rotations retained. Box C2 symmetry rotation; cup/mustard 1-degree sampled yaw. Mustard is not truly symmetric, so ADD-S must not be presented as asymmetric-object orientation accuracy.
- Every requested trial gets one JSONL row, including exceptions, missing predictions and control failures. Pose trial succeeds only when every requested frame succeeds. Pick/place separate from pose success. Wilson 95% CI uses full requested trial denominator.
- Actual tracking throughput = completed distinct track estimates divided by wall interval, including rendering, RPC and scoring. Not inverse latency. Register timing excludes scoring in round2.
- JSON manifest includes source hashes, git hash/dirty state, package versions and upstream Git IDs. Per-trial rows save seed, config, git hash, timings, VRAM, poses, diameter, missing predictions and failure reasons. Optional RGB/depth/masks replay NPZ.
- GT-assist control API wired: Controller(..., gt_assist=bool), estimated world pose for pick, same controller for place; GT callback for evaluation. C owns assistance semantics.
- No changes to sim/export_fp.py or eval/pose_metrics.py. No commits made.

## Verified so far
- tests/test_smoke.py: 2 passed.
- bench/eval/check_metrics.py: PASS (box C2, raw180, large translation failure, Wilson boundaries).
- GT smoke: 3 objects x3 seeds =9/9 pose trial success; reports/JSONL in bench/eval/gt_smoke_v1.
- FP N5 smoke is running in exclusive lock; progress/results in bench/eval/fp_smoke_v1. Do not claim full N5 until all15 rows exist.
- Independent V-E review requested; final PASS pending.

## Required remaining measurements
1. Finish N5 FP smoke and send all numbers to V-E; fix review findings.
2. N30 per object FP (90 trials) serial under GPU lock. N30 is pilot, not reliability proof.
3. N20/object perception {gt,fp} x gt-assist {on,off}, pick/place (240 trials). C flags now exist, but matrix is not yet measured.
4. Copy final report markdown/PNG into eval/report/ after accepted runs; retain raw trial directories under bench/eval/.

## Reproduce
```
source /home/user/anaconda3/etc/profile.d/conda.sh
conda activate robot_percept
cd /home/user/work/robot_percept
source sim_test/gl_env.sh
export HOST=127.0.0.1 OPENBLAS_NUM_THREADS=1
python -m pytest -q tests/test_smoke.py
python -m bench.eval.check_metrics
flock /tmp/rp_gpu.lock -c 'python -m eval.run_benchmark --n 30 --perception fp --save-replay --out bench/eval/fp_n30_v1'
for p in gt fp; do
  for a in on off; do
    flock /tmp/rp_gpu.lock -c "python -m eval.run_benchmark --n 20 --perception $p --gt-assist $a --pick on --out bench/eval/matrix_${p}_${a}_v1"
  done
done
```
Output directory must not exist. Existing runs are never overwritten.

## Round3 verifier corrections
V-E independently verified deterministic GT fields (9/9), exact metric recomputation (max diff0), diameter, Wilson and failure denominator. Conditional PASS CPU/GT only. Mustard false symmetry acceptance was identified and fixed: now asymmetric ADD. Cup retains ADD-S with <=20deg yaw-symmetry rotation gate. Box rotation symmetry now full D2. Added all-requested-frame success table. GT results explicitly labeled wiring smoke. The original running smoke used earlier scoring; preserve it and derive corrected metrics using `python -m eval.harness.rescore SOURCE NEW_OUT`. Final smoke sources: bench/eval/gt_smoke_r3 and bench/eval/fp_smoke_r3; corresponding report files in eval/report/. Final independent PASS still pending; N30/matrix unmeasured.

## Round4 completed measurements
V-E FP smoke PASS: independent75/75 frame recomputation, max numerical diff1e-14. Corrected FP smoke: each object5/5 trials (Wilson95 [.566,1]), actual-wall median FPS mustard2.34/box3.19/cup3.05. First cold register49.6s versus warm4-5s; torch peak2.2-3.4GB; do not claim10FPS. Mustard seed2 maskIoU .27 still about1.5mm translation error.
Control API wiring smoke at seed0 only, all3objects: gt-assist on pick3/3 place3/3; off pick2/3 place1/3 (mustard physical pick failure, cup place failure). Reports with per-object requested denominators and Wilson intervals: eval/report/pick_gt_{on,off}_smoke.md. These are API smoke, not the requested N20 matrix.
N30/object FP pilot has been launched under global GPU lock (execution session1030), output bench/eval/fp_n30_r3, log bench/eval/fp_n30_r3.log. It may wait for P's GPU slot. Full N20 matrix remains pending.
