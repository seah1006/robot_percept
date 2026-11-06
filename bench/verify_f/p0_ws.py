"""P0(WS/HTTP 동일성) + 연결 누수. 사용: p0_ws.py URL SERVERPID 출력.json  (conda env: websocket-client 필요)
G1 OFF 상태에서 검증 규칙 동일성 비교(HTTP 상태코드 vs WS reply.status), 오류 후 연결 생존, 무제한 메시지, Origin, 연결 수 상한, 스레드/fd 누수."""
import sys, os, json, time, math, urllib3, websocket
url = sys.argv[1].rstrip("/"); PID = int(sys.argv[2]); OUT = sys.argv[3]
ws_url = url.replace("http://", "ws://"); http = urllib3.PoolManager()
def th(): return int([l for l in open(f"/proc/{PID}/status") if l.startswith("Threads")][0].split()[1])
def fds(): return len(os.listdir(f"/proc/{PID}/fd"))
def hpost(route, body, ct="application/json"):
    r = http.request("POST", url + route, body=body, headers={"Content-Type": ct}, timeout=5, retries=False); return r.status
def wcon(extra=None):
    return websocket.create_connection(ws_url + "/tracker/ws", timeout=5, **(extra or {}))
def wsend(c, route, body):
    c.send(json.dumps({"route": route, "data": body}) if not isinstance(body, str) else body); return json.loads(c.recv())
res = {"cases": [], "mismatch": []}
pad = lambda n: {"detected": False, "pad": "x" * n}
pose_ok = [[0.1, 0.1, 0.1, 0.9]] * 33
cases = [
 ("/humanoid/update", {"detected": "x"}), ("/humanoid/update", {"detected": True}), ("/humanoid/update", {"detected": True, "pose": "abc"}),
 ("/humanoid/update", {"detected": True, "pose": [[1, 2]]}), ("/humanoid/update", {"detected": True, "pose": [[float("nan")] * 4] * 33, "hands": {}}),
 ("/humanoid/update", {"detected": True, "pose": pose_ok, "hands": {"left": "bad"}}), ("/humanoid/update", {"detected": False}),
 ("/humanoid/update", {"detected": True, "pose": pose_ok, "hands": {}, "pose2d": [[0, 0]] * 33, "hands2d": {}}),
 ("/humanoid/update", pad(65000)), ("/humanoid/update", pad(70000)),
 ("/teleop/update", {"detected": "yes"}), ("/teleop/update", {"detected": True, "x": 2, "y": 0, "scale": 1, "pinch": 1}),
 ("/teleop/update", {"detected": True, "x": True, "y": 0, "scale": 1, "pinch": 1}), ("/teleop/update", {"detected": True, "x": .5, "y": .5, "scale": 1, "pinch": 1}),
 ("/teleop/update", {"detected": False}), ("/teleop/update", pad(7000)), ("/teleop/update", pad(9000)),
]
c = wcon()
for route, body in cases:
    raw = json.dumps(body)
    try: hs = hpost(route, raw)
    except Exception as e: hs = "exc " + str(e)[:40]
    try: wr = wsend(c, route, body); wsx = wr.get("status")
    except Exception as e: wsx = "exc " + str(e)[:40]; c = wcon()
    ok = (hs == wsx); res["cases"].append({"route": route, "size": len(raw), "http": hs, "ws": wsx, "same": ok})
    if not ok: res["mismatch"].append((route, len(raw), hs, wsx))
# 구조 오류 (WS 전용 envelope)
for name, msg in [("not json", "{bad"), ("list", "[1]"), ("no route", json.dumps({"data": {}})), ("unknown route", json.dumps({"route": "/x", "data": {}})), ("data not obj", json.dumps({"route": "/humanoid/update", "data": 5}))]:
    try: r = wsend(c, None, msg); res["cases"].append({"ws_only": name, "ws": r.get("status"), "error": r.get("error")})
    except Exception as e: res["cases"].append({"ws_only": name, "exc": str(e)[:60]}); c = wcon()
