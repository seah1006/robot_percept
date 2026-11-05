import glob, json, numpy as np, sys
d = '/home/user/work/robot_percept/bench/humanoid_s_out/'
pre = sorted(glob.glob(d + '*_off_control_30hz.npz'))[-1].replace('off_control_30hz.npz', '')
print('prefix', pre)
off = np.load(pre + 'off_control_30hz.npz', allow_pickle=True)
print('keys', list(off.keys()))
names = [str(x) for x in off['names']]; vmax = off['vmax']; amax = off['amax']
# CAP used by me (unscaled): arm 3/25, wrist 4/30, waist 1.2/8, hand 3/30 ; compare with file's vmax/amax
def cap(n): return (1.2, 8.) if n.startswith('waist') else (3., 30.) if '_hand_' in n else (4., 30.) if 'wrist' in n else (3., 25.)
mine_a = np.array([cap(n)[1] for n in names]); mine_v = np.array([cap(n)[0] for n in names])
print('amax match', np.allclose(mine_a, amax), 'vmax match', np.allclose(mine_v, vmax))
t = off['t']; dt = np.median(np.diff(t)); print('dt', dt, 'n', len(t))
def acc(z):   # my own accel: central difference of qd (independent of qdd_fd)
    qd = z['qd']; a = np.zeros_like(qd); a[1:] = np.diff(qd, axis=0) / np.diff(z['t'])[:, None]; return a
def ratio(a): return np.abs(a) / amax
oa = acc(off)
res = {}
for tt in (0.3, 0.6, 0.9, 1.2):
    for r in (0, 1):
        z = np.load(pre + 'off_to_on_t%s_r%d.npz' % (tt, r), allow_pickle=True)
        a = acc(z); tz = z['t']
        meta = z['meta'] if 'meta' in z else None
        s = np.searchsorted(tz, tt); e40 = np.searchsorted(tz, tt + .04)
        first = ratio(a[s:e40]); after = ratio(a[e40:])
        offs = ratio(oa[s:e40]); j = np.unravel_index(np.argmax(first), first.shape)[1]
        vpost = np.abs(z['qd'][s:]) / vmax
        res[(tt, r)] = dict(first40_max=round(float(first.max()), 3), joint=names[j], off_same_joint_first40=round(float(offs[:, j].max()), 3), after40_max=round(float(after.max()), 3),
                            vmax_post=round(float(vpost.max()), 3), vmax_post_envelope_last=round(float(vpost[-50:].max()), 3))
        print(tt, r, res[(tt, r)])
print('all after40<=1:', all(v['after40_max'] <= 1.0 for v in res.values()), ' all first40<=off same joint:', all(v['first40_max'] <= v['off_same_joint_first40'] for v in res.values()))
