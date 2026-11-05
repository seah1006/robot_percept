"""compare recorded JSONL v2 vs collector capture of replay (and of the live run)."""
import sys, json
rec = [json.loads(l) for l in open(sys.argv[1])]
def load(p, path):
    return [json.loads(l)['body'] for l in open(p) if json.loads(l)['path'] == path]
def strip(d):
    d = dict(d) if d else d
    if d:
        for k in ('sent_at', 'capture_at'): d.pop(k, None)
    return d
route = sys.argv[3]; key = 'humanoid' if route == '/humanoid/update' else 'features'
rep = load(sys.argv[2], route)
exp = [strip(r[key]) for r in rec if r.get(key) is not None]
print('schema', {r.get('schema') for r in rec}, 'rec_rows', len(rec), 'expected', len(exp), 'replayed', len(rep))
n = min(len(exp), len(rep)); bad = 0; first = None
for i in range(n):
    a = json.dumps(exp[i], sort_keys=True); b = json.dumps({k: v for k, v in strip(rep[i]).items() if k != 'seq'} if 'seq' not in exp[i] else strip(rep[i]), sort_keys=True)
    ea = {k: v for k, v in exp[i].items() if k != 'seq'}; eb = {k: v for k, v in strip(rep[i]).items() if k != 'seq'}
    if json.dumps(ea, sort_keys=True) != json.dumps(eb, sort_keys=True):
        bad += 1; first = first if first is not None else i
seqok = sum(1 for i in range(n) if rep[i].get('seq') == rec[i].get('seq')) if len(rec) == len(exp) else -1
print('compared', n, 'mismatch', bad, 'first_mismatch', first, 'seq_equal', seqok, 'capture_at present', sum('capture_at' in r for r in rep))
q = [r.get('quality') for r in rep if r.get('quality')]
print('quality frames', len(q), 'hand states', {(s, v.get('state')) for r in q for s, v in r.get('hands', {}).items()})
