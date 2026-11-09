"""V-T3 independent WS-failure recovery check (Windows python). Own TCP proxy (not I-K3's): blocks WS upgrades (503) and cuts established WS pipes
during [block_start, block_end] seconds after proxy start; HTTP passes. Logs every connection attempt with proxy clock. Also samples server input_count
directly (bypassing the proxy) to prove ingestion continues over HTTP. usage: r3_recover.py --server http://127.0.0.1:5092 --out DIR --tracker PATH --video PATH --bs 10 --be 20 --secs 70 --label x"""
import argparse, json, os, select, socket, socketserver, subprocess, sys, threading, time, urllib.request, pathlib
ap = argparse.ArgumentParser()
ap.add_argument("--server"); ap.add_argument("--out"); ap.add_argument("--tracker"); ap.add_argument("--video"); ap.add_argument("--bs", type=float, default=10); ap.add_argument("--be", type=float, default=20)
ap.add_argument("--secs", type=float, default=70); ap.add_argument("--label", default="rec"); ap.add_argument("--mode", default="humanoid")
A = ap.parse_args()
host, port = A.server.split("//")[1].split(":"); port = int(port)
out = pathlib.Path(A.out); out.mkdir(parents=True, exist_ok=True)
T0 = time.perf_counter(); log = []; lock = threading.Lock(); ws_pipes = []
def now(): return time.perf_counter() - T0
def blocked(): return A.bs <= now() < A.be
class H(socketserver.BaseRequestHandler):
    def handle(self):
        c = self.request; c.settimeout(5); data = b""
        try:
            while b"\r\n\r\n" not in data:
                b = c.recv(65536)
                if not b: return
                data += b
                if len(data) > 262144: break
            line = data.split(b"\r\n", 1)[0].decode("latin1"); ws = b"upgrade: websocket" in data.lower()
            if ws and blocked():
                with lock: log.append(dict(t=round(now(), 3), kind="ws_upgrade", action="blocked_503"))
                c.sendall(b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"); return
            r = socket.create_connection((host, port), timeout=5); r.sendall(data)
            if ws:
                with lock: log.append(dict(t=round(now(), 3), kind="ws_upgrade", action="passed")); ws_pipes.append((c, r))
            c.settimeout(None)
            while True:
                if ws and blocked():
                    with lock: log.append(dict(t=round(now(), 3), kind="ws_pipe", action="cut"))
                    r.close(); return
                rd, _, _ = select.select([c, r], [], [], .02)
                for s in rd:
                    b = s.recv(65536)
                    if not b: r.close(); return
                    (r if s is c else c).sendall(b)
        except OSError: return
class P(socketserver.ThreadingTCPServer): allow_reuse_address = True; daemon_threads = True
px = P(("127.0.0.1", 0), H); threading.Thread(target=px.serve_forever, daemon=True).start()
purl = f"http://127.0.0.1:{px.server_address[1]}"
for k in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "PIP_PREFIX", "PYTHONNOUSERSITE"): os.environ.pop(k, None)
os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"
sd = r"C:\Users\USER\Documents\sam_camera"
cmd = [sys.executable, "-u", A.tracker, "--mode", A.mode, "--transport", "ws", "--url", purl, "--video", A.video, "--loop-video", "--seconds", str(A.secs),
       "--model", sd + r"\models\hand_landmarker.task", "--pose-model", sd + r"\models\pose_landmarker_lite.task", "--metrics-out", str(out / (A.label + ".metrics.json"))]
tl = []; stop = [False]
def poll():
    p = "/humanoid/status" if A.mode == "humanoid" else "/teleop/status"
    while not stop[0]:
        try:
            s = json.load(urllib.request.urlopen(A.server + p, timeout=2)); tl.append((round(now(), 3), s.get("input_count")))
        except Exception: pass
        time.sleep(.1)
threading.Thread(target=poll, daemon=True).start()
so = open(out / (A.label + ".stdout.txt"), "w"); se = open(out / (A.label + ".stderr.txt"), "w")
tstart = now(); p = subprocess.Popen(cmd, stdout=so, stderr=se); rc = p.wait(); tend = now(); stop[0] = True; time.sleep(.3)
passed_after = [e["t"] for e in log if e["kind"] == "ws_upgrade" and e["action"] == "passed" and e["t"] >= A.be - 0.001]
first_ws_after = passed_after[0] if passed_after else None
# ingestion per-second rate around the block
import collections
cnt = collections.OrderedDict()
for t, n in tl:
    if n is not None: cnt[int(t)] = n
secs = sorted(cnt); rates = {s: cnt[s] - cnt[secs[i - 1]] for i, s in enumerate(secs) if i > 0}
res = dict(label=A.label, block_s=[A.bs, A.be], tracker_start_s=round(tstart, 2), tracker_end_s=round(tend, 2), rc=rc, proxy_events=log,
           first_ws_passed_after_block_end_s=first_ws_after, return_after_restore_s=(round(first_ws_after - A.be, 3) if first_ws_after is not None else None),
           within_30s=(first_ws_after is not None and first_ws_after - A.be <= 30), server_input_per_s=rates, min_rate_in_block=min([v for s, v in rates.items() if A.bs + 1 <= s < A.be - 1] or [None]))
(out / (A.label + ".recovery.json")).write_text(json.dumps(res, indent=1)); print(json.dumps({k: v for k, v in res.items() if k not in ("proxy_events", "server_input_per_s")}))
px.shutdown()
