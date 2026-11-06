import json, glob, sys, re, random
import numpy as np
pre = sys.argv[1]
rows = {}
for f in sorted(glob.glob(f"out_{pre}_r*_*.json")):
    m = re.match(rf"out_{pre}_r(\d+)_(\w+)\.json", f)
    r, p = m.groups()
    d = json.load(open(f))
    out = {}
    for o in ("0", "1"):
        raw = d["coll_raw_" + o]
        names = [k for k in raw[0][1] if "shoulder" in k or "elbow" in k]
        Q = np.array([[x[1][n] for n in names] for x in raw])
        out["rng" + o] = float(np.degrees(Q.max(0) - Q.min(0)).max())
    rows.setdefault(p, []).append((int(r), d["coll_tick_1"]["tick_p95_max"], d["coll_tick_0"]["tick_p95_max"],
        d["coll_1"]["min_mm"], d["coll_1"]["frames_below_0mm"], d["coll_tick_1"]["status_fps_min"], round(out["rng1"], 1), round(out["rng0"], 1),
        (d.get("coll_video_1") or {}).get("fps")))
for p, v in rows.items():
    print(p, "ON tick_p95_max", [x[1] for x in v], "OFF", [x[2] for x in v], "min_mm", [x[3] for x in v], "pen", [x[4] for x in v],
          "status_fps_min", [x[5] for x in v], "ON range", [x[6] for x in v], "OFF range", [x[7] for x in v], "video fps", [x[8] for x in v])
