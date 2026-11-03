"""Frozen, same-frame SAM2 candidate diagnostic. No GT in inference/selection."""
import argparse, json, time
from pathlib import Path
import numpy as np
import cv2
import torch
from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor
from sim.env import SimEnv

p=argparse.ArgumentParser();p.add_argument('--out',default='bench/ip/diagnosis');p.add_argument('--seeds',type=int,default=5);a=p.parse_args()
out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
model=build_sam2('configs/sam2.1/sam2.1_hiera_s.yaml','/home/user/ai_class/sam/checkpoints/sam2.1_hiera_small.pt',device='cuda')
pred=SAM2ImagePredictor(model); rows=[]
for name in ('mustard','box_fillet_50x30x20mm','cup_d70_h60mm'):
 for seed in range(a.seeds):
  with SimEnv(objects=(name,),seed=seed) as env:
   frame=env.render_rgbd();rgb,dep,seg=frame['rgb'],frame['depth'],frame['seg'];gt=seg==env.object_ids[name]
   yy,xx=np.where(gt);cx,cy=int(np.mean(xx)),int(np.mean(yy));
   # centroid may fall in cup void; snap to nearest visible target pixel
   ix=np.argmin((xx-cx)**2+(yy-cy)**2); center=(int(xx[ix]),int(yy[ix]))
   side=(int(xx[np.argmax(xx)]),int(yy[np.argmax(xx)]))
   for tag,click in [('center',center),('offcenter',side)]:
    t=time.perf_counter();pred.set_image(rgb)
    with torch.inference_mode(),torch.autocast('cuda',dtype=torch.float16):
     masks,scores,_=pred.predict(point_coords=np.array([click]),point_labels=np.array([1]),multimask_output=True)
    torch.cuda.synchronize(); ms=(time.perf_counter()-t)*1000
    masks=np.asarray(masks,dtype=bool);scores=np.asarray(scores)
    areas=[int(m.sum()) for m in masks]; ious=[float((m&gt).sum()/max((m|gt).sum(),1)) for m in masks]
    idx=int(np.argmax(scores)); stem=f'{name}_{seed}_{tag}'
    np.savez_compressed(out/f'{stem}.npz',rgb=rgb,depth=dep,gt=gt,masks=masks,scores=scores,click=click)
    rows.append(dict(object=name,seed=seed,point_type=tag,click=click,rgb_shape=rgb.shape,rgb_dtype=str(rgb.dtype),rgb_pixel=rgb[click[1],click[0]].tolist(),mask_shape=masks.shape,model='sam2.1_hiera_s',channel_order='MuJoCo RGB unchanged',scores=scores.tolist(),areas=areas,ious=ious,selected=idx,selected_iou=ious[idx],oracle_iou=max(ious),gt_area=int(gt.sum()),ms=ms,artifact=str(out/f'{stem}.npz')))
    print(json.dumps(rows[-1]),flush=True)
    pred.reset_predictor()
(out/'rows.json').write_text(json.dumps(rows,indent=2))
for name in set(r['object'] for r in rows):
 v=np.array([r['selected_iou'] for r in rows if r['object']==name]);print(name,'median',np.median(v),'p10',np.percentile(v,10),'min',v.min(),'failure',np.mean(v<.5),flush=True)
