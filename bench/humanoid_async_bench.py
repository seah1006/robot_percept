"""LIVE_STREAM recording-only 30fps benchmark. No camera; same-frame serial comparison."""
import os
os.environ['OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS']='0'
import cv2,time,json,pathlib,threading,numpy as np,mediapipe as mp
base=pathlib.Path.home()/'Documents/sam_camera';cap=cv2.VideoCapture(str(base/'teleop_final_hand.mp4'));frames=[]
while len(frames)<90:
 ok,f=cap.read()
 if not ok:break
 frames.append(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(cv2.flip(cv2.resize(f,(640,360)),1),cv2.COLOR_BGR2RGB)))
cap.release();results={'pose':{},'hand':{}};sent={};lock=threading.Lock()
def callback(kind):
 def cb(result,image,stamp):
  with lock:results[kind][stamp]=(result,(time.perf_counter()-sent[stamp])*1000)
 return cb
V=mp.tasks.vision;B=mp.tasks.BaseOptions
hand=V.HandLandmarker.create_from_options(V.HandLandmarkerOptions(base_options=B(model_asset_path=str(base/'models/hand_landmarker.task')),running_mode=V.RunningMode.LIVE_STREAM,num_hands=2,result_callback=callback('hand')))
pose=V.PoseLandmarker.create_from_options(V.PoseLandmarkerOptions(base_options=B(model_asset_path=str(base/'models/pose_landmarker_lite.task')),running_mode=V.RunningMode.LIVE_STREAM,num_poses=1,result_callback=callback('pose')))
start=time.perf_counter()
for i,image in enumerate(frames):
 time.sleep(max(0,start+i/30-time.perf_counter()));stamp=i*34;sent[stamp]=time.perf_counter();hand.detect_async(image,stamp);pose.detect_async(image,stamp)
time.sleep(.3);hand.close();pose.close()
paired=set(results['hand'])&set(results['pose']);lat=[max(results['hand'][s][1],results['pose'][s][1]) for s in paired]
print(json.dumps({'frames':len(frames),'hand_callbacks':len(results['hand']),'pose_callbacks':len(results['pose']),'paired':len(paired),'paired_hz':len(paired)/(len(frames)/30),'hand_positive':sum(bool(results['hand'][s][0].hand_landmarks) for s in paired),'latency_p50':float(np.median(lat)),'latency_p95':float(np.percentile(lat,95))}),flush=True)
ref=V.PoseLandmarker.create_from_options(V.PoseLandmarkerOptions(base_options=B(model_asset_path=str(base/'models/pose_landmarker_lite.task')),running_mode=V.RunningMode.VIDEO,num_poses=1));diff=[]
for i,image in enumerate(frames):
 p=ref.detect_for_video(image,i*34)
 if i*34 not in paired or not p.pose_landmarks:continue
 async_p=results['pose'][i*34][0]
 if not async_p.pose_landmarks:continue
 a=np.array([[v.x*640,v.y*360] for v in p.pose_landmarks[0]]);b=np.array([[v.x*640,v.y*360] for v in async_p.pose_landmarks[0]]);diff.append(np.linalg.norm(a-b,axis=1).mean())
print(json.dumps({'paired_pose_difference_px':float(np.mean(diff)) if diff else None,'not_ground_truth':True}));ref.close()
