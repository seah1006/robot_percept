"""Same-frame camera-free hand-positive candidate benchmark. Deltas are not GT accuracy."""
import os
os.environ['OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS']='0'
import cv2,time,json,pathlib,sys,concurrent.futures as cf,numpy as np
BASE=pathlib.Path.home()/'Documents/sam_camera'
def models(kind,confidence=.5):
 import mediapipe as mp
 V=mp.tasks.vision;B=mp.tasks.BaseOptions
 if kind in ('hand','roi'):return V.HandLandmarker.create_from_options(V.HandLandmarkerOptions(base_options=B(model_asset_path=str(BASE/'models/hand_landmarker.task')),running_mode=V.RunningMode.IMAGE if kind=='roi' else V.RunningMode.VIDEO,num_hands=2,min_tracking_confidence=confidence))
 return V.PoseLandmarker.create_from_options(V.PoseLandmarkerOptions(base_options=B(model_asset_path=str(BASE/'models/pose_landmarker_lite.task')),running_mode=V.RunningMode.VIDEO,num_poses=1))
def infer(model,frame,stamp,kind):
 import mediapipe as mp
 t=time.perf_counter();image=mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB));r=model.detect(image) if kind=='roi' else model.detect_for_video(image,stamp)
 if kind in ('hand','roi'):out=[np.array([[v.x,v.y] for v in h]) for h in r.hand_landmarks]
 else:out=[np.array([[v.x,v.y] for v in h]) for h in r.pose_landmarks]
 return out,(time.perf_counter()-t)*1000
PROC=None
KIND=None
def init_process(kind):
 global PROC,KIND
 KIND=kind;PROC=models(kind)
def proc_infer(frame,stamp):return infer(PROC,frame,stamp,KIND)
def run():
 cap=cv2.VideoCapture(str(BASE/'teleop_final_hand.mp4'));frames=[]
 while len(frames)<90:
  ok,f=cap.read()
  if not ok:break
  frames.append(cv2.flip(cv2.resize(f,(640,360)),1))
 cap.release();reference=None;report=[]
 for mode in (['serial640']+sys.argv[1:] if len(sys.argv)>1 else ['serial640','threads640','hand480','hand320','roi','tracking03','processes']):
  roi_model=models('roi') if mode=='roi' else None
  parallel=mode!='serial640';hm=models('hand',.3 if mode=='tracking03' else .5);pm=models('pose');pool=cf.ThreadPoolExecutor(2)
  hp=pp=None
  if mode=='processes':
   hp=cf.ProcessPoolExecutor(1,initializer=init_process,initargs=('hand',));pp=cf.ProcessPoolExecutor(1,initializer=init_process,initargs=('pose',))
   hp.submit(proc_infer,frames[0],0).result();pp.submit(proc_infer,frames[0],0).result()
  times=[];hand_ms=[];pose_ms=[];out=[];prev=[];last_pose=[];fallbacks=0
  for i,f in enumerate(frames):
   t=time.perf_counter();stamp=(i+1)*34;crop=(0,0,640,360);hf=f
   if mode in ('hand480','hand320'):
    w=480 if mode=='hand480' else 320;hf=cv2.resize(f,(w,w*9//16))
   if mode=='roi':
    if prev:
     points=np.concatenate(prev)*[640,360];lo=points.min(0);hi=points.max(0);center=(lo+hi)/2;size=max(hi-lo)*1.8;size=max(size,120)
    elif last_pose:
     wrists=last_pose[0][[15,16]]*[640,360];center=wrists.mean(0);size=max(np.ptp(wrists,axis=0).max()+180,220)
    else:center=np.array([320,180]);size=640
    x0,y0=np.maximum(0,center-size/2).astype(int);x1,y1=np.minimum([640,360],center+size/2).astype(int);crop=(x0,y0,x1,y1);hf=cv2.resize(f[y0:y1,x0:x1],(320,320))
   if mode=='processes':
    a=hp.submit(proc_infer,f,stamp);b=pp.submit(proc_infer,f,stamp);h,ht=a.result();p,pt=b.result()
   elif parallel:
    a=pool.submit(infer,roi_model if roi_model else hm,hf,stamp,'roi' if roi_model else 'hand');b=pool.submit(infer,pm,f,stamp,'pose');h,ht=a.result();p,pt=b.result()
   else:h,ht=infer(hm,hf,stamp,'hand');p,pt=infer(pm,f,stamp,'pose')
   if mode=='roi':
    if not h:
     fallbacks+=1;h,extra=infer(hm,f,stamp+1,'hand');ht+=extra
    else:
     x0,y0,x1,y1=crop;h=[(v*[x1-x0,y1-y0]+[x0,y0])/[640,360] for v in h]
   prev=h;last_pose=p;out.append(h);hand_ms.append(ht);pose_ms.append(pt);times.append((time.perf_counter()-t)*1000)
  if reference is None:reference=out
  differences=[];common=0
  for hs,rs in zip(out,reference):
   if hs and rs:common+=1
   for h in hs:
    if rs:
     r=min(rs,key=lambda r:np.linalg.norm(h[0]-r[0]));differences.extend(np.linalg.norm((h-r)*[640,360],axis=1).tolist())
  row=dict(mode=mode,frames=len(frames),hz=1000/np.mean(times),p50=np.percentile(times,50),p95=np.percentile(times,95),hand_p50=np.median(hand_ms),pose_p50=np.median(pose_ms),detected=sum(bool(v) for v in out),common=common,delta_px=np.mean(differences) if differences else None,delta_p95_px=np.percentile(differences,95) if differences else None,fallbacks=fallbacks)
  row={k:float(v) if isinstance(v,np.floating) else v for k,v in row.items()};print(json.dumps(row),flush=True);report.append(row)
  hm.close();pm.close();pool.shutdown()
  if roi_model:roi_model.close()
  if hp:hp.shutdown();pp.shutdown()
 print(json.dumps({'all':report}),flush=True)
if __name__=='__main__':run()
