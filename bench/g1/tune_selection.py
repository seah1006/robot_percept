import json,time,hashlib
from pathlib import Path
R=Path('bench/g1');s=json.loads((R/'tune_diagnosis_single_corrected.json').read_text());m=json.loads((R/'tune_span_corrected.json').read_text());v=json.loads(Path('config/vocab_ko_en.yaml').read_text())['phrases']
def iou(a,b):
 x=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]));return x/max(1e-9,(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-x)
def choose(rows,th):
 rows=[d for d in rows if d['score']>=th and (d['box'][2]-d['box'][0])*(d['box'][3]-d['box'][1])/(640*480)<=.04];return max(rows,key=lambda d:d['score']) if rows else None
single={(r['seed'],r['keys'][0]):r for r in s['records'] if r['style']=='color'};multi={r['seed']:r for r in m['records']};out=[]
for mode in ('a_single','b_span_min'):
 for th in (.35,.45,.55):
  n=ok=absent=absent_ok=dup_n=dup_ok=nodet=0;lat=[]
  for seed in range(1000,1020):
   mr=multi[seed];targets=mr['targets']
   for cls in v:
    gt=[t for t in targets if t['class_id']==cls];rows=single[seed,cls]['candidates'] if mode=='a_single' else [d for d in mr['candidates']['span_min'] if d['class_id']==cls];picked=choose(rows,th);ms=single[seed,cls]['ms'] if mode=='a_single' else mr['ms']
    if not gt:absent+=1;absent_ok+=picked is None
    for target in gt:
     n+=1;success=picked is not None and iou(picked['box'],target['box'])>=.5;ok+=success;nodet+=picked is None;lat.append(ms)
     if len(gt)>1:dup_n+=1;dup_ok+=success
  out.append(dict(mode=mode,threshold=th,n=n,correct=ok,accuracy=ok/n,no_detection=nodet,absent_n=absent,absent_correct=absent_ok,absent_specificity=absent_ok/absent,duplicate_n=dup_n,duplicate_correct=dup_ok,duplicate_color_distinguishable=False,mean_model_ms=sum(lat)/len(lat)))
best=max(out,key=lambda x:(x['accuracy'],x['absent_specificity'],-x['mean_model_ms']))
freeze=dict(source='[시뮬인식]',gt_assist=False,split='tuning',frozen_at=time.time(),primary='per instructed instance top1 IoU>=0.5; no detection counts failure',selection_rule='maximize tune present-target selection accuracy; tiebreak absent specificity then latency',selected=best,comparisons=out,width=640,height=480,area_cap=.04,text_threshold=.25,model_revision='a2bb814dd30d776dcf7e30523b00659f4f141c71',eval_seeds=[100000,100099],preseen_seeds=[100000,100009],duplicate_policy='same-class instances use same catalog color/phrase; no GT identity tie-break; count each target separately',single_prompt='catalog color+noun lower-case followed by spaced period; no article',multi_prompt='all9 catalog phrases lower-case separated by spaced periods',eval_methods={'a_single':best['threshold'] if best['mode']=='a_single' else .35,'b_span_min':best['threshold'] if best['mode']=='b_span_min' else .35})
freeze['sha256']=hashlib.sha256(json.dumps(freeze,sort_keys=True).encode()).hexdigest();(R/'selection_freeze.json').write_text(json.dumps(freeze,indent=2));print(json.dumps(freeze,indent=2))