# preview 바이너리 (HTTP와 비교)
jpg = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "pl", "preview.jpg"), "rb").read() if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "pl", "preview.jpg")) else b"\xff\xd8" + b"\0" * 100 + b"\xff\xd9"
for name, b in [("valid jpeg", jpg), ("not jpeg", b"hello" * 10), ("empty", b""), ("250000", b"\xff\xd8" + b"\0" * 249996 + b"\xff\xd9"), ("250001", b"\xff\xd8" + b"\0" * 249997 + b"\xff\xd9")]:
    hs = hpost("/teleop/preview", b, "image/jpeg")
    try: c.send_binary(b); wsx = json.loads(c.recv()).get("status")
    except Exception as e: wsx = "exc " + str(e)[:40]; c = wcon()
    res["cases"].append({"preview": name, "size": len(b), "http": hs, "ws": wsx, "same": hs == wsx})
    if hs != wsx: res["mismatch"].append(("preview " + name, len(b), hs, wsx))
# 오류 후 같은 연결 생존
try: res["alive_after_errors"] = wsend(c, "/humanoid/update", {"detected": False}).get("status") == 200
except Exception as e: res["alive_after_errors"] = "exc " + str(e)[:60]
# 거대 메시지: 연결 종료는 허용, 서버 생존 필수
t0 = th()
for name, size, binary in [("text 1MB", 1 << 20, False), ("binary 5MB", 5 << 20, True)]:
    cc = wcon(); t = time.monotonic()
    try:
        cc.send_binary(b"\xff\xd8" + b"0" * size) if binary else cc.send("x" * size)
        r = cc.recv(); out = ("reply " + str(r)[:80]) if r else "closed by server (empty recv)"
    except Exception as e: out = "closed/exc " + type(e).__name__
    try: cc.close()
    except Exception: pass
    alive = hpost("/humanoid/update", json.dumps({"detected": False})) == 200
    res["cases"].append({"huge": name, "result": out, "server_alive": alive, "sec": round(time.monotonic() - t, 2)})
# Origin
for origin in ("http://evil.example", url):
    try: cc = websocket.create_connection(ws_url + "/tracker/ws", timeout=3, origin=origin); cc.send(json.dumps({"route": "/humanoid/update", "data": {"detected": False}})); r = cc.recv(); out = ("accepted " + str(r)[:50]) if r else "rejected (closed, empty recv)"
    except Exception as e: out = "rejected/exc " + type(e).__name__
    res["cases"].append({"origin": origin, "result": out})
try: cc = websocket.create_connection(ws_url + "/status/ws", timeout=3, origin="http://evil.example"); r = cc.recv(); out = "accepted (데이터 수신)" if r else "rejected (closed, empty recv)"
except Exception as e: out = "rejected/exc " + type(e).__name__
res["cases"].append({"origin_status_ws": "evil", "result": out})
# 연결 수 상한 (status ws)
cons = []; got = 0
for i in range(10):
    try:
        cc = websocket.create_connection(ws_url + "/status/ws", timeout=3); cons.append(cc)
    except Exception: pass
time.sleep(1.5)
for cc in cons:
    try: cc.settimeout(1.5); got += 1 if cc.recv() else 0
    except Exception: pass
res["status_ws_10_open"] = {"opened": len(cons), "receiving_data": got}
for cc in cons:
    try: cc.close()
    except Exception: pass
# 누수: 24회 open/close (tracker, status), 시작/끝 스레드·fd
time.sleep(2); s_th, s_fd = th(), fds()
for i in range(24):
    cc = wcon(); wsend(cc, "/humanoid/update", {"detected": False}); cc.close()
for i in range(24):
    cc = websocket.create_connection(ws_url + "/status/ws", timeout=3); cc.recv(); cc.close()
for i in range(12):  # 비정상 종료: 소켓만 닫기
    cc = wcon(); cc.sock.close()
time.sleep(4); res["leak"] = {"threads": [s_th, th()], "fds": [s_fd, fds()]}
try: c.close()
except Exception: pass
time.sleep(3); res["leak"]["threads_after_settle"] = th(); res["leak"]["fds_after_settle"] = fds()
res["mismatch_count"] = len(res["mismatch"])
json.dump(res, open(OUT, "w"), indent=1, default=str); print(json.dumps({k: res[k] for k in ("mismatch", "alive_after_errors", "status_ws_10_open", "leak")}, default=str))
