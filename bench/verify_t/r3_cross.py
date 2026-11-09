"""V-T3 cross harness (WSL side). Count-based server rates (first increase .. first arrival of last value).
usage: r3_cross.py --url --pid --out --secs --order http,ws,... --video W:\\path --mode humanoid|panda --tracker W:\\path"""
import sys, os, time, json, subprocess, threading, http.client, urllib.parse, argparse
import numpy as np
ap = argparse.ArgumentParser()
ap.add_argument("--url"); ap.add_argument("--pid", type=int); ap.add_argument("--out"); ap.add_argument("--secs", type=float, default=30)
ap.add_argument("--order"); ap.add_argument("--video"); ap.add_argument("--mode", default="humanoid"); ap.add_argument("--tracker")
ap.add_argument("--winout", default=r"C:\Users\USER\AppData\Local\Temp\vt3_out")
A = ap.parse_args()
u = urllib.parse.urlparse(A.url); TK = os.sysconf("SC_CLK_TCK"); OUT = A.out; ORDER = A.order.split(",")
WIN_L = "/mnt/c/" + A.winout[3:].replace("\\", "/")
PS1 = r"C:\Users\USER\AppData\Local\Temp\vt3\bin\r3_win_run.ps1"
HUM = A.mode == "humanoid"
def tree(pid):
    ch = {}
    for d in os.listdir("/proc"):
        if d.isdigit():
            try: ch.setdefault(int(open(f"/proc/{d}/stat").read().rsplit(")", 1)[1].split()[1]), []).append(int(d))
            except Exception: pass
    out = [pid]; i = 0
    while i < len(out): out += ch.get(out[i], []); i += 1
    return out
def cpu(pid):
    m = tot = 0; rss = 0
    for p in tree(pid):
        try:
            f = open(f"/proc/{p}/stat").read().rsplit(")", 1)[1].split(); v = int(f[11]) + int(f[12]); tot += v
            rss += int(f[21]) * 4096
            if p == pid: m = v
        except Exception: pass
    return m / TK, tot / TK, rss / 1e6
def req(m, p, b=None):
    c = http.client.HTTPConnection(u.hostname, u.port, timeout=70); c.request(m, p, json.dumps(b) if b is not None else None, {"Content-Type": "application/json"}); r = c.getresponse(); d = r.read(); c.close(); return json.loads(d)
if HUM:
    req("POST", "/teleop/mode", {"enabled": False}); req("POST", "/humanoid/mode", {"enabled": True})
    dl = time.monotonic() + 70
    while time.monotonic() < dl and req("GET", "/humanoid/status").get("state") != "ready": time.sleep(.1)
else:
    req("POST", "/humanoid/mode", {"enabled": False}); req("POST", "/teleop/mode", {"enabled": True})
time.sleep(2)
stop = [False]; ts = []; samples = []; jumps = []
def vid():
    c = http.client.HTTPConnection(u.hostname, u.port, timeout=10); c.request("GET", "/humanoid/video" if HUM else "/video"); r = c.getresponse(); buf = b""
    while not stop[0]:
        ch = r.read1(65536)
        if not ch: break
        buf += ch
        while True:
            i = buf.find(b"\xff\xd8"); j = buf.find(b"\xff\xd9", i + 2) if i >= 0 else -1
            if i < 0 or j < 0: break
            ts.append(time.monotonic()); buf = buf[j + 2:]
    c.close()
lastcpu = [0, None]
def sampler():
    c = http.client.HTTPConnection(u.hostname, u.port, timeout=5)
    while not stop[0]:
        try:
            if HUM:
                c.request("GET", "/humanoid/status"); s = json.loads(c.getresponse().read()); inp = s.get("input_count")
                c.request("GET", "/teleop/status"); t = json.loads(c.getresponse().read()); pv = t.get("preview_count")
            else:
                c.request("GET", "/teleop/status"); t = json.loads(c.getresponse().read()); inp = t.get("input_count"); pv = t.get("preview_count")
            now = time.monotonic()
            if now - lastcpu[0] >= 0.5 or not lastcpu[1]: lastcpu[1] = cpu(A.pid) + (now,); lastcpu[0] = now
            samples.append((now, inp, pv, lastcpu[1]))
        except Exception: c.close(); c = http.client.HTTPConnection(u.hostname, u.port, timeout=5)
        time.sleep(.05)
def probe():
    pm, pr = time.monotonic(), time.time()
    while not stop[0]:
        time.sleep(.02); m, r = time.monotonic(), time.time(); sk = (r - pr) - (m - pm)
        if abs(sk) > .02: jumps.append((m, round(sk * 1000, 1)))
        pm, pr = m, r
