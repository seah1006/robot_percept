import json,numpy as np,glob
for f in sorted(glob.glob("bench/verify_s2/out_n_coll_*.json")):
    d=json.load(open(f))
    for o in ("0","1"):
        raw=d["coll_raw_"+o]; names=[k for k in raw[0][1] if "shoulder" in k or "elbow" in k]
        Q=np.array([[r[1][n] for n in names] for r in raw]); rng=np.degrees(Q.max(0)-Q.min(0))
        c=d["coll_"+o]; print(f.split("out_")[1][:-5],o,"min",c["min_mm"],"neg",c["frames_below_0mm"],"range max %.1f"%rng.max(),"fps",(d.get("coll_video_"+o) or {}).get("fps"),"tick",d.get("coll_tick_"+o))
