import re
p = r"\\wsl.localhost\Ubuntu-24.04\home\my\work\robot_percept\bench\verify_f\sender_f.py"
s = open(p, encoding="utf8").read()
s = s.replace("s.pool = urllib3.PoolManager(num_pools=1, maxsize=1)\n    def post(s, body):\n",
'''s.pool = urllib3.PoolManager(num_pools=1, maxsize=1); s.ws = None; s.reconn = 0
    def post_ws(s, body):
        # tools/teleop_tracker_win.py WebSocketTransport와 동일: 스레드별 동기 연결, timeout .6, 실패 시 1회 재연결 후 재전송
        import websocket
        a = time.perf_counter(); s.sent += 1
        for attempt in range(2):
            try:
                if s.ws is None:
                    s.ws = websocket.create_connection(url.replace("http://", "ws://") + "/tracker/ws", timeout=.6, enable_multithread=True)
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
        if TR == "ws": return s.post_ws(body)
''', 1)
s = s.replace('return {"sent": ch.sent,', 'return {"reconnects": ch.reconn, "sent": ch.sent,', 1)
open(p, "w", encoding="utf8", newline="\n").write(s)
q = r"\\wsl.localhost\Ubuntu-24.04\home\my\work\robot_percept\bench\verify_f\scen_f.py"
t = open(q, encoding="utf8").read()
t = t.replace('"/mnt/c/Users/my/AppData/Local/Programs/Python/Python313/python.exe", f"{WD}\\\\sender_f.py", "http://127.0.0.1:%d" % u.port, str(dur), WD, f"{WD}\\\\{LBL}.{tag}.json"]',
 '"/mnt/c/Users/my/rp_vf/venv/Scripts/python.exe", f"{WD}\\\\sender_f.py", "http://127.0.0.1:%d" % u.port, str(dur), WD, f"{WD}\\\\{LBL}.{tag}.json", TRANSPORT]', 1)
t = t.replace('u = urllib.parse.urlparse(url);', 'TRANSPORT = os.environ.get("VF_TRANSPORT", "http"); u = urllib.parse.urlparse(url);', 1)
t = t.replace('subprocess.run([sys.executable, f"{HERE}/sender_f.py", url, str(dur), PD, o], capture_output=True)', 'subprocess.run([sys.executable, f"{HERE}/sender_f.py", url, str(dur), PD, o, TRANSPORT], capture_output=True)', 1)
t = t.replace('res = {"label": LBL, "sender": SND,', 'res = {"label": LBL, "transport": TRANSPORT, "sender": SND,', 1)
open(q, "w", encoding="utf8", newline="\n").write(t)
print("ok", "post_ws" in s, "TRANSPORT" in t, t.count("venv"))