for f in (vid, sampler, probe): threading.Thread(target=f, daemon=True).start()
time.sleep(1.5)
os.makedirs(OUT, exist_ok=True); results = []
def span(w, idx):
    base = w[0][idx]; ch = [s for s in w if s[idx] is not None and s[idx] > base]
    if len(ch) < 2: return None
    a0 = ch[0]; a1 = next(s for s in w if s[idx] == w[-1][idx]); return a0, a1
for k, tr in enumerate(ORDER):
    label = f"w{k+1}_{tr}"; n0 = len(samples); load0 = open("/proc/loadavg").read().split()[:3]
    cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", PS1, "-Transport", tr, "-Label", label, "-Seconds", str(A.secs), "-Url", A.url, "-OutDir", A.winout, "-Video", A.video, "-Mode", A.mode, "-Tracker", A.tracker]
    import glob
    for stale in glob.glob(f"{WIN_L}/{label}.*"): os.remove(stale)
    tops = []
    def snap_top():
        for dly in (12, 13):
            time.sleep(dly)
            try: tops.append(subprocess.run("top -bn1 -w 160 | sed -n 7,12p | cut -c1-140", shell=True, capture_output=True, text=True).stdout)
            except Exception: pass
    threading.Thread(target=snap_top, daemon=True).start()
    t_start = time.monotonic(); p = subprocess.run(cmd, capture_output=True, text=True, timeout=240); t_end = time.monotonic()
    r = {"label": label, "transport": tr, "video": A.video, "mode": A.mode, "load_before": load0, "ps_rc": p.returncode, "ps_err": p.stderr[-300:]}
    for key, suf in (("tracker", "metrics"), ("wincpu", "wincpu")):
        try: r[key] = json.load(open(f"{WIN_L}/{label}.{suf}.json", encoding="utf-8-sig"))
        except Exception as e: r[key] = None; r[key + "_err"] = str(e)
    w = [s for s in samples[n0:] if s[1] is not None]
    sp = span(w, 1) if w else None
    if sp:
        a0, a1 = sp; dtw = a1[0] - a0[0]
        fr = np.array([x for x in ts if a0[0] <= x <= a1[0]]); gp = np.diff(fr) * 1000 if len(fr) > 1 else np.array([0.])
        srv = {"span_s": round(dtw, 2), "recv_updates": a1[1] - a0[1], "recv_hz": round((a1[1] - a0[1]) / dtw, 3),
               "recv_hz_fit": round(float(np.polyfit([x[0] for x in w if a0[0] <= x[0] <= a1[0]], [x[1] for x in w if a0[0] <= x[0] <= a1[0]], 1)[0]), 3), "screen_frames": int(len(fr)), "screen_fps": round(len(fr) / dtw, 3), "screen_max_gap_ms": round(float(gp.max()), 1), "screen_gaps_gt200": int((gp > 200).sum()),
               "cpu_main_pct": round((a1[3][0] - a0[3][0]) / (a1[3][3] - a0[3][3]) * 100, 1), "cpu_tree_pct": round((a1[3][1] - a0[3][1]) / (a1[3][3] - a0[3][3]) * 100, 1), "rss_tree_mb": round(a1[3][2], 1)}
        pw = [s for s in w if s[2] is not None]
        sp2 = span(pw, 2) if pw else None
        if sp2: srv["preview_updates"] = sp2[1][2] - sp2[0][2]; srv["preview_fps"] = round((sp2[1][2] - sp2[0][2]) / (sp2[1][0] - sp2[0][0]), 3)
        r["server"] = srv
        r["walljumps_in_span"] = len([1 for m, sk in jumps if a0[0] <= m <= a1[0]])
    else: r["server"] = None
    r["top_mid_window"] = tops; r["load_after"] = open("/proc/loadavg").read().split()[:3]; r["wall_s"] = round(t_end - t_start, 1)
    results.append(r); json.dump(r, open(f"{OUT}/{label}.json", "w"), indent=1, default=str)
    print(label, "ratio", (r["tracker"] or {}).get("processed_input_ratio"), "hz", (r["tracker"] or {}).get("hz"), "recv_hz", (r["server"] or {}).get("recv_hz"), "prev_fps", (r["server"] or {}).get("preview_fps"), "screen_fps", (r["server"] or {}).get("screen_fps"), "post_p95", (r["tracker"] or {}).get("post_ms_p95"), flush=True)
stop[0] = True; time.sleep(1)
req("POST", "/humanoid/mode" if HUM else "/teleop/mode", {"enabled": False})
json.dump(results, open(f"{OUT}/all.json", "w"), indent=1, default=str)
