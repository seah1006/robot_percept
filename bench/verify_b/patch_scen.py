q = r"\\wsl.localhost\Ubuntu-24.04\home\my\work\robot_percept\bench\verify_f\scen_f.py"
t = open(q, encoding="utf8").read()
t = t.replace('''ths = [threading.Thread(target=poller, args=a, daemon=True) for a in (("/humanoid/status", 10), ("/teleop/status", 10), ("/status", 3))] +''',
'''PUSH = os.environ.get("VF_STATUS", "poll") == "push"; pushc = {}
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
ths = ([threading.Thread(target=pusher, daemon=True)] if PUSH else []) + [threading.Thread(target=poller, args=a, daemon=True) for a in POLLS] +''', 1)
t = t.replace('"poll_total_req_per_s": round(sum(len(v) for v in lat.values()) / dt, 2),', '"poll_total_req_per_s": round(sum(len(v) for v in lat.values()) / dt, 2), "push": {"mode": "push" if PUSH else "poll", "msgs_per_s": round(sum(v for k, v in pushc.items() if k != "bytes") / dt, 2), "bytes_per_s": round(pushc.get("bytes", 0) / dt), "by_type": dict(pushc)},', 1)
t = t.replace('res = {"label": LBL, "transport": TRANSPORT,', 'res = {"label": LBL, "status_mode": os.environ.get("VF_STATUS", "poll"), "transport": TRANSPORT,', 1)
open(q, "w", encoding="utf8", newline="\n").write(t)
print("pusher" in t, t.count("PUSH"))
