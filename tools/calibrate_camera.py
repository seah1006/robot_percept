"""Offline checkerboard calibration. Live capture is opt-in and exclusive.
Extrinsics use the first image's board frame (origin first inner corner),
board +Z normal. Supply T_world_board for robot/world registration.
"""
import argparse
import contextlib
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
import yaml
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from perception.interfaces import CameraModel

def board_points(pattern=(9,6), square_m=.025):
    if min(pattern)<3 or square_m<=0: raise ValueError('board geometry')
    p=np.zeros((pattern[0]*pattern[1],3),np.float32)
    p[:,:2]=np.mgrid[:pattern[0],:pattern[1]].T.reshape(-1,2)*square_m
    return p

def estimate(images, pattern=(9,6), square_m=.025, T_world_board=None, mode='offline'):
    obj=board_points(pattern,square_m); objects=[]; corners=[]; size=None
    for image in images:
        gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY) if image.ndim==3 else image
        current=(gray.shape[1],gray.shape[0])
        if size is not None and current!=size: raise ValueError('mixed image sizes')
        size=current
        ok,p=cv2.findChessboardCornersSB(gray,pattern,cv2.CALIB_CB_NORMALIZE_IMAGE)
        if ok:
            # Plain board has a 180-degree ambiguity. Define the first corner
            # as the image-top-left endpoint; real world registration must match.
            if p[0,0].sum()>p[-1,0].sum(): p=p[::-1].copy()
            objects.append(obj); corners.append(p.astype(np.float32))
    if len(corners)<6: raise ValueError('at least 6 diverse checkerboard views required')
    rms,K,dist,rvecs,tvecs=cv2.calibrateCamera(objects,corners,size,None,None,flags=cv2.CALIB_FIX_K3)
    # Fail closed for noisy/degenerate/unphysical solutions. These gates do
    # not establish independent metric accuracy (validation_error_m stays null).
    centers=np.array([p.reshape(-1,2).mean(0) for p in corners])
    normals=np.array([cv2.Rodrigues(r)[0][:,2] for r in rvecs])
    angular_span=max(float(np.degrees(np.arccos(np.clip(a@b,-1,1)))) for a in normals for b in normals)
    center_span=float(np.linalg.norm(np.ptp(centers,axis=0)/np.array(size)))
    if not np.isfinite(rms) or rms>.5: raise ValueError('calibration quality: RMS > 0.5px')
    if center_span<.03 or angular_span<10: raise ValueError('calibration quality: insufficient viewpoint diversity')
    if not np.isfinite(K).all() or not np.isfinite(dist).all() or not all(.2*max(size)<K[i,i]<5*max(size) for i in (0,1)) or not (0<K[0,2]<size[0] and 0<K[1,2]<size[1]) or np.max(np.abs(dist))>5: raise ValueError('calibration quality: implausible intrinsics')
    R=cv2.Rodrigues(rvecs[0])[0]; T_board_cam=np.eye(4)
    T_board_cam[:3,:3]=R.T; T_board_cam[:3,3]=-R.T@tvecs[0].ravel()
    Twb=np.eye(4) if T_world_board is None else np.asarray(T_world_board,dtype=float)
    T=Twb@T_board_cam; n=Twb[:3,2]; plane=(*n,-float(n@Twb[:3,3]))
    identifier=hashlib.sha256(json.dumps([K.tolist(),dist.tolist(),T.tolist(),size]).encode()).hexdigest()[:20]
    fov=tuple(float(np.degrees(2*np.arctan(size[i]/(2*K[i,i])))) for i in range(2))
    model=CameraModel(identifier,tuple(map(tuple,K)),tuple(dist.ravel()),tuple(map(tuple,T)),plane,size,(0,0,*size),fov,mode)
    return model,{'rms_px':float(rms),'accepted_views':len(corners),'extrinsics_reference':'first_accepted_board','independent_validation':'not_performed','quality_gates':'passed','distortion_model':'k1_k2_p1_p2_k3fixed0','view_normal_span_deg':angular_span,'normalized_center_span':center_span}

