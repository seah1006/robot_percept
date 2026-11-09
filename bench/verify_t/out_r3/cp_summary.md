# cp summary (video=teleop_round2_compact.mp4, mode=humanoid)

| window | ratio_pct | tracker_hz | recv_hz | recv_hz_fit | preview_fps | screen_fps | post_p50 | post_p95 | srv_main_cpu | srv_tree_cpu | neural_p95 | hand_rate_pct | pose_rate_pct | net_err | win_sys_cpu | load_before | walljumps |
|-|-|-|-|-|-|-|-|-|-|-|-|-|-|-|-|-|-|
| A.w1_http_http | 100.000 | 30.014 | 30.034 | 29.999 | 30.000 | 31.938 | 7.759 | 22.410 | 33.400 | 153.300 | 30.099 | 0.000 | 100.000 | 0.000 | 63.300 | 0.930 | 12.000 |
| A.w2_ws_ws | 100.000 | 30.012 | 29.988 | 30.002 | 29.956 | 31.994 | 2.301 | 3.665 | 26.700 | 140.000 | 28.265 | 0.000 | 100.000 | 0.000 | 57.200 | 1.500 | 11.000 |
| A.w3_http_http | 100.000 | 30.013 | 30.043 | 29.996 | 30.040 | 31.917 | 6.512 | 26.670 | 32.400 | 147.800 | 25.420 | 0.000 | 100.000 | 0.000 | 59.900 | 1.510 | 12.000 |
| A.w4_ws_ws | 100.000 | 30.014 | 30.004 | 30.002 | 30.004 | 31.940 | 2.006 | 3.623 | 26.800 | 139.600 | 26.009 | 0.000 | 100.000 | 0.000 | 58.900 | 1.210 | 12.000 |
| B.w1_ws_ws | 100.000 | 30.012 | 30.031 | 29.997 | 30.062 | 31.942 | 2.152 | 3.611 | 26.300 | 136.500 | 27.993 | 0.000 | 100.000 | 0.000 | 60.500 | 0.910 | 6.000 |
| B.w2_http_http | 100.000 | 30.011 | 30.020 | 30.002 | 30.020 | 31.992 | 6.790 | 17.583 | 32.000 | 147.700 | 28.512 | 0.000 | 100.000 | 0.000 | 60.800 | 0.900 | 12.000 |

## ws - http paired diff, bootstrap 95pct CI (pairs=3, coarse)
| metric | mean diff | CI | verdict |
|-|-|-|-|
| ratio_pct | +0.000 | [+0.000, +0.000] | diff not proven (includes 0) |
| tracker_hz | +0.000 | [-0.002, +0.001] | diff not proven (includes 0) |
| recv_hz | -0.025 | [-0.046, +0.011] | diff not proven (includes 0) |
| recv_hz_fit | +0.001 | [-0.005, +0.006] | diff not proven (includes 0) |
| preview_fps | -0.013 | [-0.044, +0.042] | diff not proven (includes 0) |
| screen_fps | +0.010 | [-0.050, +0.056] | diff not proven (includes 0) |
| post_p50 | -4.867 | [-5.458, -4.505] | 0 not included |
| post_p95 | -18.588 | [-23.047, -13.972] | 0 not included |
| srv_main_cpu | -6.000 | [-6.700, -5.600] | 0 not included |
| srv_tree_cpu | -10.900 | [-13.300, -8.200] | 0 not included |
| neural_p95 | -0.588 | [-1.835, +0.589] | diff not proven (includes 0) |
| hand_rate_pct | +0.000 | [+0.000, +0.000] | diff not proven (includes 0) |
| pose_rate_pct | +0.000 | [+0.000, +0.000] | diff not proven (includes 0) |
| net_err | +0.000 | [+0.000, +0.000] | diff not proven (includes 0) |
| win_sys_cpu | -2.467 | [-6.100, -0.300] | 0 not included |
| load_before | +0.093 | [-0.300, +0.570] | diff not proven (includes 0) |
| walljumps | -2.333 | [-6.000, +0.000] | diff not proven (includes 0) |

## absolute thresholds per window (ratio>=99, recv>=29.7, preview>=29.7, screen>=29.7)
- A.w1_http_http: ratio True, recv True, preview True, screen True
- A.w2_ws_ws: ratio True, recv True, preview True, screen True
- A.w3_http_http: ratio True, recv True, preview True, screen True
- A.w4_ws_ws: ratio True, recv True, preview True, screen True
- B.w1_ws_ws: ratio True, recv True, preview True, screen True
- B.w2_http_http: ratio True, recv True, preview True, screen True