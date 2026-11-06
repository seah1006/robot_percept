"""지표3,4(+부하 하 지표1) 시나리오. 사용: scen_f.py URL SERVERPID 라벨 출력.json PAYLOAD_DIR_WSL [win|wsl] [WIN_DIR]
순서: 유휴 CPU 10초 -> G1 ON/ready -> W1(송신만 30초) -> W2(송신+폴링3+MJPEG2 시청, 30초; CPU/폴링 측정)."""
import sys, os, time, json, subprocess, threading, http.client, urllib.parse, socket, statistics
url = sys.argv[1]; PID = int(sys.argv[2]); LBL = sys.argv[3]; OUT = sys.argv[4]; PD = sys.argv[5]
SND = sys.argv[6] if len(sys.argv) > 6 else "win"; WD = sys.argv[7] if len(sys.argv) > 7 else ""
TRANSPORT = os.environ.get("VF_TRANSPORT", "http"); u = urllib.parse.urlparse(url); HERE = os.path.dirname(os.path.abspath(__file__)); TK = os.sysconf("SC_CLK_TCK")
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
    m = 0; tot = 0; n = 0
    for p in tree(pid):
        try:
            f = open(f"/proc/{p}/stat").read().rsplit(")", 1)[1].split(); v = int(f[11]) + int(f[12]); tot += v; n += 1
            if p == pid: m = v
        except Exception: pass
    return m / TK, tot / TK, n
def cpu_window(fn):
    t0 = time.monotonic(); a = cpu(PID); fn(); b = cpu(PID); dt = time.monotonic() - t0
    return {"main_pct": round((b[0] - a[0]) / dt * 100, 1), "tree_pct": round((b[1] - a[1]) / dt * 100, 1), "procs": b[2], "dur_s": round(dt, 2)}
def req(m, p, b=None):
    c = http.client.HTTPConnection(u.hostname, u.port, timeout=70); c.request(m, p, json.dumps(b) if b is not None else None, {"Content-Type": "application/json"}); r = c.getresponse(); d = r.read(); c.close(); return json.loads(d)
res = {"label": LBL, "status_mode": os.environ.get("VF_STATUS", "poll"), "transport": TRANSPORT, "sender": SND, "load0": open("/proc/loadavg").read().split()[:3]}
res["idle_cpu"] = cpu_window(lambda: time.sleep(10))
req("POST", "/humanoid/mode", {"enabled": True})
dl = time.monotonic() + 70
while time.monotonic() < dl and req("GET", "/humanoid/status").get("state") != "ready": time.sleep(.1)
time.sleep(2)
def run_sender(tag, dur):
    o = f"{HERE}/out/{LBL}.{tag}.json"
    if SND == "win":
        cmd = ["/mnt/c/Users/my/rp_vf/venv/Scripts/python.exe", f"{WD}\\sender_f.py", "http://127.0.0.1:%d" % u.port, str(dur), WD, f"{WD}\\{LBL}.{tag}.json", TRANSPORT]
        r = subprocess.run(cmd, capture_output=True, text=True)
        open(o, "w").write(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "{}")
        if r.returncode: res[tag + "_err"] = r.stderr[-400:]
    else:
        subprocess.run([sys.executable, f"{HERE}/sender_f.py", url, str(dur), PD, o, TRANSPORT], capture_output=True)
    try: return json.load(open(o))
    except Exception: return None
res["W1_sender_only"] = run_sender("w1", 30)
stop = [False]; lat = {}; cnt = {}
def poller(path, hz):
    c = http.client.HTTPConnection(u.hostname, u.port, timeout=5); n = 0; t0 = time.monotonic(); lat[path] = []
    while not stop[0]:
        a = time.perf_counter()
        try: c.request("GET", path); r = c.getresponse(); r.read(); lat[path].append((time.perf_counter() - a) * 1000)
        except Exception: c.close()
        n += 1; d = t0 + n / hz - time.monotonic()
        if d > 0: time.sleep(d)
        elif d < -1: n = int((time.monotonic() - t0) * hz)
def viewer(path):
    try:
        s = socket.create_connection((u.hostname, u.port)); s.settimeout(2); s.sendall(f"GET {path} HTTP/1.0\r\nHost: x\r\n\r\n".encode()); b = 0
        while not stop[0]:
            try: d = s.recv(262144); b += len(d)
            except socket.timeout: continue
            if not d: break
        cnt["view:" + path] = b
    except Exception as e: cnt["view:" + path] = "err " + str(e)
PUSH = os.environ.get("VF_STATUS", "poll") == "push"; pushc = {}
def pusher():
    # F3: 브라우저 탭 1개 대신 /status/ws 구독자 1개 (메시지 종류별 수신 수, 상태 JSON 바이트)
    from simple_websocket import Client
    c = Client.connect("ws://%s:%d/status/ws" % (u.hostname, u.port)); pushc["bytes"] = 0
    while not stop[0]:
        try: m = c.receive(timeout=.5)
        except Exception: continue
        if m is None: continue
        pushc["bytes"] += len(m); k = json.loads(m)["type"]; pushc[k] = pushc.get(k, 0) + 1
    c.close()
POLLS = [] if PUSH else [("/humanoid/status", 10), ("/teleop/status", 10), ("/status", 3)]
ths = ([threading.Thread(target=pusher, daemon=True)] if PUSH else []) + [threading.Thread(target=poller, args=a, daemon=True) for a in POLLS] + [threading.Thread(target=viewer, args=(p,), daemon=True) for p in ("/humanoid/video", "/teleop/preview.mjpg")]
for t in ths: t.start()
time.sleep(1)
c0 = cpu(PID); tstart = time.monotonic(); snd = run_sender("w2", 30); dt = time.monotonic() - tstart; c1 = cpu(PID)
stop[0] = True; time.sleep(2.5)
res["W2_load"] = {"sender": snd, "cpu": {"main_pct": round((c1[0] - c0[0]) / dt * 100, 1), "tree_pct": round((c1[1] - c0[1]) / dt * 100, 1), "procs": c1[2], "dur_s": round(dt, 2)},
  "poll": {p: {"req_per_s": round(len(lat[p]) / dt, 2), "p50_ms": round(statistics.median(lat[p]), 2) if lat[p] else None, "p95_ms": round(sorted(lat[p])[int(.95 * len(lat[p]))], 2) if lat[p] else None, "n": len(lat[p])} for p in lat},
  "poll_total_req_per_s": round(sum(len(v) for v in lat.values()) / dt, 2), "push": {"mode": "push" if PUSH else "poll", "msgs_per_s": round(sum(v for k, v in pushc.items() if k != "bytes") / dt, 2), "bytes_per_s": round(pushc.get("bytes", 0) / dt), "by_type": dict(pushc)}, "viewer_bytes": dict(cnt)}
res["load1_end"] = open("/proc/loadavg").read().split()[:3]
req("POST", "/humanoid/mode", {"enabled": False})
json.dump(res, open(OUT, "w"), indent=1, default=str); print(json.dumps(res, indent=1, default=str))
