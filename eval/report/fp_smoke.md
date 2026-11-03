# Headless evaluation pilot

All requested trials, including exceptions and missing estimates, remain in the denominator. FPS counts completed tracking estimates over actual wall time, including render and RPC. Offline fixed-step motion is not a real-time frame-drop experiment.

SAM click is the visible GT-segmentation centroid, snapped to the nearest visible pixel. GT does not select a SAM candidate; maximum SAM score does. Object identity is supplied by the benchmark. Existing depth-edge filtering remains enabled.

Symmetry: box D2 (pi about each principal axis), cup yaw with a 20-degree symmetry-rotation acceptance gate. Mustard is asymmetric and uses ADD. Cup yaw rotation is sampled at 1-degree spacing. GT-perception results are wiring smoke only: pred=GT by construction. N=30 is a pilot, not reliability proof.

| Object | perception | GT assist | N | pose success (95% Wilson) | reg med/p95 s | track FPS med | pick/place |
|---|---|---|---:|---|---|---|---|
| mustard | fp | on | 5 | 5/5 (0.566, 1.000) | 5.099/40.701 | 2.34 | off |
| box | fp | on | 5 | 5/5 (0.566, 1.000) | 4.385/4.833 | 3.19 | off |
| cup | fp | on | 5 | 5/5 (0.566, 1.000) | 4.060/4.858 | 3.05 | off |

## Frame-level success (all requested frames)

| Object | Successful / requested frames | Missing frames |
|---|---|---|
| mustard | 25/25 | 0 |
| box | 25/25 | 0 |
| cup | 25/25 | 0 |

## Pose and failure diagnostics

| Object | translation median/p95 mm | raw rotation median/p95 deg | symmetry rotation median/p95 deg | ADD-S median/p95 mm | failed trials |
|---|---|---|---|---|---|
| mustard | 1.518/1.701 | 0.798/1.064 | 0.798/1.064 | 1.322/1.529 | 0 |
| box | 1.299/3.205 | 178.373/179.785 | 0.856/1.673 | 1.088/2.647 | 0 |
| cup | 0.899/1.103 | 121.186/177.839 | 1.144/1.484 | 1.008/1.126 | 0 |

Frame-error quantiles condition on available estimates; trial success above requires every requested estimate and retains failures in its denominator.


## Independently verified smoke limitations
- V-E recomputed all 75 frame metrics, max numeric difference 1e-14; 75/75 frames and 15/15 trials passed corrected scoring.
- Actual tracking throughput observed 1.8-3.7 FPS, not 10 FPS. First cold registration was 49.6 s versus roughly 4-5 s warm; GPU peak allocation was 2.2-3.4 GB (PyTorch allocation, not total device usage).
- Mustard seed2 mask IoU was 0.27 despite approximately 1.5 mm translation error.
- N=5 per object is a smoke pilot only; each Wilson lower bound is 0.566.
