import json, sys, glob, os
os.chdir('/home/user/work/robot_percept/bench/verify_s')
for f in sorted(glob.glob('out_%s_*.json' % sys.argv[1])):
    d = json.load(open(f)); print('##', f, 'load1', d.get('load1'))
    if 'static' in d:
        s = d['static']; print(' static max_u1/u2/wrist/wristActualS/lr', s['max_u1'], s['max_u2'], s['max_wrist_mm'], s['max_wrist_mm_actualS'], s['max_lr_diff'], 'mean', s['mean_dir'])
        print('  worst poses', sorted(((max(r['left']['u1_deg'], r['left']['u2_deg'], r['right']['u1_deg'], r['right']['u2_deg']), r['pose'], r['gap_mm']) for r in s['rows']), reverse=True)[:4])
    if 'release' in d: print(' release', {k: v for k, v in d['release'].items() if k != 'series'})
    if 'asym' in d: print(' asym', {k: v for k, v in d['asym'].items() if k != 'rows'} if isinstance(d['asym'], dict) else d['asym'])
    for k in d:
        if k.startswith('coll_tick_'): print(' ', k, d[k])
        if k.startswith('coll_video_'): print(' ', k, d[k])
        if k in ('coll_1', 'coll_0'): print(' ', k, {a: d[k][a] for a in ('min_mm', 'frames_below_0mm', 'frames_below_5mm', 'n', 'pattern')})
        if k.startswith('coll_status_'): print(' ', k, d[k])
    for k in ('dynv', 'degen', 'p1b_v', 'speed'):
        if k in d: print(' ', k, json.dumps(d[k])[:900])
    print('  keys', [k for k in d if k not in ('coll_raw_0', 'coll_raw_1', 'static')])
