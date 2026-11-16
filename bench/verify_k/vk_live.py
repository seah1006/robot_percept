"""V-K 독립 재현: 실제 Runtime(sim_worker 프로세스)+werkzeug 서버(5096). 측정 락 밖 호출 금지(락은 호출측 flock).
usage: python vk_live.py <mode>   mode: keys|expiry|stop|api|status
[시뮬GT] 타이밍·상태 검증만(GT pose를 pick 입력으로 사용). 인식 성공 주장 아님.
"""
import os, sys, time, json, threading, urllib.request
os.environ.setdefault("PERCEPTION", "stub"); os.environ.setdefault("RP_PERCEPTION_WARMUP", "0")
os.environ["RP_CELL_DB"] = os.environ.get("RP_CELL_DB", "/tmp/vk_cell.sqlite3")
sys.path.insert(0, "/home/user/work/robot_percept")
import web.app as A
from werkzeug.serving import make_server
CAP = {}
_orig = A.Runtime.__init__
def _init(self, *a, **k):
    _orig(self, *a, **k); CAP["rt"] = self
A.Runtime.__init__ = _init
PORT = 5096
BASE = f"http://127.0.0.1:{PORT}"

def http(method, path, body=None, key=None):
    hd = {"Content-Type": "application/json"}
    if key: hd["Idempotency-Key"] = key
    elif method == "POST" and path == "/tasks": hd["Idempotency-Key"] = "vk-" + str(time.monotonic())
    req = urllib.request.Request(BASE + path, method=method, data=None if body is None else json.dumps(body).encode(), headers=hd)
    try:
        with urllib.request.urlopen(req, timeout=30) as r: return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try: return e.code, json.loads(raw)
        except Exception: return e.code, raw[:200]

def boot():
    app = A.create_app(); srv = make_server("127.0.0.1", PORT, app, threaded=True)
    th = threading.Thread(target=srv.serve_forever, daemon=True); th.start()
    rt = CAP["rt"]
    for _ in range(100):
        if dict(rt.status).get("ready") or dict(rt.status).get("objects"): break
        time.sleep(.1)
    return app, srv, rt

