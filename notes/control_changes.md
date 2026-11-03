# Control changes (I-C, pending independent V-C verification)

- `sim/grasp.py`, `sim/ik.py`: tall-object fast-first IK pass and deterministic bounded fallback (45 iterations x 2 restarts, five seeds), while `solve_ik` retains legacy 10 restarts by default. No geometric tolerances relaxed. New 30-seed CPU times (`MUJOCO_GL=egl OPENBLAS_NUM_THREADS=1`): mustard p50/p95/max .085/.169/.206 s, box .020/.099/.126 s, cup .015/.119/.133 s; all zero planner failures. Paired baseline measurement in progress.
- `sim/control.py`: `gt_assist=True` default, off uses estimated grasp-relative transform and initial estimated z, disables weld/GT correction and height gate; GT callbacks still score success. `return_home` checks 81 joint-space path samples, uses checked 10cm Cartesian clearance if obstructed, monitors live arm/table/object contacts and verifies <.02 rad error and <5mm object displacement. `web/sim_worker.py` accepts pick command `gt_assist`, homes after place, exposes home phase/error.
- `notes/gt_usage.md` audits all control GT use, `notes/control_api.md` documents evaluation API.
- `tests/test_pick_place.py`: `--no-gt-assist`, home assertions, fixed image path, on/off results names. Smoke: 2/2 passed. Single-object seed0 default mustard/box/cup picked+placed+homed. Seed0 off mode: mustard pick true/place error 204mm/upright 0.005; box pick true/place error 9.77mm/upright 1; cup pick true/place error 40.47mm/upright 1. These are diagnostics, not 20-seed success rates.
- Shared `mesh_spec` collision-hull writes race across independent processes. Avoid parallel SimEnv runs; transient MuJoCo '<4 vertices' error occurred in paired benchmark before serialization. No edits to sim/objects.py (outside pair ownership).

Repro: `source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept; MUJOCO_GL=egl OPENBLAS_NUM_THREADS=1 python -m pytest -q tests/test_smoke.py`; `python tests/test_pick_place.py --trials 20 --suite all` and `--no-gt-assist`. Full 20-seed regression and V-C PASS remain pending.

## V-C round 1 response
V-C found default mustard pick regression (8/10) from fast IK random restarts choosing exotic postures. Fast pass now has restarts=1; seeds 4 and 5 both picked, placed, homed locally. Off-mode pick ok now uses width plus bilateral contact instead of GT lift; lifted and gt_lift_ok remain scoring. Web pick/place routes forward optional gt_assist. Worker records home warnings separately after successful place. Ten-seed mustard rerun pending.

## V-C round 2 response
- Worker status now exposes status["last_pick"]={ok, gt_lift_ok, lifted_m} (GT values are scoring-only).
- gt_assist=off caveat: pick ok is contact/width based and OPTIMISTIC (drops after lift possible; V-C saw lift -0.036 m with ok=true). Use gt_lift_ok for scoring. Off-mode place success is the honest metric (V-C N=10: mustard place 0/10, box 10/10, cup 6/10, multi 0/10).
- _neighbor_checker residual GT xpos association remains listed in notes/gt_usage.md.
- Not done: obstructed-home negative test; 20-seed regression (single suite exceeded my 600 s shell limit). V-C N=10 defaults were 10/10 for all suites.
