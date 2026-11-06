"""G1 30초 창. 사용: q_window.py URL DUR 출력.json [collision]. 모든 시각 time.monotonic/perf_counter.
POST(30Hz 합성) 후 다음 MJPEG 프레임까지 프록시 + 서버 내장 server_latency_ms(status) 기록."""
import sys, os, time, json, threading, http.client, urllib.parse
sys.path.insert(0, os.getcwd())
import numpy as np
from tools import humanoid_synth as hs
url = urllib.parse.urlparse(sys.argv[1]); DUR = float(sys.argv[2]); OUT = sys.argv[3]; COL = len(sys.argv) > 4 and sys.argv[4] == "collision"
def conn(): return http.client.HTTPConnection(url.hostname, url.port, timeout=70)
def req(m, p, b=None, c=None):
    c = c or conn(); c.request(m, p, json.dumps(b) if b is not None else None, {"Content-Type": "application/json"}); r = c.getresponse(); d = r.read()
    try: return r.status, json.loads(d)
    except Exception: return r.status, d[:80]
def wait_ready(t=70):
    dl = time.monotonic() + t
    while time.monotonic() < dl:
        if req("GET", "/humanoid/status")[1].get("state") == "ready": return True
        time.sleep(.05)
    return False
res = {"transport": os.environ.get("VF_TRANSPORT", "http"), "collision_requested": COL, "load0": open("/proc/loadavg").read().split()[:3]}
res["mode_on"] = req("POST", "/humanoid/mode", {"enabled": True})[0]
if COL: res["options_post"] = req("POST", "/humanoid/options", {"collision_avoidance": True})
res["ready"] = wait_ready(); time.sleep(2)
st0 = req("GET", "/humanoid/status")[1]
res["status_flags"] = {k: st0.get(k) for k in ("safety_brake", "collision_avoidance", "state", "options")}
ts = []; stop = [False]
def vid():
    c = conn(); c.request("GET", "/humanoid/video"); r = c.getresponse(); buf = b""
    while not stop[0]:
        ch = r.read1(65536)
        if not ch: break
        buf += ch
        while True:
            i = buf.find(b"\xff\xd8"); j = buf.find(b"\xff\xd9", i + 2) if i >= 0 else -1
            if i < 0 or j < 0: break
            ts.append(time.monotonic()); buf = buf[j + 2:]
    c.close()
jumps = []
def probe():
    pm, pr = time.monotonic(), time.time()
    while not stop[0]:
        time.sleep(.02); m, r = time.monotonic(), time.time(); sk = (r - pr) - (m - pm)
        if abs(sk) > .02: jumps.append((m, round(sk * 1000, 1)))
        pm, pr = m, r
tv = threading.Thread(target=vid, daemon=True); tp = threading.Thread(target=probe, daemon=True); tv.start(); tp.start(); time.sleep(1)
WSM = os.environ.get("VF_TRANSPORT") == "ws"
if WSM:
    import websocket; wsc = websocket.create_connection("ws://%s:%d/tracker/ws" % (url.hostname, url.port), timeout=2)
posts = []; c = conn(); t0 = time.monotonic(); n = 0; pms = []; codes = {}
while time.monotonic() - t0 < DUR:
    tm = (time.monotonic() - t0) % 21.0; d, _ = hs.payload(tm); d = dict(d); d["sent_at"] = time.time()
    a = time.monotonic()
    try:
        if WSM: wsc.send(json.dumps({"route": "/humanoid/update", "data": d})); j = json.loads(wsc.recv()); stc = j.get("status")
        else: stc, j = req("POST", "/humanoid/update", d, c)
    except Exception: c = conn(); codes["exc"] = codes.get("exc", 0) + 1; continue
    b = time.monotonic(); codes[stc] = codes.get(stc, 0) + 1; posts.append((a, b)); pms.append(j.get("process_ms", 0) if isinstance(j, dict) else 0); n += 1
    time.sleep(max(0, t0 + n / 30. - time.monotonic()))
t1 = time.monotonic()
stf = req("GET", "/humanoid/status")[1]
stop[0] = True; time.sleep(.3)
a = np.array(ts); w = a[(a >= t0) & (a <= t1)]; gp = np.diff(w)*1000 if len(w) > 1 else np.array([0.])
lat = [(a[i] - b) * 1000 for _, b in posts for i in [int(np.searchsorted(a, b))] if i < len(a)]
lat = np.array(lat or [0.])
res["window"] = {"dur_s": round(t1 - t0, 3), "frames": int(len(w)), "fps_count": round(len(w) / (t1 - t0), 3), "max_gap_ms": round(float(gp.max()), 1), "gaps_gt200": int((gp > 200).sum()),
  "posts": len(posts), "post_rate_hz": round(len(posts) / (t1 - t0), 2), "post_codes": codes,
  "proxy_post_to_next_frame_ms": {"p50": round(float(np.percentile(lat, 50)), 1), "p95": round(float(np.percentile(lat, 95)), 1), "max": round(float(lat.max()), 1)},
  "process_ms_p50_p95": [round(float(np.percentile(pms, 50)), 2), round(float(np.percentile(pms, 95)), 2)]}
res["server_latency_ms"] = stf.get("server_latency_ms"); res["latency_ms_status"] = stf.get("latency_ms")
res["end_flags"] = {k: stf.get(k) for k in ("safety_brake", "collision_avoidance", "collision_state", "state")}
res["walljumps_in_window"] = [(round(m - t0, 2), s) for m, s in jumps if t0 <= m <= t1]; res["walljump_count"] = len(res["walljumps_in_window"])
res["load1"] = open("/proc/loadavg").read().split()[:3]
req("POST", "/humanoid/mode", {"enabled": False})
json.dump(res, open(OUT, "w"), indent=1, default=str); print(json.dumps(res, indent=1, default=str))
