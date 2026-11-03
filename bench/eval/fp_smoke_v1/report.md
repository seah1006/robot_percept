# Headless evaluation pilot

All requested trials, including exceptions and missing estimates, remain in the denominator. FPS counts completed tracking estimates over actual wall time, including render and RPC. Offline fixed-step motion is not a real-time frame-drop experiment.

SAM click is the visible GT-segmentation centroid, snapped to the nearest visible pixel. GT does not select a SAM candidate; maximum SAM score does. Object identity is supplied by the benchmark. Existing depth-edge filtering remains enabled.

Symmetry: box C2 yaw; cup and mustard yaw-ambiguous ADD-S pilot policy (mustard is not exactly symmetric). Rotation uses 1-degree yaw sampling for the latter. N=30 is a pilot, not reliability proof.

| Object | perception | GT assist | N | pose success (95% Wilson) | reg med/p95 s | track FPS med | pick/place |
|---|---|---|---:|---|---|---|---|
| mustard | fp | on | 5 | 5/5 (0.566, 1.000) | 5.099/40.701 | 2.34 | off |
| box | fp | on | 5 | 5/5 (0.566, 1.000) | 4.385/4.833 | 3.19 | off |
| cup | fp | on | 5 | 5/5 (0.566, 1.000) | 4.060/4.858 | 3.05 | off |
