# GA2 changes

## Status
FakeEnv contract implementation complete. Real-env tuning/evaluation pending GA1 readiness notification from parent. No evaluation seeds have been run or used for tuning.

## Owned files
- tools/m2a_grasp_gate.py
- tests/test_m2a_grasp_gate.py
- notes/m2a/ga2_changes.md
- bench/m2a_ga/ (future real-env output)

No edits to GA1 or existing operational files. No install, download, commit or push.

## Sequence and parameters
reset -> open -> pregrasp at +0.10m -> descend offset +0.005m -> close linearly over .5s -> lift .10m over 1s -> hold 2s. Approach and descend settling .5s each. Samples .02s (50Hz), stage wall timeout 15s. Params dataclass accepts JSON overrides. Optional env.pregrasp_pose converts desired object-relative height/yaw into the palm-down target; otherwise wxyz yaw-composed X half-turn is used.

Judge uses only truth object/palm positions and quaternion, contact values, finite state and penetration, not weld state. Relative position is expressed in palm coordinates. Exact .05m lift and .03m drift boundaries accepted (1e-9 numerical tolerance). Complete hold must span 2s and every adjacent gap <=.02s. Penetration checked over all phases. IK/stage timeout are runner errors, independently from weld.

Raw per-trial JSONL includes seed, mode/object, success/code, max_lift, hold_time, max_relative_drift, max_penetration, unique closing finger contacts, simulation and wall durations. Summary JSON/MD includes successes, Wilson 95%, failure distribution, >=12/20 classification only when n=20, git commit/dirty flag, params, mujoco version and seeds. Existing raw output paths rejected to avoid accidental result mixing. PNG options capture lift and hold endpoints for first N trials. Gate explicitly described as weld approximation; oracle CLI excluded.

## Tuning history
No tuning yet. Reserved tuning seeds 0-99 and evaluation seeds 1000-1019; evaluation data must not be used to adjust parameters.

## Tests
Command: `wsl -d Ubuntu-24.04 -- bash /tmp/m2a_ga2_test.sh`
Result: **17 passed**, 0.06s, one unrelated dash pytest deprecation warning.
Tests cover all seven failure codes, height/drift boundaries, table contact, duration/sample gaps, weld independence, palm-frame rotation, Wilson intervals, seed parsing, summary report, FakeEnv full sequence, IK failure, invalid sampling.

## Pending / unresolved
GA1 readiness notification required before actual integration, tuning and six mode-object evaluation batches. No real-world or simulated gate pass claim made at this stage.

## GA1 preliminary clearance integration (no real measurements)
GA1 advised optional clearance waypoint from pregrasp_pose(height=.16), override x=.13, settle 2s before normal pregrasp. Added Params waypoint_x (default None, preserving FakeEnv baseline), waypoint_height=.16 and waypoint_seconds=2; descent now interpolates targets instead of a single jump. These are preparatory options, not tuned/evaluated parameters. GA1 still adjusting low descent/table geometry. New regression test verifies optional waypoint path; latest command `wsl -d Ubuntu-24.04 -- bash /tmp/m2a_ga2_waypoint_test.sh`: **18 passed**, 0.06s. Earlier /tmp test script had disappeared and was recreated with a new name.
