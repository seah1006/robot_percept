"""열린 연결 중 종료: G1 ON + MJPEG 2(/humanoid/video,/teleop/preview.mjpg) + /status/ws 1 + /tracker/ws 송신(sender_q3 ws) 상태에서 신호.
사용: openconn.py TREE OUTDIR N  (환경: 락 안, 포트 5092)"""
import sys, os, time, json, signal, subprocess, threading, http.client, urllib.request, socket
TREE, OUT, N = sys.argv[1], sys.argv[2], int(sys.argv[3]); PORT = 5092; R = os.path.expanduser("~/work/robot_percept")
os.makedirs(OUT, exist_ok=True)
env = dict(os.environ, HOST="0.0.0.0", PYTHONPATH=TREE, PERCEPTION="stub", RP_PERCEPTION_WARMUP="0", PORT=str(PORT))
PY = sys.executable
def tree(pid):
    ch = {}
    for d in os.listdir("/proc"):
        if d.isdigit():
            try: ch.setdefault(int(open(f"/proc/{d}/stat").read().rsplit(")", 1)[1].split()[1]), []).append(int(d))
            except Exception: pass
    out = [pid]; i = 0
    while i < len(out): out += ch.get(out[i], []); i += 1
    return out[1:]
def alive(p):
    try:
        s = open(f"/proc/{p}/status").read()
        return "\nState:\tZ" not in s
    except Exception: return False
def req(m, path, body=None):
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=70)
    c.request(m, path, json.dumps(body) if body is not None else None, {"Content-Type": "application/json"}); r = c.getresponse(); d = r.read(); c.close(); return r.status, d
def run_one(sig, label):
    res = {"label": label, "signal": sig.name}
    log = open(f"{OUT}/{label}.server.log", "w")
    p = subprocess.Popen([PY, "-c", "import signal,os;signal.signal(signal.SIGINT,signal.default_int_handler);os.execvp('python',['python','-m','web.app'])"], cwd=TREE, env=env, stdout=log, stderr=log)
    for _ in range(160):
        try:
            if req("GET", "/humanoid/status")[0] == 200: break
        except Exception: time.sleep(.5)
    st, _ = req("POST", "/humanoid/mode", {"enabled": True}); res["on_http"] = st
    time.sleep(2)
    ends = {}; stop = threading.Event()
    def mjpeg(name, path):
        n = 0
        try:
            c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=15); c.request("GET", path); r = c.getresponse(); res[name + "_status"] = r.status
            while True:
                b = r.read1(65536)
                if not b: ends[name] = {"end": "eof", "bytes": n, "t": time.monotonic()}; return
                n += len(b)
        except Exception as e: ends[name] = {"end": type(e).__name__, "bytes": n, "t": time.monotonic()}
    def wsr():
        import websocket
        n = 0
        try:
            w = websocket.create_connection(f"ws://127.0.0.1:{PORT}/status/ws", timeout=15)
            while True:
                m = w.recv()
                if m == "" or m is None: ends["status_ws"] = {"end": "empty_recv", "msgs": n, "t": time.monotonic()}; return
                n += 1
        except Exception as e: ends["status_ws"] = {"end": type(e).__name__ + ":" + str(e)[:40], "msgs": n, "t": time.monotonic()}
    ths = [threading.Thread(target=mjpeg, args=("mjpeg_humanoid", "/humanoid/video")), threading.Thread(target=mjpeg, args=("mjpeg_teleop", "/teleop/preview.mjpg")), threading.Thread(target=wsr)]
    for t in ths: t.daemon = True; t.start()
    sp = subprocess.Popen([PY, f"{R}/bench/verify_q2/sender_q3.py", f"http://127.0.0.1:{PORT}", "14", f"{OUT}/pl", f"{OUT}/{label}.sender.json", "ws"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=R, text=True)
    sp.stdout.readline(); time.sleep(5)
    kids = tree(p.pid); res["children"] = len(kids)
    t0 = time.monotonic(); os.kill(p.pid, sig)
    left = list(kids); parent_t = None
    while time.monotonic() - t0 < 12:
        left = [k for k in left if alive(k)]
        if parent_t is None and p.poll() is not None: parent_t = time.monotonic() - t0
        if p.poll() is not None and not left: break
        time.sleep(.02)
    res["parent_exit_s"] = None if parent_t is None else round(parent_t, 3)
    res["all_gone_s"] = round(time.monotonic() - t0, 3); res["left"] = len(left)
    res["left_cmd"] = [open(f"/proc/{k}/cmdline").read().replace("\0", " ")[:60] for k in left if alive(k)]
    res["parent_rc"] = p.poll()
    try: so, se = sp.communicate(timeout=25)
    except Exception: sp.kill(); so = se = ""
    for t in ths: t.join(3)
    res["clients"] = {k: {kk: (round(vv - t0, 3) if kk == "t" else vv) for kk, vv in v.items()} for k, v in ends.items()}
    try:
        sj = json.load(open(f"{OUT}/{label}.sender.json")); res["sender_codes"] = {k: sj.get(k, {}).get("codes") for k in ("update", "preview")}
    except Exception as e: res["sender_codes"] = "n/a " + type(e).__name__
    res["sender_err_tail"] = se.strip().splitlines()[-1][:120] if se.strip() else ""
    for k in kids:
        try: os.kill(k, 9)
        except Exception: pass
    try: p.kill()
    except Exception: pass
    p.wait(); time.sleep(1)
    return res
subprocess.run([PY, f"{R}/bench/verify_f/gen_payloads.py", f"{OUT}/pl"], stdout=subprocess.DEVNULL)
allr = []
for sig in (signal.SIGTERM, signal.SIGINT):
    for i in range(1, N + 1):
        r = run_one(sig, f"{sig.name}_{i}"); allr.append(r)
        print(json.dumps(r, ensure_ascii=False), flush=True)
json.dump(allr, open(f"{OUT}/all.json", "w"), ensure_ascii=False, indent=1)
