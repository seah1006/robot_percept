"""Same-frame landmark effect of GetTickCount64 vs QPC timestamp quantisation.
Synthetic timestamp schedule only, real recording images; differences are not GT.
"""
import cv2,pathlib,numpy as np,json,concurrent.futures as cf
from humanoid_tracker_candidates import models,infer
from humanoid_pipeline_bench import jitter
base=pathlib.Path.home()/'Documents/sam_camera';cap=cv2.VideoCapture(str(base/'teleop_final_hand.mp4'));frames=[]
while len(frames)<90:
 ok,f=cap.read()
 if not ok:break
 frames.append(cv2.flip(cv2.resize(f,(640,360)),1))
cap.release();reference=None
for clock in ['quantised_15.625ms','qpc']:
 hand=models('hand');pose=models('pose');pool=cf.ThreadPoolExecutor(2);hands=[];poses=[]
 for i,f in enumerate(frames):
  stamp=int(np.floor((i/30)/.015625)*.015625*1000) if clock.startswith('quantised') else int(i/30*1000)
  h=pool.submit(infer,hand,f,stamp,'hand');p=pool.submit(infer,pose,f,stamp,'pose');hands.append(h.result()[0]);poses.append(p.result()[0])
 if reference is None:reference=(hands,poses)
 diffs=[]
 for hs,rs in zip(hands,reference[0]):
  for h in hs:
   if rs:
    r=min(rs,key=lambda x:np.linalg.norm(x[0]-h[0]));diffs.extend(np.linalg.norm((h-r)*[640,360],axis=1).tolist())
 # Upper-body image acceleration; ignore extrapolated invisible feet.
 acceleration=[]
 for i in range(2,len(poses)):
  if not all(poses[j] for j in [i-2,i-1,i]):continue
  a,b,c=[poses[j][0][[11,12,13,14,15,16,23,24]] for j in [i,i-1,i-2]];acceleration.extend(np.linalg.norm((a-2*b+c)*[640,360],axis=1).tolist())
 print(json.dumps({'clock':clock,'frames':len(frames),'detected':sum(bool(v) for v in hands),'hand_delta_px':float(np.mean(diffs)) if diffs else None,'hand_jitter_px':jitter(hands),'upper_pose_jitter_px':float(np.mean(acceleration)),'not_ground_truth':True}),flush=True)
 hand.close();pose.close();pool.shutdown()
