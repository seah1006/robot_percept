"""지표1 합성 트래커 송신기 (Windows py 또는 WSL python, urllib3만 필요).
tools/teleop_tracker_win.py의 post()와 동일: urllib3.PoolManager(num_pools=1,maxsize=1), Timeout(total=.6), retries=False,
제어 스레드(/humanoid/update JSON)와 preview 스레드(/teleop/preview JPEG) 분리, 각 30Hz 페이싱(perf_counter), sent_at=time.time().
사용: sender_f.py URL 초 payload_dir 출력.json [transport]   (transport 기본 http)"""
import sys, os, json, time, threading, statistics, urllib3, platform
url = sys.argv[1].rstrip("/"); DUR = float(sys.argv[2]); D = sys.argv[3]; OUT = sys.argv[4]; TR = sys.argv[5] if len(sys.argv) > 5 else "http"
pl = json.load(open(os.path.join(D, "payloads.json"))); jpg = open(os.path.join(D, os.environ.get("VF_PREVIEW", "preview.jpg")), "rb").read()
def status(path):
    p = urllib3.PoolManager(); r = p.request("GET", url + path, timeout=3); return json.loads(r.data)
def pct(a, q):
    a = sorted(a); return round(a[min(len(a) - 1, int(q / 100 * len(a)))], 2) if a else None
class Ch:
    def __init__(s, route, raw):
        s.route = route; s.raw = raw; s.rtt = []; s.err = 0; s.sent = 0; s.codes = {}; s.pool = urllib3.PoolManager(num_pools=1, maxsize=1); s.ws = None; s.reconn = 0
    def post_ws(s, body):
        # tools/teleop_tracker_win.py WebSocketTransport와 동일: 스레드별 동기 연결, timeout .6, 실패 시 1회 재연결 후 재전송
        import websocket
        a = time.perf_counter(); s.sent += 1
        for attempt in range(2):
            try:
                if s.ws is None:
                    s.ws = websocket.create_connection(url.replace("http://", "ws://") + "/tracker/ws", timeout=.6, enable_multithread=True, sockopt=([(__import__("socket").IPPROTO_TCP, __import__("socket").TCP_NODELAY, 1)] if os.environ.get("VF_WS_NODELAY") else None))
                if s.raw: s.ws.send_binary(body)
                else: s.ws.send(json.dumps({"route": s.route, "data": json.loads(body)}, separators=(",", ":")))
                rep = json.loads(s.ws.recv()); b = time.perf_counter(); st = rep.get("status", 200)
                s.codes[st] = s.codes.get(st, 0) + 1
                if not rep.get("ok"): s.err += 1
                else: s.rtt.append((b - a) * 1000)
                return
            except Exception:
                s.reconn += 1
                try: s.ws.close()
                except Exception: pass
                s.ws = None
                if attempt == 0: time.sleep(.05)
        s.err += 1; s.codes["exc"] = s.codes.get("exc", 0) + 1
    def post(s, body):
        if TR == "ws" and not s.raw: return s.post_ws(body)  # hybrid: raw preview는 HTTP
        a = time.perf_counter(); s.sent += 1
        try:
            r = s.pool.request("POST", url + s.route, body=body, headers={"Content-Type": "image/jpeg" if s.raw else "application/json"}, timeout=urllib3.Timeout(total=.6), retries=False, preload_content=False)
            r.read(); r.release_conn(); b = time.perf_counter(); s.codes[r.status] = s.codes.get(r.status, 0) + 1
            if r.status >= 400: s.err += 1
            else: s.rtt.append((b - a) * 1000)
        except Exception:
            s.err += 1; s.codes["exc"] = s.codes.get("exc", 0) + 1
upd = Ch("/humanoid/update", False); pre = Ch("/teleop/preview", True)
s0h = status("/humanoid/status"); s0t = status("/teleop/status")
t0 = time.perf_counter()
def loop(ch, mk):
    n = 0
    while time.perf_counter() - t0 < DUR:
        ch.post(mk(n)); n += 1
        d = t0 + n / 30. - time.perf_counter()
        if d > 0: time.sleep(d)
def mk_upd(n):
    d = dict(pl[n % len(pl)]); d["sent_at"] = time.time(); d["capture_at"] = time.time(); d["seq"] = n
    return json.dumps(d, separators=(",", ":")).encode()
th = [threading.Thread(target=loop, args=(upd, mk_upd)), threading.Thread(target=loop, args=(pre, lambda n: jpg))]
for t in th: t.start()
for t in th: t.join()
el = time.perf_counter() - t0; time.sleep(.5)
s1h = status("/humanoid/status"); s1t = status("/teleop/status")
def summ(ch):
    return {"reconnects": ch.reconn, "sent": ch.sent, "ok": len(ch.rtt), "err": ch.err, "codes": ch.codes, "rtt_ms": {"p50": pct(ch.rtt, 50), "p95": pct(ch.rtt, 95), "max": round(max(ch.rtt), 2) if ch.rtt else None, "mean": round(statistics.mean(ch.rtt), 2) if ch.rtt else None}}
ic = s1h["input_count"] - s0h["input_count"]; pc = s1t["preview_count"] - s0t["preview_count"]
res = {"transport": TR, "client": platform.platform() + " py" + platform.python_version() + " urllib3 " + urllib3.__version__, "dur_s": round(el, 3), "update": summ(upd), "preview": summ(pre),
  "server_input_count_delta": ic, "server_processed_ratio": round(ic / max(1, upd.sent), 4), "server_rx_hz": round(ic / el, 2), "server_input_hz_status": s1h.get("input_hz"),
  "preview_count_delta": pc, "preview_processed_ratio": round(pc / max(1, pre.sent), 4), "send_hz_update": round(upd.sent / el, 2), "server_latency_ms_status": s1h.get("server_latency_ms")}
json.dump(res, open(OUT, "w"), indent=1); print(json.dumps(res))
