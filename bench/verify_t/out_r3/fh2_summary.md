# fh2 summary (video=teleop_final_hand.mp4, mode=humanoid)

| window | ratio_pct | tracker_hz | recv_hz | recv_hz_fit | preview_fps | screen_fps | post_p50 | post_p95 | srv_main_cpu | srv_tree_cpu | neural_p95 | hand_rate_pct | pose_rate_pct | net_err | win_sys_cpu | load_before | walljumps |
|-|-|-|-|-|-|-|-|-|-|-|-|-|-|-|-|-|-|
| A.w1_http_http | 94.673 | 28.426 | 28.460 | 28.302 | 28.460 | 31.566 | 10.422 | 24.460 | 41.000 | 190.100 | 46.963 | 68.347 | 100.000 | 0.000 | 80.500 | 1.920 | 12.000 |
| A.w2_ws_ws | 99.001 | 29.723 | 29.727 | 30.005 | 29.719 | 31.736 | 3.580 | 5.953 | 33.100 | 170.800 | 43.887 | 69.507 | 100.000 | 0.000 | 73.300 | 2.930 | 11.000 |
| A.w3_http_http | 95.006 | 28.517 | 28.541 | 28.734 | 28.541 | 31.446 | 10.533 | 21.591 | 40.300 | 186.700 | 48.092 | 68.458 | 100.000 | 0.000 | 75.200 | 2.470 | 12.000 |
| A.w4_ws_ws | 99.001 | 29.723 | 29.743 | 29.657 | 29.713 | 31.685 | 3.245 | 5.318 | 32.000 | 161.400 | 42.105 | 69.507 | 100.000 | 0.000 | 64.000 | 2.580 | 12.000 |
| B.w1_ws_ws | 100.000 | 30.010 | 30.055 | 30.019 | 30.055 | 31.660 | 3.483 | 6.112 | 33.300 | 167.900 | 40.807 | 68.812 | 100.000 | 0.000 | 71.700 | 1.040 | 12.000 |
| B.w2_http_http | 95.893 | 28.771 | 28.743 | 28.123 | 28.743 | 30.512 | 10.744 | 27.550 | 40.700 | 188.400 | 45.655 | 68.750 | 100.000 | 0.000 | 79.400 | 2.140 | 11.000 |

## ws - http paired diff, bootstrap 95pct CI (pairs=3, coarse)
| metric | mean diff | CI | verdict |
|-|-|-|-|
| ratio_pct | +4.144 | [+3.996, +4.329] | 0 not included |
| tracker_hz | +1.247 | [+1.206, +1.297] | 0 not included |
| recv_hz | +1.260 | [+1.202, +1.312] | 0 not included |
| recv_hz_fit | +1.507 | [+0.923, +1.896] | 0 not included |
| preview_fps | +1.248 | [+1.172, +1.312] | 0 not included |
| screen_fps | +0.519 | [+0.170, +1.148] | 0 not included |
| post_p50 | -7.131 | [-7.288, -6.842] | 0 not included |
| post_p95 | -18.739 | [-21.438, -16.272] | 0 not included |
| srv_main_cpu | -7.867 | [-8.300, -7.400] | 0 not included |
| srv_tree_cpu | -21.700 | [-25.300, -19.300] | 0 not included |
| neural_p95 | -4.637 | [-5.987, -3.076] | 0 not included |
| hand_rate_pct | +0.757 | [+0.062, +1.160] | 0 not included |
| pose_rate_pct | +0.000 | [+0.000, +0.000] | diff not proven (includes 0) |
| net_err | +0.000 | [+0.000, +0.000] | diff not proven (includes 0) |
| win_sys_cpu | -8.700 | [-11.200, -7.200] | 0 not included |
| load_before | +0.007 | [-1.100, +1.010] | diff not proven (includes 0) |
| walljumps | +0.000 | [-1.000, +1.000] | diff not proven (includes 0) |

## absolute thresholds per window (ratio>=99, recv>=29.7, preview>=29.7, screen>=29.7)
- A.w1_http_http: ratio False, recv False, preview False, screen True
- A.w2_ws_ws: ratio True, recv True, preview True, screen True
- A.w3_http_http: ratio False, recv False, preview False, screen True
- A.w4_ws_ws: ratio True, recv True, preview True, screen True
- B.w1_ws_ws: ratio True, recv True, preview True, screen True
- B.w2_http_http: ratio False, recv False, preview False, screen True