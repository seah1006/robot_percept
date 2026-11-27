"""Why do O3 runs end in FALSE_COMPLETION (wrong missing report)? usage: python -m m2a.run.diag_missing runs/<id>  (reads result.json)."""
import json, sys
from collections import Counter
from m2a.common import load_layout
from m2a.scene.generator import generate
layout = load_layout()
d = json.load(open(sys.argv[1] + '/result.json'))
c = Counter()
for e in d['episodes']:
    if e['config'] != 'B1' or e['fail_code'] != 'FALSE_COMPLETION':
        continue
    spec = generate(e['seed'], e['level'], e['situation'], 'dev', layout=layout)
    need = list(e['goal']['trays'].values())[0]
    pid = next(iter(need))
    objs = {o['oid']: o for o in spec['objects']}
    cand = [o for o in objs.values() if o['part_id'] == pid]
    p = e['percept']
    for o in cand:
        why = 'missed' if o['oid'] in p['initial_missed_gt'] else 'seen'
        print(e['seed'], pid, o['oid'], why, o['region'], o['in_tray'], [round(v, 2) for v in o['xyz']] if 'xyz' in o else '', 'wrong_part_preds', p['initial_wrong_part'])
        c[(why, o['region'])] += 1
print(c)
