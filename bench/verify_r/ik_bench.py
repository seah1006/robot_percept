"""V-R IK bench. usage: python ik_bench.py <module> [N]   module: sim.ik (current) or baseline_ik (file bench/verify_r/baseline_ik.py)
Targets = FK of random q inside 90% of official limits (reachable by construction), q_init = HOME."""
import sys, time, json, importlib
import numpy as np, mujoco
sys.path.insert(0, '.'); sys.path.insert(0, 'bench/verify_r')
from sim.env import SimEnv
mod = importlib.import_module(sys.argv[1]); N = int(sys.argv[2]) if len(sys.argv) > 2 else 200
import inspect
solve = mod.solve_ik
rot_err = mod._rotation_error
env = SimEnv(('mustard',), 64, 48); m = env.model
qadr, dofs, lim = mod.arm_indices(m)
rng = np.random.default_rng(1234)
d = mujoco.MjData(m)
def fk(q):
    d.qpos[:] = env.data.qpos; d.qpos[qadr] = q; mujoco.mj_forward(m, d); return mod.tcp_pose(m, d)
mid = lim.mean(1); half = (lim[:, 1] - lim[:, 0]) / 2
def run(label, make_init):
    ok = 0; pe = []; re = []; ts = []; jump = []
    for k in range(N):
        qt = mid + rng.uniform(-.8, .8, 7) * half
        T = fk(qt)
        if T[2, 3] < 0.05: T = fk(qt)
        t0 = time.perf_counter(); out = solve(m, env.data, T, q_init=make_init(qt)); dt = time.perf_counter() - t0
        q = out[0]; s = out[1]
        Tq = fk(q); e1 = np.linalg.norm(Tq[:3, 3] - T[:3, 3]); e2 = np.linalg.norm(rot_err(T[:3, :3], Tq[:3, :3]))
        inl = np.all(q >= lim[:, 0] - 1e-6) and np.all(q <= lim[:, 1] + 1e-6)
        ok += int(bool(s) and inl and e1 < 2e-3 and e2 < np.deg2rad(2)); pe.append(e1); re.append(e2); ts.append(dt)
    pe, re, ts = map(np.array, (pe, re, ts))
    r = dict(label=label, N=N, success=ok / N, pos_err_mm_med=float(np.median(pe) * 1e3), pos_err_mm_p95=float(np.percentile(pe, 95) * 1e3),
             rot_err_deg_med=float(np.degrees(np.median(re))), rot_err_deg_p95=float(np.degrees(np.percentile(re, 95))),
             t_ms_med=float(np.median(ts) * 1e3), t_ms_p95=float(np.percentile(ts, 95) * 1e3), t_ms_max=float(ts.max() * 1e3))
    print(json.dumps(r)); return r
res = [run('init=HOME', lambda qt: mod.HOME if hasattr(mod, 'HOME') else None),
       run('init=near(qt+0.3rad noise)', lambda qt: np.clip(qt + rng.normal(0, .3, 7), lim[:, 0], lim[:, 1]))]

# continuity: smooth circular path with orientation sweep, warm-started tick-by-tick
def path(n=400):
    c = np.array([.5, 0., .5]); out = []
    for s in np.linspace(0, 1, n):
        a = 2 * np.pi * s
        p = c + [.12 * np.cos(a), .15 * np.sin(a), .06 * np.sin(2 * a)]
        yaw, pitch = .6 * np.sin(a), .4 * np.sin(2 * a)
        Rb = np.diag([1., -1., -1.])
        cz, sz, cy, sy = np.cos(yaw), np.sin(yaw), np.cos(pitch), np.sin(pitch)
        Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]); Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
        T = np.eye(4); T[:3, :3] = Rz @ Ry @ Rb; T[:3, 3] = p; out.append(T)
    return out
q = np.array(mod.HOME if hasattr(mod, 'HOME') else env.arm_qpos()); maxdq = 0; fails = 0; flips = 0; errs = []
q = solve(m, env.data, path()[0], q_init=q)[0]
for T in path():
    q2, s = solve(m, env.data, T, q_init=q)[:2]
    dqm = np.max(np.abs(q2 - q)); maxdq = max(maxdq, dqm); flips += int(dqm > .2); fails += int(not s)
    errs.append(np.linalg.norm(fk(q2)[:3, 3] - T[:3, 3])); q = q2
cont = dict(label='circle path 400 pts', max_dq_per_step=float(maxdq), steps_dq_gt_0p2=flips, fails=fails, pos_err_mm_max=float(max(errs) * 1e3))
print(json.dumps(cont)); res.append(cont)
json.dump(res, open(f'bench/verify_r/ik_{sys.argv[1].replace(".", "_")}.json', 'w'), indent=1)
