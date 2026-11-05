import json, glob, math, collections
V = '/home/user/work/robot_percept/bench/verify_c/'
def wilson(k, n, z=1.96):
    if n == 0: return (0, 0)
    p = k / n; d = 1 + z*z/n
    c = (p + z*z/(2*n)) / d; h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return round(100*(c-h), 1), round(100*(c+h), 1)
def fmt(k, n): lo, hi = wilson(k, n); return f'{k}/{n} ({100*k/n:.0f}%, CI {lo}-{hi})'
# ---- off
single = collections.defaultdict(list); multi = []
for f in sorted(glob.glob(V+'d_off_single_*.json')):
    for k, v in json.load(open(f)).items():
        if k != 'gtcalls': single[k] += v
for f in sorted(glob.glob(V+'d_off_multi_*.json')):
    multi += json.load(open(f)).get('multi', [])
print('== gt_assist OFF')
def row(name, rows):
    n = len(rows); pk = sum(r['pick'] for r in rows); pl = sum(r.get('place', False) for r in rows)
    lift = sum(1 for r in rows if r['pick'] and (r.get('lifted') or -1) > .05)
    hm = sum(1 for r in rows if r.get('home_ok'))
    errs = [r['err_mm'] for r in rows if 'err_mm' in r]
    print(name, 'pick(ok)', fmt(pk, n), '| lift>5cm', fmt(lift, n), '| place', fmt(pl, n), '| home', fmt(hm, n), '| place err mm median', round(sorted(errs)[len(errs)//2], 1) if errs else None)
    fails = collections.Counter()
    for r in rows:
        if not r['pick']: fails['pick_fail' + (':' + r['error'][:40] if 'error' in r else '')] += 1
        elif (r.get('lifted') or -1) <= .05: fails['pick_ok_but_not_lifted(drop)'] += 1
        if r['pick'] and not r.get('place'): fails['place_fail(err>=20mm)'] += 1
    print('   fail types', dict(fails))
for k, rows in single.items(): row(k, rows)
for i, k in enumerate(('mustard', 'box', 'cup')): row('multi ' + k, [t[i] for t in multi])
print('multi all-three place', fmt(sum(all(r['pick'] and r.get('place') for r in t) for t in multi), len(multi)))
# ---- home obstacle
print('== home obstacle')
vs = collections.Counter(); skipped = 0
for f in sorted(glob.glob(V+'d_ho_*.json')):
    for r in json.load(open(f))['rows']:
        if 'skipped' in r: skipped += 1; continue
        vs[r['verdict']] += 1
        print(r.get('seed'), r.get('case') or (r['blocker'][:4], r['f']), r['verdict'], (r.get('err') or '')[:60], 'pen_mm', round(r.get('pen_mm', r.get('table_pen_mm', 0)), 2) if r.get('pen_mm', 0) is not None else '')
print(dict(vs), 'skipped(blocker overlapped at start)', skipped)
# ---- latency
for t in ('base', 'cur'):
    try: print('lat', t, json.load(open(V+f'd_lat_{t}.json')))
    except Exception as e: print('lat', t, 'missing')
