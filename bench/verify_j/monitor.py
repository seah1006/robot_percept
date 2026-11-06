"""V-J 서버 모니터. 사용: monitor.py PORT PIDFILE OUTDIR [enable_mode=1]
status 0.25s 샘플(input_count), MJPEG(/humanoid/video) 프레임 타임스탬프, 60초마다 스레드/fd/RSS/G1fps 기록. 서버 재기동에 견디도록 재연결."""
import sys, os, time, json, threading, http.client
PORT, PIDF, OUT = int(sys.argv[1]), sys.argv[2], sys.argv[3]; MODE = sys.argv[4] if len(sys.argv) > 4 else "1"; EN = MODE in ("1", "once")
os.makedirs(OUT, exist_ok=True)
frames = []; stop = [False]; st = open(f"{OUT}/status.csv", "a", buffering=1)
def pid():
    try: return int(open(PIDF).read().strip())
    except Exception: return None
def tree(p):
    ch = {}
    for d in os.listdir("/proc"):
        if d.isdigit():
            try: ch.setdefault(int(open(f"/proc/{d}/stat").read().rsplit(")", 1)[1].split()[1]), []).append(int(d))
            except Exception: pass
    o = [p]; i = 0
    while i < len(o): o += ch.get(o[i], []); i += 1
    return o
def rss(p):
    try:
        for l in open(f"/proc/{p}/status"):
            if l.startswith("VmRSS"): return int(l.split()[1]) // 1024
    except Exception: return None
def vid():
    while not stop[0]:
        try:
            c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=5); c.request("GET", "/humanoid/video"); r = c.getresponse(); buf = b""
            while not stop[0]:
                ch = r.read1(65536)
                if not ch: break
                buf += ch
                while True:
                    i = buf.find(b"\xff\xd8"); j = buf.find(b"\xff\xd9", i + 2) if i >= 0 else -1
                    if i < 0 or j < 0: break
                    frames.append(time.monotonic()); buf = buf[j + 2:]
        except Exception: time.sleep(1)
def sampler():
    c = None; en = False
    while not stop[0]:
        try:
            if c is None: c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=3)
            if EN and not en:
                c.request("POST", "/humanoid/mode", json.dumps({"enabled": True}), {"Content-Type": "application/json"}); c.getresponse().read(); en = True
            c.request("GET", "/humanoid/status"); s = json.loads(c.getresponse().read())
            st.write(f"{time.time():.3f},{time.monotonic():.3f},{s.get('input_count')},{s.get('input_hz')},{s.get('state')},{len(frames)}\n")
        except Exception:
            st.write(f"{time.time():.3f},{time.monotonic():.3f},ERR,,,{len(frames)}\n"); c = None; en = (en if MODE == "once" else False)
        time.sleep(.25)
threading.Thread(target=vid, daemon=True).start(); threading.Thread(target=sampler, daemon=True).start()
last = 0; lastt = time.monotonic(); f = open(f"{OUT}/minute.jsonl", "a", buffering=1)
while True:
    time.sleep(60); p = pid(); now = time.monotonic(); n = len(frames)
    rec = {"t": time.time(), "pid": p, "g1_fps_last_min": round((n - last) / (now - lastt), 2), "load": open("/proc/loadavg").read().split()[:3]}
    last, lastt = n, now
    try:
        rec["threads_main"] = len(os.listdir(f"/proc/{p}/task")); rec["fd_main"] = len(os.listdir(f"/proc/{p}/fd"))
        tr = tree(p); rec["procs_tree"] = len(tr); rec["rss_main_mb"] = rss(p); rec["rss_tree_mb"] = sum(rss(x) or 0 for x in tr)
        rec["threads_tree"] = sum(len(os.listdir(f"/proc/{x}/task")) for x in tr if os.path.isdir(f"/proc/{x}/task")); rec["fd_tree"] = sum(len(os.listdir(f"/proc/{x}/fd")) for x in tr if os.path.isdir(f"/proc/{x}/fd"))
    except Exception as e: rec["err"] = str(e)
    f.write(json.dumps(rec) + "\n")
