"""Tuning-only diagnostics; never imports GT into production perception.
Run with measure->gpu locks, timeout285, clone env. Outputs incremental JSON.
"""
import argparse,json,os,time,threading,subprocess
from pathlib import Path
import numpy as np
import torch,mujoco
from PIL import Image
from transformers import AutoProcessor,AutoModelForZeroShotObjectDetection
from perception.grounding import REVISION,MODEL_ID
from sim.cell_scene_eval import open_evaluation_scene
p=argparse.ArgumentParser();p.add_argument('--phase',choices=['multi','single'],default='multi');a=p.parse_args()
torch.set_num_threads(4)
vocab=json.loads(Path('config/vocab_ko_en.yaml').read_text())['phrases']
nouns={'mug':'mug','small_box':'small box','can':'can','ball':'ball','block':'block','bottle':'bottle','mustard':'mustard bottle','box':'box','cup':'cup'}
proc=AutoProcessor.from_pretrained(MODEL_ID,revision=REVISION)
model=AutoModelForZeroShotObjectDetection.from_pretrained(MODEL_ID,revision=REVISION).eval().to('cuda')
used=[]; stop=threading.Event()
def monitor():
    while not stop.wait(.02):
        free,total=torch.cuda.mem_get_info();used.append((total-free)/2**20)
thread=threading.Thread(target=monitor,daemon=True);thread.start();torch.cuda.reset_peak_memory_stats()
records=[]; load_start=os.getloadavg(); began=time.monotonic()
output=Path('bench/g1/tune_diagnosis_'+a.phase+'.json')
def iou(x,y):
    inter=max(0,min(x[2],y[2])-max(x[0],y[0]))*max(0,min(x[3],y[3])-max(x[1],y[1]))
    return inter/max(1e-9,(x[2]-x[0])*(x[3]-x[1])+(y[2]-y[0])*(y[3]-y[1])-inter)
def save():
    output.write_text(json.dumps(dict(source='[시뮬인식]',gt_assist=False,split='tuning',seeds=list(range(1000,1020)),phase=a.phase,revision=REVISION,box_threshold_production=.35,text_threshold_production=.25,diagnostic_box_threshold=.10,records=records,elapsed_s=time.monotonic()-began,loadavg_start=load_start,loadavg_end=os.getloadavg(),device_used_peak_sampled_mib=max(used) if used else None,sample_interval_ms=20,process_max_allocated_mib=torch.cuda.max_memory_allocated()/2**20,process_max_reserved_mib=torch.cuda.max_memory_reserved()/2**20,concurrency=subprocess.getoutput('ps -eo pid,args | grep -E "pytest|bench_gpu|eval_cell"')),indent=2))
try:
 for seed in range(1000,1020):
  for width,height in ([(320,240),(640,480),(1280,720)] if a.phase=='multi' else [(640,480)]):
   scene=open_evaluation_scene(seed,width,height)
   try:
    rgb=scene.rgb(); image=Image.fromarray(rgb)
    # Obtain GT AFTER image capture, solely for independent scoring.
    truth=scene.ground_truth(); w=scene._world
    w.renderer.close(); w.renderer=None; w.model.vis.quality.offsamples=0; scene.rgb()
    w.renderer.enable_segmentation_rendering(); seg=w.renderer.render(); w.renderer.disable_segmentation_rendering()
    targets=[]
    for row in truth:
     bid=w.model.body(row['instance_id']).id; ids=np.where(w.model.geom_bodyid==bid)[0]
     mask=np.isin(seg[:,:,0],ids)&(seg[:,:,1]==int(mujoco.mjtObj.mjOBJ_GEOM)); yy,xx=np.where(mask)
     if len(xx):
      colors=rgb[mask].astype(float)
      targets.append(dict(instance_id=row['instance_id'],class_id=row['class_id'],box=[int(xx.min()),int(yy.min()),int(xx.max()+1),int(yy.max()+1)],visible_pixels=len(xx),pixel_width=int(xx.max()+1-xx.min()),pixel_height=int(yy.max()+1-yy.min()),rgb_std=colors.std(axis=0).tolist(),area_ratio=float((xx.max()+1-xx.min())*(yy.max()+1-yy.min())/(width*height))))
    for style,phrases in [('color',vocab),('noun',nouns)]:
     groups=[list(phrases)] if a.phase=='multi' else [[k] for k in phrases]
     for keys in groups:
      prompt=' . '.join(phrases[k].lower() for k in keys)+' .'
      inputs=proc(images=image,text=prompt,return_tensors='pt',do_resize=False).to('cuda')
      start=time.perf_counter()
      with torch.inference_mode(): result=model(**inputs)
      torch.cuda.synchronize(); ms=(time.perf_counter()-start)*1000
      post=proc.post_process_grounded_object_detection(result,inputs.input_ids,threshold=.10,text_threshold=.25,target_sizes=[(height,width)])[0]
      candidates=[]
      for label,score,box in zip(post.get('text_labels',post.get('labels')),post['scores'],post['boxes']):
       label=str(label); matches=[k for k in keys if phrases[k].lower().strip(' .')==label.lower().strip(' .')]
       loose=[k for k in keys if label.lower().strip(' .') in (phrases[k].lower().strip(' .'),nouns[k])]
       candidates.append(dict(label=label,score=float(score),box=box.tolist(),exact_classes=matches,loose_classes=loose))
      if seed==1000 and a.phase=='multi':
       from PIL import ImageDraw
       overlay=image.copy(); draw=ImageDraw.Draw(overlay)
       for target in targets:
        draw.rectangle(target['box'],outline='lime',width=2); draw.text((target['box'][0],target['box'][1]),'GT:'+target['class_id'],fill='lime')
       for candidate in candidates:
        if candidate['score']>=.35:
         draw.rectangle(candidate['box'],outline='red',width=2); draw.text((candidate['box'][0],candidate['box'][1]),candidate['label']+':'+str(round(candidate['score'],2)),fill='red')
       overlay.save('bench/g1/tune1000_'+str(width)+'_'+style+'_scoring.png')
      scored=[]
      for t in targets:
       if a.phase=='single' and t['class_id'] not in keys: continue
       overlaps=[(iou(c['box'],t['box']),c) for c in candidates]
       best=max(overlaps,key=lambda z:z[0]) if overlaps else (0,None)
       def bestscore(min_iou,match):
        scores=[c['score'] for ov,c in overlaps if ov>=min_iou and (match=='any' or t['class_id'] in c[match])]
        return max(scores) if scores else None
       scored.append(dict(instance_id=t['instance_id'],class_id=t['class_id'],best_iou=best[0],best_iou_label=best[1]['label'] if best[1] else None,score_iou50_any=bestscore(.5,'any'),score_iou25_any=bestscore(.25,'any'),score_iou50_exact=bestscore(.5,'exact_classes'),score_iou50_loose=bestscore(.5,'loose_classes')))
      records.append(dict(seed=seed,width=width,height=height,style=style,keys=keys,prompt=prompt,ms=ms,targets=targets,candidates=candidates,scored=scored))
      del inputs,result,post
    save()
   finally: scene.close()
finally:
 stop.set();thread.join();save();model.to('cpu');torch.cuda.empty_cache()
print(output, 'records',len(records),'seconds',time.monotonic()-began,flush=True)
