# Headless evaluation pilot

All requested trials, including exceptions and missing estimates, remain in the denominator. FPS counts completed tracking estimates over actual wall time, including render and RPC. Offline fixed-step motion is not a real-time frame-drop experiment.

SAM click is the visible GT-segmentation centroid, snapped to the nearest visible pixel. GT does not select a SAM candidate; maximum SAM score does. Object identity is supplied by the benchmark. Existing depth-edge filtering remains enabled.

Symmetry: box C2 yaw; cup and mustard yaw-ambiguous ADD-S pilot policy (mustard is not exactly symmetric). Rotation uses 1-degree yaw sampling for the latter. N=30 is a pilot, not reliability proof.

| Object | perception | GT assist | N | pose success (95% Wilson) | reg med/p95 s | track FPS med | pick/place |
|---|---|---|---:|---|---|---|---|
| mustard | gt | on | 3 | 3/3 (0.439, 1.000) | 0.154/0.223 | 4.33 | off |
| box | gt | on | 3 | 3/3 (0.439, 1.000) | 0.011/0.019 | 8.99 | off |
| cup | gt | on | 3 | 3/3 (0.439, 1.000) | 0.097/0.098 | 5.29 | off |
