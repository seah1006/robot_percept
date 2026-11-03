# Headless evaluation pilot

All requested trials, including exceptions and missing estimates, remain in the denominator. FPS counts completed tracking estimates over actual wall time, including render and RPC. Offline fixed-step motion is not a real-time frame-drop experiment.

SAM click is the visible GT-segmentation centroid, snapped to the nearest visible pixel. GT does not select a SAM candidate; maximum SAM score does. Object identity is supplied by the benchmark. Existing depth-edge filtering remains enabled.

Symmetry: box D2 (pi about each principal axis), cup yaw with a 20-degree symmetry-rotation acceptance gate. Mustard is asymmetric and uses ADD. Cup yaw rotation is sampled at 1-degree spacing. GT-perception results are wiring smoke only: pred=GT by construction. N=30 is a pilot, not reliability proof.

| Object | perception | GT assist | N | pose success (95% Wilson) | reg med/p95 s | track FPS med | pick/place |
|---|---|---|---:|---|---|---|---|
| mustard | gt | off | 1 | 1/1 (0.207, 1.000) | 0.000/0.000 | 3.10 | pick 0/1 (0.000, 0.793); place 0/1 (0.000, 0.793) |
| box | gt | off | 1 | 1/1 (0.207, 1.000) | 0.000/0.000 | 3.39 | pick 1/1 (0.207, 1.000); place 1/1 (0.207, 1.000) |
| cup | gt | off | 1 | 1/1 (0.207, 1.000) | 0.000/0.000 | 2.18 | pick 1/1 (0.207, 1.000); place 0/1 (0.000, 0.793) |

## Frame-level success (all requested frames)

| Object | Successful / requested frames | Missing frames |
|---|---|---|
| mustard | 5/5 | 0 |
| box | 5/5 | 0 |
| cup | 5/5 | 0 |

## Pose and failure diagnostics

| Object | translation median/p95 mm | raw rotation median/p95 deg | symmetry rotation median/p95 deg | ADD-S median/p95 mm | failed trials |
|---|---|---|---|---|---|
| mustard | 0.000/0.000 | 0.000/0.000 | 0.000/0.000 | 0.000/0.000 | 0 |
| box | 0.000/0.000 | 0.000/0.000 | 0.000/0.000 | 0.000/0.000 | 0 |
| cup | 0.000/0.000 | 0.000/0.000 | 0.000/0.000 | 0.000/0.000 | 0 |

Frame-error quantiles condition on available estimates; trial success above requires every requested estimate and retains failures in its denominator.

- mustard seed 0: ['pick_failure']
- cup seed 0: ['place_failure']
