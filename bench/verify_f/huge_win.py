"""Windows py → WSL WS 대용량/상한 점검. 사용: huge_win.py URL (websocket-client 필요)"""
import sys, json, time, websocket
u = sys.argv[1].replace("http://", "ws://") + "/tracker/ws"; out = {}
def t(name, send, binary):
    c = websocket.create_connection(u, timeout=8); a = time.monotonic()
    try:
        c.send_binary(send) if binary else c.send(send); r = c.recv(); res = ("reply " + r[:90]) if r else "closed by server (empty recv)"
    except Exception as e: res = "exc " + type(e).__name__
    out[name] = {"result": res, "sec": round(time.monotonic() - a, 2)}
    try: c.close()
    except Exception: pass
t("binary 5MB", b"\xff\xd8" + b"0" * (5 << 20), True); t("binary 70001B", b"\xff\xd8" + b"0" * 69999, True); t("binary 60000B bad-jpeg-tail", b"\xff\xd8" + b"0" * 59998, True)
t("text 1MB", "x" * (1 << 20), False)
c = websocket.create_connection(u, timeout=5); c.send(json.dumps({"route": "/humanoid/update", "data": {"detected": False}})); out["normal update after"] = json.loads(c.recv())
print(json.dumps(out, ensure_ascii=False))
