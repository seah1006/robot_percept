"""Summarize tuning diagnostics only; no model execution."""
import json
from pathlib import Path
import numpy as np
summary={}
for file in Path('bench/g1').glob('tune_diagnosis_*.json'):
 data=json.loads(file.read_text()); groups={}
 for r in data['records']:
  key=f"{r['width']}x{r['height']}/{r['style']}"; g=groups.setdefault(key,dict(targets=0,hit_iou50_any=0,hit_iou25_any=0,hit_iou50_exact=0,hit_iou50_loose=0,matched_below_threshold=0,exact_label_loss=0,ms=[],area=[],pixel_width=[],pixel_height=[],per_class={}))
  g['ms'].append(r['ms'])
  if len(r['keys'])>1:
   for t in r['targets']:
    g['area'].append(t['area_ratio']);g['pixel_width'].append(t['pixel_width']);g['pixel_height'].append(t['pixel_height'])
  for s in r['scored']:
   g['targets']+=1; c=g['per_class'].setdefault(s['class_id'],dict(gt=0,tp_exact=0,tp_any=0,best_scores=[]));c['gt']+=1
   for field in ['iou50_any','iou25_any','iou50_exact','iou50_loose']:
    score=s['score_'+field]
    if score is not None and score>=.35:g['hit_'+field]+=1
   if s['score_iou50_any'] is not None:
    c['best_scores'].append(s['score_iou50_any'])
    if s['score_iou50_any']>=.35: c['tp_any']+=1
    if s['score_iou50_any']<.35: g['matched_below_threshold']+=1
    if s['score_iou50_any']>=.35 and (s['score_iou50_exact'] is None or s['score_iou50_exact']<.35):g['exact_label_loss']+=1
   if s['score_iou50_exact'] is not None and s['score_iou50_exact']>=.35:c['tp_exact']+=1
 for g in groups.values():
  for name in ['ms','area','pixel_width','pixel_height']:
   values=g.pop(name)
   g[name+'_distribution']={k:float(v) for k,v in zip(['min','p50','p95','p99','max'],np.percentile(values,[0,50,95,99,100]))} if values else None
  for c in g['per_class'].values():
   scores=c.pop('best_scores');c['matched_score_distribution']={k:float(v) for k,v in zip(['min','p50','p95','max'],np.percentile(scores,[0,50,95,100]))} if scores else None
 summary[file.name]=dict(groups=groups,records=len(data['records']),elapsed_s=data['elapsed_s'],device_used_peak_sampled_mib=data['device_used_peak_sampled_mib'])
Path('bench/g1/tune_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
