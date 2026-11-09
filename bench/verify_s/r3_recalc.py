"""Independent penetration recompute from 500Hz raw qpos npz (own capsule definition, NOT sim.humanoid_collision).
usage: python r3_recalc.py TREE RAW.npz [RAW2.npz ...]   radii torso118/upper53/fore45/hand57 mm (I-S3 latest MESH_RADII; verify by grep)
Capsules: torso pelvis->shoulder mid; upper shoulder_roll->elbow; fore elbow->wrist_pitch; hand wrist_pitch->wrist_yaw+R*[.09,0,0].
13 pairs. Approximation: capsules, no fingers/face/mesh; 500Hz sample (2ms), no continuous-time between samples."""
import sys, os, json, numpy as np, mujoco
tree = sys.argv[1]; sys.path.insert(0, tree); os.chdir(tree)
from sim.humanoid_env import HumanoidEnv
e = HumanoidEnv(); M = e.model; D = mujoco.MjData(M)
RT, RU, RF, RH = [float(x) / 1000 for x in os.environ.get('RADII_MM', '118,53,45,57').split(',')]
bid = lambda n: mujoco.mj_name2id(M, mujoco.mjtObj.mjOBJ_BODY, n)
ids = {n: bid(n) for n in ['pelvis'] + [f'{s}_{b}' for s in ('left', 'right') for b in ('shoulder_roll_link', 'elbow_link', 'wrist_pitch_link', 'wrist_yaw_link')]}
def sd(p0, p1, q0, q1):
    d1, d2, r = p1 - p0, q1 - q0, p0 - q0; a, ee, f = d1 @ d1, d2 @ d2, d2 @ r
    if a < 1e-12 and ee < 1e-12: return float(np.linalg.norm(r))
    if a < 1e-12: s, t = 0., np.clip(f / ee, 0, 1)
    else:
        c = d1 @ r
        if ee < 1e-12: t, s = 0., np.clip(-c / a, 0, 1)
        else:
            b = d1 @ d2; den = a * ee - b * b
            s = np.clip((b * f - c * ee) / den, 0, 1) if den > 1e-12 else 0.
            t = (b * s + f) / ee
            if t < 0: t, s = 0., np.clip(-c / a, 0, 1)
            elif t > 1: t, s = 1., np.clip((b - c) / a, 0, 1)
    return float(np.linalg.norm((p0 + d1 * s) - (q0 + d2 * t)))
PAIRS = [('torso', f'{s}_{p}') for s in ('left', 'right') for p in ('fore', 'hand')] + [(f'left_{a}', f'right_{b}') for a in ('upper', 'fore', 'hand') for b in ('upper', 'fore', 'hand')]
def gap(q):
    D.qpos[:] = q; mujoco.mj_kinematics(M, D)
    X = lambda n: D.xpos[ids[n]]
    sh = {s: X(f'{s}_shoulder_roll_link').copy() for s in ('left', 'right')}
    c = {'torso': (X('pelvis').copy(), (sh['left'] + sh['right']) / 2, RT)}
    for s in ('left', 'right'):
        E, W = X(f'{s}_elbow_link').copy(), X(f'{s}_wrist_pitch_link').copy()
        Pm = X(f'{s}_wrist_yaw_link').copy(); Rm = D.xmat[ids[f'{s}_wrist_yaw_link']].reshape(3, 3)
        c[f'{s}_upper'] = (sh[s], E, RU); c[f'{s}_fore'] = (E, W, RF); c[f'{s}_hand'] = (W, Pm + Rm @ np.array([.09, 0, 0]), RH)
    best = (1e9, None)
    for a, b in PAIRS:
        d = sd(c[a][0], c[a][1], c[b][0], c[b][1]) - c[a][2] - c[b][2]
        if d < best[0]: best = (d, f'{a}|{b}')
    return best
for f in sys.argv[2:]:
    z = np.load(f); Q = z['qpos']; T = z['t']
    g = [gap(q) for q in Q]; d = np.array([x[0] for x in g]) * 1000
    names = [mujoco.mj_id2name(M, mujoco.mjtObj.mjOBJ_JOINT, j) for j in range(M.njnt)]
    arm = [j for j, n in enumerate(names) if n and ('shoulder' in n or 'elbow' in n)]
    qa = np.array([Q[:, M.jnt_qposadr[j]] for j in arm]).T
    rng = np.degrees(qa.max(0) - qa.min(0)); half = len(Q) // 2
    rng2 = np.degrees(qa[half:].max(0) - qa[half:].min(0))
    tv2 = float(np.degrees(np.abs(np.diff(qa[half:], axis=0)).sum(0)).max())
    i = int(d.argmin())
    print(json.dumps(dict(file=os.path.basename(f), n=len(d), min_mm=round(float(d.min()), 2), argmin_t=round(float(T[i]), 2), pair=g[i][1], below0=int((d < 0).sum()), below5=int((d < 5).sum()),
                          arm_range_max_deg=round(float(rng.max()), 1), arm_range_2nd_half_deg=round(float(rng2.max()), 1), path_len_2nd_half_deg=round(tv2, 1))))
