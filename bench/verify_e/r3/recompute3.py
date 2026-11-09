#!/usr/bin/env python3
"""V-E3 independent recompute from raw trials.jsonl (pred/gt 4x4 per frame). Does NOT import eval.*.
usage: recompute3.py TRIALS.jsonl [planned_N_per_group]
Success per trial = all `frames` requested frames present AND each frame passes:
 mustard ADD<=0.1d ; box ADD-S<=0.1d ; cup ADD-S<=0.1d and min-over-yaw(z) rotation<=20deg.
Denominator = planned N (if given) else rows; rows missing for a planned seed count as failure."""
import sys, json, math, collections, numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.distance import pdist
R = '/home/user/work/robot_percept/'
MESH = {'mustard': R + 'downloads/demo_data/mustard0/mesh/textured_simple.obj',
        'box': R + 'cad_uploads/converted/box_fillet_50x30x20mm/box_fillet_50x30x20mm.obj',
        'cup': R + 'cad_uploads/converted/cup_d70_h60mm/cup_d70_h60mm.obj'}
def verts(p): return np.array([[float(x) for x in l.split()[1:4]] for l in open(p) if l.startswith('v ')])
V = {k: verts(p) for k, p in MESH.items()}
from scipy.spatial import ConvexHull
DIA = {k: pdist(v[ConvexHull(v).vertices]).max() * 1000 for k, v in V.items()}
def tf(T, v): T = np.asarray(T); return v @ T[:3, :3].T + T[:3, 3]
def wilson(k, n, z=1.959963984540054):
    if n == 0: return (0., 1.)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)
def yaw_rot(p, g):
    Rr = np.asarray(g)[:3, :3].T @ np.asarray(p)[:3, :3]   # in object frame
    best = 1e9
    for a in np.linspace(0, 2 * math.pi, 3600, endpoint=False):
        c, s = math.cos(a), math.sin(a); Z = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
        M = Rr @ Z; best = min(best, math.degrees(math.acos(max(-1, min(1, (np.trace(M) - 1) / 2)))))
    return best
def frame_ok(obj, p, g):
    v = V[obj]; a, b = tf(p, v), tf(g, v)
    if obj == 'mustard': e = np.linalg.norm(a - b, axis=1).mean() * 1000
    else: e = cKDTree(b).query(a)[0].mean() * 1000
    ok = e <= .1 * DIA[obj]
    if obj == 'cup': ok = ok and yaw_rot(p, g) <= 20
    return bool(ok), e
if __name__ == '__main__':
    rows = [json.loads(l) for l in open(sys.argv[1])]
    plan = int(sys.argv[2]) if len(sys.argv) > 2 else None
    g = collections.defaultdict(list); mism = 0; fr_tot = 0; fr_ok = 0; maxd = 0
    for r in rows:
        if r.get('failure_reasons') and r['failure_reasons'] == ['missing_trial']: g[(r['object'], r['config']['perception'], r['config']['gt_assist'])].append(False); continue
        nf = r['config']['frames']; oks = []
        for f in r['frames']:
            ok, e = frame_ok(r['object'], f['pred'], f['gt']); oks.append(ok); fr_tot += 1; fr_ok += ok
            crit = f.get('adds_mm') if r['object'] != 'mustard' else f.get('add_mm')
            if crit is not None: maxd = max(maxd, abs(crit - e))
            if bool(f.get('success')) != ok: mism += 1
        s = len(oks) == nf and all(oks)
        if bool(r['success']) != s: mism += 1
        g[(r['object'], r['config']['perception'], r['config']['gt_assist'])].append(s)
    print('diam_mm', {k: round(v, 2) for k, v in DIA.items()})
    for k, v in sorted(g.items()):
        n = plan or len(v); kk = sum(v)
        print(k, f'k={kk} rows={len(v)} denom={n}', 'wilson', tuple(round(x, 3) for x in wilson(kk, n)))
    print(f'frames ok {fr_ok}/{fr_tot}; success-flag mismatches vs report: {mism}; max |metric diff| mm: {maxd:.2e}')
