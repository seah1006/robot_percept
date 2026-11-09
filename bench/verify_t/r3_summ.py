"""usage: r3_summ.py TAG  -> out_r3/TAG_summary.md  (reads out_r3/TAG_A/w*.json, TAG_B/w*.json; pairs = A(1,2)(3,4) B(1,2); diff = ws - http)"""
import json, sys, glob, os
import numpy as np
tag = sys.argv[1]; O = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out_r3")
def load(part):
    return {os.path.basename(f)[:-5]: json.load(open(f)) for f in sorted(glob.glob(f"{O}/{tag}_{part}/w*.json")) if "all" not in f}
A = load("A"); Bp = load("B")
def g(r, k):
    t = r.get("tracker") or {}; s = r.get("server") or {}; w = r.get("wincpu") or {}
    m = {"ratio_pct": (t.get("processed_input_ratio") or 0) * 100, "tracker_hz": t.get("hz"), "recv_hz": s.get("recv_hz"), "recv_hz_fit": s.get("recv_hz_fit"), "preview_fps": s.get("preview_fps"),
         "screen_fps": s.get("screen_fps"), "post_p50": t.get("post_ms_p50"), "post_p95": t.get("post_ms_p95"), "srv_main_cpu": s.get("cpu_main_pct"), "srv_tree_cpu": s.get("cpu_tree_pct"),
         "neural_p95": t.get("inference_ms_p95"), "hand_rate_pct": (t.get("hand_detection_rate") or 0) * 100, "pose_rate_pct": (t.get("pose_detection_rate") or 0) * 100,
         "net_err": t.get("network_errors"), "win_sys_cpu": w.get("sys_cpu_mean_pct"), "load_before": float((r.get("load_before") or [0])[0]), "walljumps": r.get("walljumps_in_span")}
    return m[k]
keys = ["ratio_pct", "tracker_hz", "recv_hz", "recv_hz_fit", "preview_fps", "screen_fps", "post_p50", "post_p95", "srv_main_cpu", "srv_tree_cpu", "neural_p95", "hand_rate_pct", "pose_rate_pct", "net_err", "win_sys_cpu", "load_before", "walljumps"]
wins = [(f"A.{k}", r) for k, r in A.items()] + [(f"B.{k}", r) for k, r in Bp.items()]
pairs = []
def pr(d, a, b):
    if a in d and b in d:
        x, y = d[a], d[b]
        h, w = (x, y) if x["transport"] == "http" else (y, x); pairs.append((h, w))
pr(A, "w1_http", "w2_ws"); pr(A, "w3_http", "w4_ws"); pr(Bp, "w1_ws", "w2_http")
rng = np.random.default_rng(0)
L = [f"# {tag} summary (video={wins[0][1]['video'].split(chr(92))[-1]}, mode={wins[0][1]['mode']})", "", "| window | " + " | ".join(keys) + " |", "|" + "-|" * (len(keys) + 1)]
for n, r in wins:
    L.append(f"| {n}_{r['transport']} | " + " | ".join("-" if g(r, k) is None else f"{g(r, k):.3f}" for k in keys) + " |")
L += ["", "## ws - http paired diff, bootstrap 95pct CI (pairs=" + str(len(pairs)) + ", coarse)", "| metric | mean diff | CI | verdict |", "|-|-|-|-|"]
for k in keys:
    d = np.array([(g(w, k) or 0) - (g(h, k) or 0) for h, w in pairs], float)
    if len(d) == 0: continue
    bs = [rng.choice(d, len(d)).mean() for _ in range(5000)]; lo, hi = np.percentile(bs, [2.5, 97.5])
    L.append(f"| {k} | {d.mean():+.3f} | [{lo:+.3f}, {hi:+.3f}] | {'0 not included' if lo > 0 or hi < 0 else 'diff not proven (includes 0)'} |")
L += ["", "## absolute thresholds per window (ratio>=99, recv>=29.7, preview>=29.7, screen>=29.7)"]
for n, r in wins:
    ok = [(g(r, "ratio_pct") or 0) >= 99, (g(r, "recv_hz") or 0) >= 29.7, (g(r, "preview_fps") or 0) >= 29.7, (g(r, "screen_fps") or 0) >= 29.7]
    L.append(f"- {n}_{r['transport']}: ratio {ok[0]}, recv {ok[1]}, preview {ok[2]}, screen {ok[3]}")
open(f"{O}/{tag}_summary.md", "w").write("\n".join(L)); print("\n".join(L))
