"""V2 freeze on TUNING ONLY; never opens eval output."""
import json,time,hashlib
from pathlib import Path
R=Path('bench/g1');s=json.loads((R/'tune_diagnosis_single_corrected.json').read_text());m=json.loads((R/'tune_span_corrected.json').read_text());v=json.loads(Path('config/vocab_ko_en.yaml').read_text())['phrases']
def iou(a,b):
 x=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]));return x/max(1e-9,(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-x)
def valid(rows,th):return [d for d in rows if d['score']>=th and (d['box'][2]-d['box'][0])*(d['box'][3]-d['box'][1])/(640*480)<=.04]
single={(r['seed'],r['keys'][0]):r for r in s['records'] if r['style']=='color'};multi={r['seed']:r for r in m['records']};out=[]
for mode in ('a_single','b_span_min','c_agreement'):
 for th in (.35,.45,.55):
  n=ok=absent=absent_ok=wrong=dup_n=dup_ok=nodet=0;lat=[]
  for seed in range(1000,1020):
   mr=multi[seed];targets=mr['targets']
   for cls in v:
    gt=[t for t in targets if t['class_id']==cls];aa=valid(single[seed,cls]['candidates'],th);bb=valid([d for d in mr['candidates']['span_min'] if d['class_id']==cls],th);pa=max(aa,key=lambda d:d['score']) if aa else None;pb=max(bb,key=lambda d:d['score']) if bb else None
    picked=pa if mode=='a_single' else pb if mode=='b_span_min' else pa if pa and any(iou(pa['box'],d['box'])>=.5 for d in bb) else None
    ms=single[seed,cls]['ms'] if mode=='a_single' else mr['ms'] if mode=='b_span_min' else single[seed,cls]['ms']+mr['ms']
    if not gt:absent+=1;absent_ok+=picked is None
    for target in gt:
     n+=1;success=picked is not None and iou(picked['box'],target['box'])>=.5;ok+=success;nodet+=picked is None;wrong+=picked is not None and not success;lat.append(ms)
     if len(gt)>1:dup_n+=1;dup_ok+=success
  out.append(dict(mode=mode,threshold=th,n=n,correct=ok,accuracy=ok/n,no_detection=nodet,wrong_present=wrong,absent_n=absent,absent_correct=absent_ok,absent_specificity=absent_ok/absent,wrong_total=wrong+absent-absent_ok,duplicate_n=dup_n,duplicate_correct=dup_ok,duplicate_color_distinguishable=False,mean_model_ms=sum(lat)/len(lat)))
best=min(out,key=lambda x:(x['wrong_total'],-x['accuracy'],x['mean_model_ms']))
freeze=dict(source='[시뮬인식]',gt_assist=False,split='tuning',frozen_at=time.time(),revision=2,prior_freeze_sha256=json.loads((R/'selection_freeze.json').read_text())['sha256'],rule='minimize wrong_present + absent_false_selection; tie maximize present accuracy, then latency',selected=best,comparisons=out,width=640,height=480,area_cap=.04,text_threshold=.25,model_revision='a2bb814dd30d776dcf7e30523b00659f4f141c71',eval_status_at_freeze='old a/b raw prediction collection already running, results never inspected; v2 scored only after this freeze',dataset_rule='same one-shot raw predictions, no reinference; cached scores>=.35 can apply frozen .35/.45/.55 policies',eval_methods={x:best['threshold'] if best['mode']==x else .35 for x in ('a_single','b_span_min','c_agreement')})
freeze['sha256']=hashlib.sha256(json.dumps(freeze,sort_keys=True).encode()).hexdigest();(R/'selection_freeze_v2.json').write_text(json.dumps(freeze,indent=2));print(json.dumps(freeze,indent=2))
