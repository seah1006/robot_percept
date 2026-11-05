import json, numpy as np, sys
base = '/home/user/work/robot_percept/bench/verify_s/out_%s.json'
for pat in ('chest', 'jump', 'twist'):
    for o in ('0', '1'):
        d = json.load(open(base % ('cand8x_' + pat)))
        raw = d['coll_raw_' + o]; st = d['coll_status_' + o]
        names = [k for k in raw[0][1] if 'shoulder' in k or 'elbow' in k]
        Q = np.array([[r[1][n] for n in names] for r in raw])
        rng = np.degrees(Q.max(0) - Q.min(0))
        print(pat, 'avoid=' + o, 'joint range deg (shoulder/elbow, 14 joints) max %.1f mean %.1f' % (rng.max(), rng.mean()), 'q std deg mean %.1f' % np.degrees(Q.std(0)).mean(), 'status', json.dumps(st)[:220])
