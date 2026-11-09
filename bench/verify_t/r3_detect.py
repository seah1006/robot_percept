import sys,glob,json,cv2,mediapipe as mp
SD=r"C:/Users/USER/Documents/sam_camera/"
res={}
for f in sorted(glob.glob(SD+"teleop_*.mp4")):
    h=mp.tasks.vision.HandLandmarker.create_from_options(mp.tasks.vision.HandLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_path=SD+"models/hand_landmarker.task"),running_mode=mp.tasks.vision.RunningMode.VIDEO,num_hands=1))
    p=mp.tasks.vision.PoseLandmarker.create_from_options(mp.tasks.vision.PoseLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_path=SD+"models/pose_landmarker_lite.task"),running_mode=mp.tasks.vision.RunningMode.VIDEO,num_poses=1))
    c=cv2.VideoCapture(f);n=hh=pp=0
    while True:
        ok,fr=c.read()
        if not ok:break
        im=mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(fr,cv2.COLOR_BGR2RGB));ts=int(n*1000/30)
        hh+=bool(h.detect_for_video(im,ts).hand_landmarks);pp+=bool(p.detect_for_video(im,ts).pose_landmarks);n+=1
    res[f.split('/')[-1]]=dict(frames=n,hand=round(100*hh/max(n,1),1),pose=round(100*pp/max(n,1),1))
    print(f.split('/')[-1],res[f.split('/')[-1]],flush=True)
