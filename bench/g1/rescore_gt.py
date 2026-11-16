"""Rescore SAVED predictions against anti-alias-free evaluation masks. No inference.
GT-only renderer offsamples=0; inference RGB remains original MSAA4 image.
"""
import json,time,math
from pathlib import Path
import numpy as np,mujoco
from sim.cell_scene_eval import open_evaluation_scene
root=Path('bench/g1');cache={};began=time.monotonic()
def iou(a,b):
 v=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]));return v/max(1e-9,(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-v)
def targets(seed,width,height):
 key=(seed,width,height)
 if key in cache:return cache[key]
 scene=open_evaluation_scene(seed,width,height);w=scene._world;w.model.vis.quality.offsamples=0
 try:
  scene.rgb();w.renderer.enable_segmentation_rendering();opt=mujoco.MjvOption();opt.geomgroup[3]=0;w.renderer.update_scene(w.data,camera='front',scene_option=opt);seg=w.renderer.render().copy();w.renderer.disable_segmentation_rendering();rows=[]
  for item in scene.ground_truth():
   bid=w.model.body(item['instance_id']).id;ids=np.where(w.model.geom_bodyid==bid)[0];mask=np.isin(seg[:,:,0],ids)&(seg[:,:,1]==int(mujoco.mjtObj.mjOBJ_GEOM));y,x=np.where(mask)
   if len(x):rows.append(dict(instance_id=item['instance_id'],class_id=item['class_id'],box=[int(x.min()),int(y.min()),int(x.max()+1),int(y.max()+1)],visible_pixels=len(x),pixel_width=int(x.max()+1-x.min()),pixel_height=int(y.max()+1-y.min()),area_ratio=float((x.max()+1-x.min())*(y.max()+1-y.min())/(width*height))))
  cache[key]=rows;return rows
 finally:scene.close()
for phase in ('multi','single'):
 data=json.loads((root/f'tune_diagnosis_{phase}.json').read_text())
 for r in data['records']:
  r['targets']=targets(r['seed'],r['width'],r['height']);scored=[]
  for t in r['targets']:
   if phase=='single' and t['class_id'] not in r['keys']:continue
   overlaps=[(iou(c['box'],t['box']),c) for c in r['candidates']];best=max(overlaps,key=lambda z:z[0]) if overlaps else (0,None)
   def score(th,match):
    values=[c['score'] for ov,c in overlaps if ov>=th and (match=='any' or t['class_id'] in c[match])];return max(values) if values else None
   scored.append(dict(instance_id=t['instance_id'],class_id=t['class_id'],best_iou=best[0],best_iou_label=best[1]['label'] if best[1] else None,score_iou50_any=score(.5,'any'),score_iou25_any=score(.25,'any'),score_iou50_exact=score(.5,'exact_classes'),score_iou50_loose=score(.5,'loose_classes')))
  r['scored']=scored
 data['gt_correction']='offsamples0 evaluation masks; original inference RGB MSAA4 unchanged'
 (root/f'tune_diagnosis_{phase}_corrected.json').write_text(json.dumps(data,indent=2))
max_area=max(t['area_ratio'] for ts in cache.values() for t in ts);cap=math.ceil(max_area*3*100)/100
span=json.loads((root/'tune_span.json').read_text());span['gt_correction']='offsamples0 evaluation masks; original inference RGB MSAA4 unchanged';span['area_cap']=cap
for r in span['records']:
 r['targets']=targets(r['seed'],640,480);modes={}
 for mode,rows in r['candidates'].items():
  for filtering in (False,True):
   valid=[d for d in rows if not filtering or (d['box'][2]-d['box'][0])*(d['box'][3]-d['box'][1])/(640*480)<=cap];matched=set();cls={}
   for t in r['targets']:cls.setdefault(t['class_id'],dict(gt=0,tp=0,fp=0))['gt']+=1
   for d in sorted(valid,key=lambda d:-d['score']):
    matches=[(iou(d['box'],t['box']),i) for i,t in enumerate(r['targets']) if i not in matched and t['class_id']==d['class_id']];stat=cls.setdefault(d['class_id'],dict(gt=0,tp=0,fp=0))
    if matches and max(matches)[0]>=.5:matched.add(max(matches)[1]);stat['tp']+=1
    else:stat['fp']+=1
   modes[mode+'/'+str(filtering)]=dict(per_class=cls,tp=len(matched),fp=len(valid)-len(matched),gt=len(r['targets']),matched_instances=[r['targets'][i]['instance_id'] for i in matched])
 r['modes']=modes
(root/'tune_span_corrected.json').write_text(json.dumps(span,indent=2));(root/'gt_correction_summary.json').write_text(json.dumps(dict(source='[시뮬인식]',gt_assist=False,split='tuning',inference_changed=False,mask_offsamples=0,normal_box_area_max=max_area,margin_factor=3,cell_area_cap=cap,elapsed_s=time.monotonic()-began,targets=[dict(seed=k[0],width=k[1],height=k[2],targets=v) for k,v in cache.items()]),indent=2));print('corrected scenes',len(cache),'cap',cap,'max_area',max_area,'seconds',time.monotonic()-began)
