# Headless evaluation pilot

All requested trials, including exceptions and missing estimates, remain in the denominator. FPS counts completed tracking estimates over actual wall time, including render and RPC. Offline fixed-step motion is not a real-time frame-drop experiment.

SAM click is the visible GT-segmentation centroid, snapped to the nearest visible pixel. GT does not select a SAM candidate; the current depth-aware SAM candidate policy and click-connected component do. Object identity is supplied by the benchmark. Existing depth-edge filtering remains enabled.

Symmetry: box D2 (pi about each principal axis), cup yaw with a 20-degree symmetry-rotation acceptance gate. Mustard is asymmetric and uses ADD. Cup yaw rotation is sampled at 1-degree spacing. GT-perception results are wiring smoke only: pred=GT by construction. N=30 is a pilot, not reliability proof.

| Object | perception | GT assist | N | pose success (95% Wilson) | reg med/p95 s | track FPS med | pick/place |
|---|---|---|---:|---|---|---|---|
| mustard | gt | on | 20 | 0/20 (0.000, 0.161) | - | - | pick 0/20 (0.000, 0.161); place 0/20 (0.000, 0.161) |
| box | gt | on | 20 | 0/20 (0.000, 0.161) | - | - | pick 0/20 (0.000, 0.161); place 0/20 (0.000, 0.161) |
| cup | gt | on | 20 | 0/20 (0.000, 0.161) | - | - | pick 0/20 (0.000, 0.161); place 0/20 (0.000, 0.161) |
| mustard | gt | off | 20 | 0/20 (0.000, 0.161) | - | - | pick 0/20 (0.000, 0.161); place 0/20 (0.000, 0.161) |
| box | gt | off | 20 | 0/20 (0.000, 0.161) | - | - | pick 0/20 (0.000, 0.161); place 0/20 (0.000, 0.161) |
| cup | gt | off | 20 | 0/20 (0.000, 0.161) | - | - | pick 0/20 (0.000, 0.161); place 0/20 (0.000, 0.161) |
| mustard | fp | on | 20 | 0/20 (0.000, 0.161) | - | - | pick 0/20 (0.000, 0.161); place 0/20 (0.000, 0.161) |
| box | fp | on | 20 | 0/20 (0.000, 0.161) | - | - | pick 0/20 (0.000, 0.161); place 0/20 (0.000, 0.161) |
| cup | fp | on | 20 | 0/20 (0.000, 0.161) | - | - | pick 0/20 (0.000, 0.161); place 0/20 (0.000, 0.161) |
| mustard | fp | off | 20 | 0/20 (0.000, 0.161) | - | - | pick 0/20 (0.000, 0.161); place 0/20 (0.000, 0.161) |
| box | fp | off | 20 | 0/20 (0.000, 0.161) | - | - | pick 0/20 (0.000, 0.161); place 0/20 (0.000, 0.161) |
| cup | fp | off | 20 | 0/20 (0.000, 0.161) | - | - | pick 0/20 (0.000, 0.161); place 0/20 (0.000, 0.161) |

## Frame-level success (all requested frames)

| Object | Successful / requested frames | Missing frames |
|---|---|---|
| mustard | 0/100 | 100 |
| box | 0/100 | 100 |
| cup | 0/100 | 100 |
| mustard | 0/100 | 100 |
| box | 0/100 | 100 |
| cup | 0/100 | 100 |
| mustard | 0/100 | 100 |
| box | 0/100 | 100 |
| cup | 0/100 | 100 |
| mustard | 0/100 | 100 |
| box | 0/100 | 100 |
| cup | 0/100 | 100 |

## Pose and failure diagnostics

| Object | translation median/p95 mm | raw rotation median/p95 deg | symmetry rotation median/p95 deg | ADD-S median/p95 mm | failed trials |
|---|---|---|---|---|---|
| mustard | - | - | - | - | 20 |
| box | - | - | - | - | 20 |
| cup | - | - | - | - | 20 |
| mustard | - | - | - | - | 20 |
| box | - | - | - | - | 20 |
| cup | - | - | - | - | 20 |
| mustard | - | - | - | - | 20 |
| box | - | - | - | - | 20 |
| cup | - | - | - | - | 20 |
| mustard | - | - | - | - | 20 |
| box | - | - | - | - | 20 |
| cup | - | - | - | - | 20 |

Frame-error quantiles condition on available estimates; trial success above requires every requested estimate and retains failures in its denominator.

- mustard seed 0: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 1: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 2: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 3: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 4: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 5: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 6: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 7: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 8: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 9: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 10: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 11: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 12: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 13: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 14: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 15: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 16: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 17: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 18: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 19: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 0: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 1: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 2: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 3: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 4: ['missing_trial: unexecuted/interrupted/timeout']
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
- mustard seed 0: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 1: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 2: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 3: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 4: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 5: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 6: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 7: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 8: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 9: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 10: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 11: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 12: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 13: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 14: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 15: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 16: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 17: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 18: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 19: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 0: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 1: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 2: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 3: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 4: ['missing_trial: unexecuted/interrupted/timeout']
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
- mustard seed 0: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 1: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 2: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 3: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 4: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 5: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 6: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 7: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 8: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 9: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 10: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 11: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 12: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 13: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 14: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 15: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 16: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 17: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 18: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 19: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 0: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 1: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 2: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 3: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 4: ['missing_trial: unexecuted/interrupted/timeout']
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
- mustard seed 0: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 1: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 2: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 3: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 4: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 5: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 6: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 7: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 8: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 9: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 10: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 11: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 12: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 13: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 14: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 15: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 16: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 17: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 18: ['missing_trial: unexecuted/interrupted/timeout']
- mustard seed 19: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 0: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 1: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 2: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 3: ['missing_trial: unexecuted/interrupted/timeout']
- box seed 4: ['missing_trial: unexecuted/interrupted/timeout']
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
