"""Windows recording-only benchmark, no camera/HTTP. Pixel difference is not GT."""
import os
os.environ['OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS']='0'
import cv2,time,json,pathlib,concurrent.futures,sys,numpy as np,mediapipe as mp
base=pathlib.Path.home()/'Documents/sam_camera'
cap=cv2.VideoCapture(str(base/(sys.argv[1] if len(sys.argv)>1 else 'teleop_round2_async.mp4')));frames=[]
while len(frames)<90:
 ok,f=cap.read()
 if not ok:break
 frames.append(cv2.flip(cv2.resize(f,(640,360)),1))
cap.release();references=None
for width,parallel in [(640,False),(640,True)]:
 hand=mp.tasks.vision.HandLandmarker.create_from_options(mp.tasks.vision.HandLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_path=str(base/'models/hand_landmarker.task')),running_mode=mp.tasks.vision.RunningMode.VIDEO,num_hands=2))
 pose=mp.tasks.vision.PoseLandmarker.create_from_options(mp.tasks.vision.PoseLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_path=str(base/'models/pose_landmarker_lite.task')),running_mode=mp.tasks.vision.RunningMode.VIDEO,num_poses=1))
 pool=concurrent.futures.ThreadPoolExecutor(2);times=[];landmarks=[];hands=[];t0=time.perf_counter()
 for i,f in enumerate(frames):
  image=mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(cv2.resize(f,(width,width*9//16)),cv2.COLOR_BGR2RGB));t=time.perf_counter()
  if parallel:
   fh=pool.submit(hand.detect_for_video,image,i*34);fp=pool.submit(pose.detect_for_video,image,i*34);h=fh.result();p=fp.result()
  else:h=hand.detect_for_video(image,i*34);p=pose.detect_for_video(image,i*34)
  times.append((time.perf_counter()-t)*1000);landmarks.append(np.array([[v.x*640,v.y*360] for v in p.pose_landmarks[0]]) if p.pose_landmarks else None);hands.append(len(h.hand_landmarks))
 elapsed=time.perf_counter()-t0
 if references is None:references=landmarks
 diffs=[np.linalg.norm(a-b,axis=1).mean() for a,b in zip(landmarks,references) if a is not None and b is not None]
 print(json.dumps(dict(width=width,parallel=parallel,hz=len(times)/elapsed,p50=float(np.median(times)),p95=float(np.percentile(times,95)),pose_frames=sum(v is not None for v in landmarks),hand_frames=sum(v>0 for v in hands),pose_difference_px=float(np.mean(diffs)) if diffs else None)),flush=True)
 hand.close();pose.close();pool.shutdown()
