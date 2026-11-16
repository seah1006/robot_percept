"""V-G1 독립 감사: sealed 원시 예측(parts) 해시/시각 대조 + 자체 구현 채점 + GT 박스 독립 재렌더 대조. 추론 없음."""
import sys, os, json, hashlib, math
sys.path.insert(0, '/home/user/work/robot_percept')
import numpy as np
R = '/home/user/work/robot_percept/bench/g1/'
out = {}
# 1) 해시 대조
man = json.load(open(R + 'sealed_hash_final.json')); ini = json.load(open(R + 'sealed_hash_initial.json'))
hs = {}
for f in man['files']:
    b = open(R + f['file'], 'rb').read(); hs[f['file']] = dict(bytes=len(b), sha_ok=hashlib.sha256(b).hexdigest() == f['sha256'], size_ok=len(b) == f['bytes'], mtime=os.path.getmtime(R + f['file']))
out['hash_final_vs_now'] = hs
out['initial_part0_match'] = [x['sha256'] for x in ini['files'] if x['file'].endswith('part0.json')][0] == [x['sha256'] for x in man['files'] if x['file'].endswith('part0.json')][0]
fr = {k: os.path.getmtime(R + k) for k in ('selection_freeze.json', 'selection_freeze_v2.json', 'selection_freeze_v2r.json', 'selection_eval_v2r_summary.json', 'sealed_hash_final.json')}
out['mtimes'] = fr
out['v2r_frozen_at'] = man['v2r_frozen_at']; out['hashed_at'] = man['hashed_at']
summ = json.load(open(R + 'selection_eval_v2r_summary.json')); out['first_parse_at'] = summ['first_outcome_parse_at']
out['order_ok'] = man['v2r_frozen_at'] < man['hashed_at'] <= summ['first_outcome_parse_at']
out['parts_mtime_before_v2r_freeze'] = {k: v['mtime'] < man['v2r_frozen_at'] for k, v in hs.items()}
# 2) 자체 채점
recs = []
for i in range(4):
    d = json.load(open(R + 'selection_eval_part%d.json' % i)); recs += d['records']
    out.setdefault('part_meta', []).append(dict(part=i, n=len(d['records']), peak_mib=d['device_used_peak_sampled_mib'], proc_max_alloc=d['process_max_allocated_mib'], elapsed_s=d['elapsed_s'], load=[d['load_start'], d['load_end']]))
assert sorted(r['seed'] for r in recs) == list(range(100000, 100100))
def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1])); i = ix * iy
    u = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - i
    return i / u if u > 0 else 0.0
def wilson(k, n, z=1.959963984540054):
    p = k / n; d = 1 + z*z/n; c = (p + z*z/(2*n)) / d; h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d; return [round(c-h, 4), round(c+h, 4)]
vocab = list(json.loads(open('/home/user/work/robot_percept/config/vocab_ko_en.yaml').read())['phrases'])
def score(mode, th, rs):
    tot = ok = nodet = wrong = absn = absok = 0; ms = []
    for r in rs:
        for cls in vocab:
            c = [p for p in r['predictions'][f'{mode}/{cls}'] if p['score'] >= th]
            pick = max(c, key=lambda p: p['score']) if c else None
            ts = [t for t in r['targets'] if t['class_id'] == cls]
            if not ts:
                absn += 1; absok += pick is None; continue
            for t in ts:
                tot += 1
                good = pick is not None and t['box'] is not None and iou(pick['box'], t['box']) >= .5
                ok += good; nodet += pick is None; wrong += (pick is not None and not good)
        ms += [t['ms'] for t in r['tasks'] if t['mode'] == mode]
    return dict(correct=ok, n=tot, acc=round(ok/tot, 4), wilson=wilson(ok, tot), no_det=nodet, wrong_present=wrong, absent=f'{absok}/{absn}', absent_spec=round(absok/absn, 4), absent_wilson=wilson(absok, absn), task_ms_mean=round(float(np.mean(ms)), 1), task_ms_p50=round(float(np.percentile(ms, 50)), 1))
out['score'] = {}
for grp, rs in (('include_all_100', recs), ('exclude_preseen_10', [r for r in recs if r['seed'] >= 100010])):
    out['score'][grp] = {'v1_a_single_.35': score('a_single', .35, rs), 'v2r_b_span_min_.35': score('b_span_min', .35, rs)}
# 요약과 대조
for grp in ('include_all_100', 'exclude_preseen_10'):
    g = summ['groups'][grp]
    out['score'][grp]['summary_says'] = {k: [v['selection']['correct'], v['selection']['n'], v['absent_specificity']['correct'], v['absent_specificity']['n']] for k, v in g.items()}
out['target_box_none'] = sum(1 for r in recs for t in r['targets'] if t['box'] is None)
out['duplicate_targets'] = sum(1 for r in recs for t in r['targets'] if sum(1 for u in r['targets'] if u['class_id'] == t['class_id']) > 1)
# 3) GT 독립 재렌더 대조
import mujoco
from sim.cell_scene_eval import open_evaluation_scene
mism = 0; checked = 0; maxdiff = 0
for r in recs[:100]:
    es = open_evaluation_scene(r['seed'], 640, 480); es.rgb(); w = es._world
    w.model.vis.quality.offsamples = 0; rr = mujoco.Renderer(w.model, 480, 640); opt = mujoco.MjvOption(); opt.geomgroup[3] = 0
    rr.enable_segmentation_rendering(); rr.update_scene(w.data, camera='front', scene_option=opt); seg = rr.render().copy(); rr.close()
    gid, typ = seg[..., 0], seg[..., 1]
    for t in r['targets']:
        bid = w.model.body(t['instance_id']).id; geoms = [g for g in range(w.model.ngeom) if w.model.geom_bodyid[g] == bid]
        m = np.isin(gid, geoms) & (typ == int(mujoco.mjtObj.mjOBJ_GEOM))
        mine = None
        if m.any():
            ys, xs = np.where(m); mine = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
        checked += 1
        if (mine is None) != (t['box'] is None): mism += 1
        elif mine is not None:
            d = max(abs(a - b) for a, b in zip(mine, t['box'])); maxdiff = max(maxdiff, d); mism += d > 1
    es.close()
out['gt_recheck'] = dict(checked=checked, mismatches_gt1px=mism, max_abs_diff_px=maxdiff)
json.dump(out, open('/home/user/work/robot_percept/bench/verify_g1/audit_eval100.json', 'w'), indent=1, ensure_ascii=False, default=str)
print(json.dumps(out, ensure_ascii=False, default=str)[:6000])
