"""Frozen one-shot evaluation, 25 scenes per lock acquisition. No tuning here."""
import argparse,json,time,os,threading,subprocess
from pathlib import Path
import numpy as np,torch,mujoco
from PIL import Image,ImageDraw
from transformers import AutoProcessor,AutoModelForZeroShotObjectDetection
from perception.grounding import MODEL_ID,REVISION,phrase_token_spans
from sim.cell_scene_eval import open_evaluation_scene
p=argparse.ArgumentParser();p.add_argument('--part',type=int,required=True);a=p.parse_args();assert 0<=a.part<4
R=Path('bench/g1');freeze=json.loads((R/'selection_freeze.json').read_text());outpath=R/f'selection_eval_part{a.part}.json'
if outpath.exists():raise RuntimeError('One-shot part already exists; refuse rerun')
(R/'gallery').mkdir(exist_ok=True);vocab=json.loads(Path('config/vocab_ko_en.yaml').read_text())['phrases'];keys=list(vocab);torch.set_num_threads(4)
proc=AutoProcessor.from_pretrained(MODEL_ID,revision=REVISION);model=AutoModelForZeroShotObjectDetection.from_pretrained(MODEL_ID,revision=REVISION).eval().to('cuda');records=[];began=time.monotonic();load=os.getloadavg();used=[];stop=threading.Event()
def monitor():
 while not stop.wait(.02):
  f,t=torch.cuda.mem_get_info();used.append((t-f)/2**20)
