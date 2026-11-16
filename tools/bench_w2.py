"""[시뮬GT] GT mesh projected boxes, NOT detector accuracy. CPU only."""
import argparse,json,os,subprocess,time
from pathlib import Path
import numpy as np
import mujoco
import trimesh
from sim.cell_scene_eval import open_evaluation_scene
from sim.cell_scene import catalog
from perception.interfaces import CameraModel,FrameMeta,Detection
from perception.localize import Localizer
from tools.calibrate_camera import estimate,synthetic_views,save_calibration

def camera_from_scene(scene,width,height):
    w=scene._world; cid=w.model.camera('front').id
    T=np.eye(4); T[:3,:3]=w.data.cam_xmat[cid].reshape(3,3)@np.diag([1,-1,-1]); T[:3,3]=w.data.cam_xpos[cid]
    f=height/(2*np.tan(np.deg2rad(w.model.cam_fovy[cid])/2)); K=((f,0,(width-1)/2),(0,f,(height-1)/2),(0,0,1))
    return CameraModel('sim-cell-front',K,(),tuple(map(tuple,T)),(0,0,1,-.30),(width,height),(0,0,width,height),(0,float(w.model.cam_fovy[cid])),'sim')

def main():
    p=argparse.ArgumentParser(); p.add_argument('--seeds',type=int,default=40); p.add_argument('--out',default='bench/w2'); p.add_argument('--start',type=int,default=100000); a=p.parse_args()
    out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
    rows=[]; rng=np.random.default_rng(2026); cat=catalog()
    for seed in range(a.start,a.start+a.seeds):
        scene=open_evaluation_scene(seed,1280,720)
        try:
            c=camera_from_scene(scene,1280,720); loc=Localizer(c); W2C=np.linalg.inv(c.T_world_cam); K=np.array(c.K)
            for gt,spec in zip(scene.ground_truth(),scene._world.specs):
                T=np.array(gt['T_world_obj']); mesh=trimesh.load(spec.visual_obj,force='mesh',process=False)
                vertices=np.array(mesh.vertices)@T[:3,:3].T+T[:3,3]
                cam=vertices@W2C[:3,:3].T+W2C[:3,3]; uv=cam@K.T; uv=uv[:,:2]/uv[:,2:]
                lo=np.maximum(uv.min(0),[0,0]); hi=np.minimum(uv.max(0)+1,[1280,720]); box=(*lo,*hi)
                meta=FrameMeta(str(seed),0,'sim_gt',None,time.time(),False,c.calibration_id,1280,720,False)
                d=Detection(gt['instance_id'],'bench',gt['class_id'],1.,box,meta)
                target=np.r_[np.mean(np.array(gt['aabb_m']),axis=0)[:2],.30]
                h=cat[gt['class_id']]['height_m']; top=target+np.array([0,0,h]); cp=W2C[:3,:3]@top+W2C[:3,3]; hp=K@cp; anchor=hp[:2]/hp[2]
                errors={}
                for name,kw in [('bbox_on',{}),('bbox_off',{'height_correction':False}),('top_on',{'anchor':anchor,'anchor_kind':'top_center'}),('top_off',{'anchor':anchor,'anchor_kind':'top_center','height_correction':False})]:
                    result=loc.localize(d,**kw)
                    errors[name]=float(np.linalg.norm(np.array(result.xyz_m)-target)*1000) if not result.error else None
                base=np.array(loc.localize(d).xyz_m); x1,y1,x2,y2=box; contact=np.array([(x1+x2)/2-.5,y2-.5])
                noisy=[]
                for delta in [(-2,-2),(-2,2),(2,-2),(2,2)]:
                    shift=np.tile(delta,2); nd=Detection(d.detection_id,d.query_id,d.canonical_class,d.score,tuple(np.array(box)+shift),meta); r=loc.localize(nd)
                    if not r.error: noisy.append(float(np.linalg.norm(np.array(r.xyz_m)-base)*1000))
                uniform=[]
                for _ in range(100):
                    delta=rng.uniform(-2,2,2); nd=Detection(d.detection_id,d.query_id,d.canonical_class,d.score,tuple(np.array(box)+np.tile(delta,2)),meta); nr=loc.localize(nd)
                    if not nr.error: uniform.append(float(np.linalg.norm(np.array(nr.xyz_m)-target)*1000))
                rows.append({'noise_uniform_errors_mm':uniform,'noise_uniform_error_p95_mm':float(np.percentile(uniform,95)),'seed':seed,'class':gt['class_id'],'instance_id':gt['instance_id'],'errors_mm':errors,'noise_max_displacement_mm':max(noisy) if noisy else None})
        finally: scene.close()
    summary={}
    for cls in sorted({r['class'] for r in rows}):
        group=[r for r in rows if r['class']==cls]; stats={}
        for metric in ['bbox_on','bbox_off','top_on','top_off']:
            values=[r['errors_mm'][metric] for r in group if r['errors_mm'][metric] is not None]
            stats[metric]={'n':len(values),'p50_mm':float(np.percentile(values,50)),'p95_mm':float(np.percentile(values,95))}
        noise=[r['noise_max_displacement_mm'] for r in group if r['noise_max_displacement_mm'] is not None]
        stats['noise_uniform_error_p95_mm']=float(np.percentile([v for r in group for v in r['noise_uniform_errors_mm']],95))
        stats['noise_pm2px']={'p50_mm':float(np.percentile(noise,50)),'p95_mm':float(np.percentile(noise,95))}; summary[cls]=stats
    try: gpu=subprocess.run(['nvidia-smi','--query-gpu=name,memory.used,utilization.gpu','--format=csv'],capture_output=True,text=True).stdout
    except FileNotFoundError: gpu='unavailable'
    report={'source':'[시뮬GT]','recognition':'GT projected mesh boxes, no learned detector; not occlusion-aware','gt_assist':True,'seeds':a.seeds,'objects':len(rows),'load':os.getloadavg(),'nvidia_smi':gpu,'concurrent_work':'shared host, serialized rp_measure lock; GPU unused','summary':summary,'rows':rows}
    (out/'localization.json').write_text(json.dumps(report,indent=2))
    # Match synthetic intrinsic K to this cell camera. Board views are diverse,
    # with known extrinsics; not a real webcam validation.
    images,poses=synthetic_views(np.array(c.K)); model,cal=estimate(images); save_calibration(out/'synthetic_calibration.yaml',model,cal)
    known=np.array(c.K); cal['max_K_error_px']=float(np.max(np.abs(np.array(model.K)-known)))
    import cv2
    r,t=poses[0]; expected=-cv2.Rodrigues(r)[0].T@t
    cal['camera_center_error_mm']=float(np.linalg.norm(np.array(model.T_world_cam)[:3,3]-expected)*1000)
    cal['source']='[시뮬GT] cell K, synthetic raster checkerboard'; (out/'calibration.json').write_text(json.dumps(cal,indent=2))
    print(json.dumps({'objects':len(rows),'summary':summary,'calibration':cal},indent=2))
if __name__=='__main__': main()


