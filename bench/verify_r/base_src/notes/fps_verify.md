# FPS verify (V) - independent HTTP bench: bench/verify/bench.py, runner run.sh, raw JSON in bench/verify/out/
Baseline measured on overlay of data/backup_fps (/home/user/work/rp_base), port 5082, 2 runs each.

| metric | baseline r1 / r2 | round1 r1 / r2 |
|---|---|---|
| video fps, 1 client (distinct frames) | 12.4 / 11.4 | 28.9 / 28.7 |
| video fps, 2 clients each | 11.4+11.4 / 10.8+10.9 | 28.9+28.9 / 28.5+28.4 |
| /status fps | 12.4 / 11.3 | 28.9 / 28.7 |
| latency proxy mean/p95 ms | 51/153 , 50/145 | 28/95 , 32/126 |
| register s (sam+fp) | 46.6 / 53.7 | 39.9 / 47.0 |
| tracking_fps mean | 3.8 / 3.9 | 4.2 / 4.0 |
| err mm mean (p95) | 0.92(0.96) / 0.94(0.96) | 0.91(0.93) / 0.90(0.93) |
| err deg mean | 1.56 / 1.52 | 1.60 / 1.57 |
| pick ok / dur s | ok 18.1 / ok 20.6 | ok 15.1 / ok 17.2 |
| place ok, err_mm, upright, dur s | ok 1.0 1.0 8.6 / 10.4 | ok 1.0 1.0 5.3 / 5.9 |
| server log errors | 0 | 0 |

Round1 verdict: video PASS, accuracy PASS, robot PASS, tracking_fps FAIL (4 vs target 10; FP refine bound, untouched).
