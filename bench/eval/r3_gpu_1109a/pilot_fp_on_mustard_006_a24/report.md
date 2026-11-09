# Headless evaluation pilot

All requested trials, including exceptions and missing estimates, remain in the denominator. FPS counts completed tracking estimates over actual wall time, including render and RPC. Offline fixed-step motion is not a real-time frame-drop experiment.

SAM click is the visible GT-segmentation centroid, snapped to the nearest visible pixel. GT does not select a SAM candidate; the current depth-aware SAM candidate policy and click-connected component do. Object identity is supplied by the benchmark. Existing depth-edge filtering remains enabled.

Symmetry: box D2 (pi about each principal axis), cup yaw with a 20-degree symmetry-rotation acceptance gate. Mustard is asymmetric and uses ADD. Cup yaw rotation is sampled at 1-degree spacing. GT-perception results are wiring smoke only: pred=GT by construction. N=30 is a pilot, not reliability proof.

| Object | perception | GT assist | N | pose success (95% Wilson) | reg med/p95 s | track FPS med | pick/place |
|---|---|---|---:|---|---|---|---|
| mustard | fp | on | 24 | 24/24 (0.862, 1.000) | 2.347/2.780 | 7.88 | off |

## Frame-level success (all requested frames)

| Object | Successful / requested frames | Missing frames |
|---|---|---|
| mustard | 120/120 | 0 |

## Pose and failure diagnostics

| Object | translation median/p95 mm | raw rotation median/p95 deg | symmetry rotation median/p95 deg | ADD-S median/p95 mm | failed trials |
|---|---|---|---|---|---|
| mustard | 1.191/1.839 | 0.602/1.385 | 0.602/1.385 | 1.114/1.509 | 0 |

Frame-error quantiles condition on available estimates; trial success above requires every requested estimate and retains failures in its denominator.

