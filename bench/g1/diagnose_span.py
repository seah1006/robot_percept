"""Tuning-only phrase token span mapping vs HF decoded label baseline."""
import json,time,os,subprocess
from pathlib import Path
import numpy as np
import torch,mujoco
from PIL import Image
from transformers import AutoProcessor,AutoModelForZeroShotObjectDetection
from perception.grounding import MODEL_ID,REVISION
from sim.cell_scene_eval import open_evaluation_scene
vocab=json.loads(Path('config/vocab_ko_en.yaml').read_text())['phrases']; keys=list(vocab)
AREA_CAP=.16 # ceil(3 * tuning max visible GT box ratio .051204427 *100)/100
prompt=' . '.join(vocab[k].lower() for k in keys)+' .'
torch.set_num_threads(4);proc=AutoProcessor.from_pretrained(MODEL_ID,revision=REVISION);model=AutoModelForZeroShotObjectDetection.from_pretrained(MODEL_ID,revision=REVISION).eval().to('cuda')
enc=proc.tokenizer(prompt,return_offsets_mapping=True);offsets=enc['offset_mapping']; spans=[];cursor=0
for k in keys:
 phrase=vocab[k].lower(); start=prompt.index(phrase,cursor);end=start+len(phrase);cursor=end
 spans.append([i for i,(a,b) in enumerate(offsets) if b>a and a>=start and b<=end])
def iou(a,b):
 v=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]));return v/max(1e-9,(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-v)
records=[]; began=time.monotonic();load=os.getloadavg()
def save():
 Path('bench/g1/tune_span.json').write_text(json.dumps(dict(source='[시뮬인식]',gt_assist=False,split='tuning',revision=REVISION,prompt=prompt,token_spans=dict(zip(keys,spans)),area_cap=AREA_CAP,elapsed_s=time.monotonic()-began,records=records,load_start=load,load_end=os.getloadavg(),torch=torch.__version__,device=torch.cuda.get_device_name(0),process_max_allocated_mib=torch.cuda.max_memory_allocated()/2**20),indent=2))
try:
 for seed in range(1000,1020):
  scene=open_evaluation_scene(seed,640,480)
  try:
   rgb=scene.rgb();inputs=proc(images=Image.fromarray(rgb),text=prompt,return_tensors='pt',do_resize=False).to('cuda');t=time.perf_counter()
   with torch.inference_mode():out=model(**inputs)
   torch.cuda.synchronize();ms=(time.perf_counter()-t)*1000
   # Pure RGB/text candidate construction finishes before GT scoring.
   logits=out.logits[0].sigmoid().cpu();boxes=out.pred_boxes[0].cpu().numpy();xy=np.stack([(boxes[:,0]-boxes[:,2]/2)*640,(boxes[:,1]-boxes[:,3]/2)*480,(boxes[:,0]+boxes[:,2]/2)*640,(boxes[:,1]+boxes[:,3]/2)*480],axis=1)
   candidates={}
   post=proc.post_process_grounded_object_detection(out,inputs.input_ids,threshold=.35,text_threshold=.25,target_sizes=[(480,640)])[0]
   candidates['hf_exact']=[]
   for label,score,box in zip(post.get('text_labels',post.get('labels')),post['scores'],post['boxes']):
    matches=[k for k in keys if vocab[k]==str(label).strip(' .')]
    if len(matches)==1:candidates['hf_exact'].append(dict(class_id=matches[0],score=float(score),box=box.tolist()))
   for mode in ('span_max','span_mean','span_min'):
    scores=torch.stack([logits[:,span].max(dim=1).values if mode=='span_max' else logits[:,span].mean(dim=1) if mode=='span_mean' else logits[:,span].min(dim=1).values for span in spans],dim=1)
    best,idx=scores.max(dim=1); rows=[]
    for i in range(len(best)):
     if best[i]>=.35:rows.append(dict(class_id=keys[int(idx[i])],score=float(best[i]),box=xy[i].tolist()))
    candidates[mode]=rows
   gt=scene.ground_truth();w=scene._world;w.renderer.close();w.renderer=None;w.model.vis.quality.offsamples=0;scene.rgb();w.renderer.enable_segmentation_rendering();seg=w.renderer.render();w.renderer.disable_segmentation_rendering();targets=[]
   for row in gt:
    bid=w.model.body(row['instance_id']).id;ids=np.where(w.model.geom_bodyid==bid)[0];mask=np.isin(seg[:,:,0],ids)&(seg[:,:,1]==int(mujoco.mjtObj.mjOBJ_GEOM));yy,xx=np.where(mask)
    if len(xx):targets.append(dict(class_id=row['class_id'],instance_id=row['instance_id'],box=[int(xx.min()),int(yy.min()),int(xx.max()+1),int(yy.max()+1)],width=int(xx.max()+1-xx.min()),height=int(yy.max()+1-yy.min()),visible_pixels=len(xx)))
   modes={}
   for mode,rows in candidates.items():
    for filtering in (False,True):
     valid=[d for d in rows if not filtering or (d['box'][2]-d['box'][0])*(d['box'][3]-d['box'][1])/(640*480)<=AREA_CAP];matched=set();cls={}
     for t in targets:cls.setdefault(t['class_id'],dict(gt=0,tp=0,fp=0))['gt']+=1
     for d in sorted(valid,key=lambda d:-d['score']):
      match=[(iou(d['box'],t['box']),i) for i,t in enumerate(targets) if i not in matched and t['class_id']==d['class_id']];stat=cls.setdefault(d['class_id'],dict(gt=0,tp=0,fp=0))
      if match and max(match)[0]>=.5:matched.add(max(match)[1]);stat['tp']+=1
      else:stat['fp']+=1
     modes[mode+'/'+str(filtering)]=dict(per_class=cls,tp=len(matched),fp=len(valid)-len(matched),gt=len(targets),matched_instances=[targets[i]['instance_id'] for i in matched])
   records.append(dict(seed=seed,ms=ms,targets=targets,candidates=candidates,modes=modes));save();del inputs,out,post
  finally:scene.close()
finally:save();model.to('cpu');torch.cuda.empty_cache()
print('span records',len(records),'seconds',time.monotonic()-began)
