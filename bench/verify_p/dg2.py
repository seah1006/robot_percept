import sys, os, json, numpy as np, torch
sys.path.insert(0,'/home/user/work/robot_percept')
from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor
import cv2
def lcc(m):
    n,l,st,_=cv2.connectedComponentsWithStats(m.astype(np.uint8))
    return (l==(1+np.argmax(st[1:,4]))) if n>1 else m
R='/home/user/work/robot_percept'; F=R+'/bench/verify_p/frames'
names=('mustard','cup_d70_h60mm','box_fillet_50x30x20mm')
cfg=sys.argv[1]; ck=sys.argv[2]; outp=sys.argv[3]
from perception.sam_runner import select_candidate
p=SAM2ImagePredictor(build_sam2(cfg,ck,device='cuda'))
clicks=json.load(open(F+'/clicks.json')); rows=[]; cur=None
for c in clicks:
    if c['scene']!=cur:
        z=np.load(f"{F}/s{c['scene']:02d}.npz"); cur=c['scene']
        with torch.inference_mode(),torch.autocast('cuda',dtype=torch.float16): p.set_image(z['rgb'])
    seg=z['seg']; gt=lcc(seg==names.index(c['obj']))
    with torch.inference_mode(),torch.autocast('cuda',dtype=torch.float16):
        ms,sc,_=p.predict(point_coords=np.array([[c['x'],c['y']]]),point_labels=np.array([1]),multimask_output=True)
    si=select_candidate(ms,sc,(c['x'],c['y']),z['depth'])
    ious=[float((m.astype(bool)&gt).sum()/max((m.astype(bool)|gt).sum(),1)) for m in ms]
    rows.append(dict(c,scores=[float(s) for s in sc],areas=[int(m.sum()) for m in ms],ious=ious,gt_area=int(gt.sum()),sel=int(si),scsel=int(np.argmax(sc)),best=int(np.argmax(ious))))
json.dump(rows,open(outp,'w'),indent=1)
print('policy: ');sel=np.array([r['ious'][r['sel']] for r in rows]); best=np.array([max(r['ious']) for r in rows])
print('selected median',np.median(sel),'fail',(sel<.5).mean(),'oracle-best median',np.median(best),'fail',(best<.5).mean())
for k in range(3): print('cand',k,'median iou',np.median([r['ious'][k] for r in rows]))
for r in rows:
    if r['ious'][r['sel']]<.5: print(r['obj'],r['kind'],(r['x'],r['y']),'scores',np.round(r['scores'],3),'ious',np.round(r['ious'],3),'areas',r['areas'],'gt',r['gt_area'])