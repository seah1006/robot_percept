# fh summary (video=teleop_final_hand.mp4, mode=humanoid)

| window | ratio_pct | tracker_hz | recv_hz | recv_hz_fit | preview_fps | screen_fps | post_p50 | post_p95 | srv_main_cpu | srv_tree_cpu | neural_p95 | hand_rate_pct | pose_rate_pct | net_err | win_sys_cpu | load_before | walljumps |
|-|-|-|-|-|-|-|-|-|-|-|-|-|-|-|-|-|-|
| A.w1_http_http | 98.890 | 29.695 | 29.678 | - | 29.678 | 31.293 | 9.811 | 23.514 | 27.200 | 165.400 | 41.692 | 69.585 | 100.000 | 0.000 | 77.400 | 1.510 | 11.000 |
| A.w2_ws_ws | 100.000 | 30.014 | 29.742 | - | 29.803 | 31.046 | 3.281 | 6.586 | 20.900 | 146.500 | 41.365 | 68.812 | 100.000 | 0.000 | 69.200 | 2.500 | 12.000 |
| A.w3_http_http | 99.778 | 29.946 | 29.809 | - | 29.842 | 31.703 | 8.722 | 21.821 | 25.200 | 151.800 | 43.035 | 68.966 | 100.000 | 0.000 | 68.100 | 2.770 | 12.000 |
| A.w4_ws_ws | 100.000 | 30.010 | 29.756 | - | 29.756 | 32.012 | 2.520 | 4.120 | 17.500 | 127.600 | 36.563 | 68.812 | 100.000 | 0.000 | 54.200 | 2.420 | 12.000 |
| B.w1_ws_ws | 92.675 | 27.833 | 27.838 | 27.508 | 27.838 | 29.612 | 4.050 | 12.267 | 38.000 | 191.100 | 48.640 | 67.665 | 100.000 | 0.000 | 80.800 | 1.510 | 12.000 |
| B.w2_http_http | 88.346 | 26.521 | 26.629 | 26.560 | 26.595 | 29.442 | 12.551 | 27.070 | 43.900 | 203.600 | 50.807 | 69.472 | 100.000 | 0.000 | 86.600 | 2.260 | 7.000 |

## ws - http paired diff, bootstrap 95pct CI (pairs=3, coarse)
| metric | mean diff | CI | verdict |
|-|-|-|-|
| ratio_pct | +1.887 | [+0.222, +4.329] | 0 not included |
| tracker_hz | +0.565 | [+0.064, +1.312] | 0 not included |
| recv_hz | +0.407 | [-0.053, +1.209] | diff not proven (includes 0) |
| recv_hz_fit | +0.316 | [+0.000, +0.948] | diff not proven (includes 0) |
| preview_fps | +0.427 | [-0.086, +1.243] | diff not proven (includes 0) |
| screen_fps | +0.077 | [-0.247, +0.309] | diff not proven (includes 0) |
| post_p50 | -7.078 | [-8.501, -6.202] | 0 not included |
| post_p95 | -16.477 | [-17.701, -14.803] | 0 not included |
| srv_main_cpu | -6.633 | [-7.700, -5.900] | 0 not included |
| srv_tree_cpu | -18.533 | [-24.200, -12.500] | 0 not included |
| neural_p95 | -2.989 | [-6.473, -0.327] | 0 not included |
| hand_rate_pct | -0.911 | [-1.808, -0.153] | 0 not included |
| pose_rate_pct | +0.000 | [+0.000, +0.000] | diff not proven (includes 0) |
| net_err | +0.000 | [+0.000, +0.000] | diff not proven (includes 0) |
| win_sys_cpu | -9.300 | [-13.900, -5.800] | 0 not included |
| load_before | -0.037 | [-0.750, +0.990] | diff not proven (includes 0) |
| walljumps | +2.000 | [+0.000, +5.000] | diff not proven (includes 0) |

## absolute thresholds per window (ratio>=99, recv>=29.7, preview>=29.7, screen>=29.7)
- A.w1_http_http: ratio False, recv False, preview False, screen True
- A.w2_ws_ws: ratio True, recv True, preview True, screen True
- A.w3_http_http: ratio True, recv True, preview True, screen True
- A.w4_ws_ws: ratio True, recv True, preview True, screen True
- B.w1_ws_ws: ratio False, recv False, preview False, screen False
- B.w2_http_http: ratio False, recv False, preview False, screen False