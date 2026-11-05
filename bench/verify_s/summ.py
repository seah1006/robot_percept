import json, sys
o = json.load(open('/home/user/work/robot_percept/bench/verify_s/out_%s.json' % sys.argv[1]))
for k, v in o.items():
    if k == 'static':
        print('static', {a: b for a, b in v.items() if a != 'rows'})
        for r in v['rows']:
            if max(r['left']['u1_deg'], r['left']['u2_deg'], r['right']['u1_deg'], r['right']['u2_deg']) > 3: print('  >3deg', r['pose'], r['left'], r['right'])
    elif k == 'asym':
        print('asym', {a: b for a, b in v.items() if a != 'rows'})
        for r in v['rows']:
            if max(r['as_first'][:2] + r['as_other'][:2]) > 3 or r['lr_diff_deg'] > 3: print('  >3', r)
    else: print(k, json.dumps(v, default=str)[:1500])
