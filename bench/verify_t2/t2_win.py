"""V-T2: G1 ON 상태에서 Windows 트래커(스톡 영상, MediaPipe 실처리)를 http/ws 교차 실행.
사용: t2_win.py URL SERVERPID OUTDIR SECS ORDER(콤마)  예: http,ws,http,ws,http,ws"""
import sys, os, time, json, subprocess, threading, http.client, urllib.parse
import numpy as np
url, PID, OUT, SECS, ORDER = sys.argv[1], int(sys.argv[2]), sys.argv[3], float(sys.argv[4]), sys.argv[5].split(",")
u = urllib.parse.urlparse(url); TK = os.sysconf("SC_CLK_TCK")
WIN_OUT = r"C:\Users\my\rp_tracker\out_t2"; WIN_OUT_L = "/mnt/c/Users/my/rp_tracker/out_t2"
PS1 = r"\\wsl.localhost\Ubuntu-24.04\home\my\work\robot_percept\bench\verify_t2\win_run.ps1"
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
    m = tot = 0
    for p in tree(pid):
        try:
            f = open(f"/proc/{p}/stat").read().rsplit(")", 1)[1].split(); v = int(f[11]) + int(f[12]); tot += v
            if p == pid: m = v
        except Exception: pass
    return m / TK, tot / TK
def req(m, p, b=None):
    c = http.client.HTTPConnection(u.hostname, u.port, timeout=70); c.request(m, p, json.dumps(b) if b is not None else None, {"Content-Type": "application/json"}); r = c.getresponse(); d = r.read(); c.close(); return json.loads(d)
req("POST", "/humanoid/mode", {"enabled": True})
dl = time.monotonic() + 70
while time.monotonic() < dl and req("GET", "/humanoid/status").get("state") != "ready": time.sleep(.1)
time.sleep(2)
stop = [False]; ts = []; samples = []; pushc = {}; jumps = []
def vid():
    c = http.client.HTTPConnection(u.hostname, u.port, timeout=10); c.request("GET", "/humanoid/video"); r = c.getresponse(); buf = b""
    while not stop[0]:
        ch = r.read1(65536)
        if not ch: break
        buf += ch
        while True:
            i = buf.find(b"\xff\xd8"); j = buf.find(b"\xff\xd9", i + 2) if i >= 0 else -1
            if i < 0 or j < 0: break
            ts.append(time.monotonic()); buf = buf[j + 2:]
    c.close()
def viewer():
    import socket
    s = socket.create_connection((u.hostname, u.port)); s.settimeout(2); s.sendall(b"GET /teleop/preview.mjpg HTTP/1.0\r\nHost: x\r\n\r\n")
    while not stop[0]:
        try:
            if not s.recv(262144): break
        except socket.timeout: continue
def pusher():
    from simple_websocket import Client
    c = Client.connect("ws://%s:%d/status/ws" % (u.hostname, u.port))
    while not stop[0]:
        try: m = c.receive(timeout=.5)
        except Exception: continue
        if m: pushc["n"] = pushc.get("n", 0) + 1
    c.close()
def sampler():
    c = http.client.HTTPConnection(u.hostname, u.port, timeout=5)
    while not stop[0]:
        try:
            c.request("GET", "/humanoid/status"); s = json.loads(c.getresponse().read())
            samples.append((time.monotonic(), s.get("input_count"), s.get("input_hz"), cpu(PID)))
        except Exception: c.close(); c = http.client.HTTPConnection(u.hostname, u.port, timeout=5)
        time.sleep(.25)
def probe():
    pm, pr = time.monotonic(), time.time()
    while not stop[0]:
        time.sleep(.02); m, r = time.monotonic(), time.time(); sk = (r - pr) - (m - pm)
        if abs(sk) > .02: jumps.append((m, round(sk * 1000, 1)))
        pm, pr = m, r
for f in (vid, viewer, pusher, sampler, probe): threading.Thread(target=f, daemon=True).start()
time.sleep(1.5)
os.makedirs(OUT, exist_ok=True); results = []
for k, tr in enumerate(ORDER):
    label = f"w{k+1}_{tr}"; n0 = len(samples); load0 = open("/proc/loadavg").read().split()[:3]
    cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", PS1, "-Transport", tr, "-Label", label, "-Seconds", str(SECS), "-Url", url, "-OutDir", WIN_OUT]
    t_start = time.monotonic(); p = subprocess.run(cmd, capture_output=True, text=True, timeout=200); t_end = time.monotonic()
    r = {"label": label, "transport": tr, "load1_5_15_before": load0, "ps_rc": p.returncode, "ps_err": p.stderr[-300:]}
    for key, suf in (("tracker", "metrics"), ("wincpu", "wincpu")):
        try: r[key] = json.load(open(f"{WIN_OUT_L}/{label}.{suf}.json", encoding="utf-8-sig"))
        except Exception as e: r[key] = None; r[key + "_err"] = str(e)
    r["stdout_tail"] = open(f"{WIN_OUT_L}/{label}.stdout.txt", errors="replace").read()[-400:]
    r["stderr_tail"] = open(f"{WIN_OUT_L}/{label}.stderr.txt", errors="replace").read()[-300:]
    w = [s for s in samples[n0:] if s[1] is not None]
    base = w[0][1] if w else 0
    ch = [s for s in w if s[1] > base]
    if len(ch) >= 2:
        a0 = ch[0]; a1 = next(s for s in w if s[1] == w[-1][1])  # 마지막 값에 처음 도달한 시각
        dtw = a1[0] - a0[0]
        fr = np.array([x for x in ts if a0[0] <= x <= a1[0]]); gp = np.diff(fr) * 1000 if len(fr) > 1 else np.array([0.])
        r["server"] = {"span_s": round(dtw, 2), "recv_updates": a1[1] - a0[1], "recv_hz": round((a1[1] - a0[1]) / dtw, 3) if dtw > 0 else None,
                       "tracker_sent_updates_total": (r["tracker"] or {}).get("sent_updates"),
                       "status_input_hz_median": float(np.median([s[2] for s in w if s[2] is not None])),
                       "g1_frames": int(len(fr)), "g1_fps": round(len(fr) / dtw, 3), "g1_max_gap_ms": round(float(gp.max()), 1), "g1_gap_p95_ms": round(float(np.percentile(gp, 95)), 1), "g1_gaps_gt200": int((gp > 200).sum()),
                       "cpu_main_pct": round((a1[3][0] - a0[3][0]) / dtw * 100, 1), "cpu_tree_pct": round((a1[3][1] - a0[3][1]) / dtw * 100, 1)}
        r["walljumps_in_span"] = len([1 for m, sk in jumps if a0[0] <= m <= a1[0]])
    else: r["server"] = None
    r["load1_5_15_after"] = open("/proc/loadavg").read().split()[:3]; r["wall_s"] = round(t_end - t_start, 1)
    results.append(r); json.dump(r, open(f"{OUT}/{label}.json", "w"), indent=1, default=str)
    print(label, "tracker_hz", (r["tracker"] or {}).get("hz"), "ratio", (r["tracker"] or {}).get("processed_input_ratio"), "recv_hz", (r["server"] or {}).get("recv_hz"), "g1_fps", (r["server"] or {}).get("g1_fps"), "wall", r["wall_s"], flush=True)
stop[0] = True; time.sleep(1)
req("POST", "/humanoid/mode", {"enabled": False})
json.dump(results, open(f"{OUT}/all.json", "w"), indent=1, default=str)