thread=threading.Thread(target=monitor,daemon=True);thread.start();torch.cuda.reset_peak_memory_stats()
def iou(a,b):
 x=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]));return x/max(1e-9,(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-x)
def run(image,qs,mode):
 phrases=[vocab[k] for k in qs];prompt=' . '.join(phrases)+' .';start=time.perf_counter();inputs=proc(images=image,text=prompt,return_tensors='pt',do_resize=False).to('cuda')
 with torch.inference_mode():out=model(**inputs)
 logits=out.logits[0].sigmoid();boxes=out.pred_boxes[0].detach().cpu().tolist()
 if mode=='a_single':score=logits.max(dim=1).values;idx=torch.zeros_like(score,dtype=torch.long)
 else:
  offsets=proc.tokenizer(prompt,return_offsets_mapping=True)['offset_mapping'];spans=phrase_token_spans(prompt,phrases,offsets);score,idx=torch.stack([logits[:,s].min(dim=1).values for s in spans],dim=1).max(dim=1)
 rows=[]
 for confidence,index,box in zip(score.detach().cpu().tolist(),idx.detach().cpu().tolist(),boxes):
  if confidence<freeze['eval_methods'][mode]:continue
  cx,cy,w,h=box;b=[max(0.,(cx-w/2)*640),max(0.,(cy-h/2)*480),min(640.,(cx+w/2)*640),min(480.,(cy+h/2)*480)]
  if b[0]>=b[2] or b[1]>=b[3] or (b[2]-b[0])*(b[3]-b[1])/(640*480)>freeze['area_cap']:continue
  rows.append(dict(class_id=qs[index],score=confidence,box=b))
 torch.cuda.synchronize();return rows,(time.perf_counter()-start)*1000

def save():
 outpath.write_text(json.dumps(dict(source='[시뮬인식]',gt_assist=False,identity_assist=False,split='evaluation',part=a.part,freeze_sha256=freeze['sha256'],records=records,elapsed_s=time.monotonic()-began,load_start=load,load_end=os.getloadavg(),device_used_peak_sampled_mib=max(used) if used else None,sample_interval_ms=20,process_max_allocated_mib=torch.cuda.max_memory_allocated()/2**20,process_max_reserved_mib=torch.cuda.max_memory_reserved()/2**20,torch=torch.__version__,device=torch.cuda.get_device_name(0),concurrency=subprocess.getoutput('ps -eo pid,args | grep -E "pytest|bench_gpu|eval_cell"')),indent=2))
try:
 for seed in range(100000+a.part*25,100025+a.part*25):
  scene=open_evaluation_scene(seed,640,480)
  try:
   rgb=scene.rgb();image=Image.fromarray(rgb);pred={};lat={}
   # Fixed catalog queries independent of GT scene content, includes absent objects.
   for k in keys:pred['a_single/'+k],lat['a_single/'+k]=run(image,[k],'a_single')
   rows,ms=run(image,keys,'b_span_min')
   for k in keys:pred['b_span_min/'+k]=[r for r in rows if r['class_id']==k];lat['b_span_min/'+k]=ms
   # Evaluation-only GT, after all model predictions are immutable.
   truth=scene.ground_truth();w=scene._world;w.renderer.close();w.renderer=None;w.model.vis.quality.offsamples=0;scene.rgb();w.renderer.enable_segmentation_rendering();opt=mujoco.MjvOption();opt.geomgroup[3]=0;w.renderer.update_scene(w.data,camera='front',scene_option=opt);seg=w.renderer.render().copy();w.renderer.disable_segmentation_rendering();targets=[]
   for t in truth:
    bid=w.model.body(t['instance_id']).id;ids=np.where(w.model.geom_bodyid==bid)[0];mask=np.isin(seg[:,:,0],ids)&(seg[:,:,1]==int(mujoco.mjtObj.mjOBJ_GEOM));yy,xx=np.where(mask)
    targets.append(dict(instance_id=t['instance_id'],class_id=t['class_id'],visible=bool(len(xx)),box=[int(xx.min()),int(yy.min()),int(xx.max()+1),int(yy.max()+1)] if len(xx) else None))
   tasks=[];absent=[];aux={}
   for mode in ('a_single','b_span_min'):
    for target in targets:
     cls=target['class_id'];candidates=pred[mode+'/'+cls];picked=max(candidates,key=lambda d:d['score']) if candidates else None;ov=iou(picked['box'],target['box']) if picked and target['box'] else 0;duplicate=sum(t['class_id']==cls for t in targets)>1
     tasks.append(dict(mode=mode,instance_id=target['instance_id'],class_id=cls,phrase=vocab[cls],visible=target['visible'],duplicate_same_color=duplicate,correct=ov>=.5,iou=ov,status='selected' if picked else 'NO_DETECTION',selected=picked,ms=lat[mode+'/'+cls]))
     if ov<.5 and a.part==0 and len(list((R/'gallery').glob('*.png')))<6:
      overlay=image.copy();draw=ImageDraw.Draw(overlay)
      if target['box']:draw.rectangle(target['box'],outline='lime',width=2)
      if picked:draw.rectangle(picked['box'],outline='red',width=2)
      draw.text((5,5),f"{seed} {mode} {cls} IoU={ov:.2f}",fill='red');overlay.resize((400,300)).save(R/'gallery'/f'{seed}_{mode}_{target["instance_id"]}.png')
    for k in keys:
     if not any(t['class_id']==k for t in targets):absent.append(dict(mode=mode,class_id=k,correct=not pred[mode+'/'+k],status='NO_DETECTION' if not pred[mode+'/'+k] else 'false_selection'))
    allrows=[d for k in keys for d in pred[mode+'/'+k]];matched=set();tp=0
    for d in sorted(allrows,key=lambda d:-d['score']):
     matches=[(iou(d['box'],t['box']),i) for i,t in enumerate(targets) if i not in matched and t['box'] and t['class_id']==d['class_id']]
     if matches and max(matches)[0]>=.5:matched.add(max(matches)[1]);tp+=1
    aux[mode]=dict(gt=len(targets),tp=tp,fp=len(allrows)-tp)
   records.append(dict(seed=seed,targets=targets,tasks=tasks,absent=absent,aux=aux,predictions=pred));save();print(seed,flush=True)
  finally:scene.close()
finally:stop.set();thread.join();save();model.to('cpu');torch.cuda.empty_cache()
print('complete part',a.part,'seconds',time.monotonic()-began)
