raise SystemExit('SEALED: parent requested no eval result inspection pending v2 policy freeze')
import json,math
from pathlib import Path
import numpy as np
R=Path('bench/g1');freeze=json.loads((R/'selection_freeze.json').read_text());records=[]
for p in sorted(R.glob('selection_eval_part*.json')):
 d=json.loads(p.read_text());assert d['freeze_sha256']==freeze['sha256'];records+=d['records']
seeds=[r['seed'] for r in records];assert len(seeds)==len(set(seeds))
def wilson(k,n):
 if not n:return None
 z=1.959963984540054;p=k/n;den=1+z*z/n;center=(p+z*z/(2*n))/den;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den;return [center-half,center+half]
def proportion(k,n):return dict(correct=k,n=n,estimate=k/n if n else None,wilson95=wilson(k,n))
summary=dict(source='[시뮬인식]',gt_assist=False,identity_assist=False,freeze=freeze,scene_count=len(records),complete=len(records)==100 and set(seeds)==set(range(100000,100100)),groups={},ci_note='Wilson binomial intervals are descriptive; instructions within a scene are correlated, no cluster-adjusted interval claimed.',GT='offsamples0 evaluation-only masks; original MSAA4 inference RGB',latency_note='per-instruction full query latency, multi-pass not amortized over targets; identical queries reused for duplicate targets')
for exclusion in (False,True):
 rs=[r for r in records if not exclusion or r['seed']>=100010];group={}
 for mode in ('a_single','b_span_min'):
  tasks=[t for r in rs for t in r['tasks'] if t['mode']==mode];absent=[t for r in rs for t in r['absent'] if t['mode']==mode];duplicates=[t for t in tasks if t['duplicate_same_color']];tp=sum(r['aux'][mode]['tp'] for r in rs);fp=sum(r['aux'][mode]['fp'] for r in rs);gt=sum(r['aux'][mode]['gt'] for r in rs);ms=[t['ms'] for t in tasks]
  group[mode]=dict(selection=proportion(sum(t['correct'] for t in tasks),len(tasks)),no_detection=sum(t['status']=='NO_DETECTION' for t in tasks),absent_specificity=proportion(sum(t['correct'] for t in absent),len(absent)),duplicates_same_color=proportion(sum(t['correct'] for t in duplicates),len(duplicates)),duplicate_color_distinguishable_n=0,latency_ms=dict(mean=float(np.mean(ms)),p50=float(np.percentile(ms,50)),p95=float(np.percentile(ms,95))) if ms else None,aux_detection=dict(gt=gt,tp=tp,fp=fp,recall=tp/gt if gt else None,precision=tp/(tp+fp) if tp+fp else None))
 summary['groups']['exclude_preseen_10' if exclusion else 'include_all_100']=group
(R/'selection_eval_summary.json').write_text(json.dumps(summary,indent=2))
lines=['\n## Frozen eval100 Grounding selection accuracy','[시뮬인식], GT 보조 없음. GT-only offsamples0.','Complete='+str(summary['complete'])+', scenes='+str(len(records)), 'Frozen selected method: '+freeze['selected']['mode']+' threshold='+str(freeze['selected']['threshold'])]
for name,group in summary['groups'].items():
 for mode,d in group.items():
  x=d['selection'];ci=x['wilson95'];lines.append(f"- {name}/{mode}: {x['correct']}/{x['n']}={x['estimate']:.4f}, Wilson95%=[{ci[0]:.4f},{ci[1]:.4f}], latency p50/p95={d['latency_ms']['p50']:.1f}/{d['latency_ms']['p95']:.1f}ms, absent correct={d['absent_specificity']['correct']}/{d['absent_specificity']['n']}, duplicates={d['duplicates_same_color']['correct']}/{d['duplicates_same_color']['n']}, auxiliary recall/precision={d['aux_detection']['recall']:.4f}/{d['aux_detection']['precision']:.4f}")
lines+=['- Same-class duplicates have identical catalog colors and phrases; color cannot distinguish them. No GT instance tie-break was supplied.','- Wilson intervals are instruction-level descriptive intervals; same-scene correlation is not adjusted. No fixed pass threshold is claimed.','- Gallery: bench/g1/gallery/*.png, GT green / selected red; evaluation overlays never enter model input.']
with Path('notes/g1_results.md').open('a') as f:f.write('\n'.join(lines)+'\n')
with Path('notes/g1_changes.md').open('a') as f:f.write('\n## Selection eval resume\n- Summary generated: bench/g1/selection_eval_summary.json; complete='+str(summary['complete'])+' scenes='+str(len(records))+'; independent V-G1 validation remains.\n')
print('\n'.join(lines))
