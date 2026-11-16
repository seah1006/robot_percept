"""One permitted unsealing after v2 freeze; never re-runs inference or tunes."""
import json,math,time,hashlib
from pathlib import Path
import numpy as np
R=Path('bench/g1');v1=json.loads((R/'selection_freeze.json').read_text());v2=json.loads((R/'selection_freeze_v2.json').read_text());output=R/'selection_eval_v2_summary.json'
if output.exists():raise RuntimeError('One-shot v2 score already exists; refuse repeat')
parts=[R/f'selection_eval_part{i}.json' for i in range(4)]
if not all(p.exists() for p in parts):raise RuntimeError('Missing sealed part')
# Hash ALL raw files before the first semantic parse of any eval result.
manifest=dict(hashed_at=time.time(),v1_sha256=v1['sha256'],v2_sha256=v2['sha256'],v2_frozen_at=v2['frozen_at'],files=[dict(file=p.name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in parts])
(R/'sealed_hash_final.json').write_text(json.dumps(manifest,indent=2));opened=time.time()
with Path('notes/g1_changes.md').open('a') as f:f.write('\n6. final sealed raw SHA256 manifest saved BEFORE outcome parsing: bench/g1/sealed_hash_final.json; first outcome parse timestamp='+str(opened)+'; v2 freeze timestamp='+str(v2['frozen_at'])+'; v2 hash='+v2['sha256']+'\n')
records=[]
for p in parts:
 d=json.loads(p.read_text());assert d['freeze_sha256']==v1['sha256'];assert len(d['records'])==25;records+=d['records']
assert {r['seed'] for r in records}==set(range(100000,100100)) and len(records)==100

def iou(a,b):
 x=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]));return x/max(1e-9,(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-x)
def wilson(k,n):
 if not n:return None
 z=1.959963984540054;p=k/n;den=1+z*z/n;center=(p+z*z/(2*n))/den;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den;return [center-half,center+half]
def stat(k,n):return dict(correct=k,n=n,estimate=k/n if n else None,wilson95=wilson(k,n))
def rows(r,mode,cls,th):
 aa=[x for x in r['predictions']['a_single/'+cls] if x['score']>=th];bb=[x for x in r['predictions']['b_span_min/'+cls] if x['score']>=th]
 if mode=='a_single':return aa
 if mode=='b_span_min':return bb
 pa=max(aa,key=lambda d:d['score']) if aa else None
 return [pa] if pa and any(iou(pa['box'],b['box'])>=.5 for b in bb) else []
policies={'v1_a_pre_collection':('a_single',.35),'v2_result_blind_freeze':(v2['selected']['mode'],v2['selected']['threshold']),'c_agreement_at_.35_comparator':('c_agreement',.35)};groups={};keys=list(json.loads(Path('config/vocab_ko_en.yaml').read_text())['phrases'])
for exclude in (False,True):
 rs=[r for r in records if not exclude or r['seed']>=100010];group={}
 for name,(mode,th) in policies.items():
  n=ok=nodet=wrong=absn=absok=dupn=dupok=tp=fp=gtcount=0;ms=[]
  for r in rs:
   targets=r['targets'];gtcount+=len(targets);allrows=[]
   latency={(t['mode'],t['class_id']):t['ms'] for t in r['tasks']}
   for cls in keys:
    rr=rows(r,mode,cls,th);allrows+=rr;picked=max(rr,key=lambda x:x['score']) if rr else None;ts=[t for t in targets if t['class_id']==cls]
    if not ts:absn+=1;absok+=picked is None
    for t in ts:
     correct=picked is not None and t['box'] is not None and iou(picked['box'],t['box'])>=.5;n+=1;ok+=correct;nodet+=picked is None;wrong+=picked is not None and not correct
     # Query latency exists only for present classes; c is sum of both passes.
     ms.append(latency.get(('a_single',cls),0)+latency.get(('b_span_min',cls),0) if mode=='c_agreement' else latency[mode,cls])
     if len(ts)>1:dupn+=1;dupok+=correct
   matched=set()
   for d in sorted(allrows,key=lambda x:-x['score']):
    matches=[(iou(d['box'],t['box']),i) for i,t in enumerate(targets) if i not in matched and t['box'] is not None and t['class_id']==d['class_id']]
    if matches and max(matches)[0]>=.5:matched.add(max(matches)[1]);tp+=1
    else:fp+=1
  group[name]=dict(mode=mode,threshold=th,selection=stat(ok,n),wrong_present=wrong,no_detection=nodet,absent_specificity=stat(absok,absn),wrong_total=wrong+absn-absok,duplicate_same_color=stat(dupok,dupn),duplicate_color_distinguishable_n=0,latency_ms=dict(mean=float(np.mean(ms)),p50=float(np.percentile(ms,50)),p95=float(np.percentile(ms,95))),aux_detection=dict(gt=gtcount,tp=tp,fp=fp,recall=tp/gtcount,precision=tp/(tp+fp) if tp+fp else None))
 groups['exclude_preseen_10' if exclude else 'include_all_100']=group
summary=dict(source='[시뮬인식]',gt_assist=False,identity_assist=False,complete=True,scenes=100,first_outcome_parse_at=opened,v1=v1,v2=v2,raw_manifest=manifest,groups=groups,ci_note='Instruction-level Wilson descriptive CI; same-scene correlation not adjusted.',chronology='v1 frozen before collection; v2 frozen after collection began but before ANY outcome inspection; same sealed predictions scored once, no repeated inference')
output.write_text(json.dumps(summary,indent=2));lines=['\n## Final one-shot selection eval100 (v1 / result-blind v2)','[시뮬인식], GT 보조 없음, GT-only offsamples0.','v1 frozen pre-collection; v2 frozen after collection started, before outcome inspection. Raw prediction hashes sealed_hash_final.json.']
for group,values in groups.items():
 for name,d in values.items():
  x=d['selection'];c=x['wilson95'];a=d['absent_specificity'];lines.append(f"- {group}/{name} ({d['mode']},threshold={d['threshold']}): selection{x['correct']}/{x['n']}={x['estimate']:.4f}, Wilson95[{c[0]:.4f},{c[1]:.4f}]; absent correct{a['correct']}/{a['n']}={a['estimate']:.4f}; wrong_total={d['wrong_total']}; NO_DETECTION={d['no_detection']}; p50/p95={d['latency_ms']['p50']:.1f}/{d['latency_ms']['p95']:.1f}ms; aux recall/precision={d['aux_detection']['recall']:.4f}/{d['aux_detection']['precision'] if d['aux_detection']['precision'] is not None else 'null'}")
lines+=['- Same-class duplicate instances use identical catalog colors/phrases; not color-distinguishable. Separate counts in JSON.','- No fixed success cutoff. Wilson intervals are descriptive; same-scene correlation not adjusted.','- Gallery PNGs are v1 scoring overlays collected without inspection; never used as model input.']
with Path('notes/g1_results.md').open('a') as f:f.write('\n'.join(lines)+'\n')
with Path('notes/g1_changes.md').open('a') as f:f.write('\n7. One-shot v2 scorer completed; selection_eval_v2_summary.json and g1_results updated. Independent V-G1 audit still required.\n')
print('\n'.join(lines))
