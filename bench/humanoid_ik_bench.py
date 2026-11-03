"""Benchmark sim.humanoid_ik.ArmIK on random reachable targets and a continuous path.

    python bench/humanoid_ik_bench.py [--n 200] [--seed 0]
Targets are FK of random joint vectors (5 deg inside limits), so they are reachable.
Cold start = from the rest posture, 40 iterations, up to 8 random restarts.  Path = 400 samples of a
smooth joint-space curve, warm started with 12 iterations per sample (teleop mode).
"""
import argparse, json, time
import numpy as np
from sim.humanoid_env import HumanoidEnv, REST, ARM
from sim.humanoid_ik import ArmIK


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--n', type=int, default=200); ap.add_argument('--seed', type=int, default=0)
    a = ap.parse_args(); rng = np.random.default_rng(a.seed)
    env = HumanoidEnv(160, 120); out = {}
    for side in ('left', 'right'):
        s = 1 if side == 'left' else -1
        rest = env.q([f'{side}_{j}_joint' for j in ARM])
        ik = ArmIK(env.model, side, rest=rest); qfull = env.data.qpos.copy()
        res = {'full6d': [], 'pos_elbow': []}
        for mode in ('full6d', 'pos_elbow'):
            for i in range(a.n):
                qt = rng.uniform(ik.lo + np.deg2rad(5), ik.hi - np.deg2rad(5))
                d = ik.fk(qfull, qt); p = ik.point().copy(); R = d.xmat[ik.hand_body].reshape(3, 3).copy(); e = d.site_xpos[ik.site['elbow_site']].copy()
                t = time.perf_counter()
                if mode == 'full6d':
                    q, diag = ik.solve(qfull, rest, p, R, None, iters=40, restarts=8, seed=i)
                    ok = diag['pos_err_mm'] < 2 and diag['rot_err_deg'] < 2
                else:
                    q, diag = ik.solve(qfull, rest, p, None, e, iters=40, restarts=8, seed=i)
                    ok = diag['pos_err_mm'] < 2 and diag['elbow_err_mm'] < 5
                res[mode].append((ok, diag['pos_err_mm'], diag['rot_err_deg'] or 0, diag['iters'], (time.perf_counter() - t) * 1000))
        summ = {}
        for mode, rows in res.items():
            r = np.array(rows, float)
            summ[mode] = {'success': float(r[:, 0].mean()), 'pos_err_mm_med': float(np.median(r[:, 1])), 'pos_err_mm_p95': float(np.percentile(r[:, 1], 95)),
                          'rot_err_deg_med': float(np.median(r[:, 2])), 'iters_med': float(np.median(r[:, 3])),
                          'ms_med': float(np.median(r[:, 4])), 'ms_p95': float(np.percentile(r[:, 4], 95)), 'ms_max': float(r[:, 4].max())}
        # Continuous path: smooth joint curve -> targets; warm-start tracking.
        T = 400; tt = np.linspace(0, 2 * np.pi, T); mid = (ik.lo + ik.hi) / 2; amp = (ik.hi - ik.lo) * .25
        q = rest.copy(); errs = []; jumps = []; times = []
        for k in range(T):
            qt = np.clip(mid * .3 + rest * .7 + amp * np.sin(tt[k] * np.arange(1, 8) / 3 + np.arange(7)), ik.lo + .05, ik.hi - .05)
            d = ik.fk(qfull, qt); p = ik.point().copy(); R = d.xmat[ik.hand_body].reshape(3, 3).copy(); e = d.site_xpos[ik.site['elbow_site']].copy()
            t = time.perf_counter(); qn, diag = ik.solve(qfull, q, p, R, e, iters=12); times.append((time.perf_counter() - t) * 1000)
            jumps.append(float(np.max(np.abs(qn - q)))); q = qn; errs.append(diag['pos_err_mm'])
        summ['path'] = {'samples': T, 'pos_err_mm_med': float(np.median(errs)), 'pos_err_mm_p95': float(np.percentile(errs, 95)),
                        'max_joint_jump_rad': float(np.max(jumps[1:])), 'ms_med': float(np.median(times)), 'ms_max': float(np.max(times))}
        out[side] = summ
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
