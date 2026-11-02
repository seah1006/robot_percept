import sys, time, json, hashlib, threading, statistics as S, urllib.request, re
BASE = sys.argv[1]; LABEL = sys.argv[2]; OUT = sys.argv[3]
def get(p, t=30): return json.load(urllib.request.urlopen(BASE+p, timeout=t))
def post(p, d, t=120):
    r = urllib.request.Request(BASE+p, json.dumps(d).encode(), {"Content-Type": "application/json"})
    try: return json.load(urllib.request.urlopen(r, timeout=t))
    except urllib.error.HTTPError as e: return {"http": e.code, "body": e.read().decode()[:300]}
def pct(a, q): 
    a = sorted(a); return a[min(len(a)-1, int(q*len(a)))] if a else None
def stats(a): return None if not a else {"mean": round(S.mean(a),3), "p95": round(pct(a,.95),3), "max": round(max(a),3), "n": len(a)}
def video_client(dur, res, i):
    resp = urllib.request.urlopen(BASE+"/video", timeout=20); buf = b""; t0 = time.time()
    frames = []; 
    while time.time()-t0 < dur:
        c = resp.read1(65536)
        if not c: break
        buf += c
        while True:
            a = buf.find(b"\xff\xd8"); b = buf.find(b"\xff\xd9", a+2) if a >= 0 else -1
            if a < 0 or b < 0: break
            frames.append((time.time(), hashlib.md5(buf[a:b+2]).hexdigest())); buf = buf[b+2:]
    resp.close(); el = time.time()-t0
    uniq = len({h for _, h in frames}); 
    ch = sum(1 for k in range(1, len(frames)) if frames[k][1] != frames[k-1][1])
    gaps = [frames[k][0]-frames[k-1][0] for k in range(1, len(frames))]
    res[i] = {"raw_fps": round(len(frames)/el,2), "changed_fps": round(ch/el,2), "unique_hash": uniq, "max_gap_s": round(max(gaps),3) if gaps else None}
def video(n, dur=15):
    res = {}; th = [threading.Thread(target=video_client, args=(dur,res,i)) for i in range(n)]
    [t.start() for t in th]; fps = []
    t0 = time.time()
    while time.time()-t0 < dur: fps.append(get("/status").get("fps")); time.sleep(1)
    [t.join() for t in th]
    return {"clients": [res[k] for k in sorted(res)], "status_fps": stats([f for f in fps if f is not None])}
def latency(n=30):
    L = []
    for _ in range(n):
        t = time.time(); s = get("/status"); r = time.time()
        L.append((r - s["timestamp"])*1000); time.sleep(.1)
    return stats(L)
def wait_cmd(cid, to=120):
    t0 = time.time()
    while time.time()-t0 < to:
        s = get("/status"); lc = s.get("last_command") or {}
        if lc.get("id") == cid: return s, time.time()-t0
        time.sleep(.25)
    return get("/status"), None
R = {"label": LABEL}
print("reset", post("/reset", {}), flush=True)
t0 = time.time()
while time.time()-t0 < 60 and not get("/status").get("ready"): time.sleep(1)
time.sleep(2)
R["video_1"] = video(1); print("v1", R["video_1"], flush=True)
R["video_2"] = video(2); print("v2", R["video_2"], flush=True)
R["latency_ms"] = latency(); print("lat", R["latency_ms"], flush=True)
s = get("/status"); xy = s["objects"]["mustard"]["center_px"]
t = time.time(); reg = post("/click", {"x": xy[0], "y": xy[1]}); R["register_s"] = round(time.time()-t, 2)
R["register"] = {k: reg.get(k) for k in ("ok","object","error_mm","error_deg","timing_ms","sam_ms","register_ms","mask_iou","http","body")}
print("reg", R["register"], flush=True)
tf, em, ed, tr = [], [], [], []
t0 = time.time(); gpu = []
import os
while time.time()-t0 < float(os.environ.get('TRACK_S','15')):
    s = get("/status"); p = s.get("pose"); g = s.get("gpu"); 
    if g: gpu.append(g)
    if p:
        if p.get("tracking_fps") is not None: tf.append(p["tracking_fps"])
        em.append(p["error_mm"]); ed.append(p["error_deg"])
    time.sleep(.2)
R["tracking_fps"] = stats(tf); R["err_mm"] = stats(em); R["err_deg"] = stats(ed)
R["gpu_last"] = gpu[-1] if gpu else None; R["gpu_samples"] = gpu[::max(1,len(gpu)//6)]
print("track", R["tracking_fps"], R["err_mm"], R["err_deg"], flush=True)
t = time.time(); c = post("/robot/pick", {}); s, d = wait_cmd(c.get("command_id")); 
R["pick"] = {"resp_ok": c.get("ok"), "dur_s": d and round(d,1), "ok": (s.get("last_command") or {}).get("ok"), "held": s.get("held_object"), "err": s.get("error")}
print("pick", R["pick"], flush=True)
c = post("/robot/place", {"xyz": [0.52,-0.15,0.34]}); s, d = wait_cmd(c.get("command_id"))
R["place"] = {"resp_ok": c.get("ok"), "dur_s": d and round(d,1), "ok": (s.get("last_command") or {}).get("ok"), "held": s.get("held_object"), "last_place": s.get("last_place"), "err": s.get("error")}
print("place", R["place"], flush=True)
t0 = time.time()
while time.time()-t0 < 120:
    s = get("/status")
    if s.get('pose') and s.get('tracking_state')=='tracking': break
    time.sleep(1)
R["reacquire_s"] = round(time.time()-t0,1)
R["post_place_state"] = {"tracking_state": s.get("tracking_state"), "pose_err_mm": (s.get("pose") or {}).get("error_mm"), "pose_err_deg": (s.get("pose") or {}).get("error_deg"), "gpu": s.get("gpu")}
json.dump(R, open(OUT, "w"), indent=1)