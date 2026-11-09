# Headless evaluation pilot

All requested trials, including exceptions and missing estimates, remain in the denominator. FPS counts completed tracking estimates over actual wall time, including render and RPC. Offline fixed-step motion is not a real-time frame-drop experiment.

SAM click is the visible GT-segmentation centroid, snapped to the nearest visible pixel. GT does not select a SAM candidate; the current depth-aware SAM candidate policy and click-connected component do. Object identity is supplied by the benchmark. Existing depth-edge filtering remains enabled.

Symmetry: box D2 (pi about each principal axis), cup yaw with a 20-degree symmetry-rotation acceptance gate. Mustard is asymmetric and uses ADD. Cup yaw rotation is sampled at 1-degree spacing. GT-perception results are wiring smoke only: pred=GT by construction. N=30 is a pilot, not reliability proof.

| Object | perception | GT assist | N | pose success (95% Wilson) | reg med/p95 s | track FPS med | pick/place |
|---|---|---|---:|---|---|---|---|
| mustard | fp | on | 30 | 30/30 (0.886, 1.000) | 2.367/25.967 | 7.72 | off |
| box | fp | on | 30 | 5/30 (0.073, 0.336) | 3.621/21.695 | 4.70 | off |
| cup | fp | on | 30 | 0/30 (0.000, 0.114) | - | - | off |

## Frame-level success (all requested frames)

| Object | Successful / requested frames | Missing frames |
|---|---|---|
| mustard | 150/150 | 0 |
| box | 25/150 | 125 |
| cup | 0/150 | 150 |

## Pose and failure diagnostics

| Object | translation median/p95 mm | raw rotation median/p95 deg | symmetry rotation median/p95 deg | ADD-S median/p95 mm | failed trials |
|---|---|---|---|---|---|
| mustard | 1.276/1.829 | 0.633/1.330 | 0.633/1.330 | 1.175/1.522 | 0 |
| box | 1.184/3.246 | 178.877/179.984 | 0.756/1.411 | 0.967/2.655 | 25 |
| cup | - | - | - | - | 30 |

Frame-error quantiles condition on available estimates; trial success above requires every requested estimate and retains failures in its denominator.

- box seed 5: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 6: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 7: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 8: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 9: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 10: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 11: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 12: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 13: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 14: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 15: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 16: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 17: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 18: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 19: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 20: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 21: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 22: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 23: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 24: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 25: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 26: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 27: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 28: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 29: ['missing_trial: unexecuted/interrupted/timeout']
- cup seed 0: ['missing_trial: unexecuted/interrupted/timeout']
- cup seed 1: ['missing_trial: unexecuted/interrupted/timeout']
- cup seed 2: ['missing_trial: unexecuted/interrupted/timeout']
- cup seed 3: ['missing_trial: unexecuted/interrupted/timeout']
- cup seed 4: ['missing_trial: unexecuted/interrupted/timeout']
- cup seed 5: ['missing_trial: unexecuted/interrupted/timeout']
- cup seed 6: ['missing_trial: unexecuted/interrupted/timeout']
- cup seed 7: ['missing_trial: unexecuted/interrupted/timeout']
- cup seed 8: ['missing_trial: unexecuted/interrupted/timeout']
- cup seed 9: ['missing_trial: unexecuted/interrupted/timeout']
- cup seed 10: ['missing_trial: unexecuted/interrupted/timeout']
- cup seed 11: ['missing_trial: unexecuted/interrupted/timeout']
- cup seed 12: ['missing_trial: unexecuted/interrupted/timeout']
- cup seed 13: ['missing_trial: unexecuted/interrupted/timeout']
- cup seed 14: ['missing_trial: unexecuted/interrupted/timeout']
- cup seed 15: ['missing_trial: unexecuted/interrupted/timeout']
- cup seed 16: ['missing_trial: unexecuted/interrupted/timeout']
- cup seed 17: ['missing_trial: unexecuted/interrupted/timeout']
- cup seed 18: ['missing_trial: unexecuted/interrupted/timeout']
- cup seed 19: ['missing_trial: unexecuted/interrupted/timeout']
- cup seed 20: ['missing_trial: unexecuted/interrupted/timeout']
- cup seed 21: ['missing_trial: unexecuted/interrupted/timeout']
- cup seed 22: ['missing_trial: unexecuted/interrupted/timeout']
- cup seed 23: ['missing_trial: unexecuted/interrupted/timeout']
- cup seed 24: ['missing_trial: unexecuted/interrupted/timeout']
- cup seed 25: ['missing_trial: unexecuted/interrupted/timeout']
- cup seed 26: ['missing_trial: unexecuted/interrupted/timeout']
- cup seed 27: ['missing_trial: unexecuted/interrupted/timeout']
- cup seed 28: ['missing_trial: unexecuted/interrupted/timeout']
- cup seed 29: ['missing_trial: unexecuted/interrupted/timeout']