def urllib_post_nokey(D):
    req = urllib.request.Request(BASE + "/tasks", method="POST", data=json.dumps(D).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r: return r.status
    except urllib.error.HTTPError as e: return e.code

def pick_payload(rt, name="mustard"):
    st = dict(rt.status); return dict(name=name, T_cam_obj=st["objects"][name]["T_cam_obj"], gt_assist=True)

def qsnap(rt):
    st = dict(rt.status)
    d = {k: st.get(k) for k in ("held_object", "gripper_width", "active_command")}
    d["arm_qpos"] = [round(float(x), 5) for x in (st.get("arm_qpos") or [])]; return d

def wait_res(rt, cid, t=60):
    end = time.monotonic() + t
    while time.monotonic() < end:
        r = rt.command_results.get(cid)
        if r and r.get('status') not in ('accepted', 'running'): return dict(r)
        time.sleep(.005)
    return None

def clear_latch(rt):  # 하네스 전용(제품 경로 없음): 다음 시도 위해 latch 해제
    rt.safety["stop"].clear()

def main(mode):
    app, srv, rt = boot(); out = {"mode": mode}
    try:
        if mode == "keys":
            out["status_keys"] = sorted(dict(rt.status).keys()); out["cell"] = dict(rt.status).get("cell")
        elif mode == "expiry":
            p = pick_payload(rt); q0 = qsnap(rt)
            # (a) 만료 deadline
            cid = rt.send("pick", deadline=time.monotonic() - 1, **p); r = wait_res(rt, cid, 10)
            out["expired_deadline"] = {"cid": cid, "cid_len": len(cid), "result": {k: r.get(k) for k in ("ok", "status", "error")} if r else None, "state_after": qsnap(rt)}
            # (b) epoch 불일치
            cid2 = rt.send("pick", epoch=rt.safety["epoch"].value - 1, **p); r2 = wait_res(rt, cid2, 10)
            out["stale_epoch"] = {"cid": cid2, "result": {k: r2.get(k) for k in ("ok", "status", "error", "epoch")} if r2 else None, "state_after": qsnap(rt)}
            # (c) cid별 결과 독립
            c3 = rt.send("refresh"); c4 = rt.send("pick", deadline=time.monotonic() - 1, **p)
            r3, r4 = wait_res(rt, c3, 10), wait_res(rt, c4, 10)
            out["per_cid"] = {"refresh": r3 and r3.get("status"), "expired": r4 and r4.get("status"), "distinct": c3 != c4 and r3 is not r4}
            out["q0"] = q0; out["moved"] = qsnap(rt) != q0
            out["epoch_final"] = rt.safety["epoch"].value
            # (d) wait timeout -> expire 후 지연 실행 금지: 실행 중 명령 뒤 큐에 쌓인 명령
            long = rt.send("pick", **p); time.sleep(.3)
            late = rt.send("refresh")      # 큐에 대기
            res_wait = rt.wait(late, timeout=.2)  # 타임아웃 유발 -> request_stop
            out["wait_timeout"] = {"result": res_wait.get("status"), "stop_set": rt.safety["stop"].is_set(), "epoch": rt.safety["epoch"].value}
            lr = wait_res(rt, long, 60); out["long_cmd"] = lr and {k: lr.get(k) for k in ("ok", "status", "error")}
            lt = wait_res(rt, late, 10); out["late_cmd"] = lt and {k: lt.get(k) for k in ("ok", "status", "error")}
            out["latch_after_timeout"] = rt.safety["stop"].is_set()
            code, body = http("POST", "/robot/place", {"xyz": [.55, .18, .34]}); out["legacy_place_after_timeout"] = [code, body if isinstance(body, dict) else str(body)]
        elif mode == "stop":
            import random; random.seed(11); trials = []
            for i in range(int(os.environ.get("N", "20"))):
                clear_latch(rt); c = rt.send("reset", seed=7); wait_res(rt, c, 30)
                st = dict(rt.status); p = pick_payload(rt); g0 = dict(rt.status).get("gripper_width")
                cid = rt.send("pick", **p); delay = random.uniform(.05, 4.0); time.sleep(delay)
                t_req = time.monotonic(); rt.request_stop()
                r = wait_res(rt, cid, 30); t_res = time.monotonic()
                st = dict(rt.status); sa = st.get("stop_ack")
                trials.append({"delay": round(delay, 3), "status": r and r.get("status"), "boundary": sa and sa.get("boundary"), "worker_latency_ms": sa and round(sa["latency_ms"], 2),
                               "t_result_ms": round((t_res - t_req) * 1000, 1), "held": st.get("held_object"), "phase": st.get("phase"), "gripper_w": st.get("gripper_width"), "g0": g0})
                if sa: rt.status["stop_ack"] = None
            out["trials"] = trials
        elif mode == "stopik":
            import random; random.seed(5); trials = []
            for i in range(int(os.environ.get("N", "20"))):
                clear_latch(rt); c = rt.send("reset", seed=7); wait_res(rt, c, 30)
                p = pick_payload(rt); T = [list(r) for r in p["T_cam_obj"]]; T[2][3] += 2.5; p["T_cam_obj"] = T  # 도달 불가
                cid = rt.send("pick", **p); delay = random.uniform(.0, .45); time.sleep(delay)
                rt.request_stop(); r = wait_res(rt, cid, 30); sa = dict(rt.status).get("stop_ack")
                trials.append({"delay": round(delay, 3), "status": r and r.get("status"), "err": r and r.get("error"), "boundary": sa and sa.get("boundary"), "worker_latency_ms": sa and round(sa["latency_ms"], 2)})
                if sa: rt.status["stop_ack"] = None
            out["trials"] = trials
        elif mode == "api":
            out["bad_payloads"] = {n: http("POST", "/tasks", b) for n, b in {"none": None, "list": [1], "empty": {}, "target_int": {"target": 5}}.items()}
            out["tasks_post_ok"] = http("POST", "/tasks", {"target": "mustard"})
            time.sleep(.5); out["tasks_list"] = http("GET", "/tasks")
            out["status_cell"] = dict(rt.status).get("cell") if False else http("GET", "/status")[1].get("cell")
            out["second_task"] = http("POST", "/tasks", {"target": "mustard"})
            out["teleop_post_while_owner"] = http("POST", "/teleop/enable", {})
            out["cancel"] = http("POST", "/tasks/none/cancel", {})
        elif mode == "api2":
            D = {"instruction": "머스타드를 집어줘", "source": "sim", "schema_version": 1}
            out["no_key"] = urllib_post_nokey(D)
            out["bad_schema"] = http("POST", "/tasks", {**D, "schema_version": 2})[0]
            out["bad_body"] = [http("POST", "/tasks", b)[0] for b in (None, [1], {}, {"instruction": 5})]
            rt.status["held_object"] = "mustard"  # [시뮬GT] slot 주입, 물리 grasp 아님
            out["held_409"] = http("POST", "/tasks", D, key="h")[0]; rt.status["held_object"] = None
            a = http("POST", "/tasks", D, key="k1"); b = http("POST", "/tasks", D, key="k1"); c = http("POST", "/tasks", {**D, "instruction": "컵"}, key="k1"); d = http("POST", "/tasks", D, key="k2")
            out["idem"] = {"first": a[0], "dup": b[0], "same_id": a[1].get("task_id") == b[1].get("task_id"), "conflict_body": c[0], "new_key_while_owner": d[0]}
            time.sleep(.6); tid = a[1].get("task_id")
            out["get_task"] = http("GET", "/tasks/" + str(tid))[0]
            out["teleop_409"] = http("POST", "/teleop/enable", {})[0]
            out["humanoid_409"] = http("POST", "/humanoid/mode", {"enabled": True})[0]
            out["cancel_wrong_version"] = http("POST", f"/tasks/{tid}/cancel", {"version": 999})[0]
            v = http("GET", "/tasks/" + str(tid))[1]; ver = v.get("version")
            out["cancel_ok"] = http("POST", f"/tasks/{tid}/cancel", {"version": ver}); out["cancel_again"] = http("POST", f"/tasks/{tid}/cancel", {"version": ver})[0]
            from simple_websocket import Client
            ws = Client.connect("ws://127.0.0.1:5096/status/ws"); types = []
            for _ in range(15):
                m = json.loads(ws.receive(timeout=3)); types.append(m.get("type"))
                if m.get("type") == "cell": out["ws_cell"] = m; break
            ws.close(); out["ws_types"] = types
        elif mode == "qpos_ik":
            import random; random.seed(3); rows = []
            for i in range(int(os.environ.get("N", "10"))):
                clear_latch(rt); c = rt.send("reset", seed=7); wait_res(rt, c, 30)
                p = pick_payload(rt); T = [list(r) for r in p["T_cam_obj"]]; T[2][3] += 2.5; p["T_cam_obj"] = T
                q0 = [float(x) for x in dict(rt.status)["arm_qpos"]]
                cid = rt.send("pick", **p); time.sleep(random.uniform(.0, .45)); rt.request_stop()
                samples = []; end = time.monotonic() + 1.0
                while time.monotonic() < end:
                    samples.append(max(abs(a - b) for a, b in zip(dict(rt.status)["arm_qpos"], q0))); time.sleep(.01)
                r = wait_res(rt, cid, 30); sa = dict(rt.status).get("stop_ack")
                rows.append({"max_dq_rad": round(max(samples), 5), "boundary": sa and sa.get("boundary"), "lat_ms": sa and round(sa["latency_ms"], 1), "status": r and r.get("status")})
                if sa: rt.status["stop_ack"] = None
            out["rows"] = rows
        elif mode == "reset":
            def cell(): return http("GET", "/status")[1].get("cell")
            out["cell0"] = cell()
            out["estop"] = http("POST", "/cell/estop", {}); c1 = cell(); out["cell_after_estop"] = c1
            out["place_while_latched"] = http("POST", "/robot/place", {})[0]
            out["task_while_latched"] = http("POST", "/tasks", {"target": "mustard"})[0]
            body = {"version": c1.get("version"), "confirmed": True, "scene_confirmed": True, "held_object_ack": None, "boot_id": c1.get("boot_id")}
            out["reset_missing_confirm"] = http("POST", "/cell/reset-stop", {**body, "confirmed": False})
            out["reset_wrong_ack"] = http("POST", "/cell/reset-stop", {**body, "held_object_ack": "mustard"})
            out["reset_wrong_version"] = http("POST", "/cell/reset-stop", {**body, "version": 999})
            time.sleep(1.0)
            out["reset_ok"] = http("POST", "/cell/reset-stop", body)
            out["cell_after_reset"] = cell()
            out["place_after_reset"] = http("POST", "/robot/place", {})[0]
            out["reset_again"] = http("POST", "/cell/reset-stop", body)[0]
        elif mode == "killme":
            out["post"] = http("POST", "/tasks", {"instruction": "머스타드를 집어줘", "source": "sim", "schema_version": 1}); time.sleep(.6)
            out["state"] = http("GET", "/tasks")[1]; print("RESULT " + json.dumps(out, default=str)); sys.stdout.flush()
            import signal; os.kill(os.getpid(), signal.SIGKILL)
        elif mode == "status":
            out["status"] = {k: v for k, v in http("GET", "/status")[1].items() if k in ("cell", "phase", "held_object")}
    finally:
        out["port_pid_note"] = "own process"
        print("RESULT " + json.dumps(out, default=str, ensure_ascii=False))
        sys.stdout.flush()
        try: srv.shutdown()
        except Exception: pass
        try: A.close_app(app, deadline=time.monotonic() + 5)
        except Exception as e: print("close err", e)
        os._exit(0)

if __name__ == "__main__":
    main(sys.argv[1])
