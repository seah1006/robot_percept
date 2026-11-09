# pd summary (video=teleop_final_hand.mp4, mode=panda)

| window | ratio_pct | tracker_hz | recv_hz | recv_hz_fit | preview_fps | screen_fps | post_p50 | post_p95 | srv_main_cpu | srv_tree_cpu | neural_p95 | hand_rate_pct | pose_rate_pct | net_err | win_sys_cpu | load_before | walljumps |
|-|-|-|-|-|-|-|-|-|-|-|-|-|-|-|-|-|-|
| A.w1_http_http | 100.000 | 30.014 | 29.944 | 29.993 | 30.041 | 29.276 | - | - | 69.700 | 135.400 | 20.228 | 68.812 | 0.000 | 0.000 | 60.700 | 1.670 | 12.000 |
| A.w2_ws_ws | 100.000 | 30.017 | 30.021 | 29.998 | 30.021 | 29.285 | - | - | 60.000 | 120.500 | 19.666 | 68.812 | 0.000 | 0.000 | 53.200 | 2.380 | 12.000 |
| A.w3_http_http | 100.000 | 30.016 | 29.982 | 30.002 | 29.982 | 29.348 | - | - | 69.200 | 133.100 | 18.162 | 68.812 | 0.000 | 0.000 | 54.600 | 1.910 | 12.000 |
| A.w4_ws_ws | 100.000 | 30.017 | 29.966 | 29.999 | 30.010 | 29.365 | - | - | 59.400 | 118.100 | 18.803 | 68.812 | 0.000 | 0.000 | 47.900 | 1.770 | 12.000 |
| B.w1_ws_ws | 100.000 | 30.018 | 30.006 | 30.001 | 29.992 | 29.337 | - | - | 58.400 | 116.900 | 17.486 | 68.812 | 0.000 | 0.000 | 47.400 | 1.160 | 11.000 |
| B.w2_http_http | 100.000 | 30.018 | 29.991 | 29.999 | 29.991 | 29.223 | - | - | 67.700 | 130.800 | 18.248 | 68.812 | 0.000 | 0.000 | 52.100 | 0.770 | 12.000 |

## ws - http paired diff, bootstrap 95pct CI (pairs=3, coarse)
| metric | mean diff | CI | verdict |
|-|-|-|-|
| ratio_pct | +0.000 | [+0.000, +0.000] | diff not proven (includes 0) |
| tracker_hz | +0.001 | [+0.000, +0.003] | diff not proven (includes 0) |
| recv_hz | +0.025 | [-0.016, +0.077] | diff not proven (includes 0) |
| recv_hz_fit | +0.001 | [-0.003, +0.005] | diff not proven (includes 0) |
| preview_fps | +0.003 | [-0.020, +0.028] | diff not proven (includes 0) |
| screen_fps | +0.047 | [+0.009, +0.114] | 0 not included |
| post_p50 | +0.000 | [+0.000, +0.000] | diff not proven (includes 0) |
| post_p95 | +0.000 | [+0.000, +0.000] | diff not proven (includes 0) |
| srv_main_cpu | -9.600 | [-9.800, -9.300] | 0 not included |
| srv_tree_cpu | -14.600 | [-15.000, -13.900] | 0 not included |
| neural_p95 | -0.227 | [-0.762, +0.641] | diff not proven (includes 0) |
| hand_rate_pct | +0.000 | [+0.000, +0.000] | diff not proven (includes 0) |
| pose_rate_pct | +0.000 | [+0.000, +0.000] | diff not proven (includes 0) |
| net_err | +0.000 | [+0.000, +0.000] | diff not proven (includes 0) |
| win_sys_cpu | -6.300 | [-7.500, -4.700] | 0 not included |
| load_before | +0.320 | [-0.140, +0.710] | diff not proven (includes 0) |
| walljumps | -0.333 | [-1.000, +0.000] | diff not proven (includes 0) |

## absolute thresholds per window (ratio>=99, recv>=29.7, preview>=29.7, screen>=29.7)
- A.w1_http_http: ratio True, recv True, preview True, screen False
- A.w2_ws_ws: ratio True, recv True, preview True, screen False
- A.w3_http_http: ratio True, recv True, preview True, screen False
- A.w4_ws_ws: ratio True, recv True, preview True, screen False
- B.w1_ws_ws: ratio True, recv True, preview True, screen False
- B.w2_http_http: ratio True, recv True, preview True, screen False