"""V-K 독립 재측정: 1600반복 최악 solve_ik 중 정지 요청 → 다음 checkpoint(ik.after)까지 지연, 그 동안 data.qpos/time 불변 확인.
요청 시각을 solve 시작 후 랜덤(1~250ms)으로 흩뿌려 N=30. [시뮬GT] 장면 타이밍만."""
import json, os, time, threading, random
import numpy as np
from sim.env import SimEnv
from sim.control import Controller
import sim.ik as ik

def main():
    random.seed(17); rows = []
    with SimEnv(objects=("mustard",), seed=7, width=64, height=48) as env:
        ctl = Controller(env); T = np.eye(4); T[:3, 3] = [10., 10., 10.]
        for i in range(int(os.environ.get("N", "30"))):
            qpos0 = env.data.qpos.copy(); t0sim = float(env.data.time)
            mark = {}; stop = threading.Event()
            def req():
                mark["at"] = time.monotonic(); mark["qpos_at_req"] = env.data.qpos.copy(); mark["sim_at_req"] = float(env.data.time); stop.set()
            def hook(b):
                if b == "ik.after" and stop.is_set():
                    mark["ack"] = time.monotonic(); raise InterruptedError(b)
            ctl.checkpoint_hook = hook
            tm = threading.Timer(random.uniform(.001, .25), req); s = time.monotonic(); tm.start()
            try: ctl.move_to_pose_joint(T)
            except InterruptedError: pass
            tm.join()
            if "ack" not in mark:  # 요청 전에 solve가 끝남
                rows.append({"status": "finished_before_req", "solve_ms": round((time.monotonic() - s) * 1000, 1)}); continue
            rows.append({"status": "stopped", "lat_ms": round((mark["ack"] - mark["at"]) * 1000, 2),
                         "dq_during": float(np.abs(env.data.qpos - mark["qpos_at_req"]).max()), "dq_total": float(np.abs(env.data.qpos - qpos0).max()),
                         "dsim_s": float(env.data.time) - t0sim})
    lat = [r["lat_ms"] for r in rows if r["status"] == "stopped"]
    print(json.dumps({"N": len(rows), "stopped": len(lat), "p50": float(np.percentile(lat, 50)), "p95": float(np.percentile(lat, 95)), "max": max(lat),
                      "max_dq_total": max(r.get("dq_total", 0) for r in rows), "max_dsim": max(r.get("dsim_s", 0) for r in rows),
                      "load": os.getloadavg(), "rows": rows}))

if __name__ == "__main__":
    main()
