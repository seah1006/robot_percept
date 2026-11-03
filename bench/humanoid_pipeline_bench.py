"""Recording-only same-frame postprocess overlap/parity benchmark. No HTTP/camera.
Run on Windows after verifier releases the CPU/GPU measurement slot.
"""
import os
os.environ['OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS']='0'
import time,json,pathlib,concurrent.futures as cf,cv2,numpy as np
from humanoid_tracker_candidates import models,infer
BASE=pathlib.Path.home()/'Documents/sam_camera'
def jitter(rows):
 out=[]
 for i in range(2,len(rows)):
  if not all(rows[j] for j in [i-2,i-1,i]):continue
  for a in rows[i]:
   b=min(rows[i-1],key=lambda x:np.linalg.norm(x[0]-a[0]));c=min(rows[i-2],key=lambda x:np.linalg.norm(x[0]-b[0]))
   out.extend(np.linalg.norm((a-2*b+c)*[640,360],axis=1).tolist())
 return float(np.mean(out)) if out else None

def main():
 cv2.setNumThreads(1);cap=cv2.VideoCapture(str(BASE/'teleop_final_hand.mp4'));frames=[]
 while len(frames)<90:
  ok,f=cap.read()
  if not ok:break
  frames.append(cv2.flip(cv2.resize(f,(640,360)),1))
 cap.release();reference=None
 for mode in ['baseline','pipeline','parity']:
  pairs=[(models('hand'),models('pose')) for _ in range(2 if mode=='parity' else 1)]
  neural=cf.ThreadPoolExecutor(4 if mode=='parity' else 2);coordinate=cf.ThreadPoolExecutor(2)
  def pair(i):
   hand,pose=pairs[i%len(pairs)];t=time.perf_counter();h=neural.submit(infer,hand,frames[i],i*34,'hand');p=neural.submit(infer,pose,frames[i],i*34,'pose');hr,ht=h.result();pr,pt=p.result();return hr,pr,(time.perf_counter()-t)*1000,ht,pt
  def postprocess(i,h,p):
   f=frames[i].copy();t=time.perf_counter()
   for hand in h:
    uv=(hand*[640,360]).astype(int)
    for chain in [[0,1,2,3,4],[0,5,6,7,8],[0,9,10,11,12],[0,13,14,15,16],[0,17,18,19,20]]:
     for a,b in zip(chain,chain[1:]):cv2.line(f,tuple(uv[a]),tuple(uv[b]),(50,230,70),1)
    for tip in [4,8,12,16,20]:cv2.circle(f,tuple(uv[tip]),6,(100,200,255),-1)
   if p:
    uv=(p[0]*[640,360]).astype(int)
    for a,b in [[11,12],[11,13],[13,15],[12,14],[14,16],[11,23],[12,24],[23,24]]:cv2.line(f,tuple(uv[a]),tuple(uv[b]),(80,230,100),2)
   draw=(time.perf_counter()-t)*1000;t=time.perf_counter();cv2.imencode('.jpg',f,[cv2.IMWRITE_JPEG_QUALITY,65]);jpeg=(time.perf_counter()-t)*1000
   t=time.perf_counter();json.dumps({'pose2d':p[0].tolist() if p else [],'hands2d':[v.tolist() for v in h]});ser=(time.perf_counter()-t)*1000
   return draw,jpeg,ser
  rows=[];inference=[];post=[];latencies=[];pending={};depth=2 if mode=='parity' else 1;t0=time.perf_counter()
  if mode!='baseline':
   for i in range(min(depth,len(frames))):pending[i]=coordinate.submit(pair,i)
  for i in range(len(frames)):
   ti=time.perf_counter()
   if mode=='baseline':h,p,ms,ht,pt=pair(i)
   else:
    h,p,ms,ht,pt=pending.pop(i).result()
    if i+depth<len(frames):pending[i+depth]=coordinate.submit(pair,i+depth)
   rows.append(h);inference.append(ms);post.append(postprocess(i,h,p));latencies.append((time.perf_counter()-ti)*1000)
  elapsed=time.perf_counter()-t0
  if reference is None:reference=rows
  delta=[]
  for hands,refs in zip(rows,reference):
   for h in hands:
    if refs:
     r=min(refs,key=lambda v:np.linalg.norm(h[0]-v[0]));delta.extend(np.linalg.norm((h-r)*[640,360],axis=1).tolist())
  pp=np.array(post)
  print(json.dumps({'mode':mode,'frames':len(rows),'hz':len(rows)/elapsed,'loop_p50':float(np.median(latencies)),'loop_p95':float(np.percentile(latencies,95)),'infer_p50':float(np.median(inference)),'infer_p95':float(np.percentile(inference,95)),'draw_p50':float(np.median(pp[:,0])),'jpeg_p50':float(np.median(pp[:,1])),'json_p50':float(np.median(pp[:,2])),'detected':sum(bool(v) for v in rows),'delta_px':float(np.mean(delta)) if delta else None,'delta_p95_px':float(np.percentile(delta,95)) if delta else None,'jitter_second_difference_px':jitter(rows),'not_ground_truth':True}),flush=True)
  coordinate.shutdown();neural.shutdown()
  for h,p in pairs:h.close();p.close()
if __name__=='__main__':main()