def save_calibration(path,model,report):
    Path(path).write_text(yaml.safe_dump({'camera':json.loads(json.dumps(model.to_dict())),'report':report},sort_keys=False))

@contextlib.contextmanager
def camera_owner(index):
    # Advisory ownership lock plus Linux holder check before VideoCapture.
    import fcntl
    import subprocess
    lock=open('/tmp/rp_camera_'+str(index)+'.lock','w')
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        result=subprocess.run(['fuser','/dev/video'+str(index)],capture_output=True)
        if result.returncode==0: raise RuntimeError('OWNER_CONFLICT: camera already held')
        if result.returncode!=1: raise RuntimeError('OWNER_CONFLICT: holder check unavailable or failed')
        yield
    finally: lock.close()

def synthetic_views(K, size=(1280,720), pattern=(9,6), square_m=.025, count=14):
    """Rasterized perspective boards; no corner coordinates passed to estimator."""
    cols,rows=pattern; tile=200
    texture=np.zeros(((rows+1)*tile,(cols+1)*tile),np.uint8)
    for y in range(rows+1):
        for x in range(cols+1): texture[y*tile:(y+1)*tile,x*tile:(x+1)*tile]=255 if (x+y)%2 else 0
    outer=np.array([[-1,-1,0],[cols,-1,0],[cols,rows,0],[-1,rows,0]],np.float32)*square_m
    src=np.array([[0,0],[texture.shape[1]-1,0],[texture.shape[1]-1,texture.shape[0]-1],[0,texture.shape[0]-1]],np.float32)
    images=[]; poses=[]
    for i in range(count):
        r=np.array([.10+.38*np.sin(i),-.15+.38*np.cos(i*.8),.15*np.sin(i*.7)])
        t=np.array([-.10+.065*np.sin(i*.4),-.065+.045*np.cos(i),.58+.07*np.sin(i*.6)])
        dst=cv2.projectPoints(outer,r,t,K,None)[0].reshape(4,2).astype(np.float32)
        H=cv2.getPerspectiveTransform(src,(dst+.5)*3-.5)
        image=cv2.warpPerspective(texture,H,(size[0]*3,size[1]*3),borderValue=150)
        image=cv2.resize(image,size,interpolation=cv2.INTER_AREA)
        images.append(image); poses.append((r,t))
    return images,poses

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--images',nargs='+'); p.add_argument('--output',required=True)
    p.add_argument('--pattern',type=int,nargs=2,default=(9,6)); p.add_argument('--square-m',type=float,default=.025)
    p.add_argument('--camera',type=int); p.add_argument('--confirm-single-owner',action='store_true')
    p.add_argument('--world-board',help='JSON 4x4 rigid transform'); a=p.parse_args()
    if a.camera is not None:
        if not a.confirm_single_owner: p.error('stop tracker and pass --confirm-single-owner')
        with camera_owner(a.camera):
            cap=cv2.VideoCapture(a.camera)
            try:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH,1280); cap.set(cv2.CAP_PROP_FRAME_HEIGHT,720)
                images=[]
                while len(images)<20:
                    ok,im=cap.read()
                    if not ok: raise RuntimeError('camera read failed')
                    if im.shape[:2]!=(720,1280): raise RuntimeError('CALIBRATION_MISMATCH: capture size')
                    cv2.imshow('SPACE: diverse board view; ESC: stop',im); key=cv2.waitKey(30)&255
                    if key==32: images.append(im.copy())
                    if key==27: break
            finally: cap.release(); cv2.destroyAllWindows()
    else:
        if not a.images: p.error('--images required without explicit --camera')
        images=[cv2.imread(f) for f in a.images]
        if any(i is None for i in images): p.error('unreadable image')
    model,report=estimate(images,tuple(a.pattern),a.square_m,json.loads(a.world_board) if a.world_board else None)
    save_calibration(a.output,model,report); print(json.dumps(report))
if __name__=='__main__': main()





