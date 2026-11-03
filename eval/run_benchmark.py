#!/usr/bin/env python3
"""Headless paired-seed RGB-D evaluation. Never starts a web server."""
import argparse
import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
import time
from pathlib import Path
if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from eval.pose_metrics import load_vertices
from eval.harness.metrics import diameter_mm, score
from eval.harness.worker import Client
from eval.harness.report import report

ROOT=Path(__file__).resolve().parents[1]
NAMES={'mustard':'mustard','box':'box_fillet_50x30x20mm','cup':'cup_d70_h60mm'}


def make_env(name,seed,width,height):
    from sim.env import SimEnv
    env=SimEnv(objects=('mustard',) if name=='mustard' else (),seed=seed,width=width,height=height)
    if name!='mustard':
        full=NAMES[name]; d=ROOT/'cad_uploads/converted'/full
        env.add_object_from_mesh(full,d/(full+'.obj'),sorted(d.glob('*_collision_coacd_*.obj')))
    env.reset(seed=seed,randomize=True)
    return env


def trial(a,name,seed,client,git_hash):
    started=time.perf_counter()
    r=dict(schema_version=1,object=name,seed=seed,git_hash=git_hash,config=vars(a).copy(),success=False,frames=[],failure_reasons=[],pick_success=None,place_success=None,tracking_fps=None,register_s=None,lock_wait_s=float(os.getenv('RP_LOCK_WAIT_S','0')))
    env=None
    try:
        env=make_env(name,seed,a.width,a.height); full=NAMES[name]
        vertices=load_vertices(env.object_mesh_path(full)); diameter=diameter_mm(vertices)
        r['diameter_mm']=diameter
        frame=env.render_rgbd(); mask=frame['seg']==env.object_ids[full]
        y,x=np.nonzero(mask)
        if not len(x):raise ValueError('Target not visible')
        idx=np.argmin((x-x.mean())**2+(y-y.mean())**2); click=[int(x[idx]),int(y[idx])]
        r['click_xy']=click
        K=env.camera_K(); latest=None; tracking_started=None; updates=0
        for i in range(a.frames):
            if i:
                # Adapted exporter push motion, parameterized by selected object.
                bid=env.model.body(full).id
                env.data.xfrc_applied[bid]=0
                env.data.xfrc_applied[bid,:3]=[0.,-.5,0.]
                env.step(8); env.data.xfrc_applied[bid]=0
                frame=env.render_rgbd()
            gt=env.T_cam_obj(full)
            t=time.perf_counter()
            if a.perception=='gt':
                latest=gt.copy(); result={'latency_s':time.perf_counter()-t,'peak_bytes':0}
            else:
                result=client.call(op='register' if i==0 else 'track',name=full,mesh=env.object_mesh_path(full),rgb=frame['rgb'],depth=frame['depth'],K=K,click=click)
                latest=np.asarray(result['pose'])
            estimate_wall_s=time.perf_counter()-t
            if not np.isfinite(latest).all():raise ValueError('Nonfinite pose')
            scored=score(latest,gt,vertices,name,diameter)
            r['frames'].append(dict(frame_id=i,simulation_s=float(env.data.time),pred=latest.tolist(),gt=gt.tolist(),latency_s=result['latency_s'],peak_bytes=result['peak_bytes'],**scored))
            if i==0:
                r['register_s']=estimate_wall_s
                if a.perception=='fp':
                    predmask=result['mask']; union=np.count_nonzero(predmask|mask)
                    r['mask_iou']=np.count_nonzero(predmask&mask)/union if union else 1.
                    r['sam_scores']=result['scores'];r['sam_selected_index']=result['selected_index'];r['sam_s']=result['sam_s'];r['sam_peak_bytes']=result['sam_peak_bytes']
                    if a.save_replay:
                        np.savez_compressed(Path(a.out)/f'{name}_{seed}_replay.npz',rgb=frame['rgb'],depth=frame['depth'],gt_mask=mask,sam_mask=predmask,K=K,click=click)
                tracking_started=time.perf_counter()
            else:
                updates+=1
        elapsed=time.perf_counter()-tracking_started
        r['tracking_updates']=updates;r['tracking_wall_s']=elapsed
        r['tracking_fps']=updates/elapsed if updates else None
        r['success']=len(r['frames'])==a.frames and all(f['success'] for f in r['frames'])
        if not r['success']:r['failure_reasons'].append('pose_threshold')
        # Retain GT/estimate frame transformation from the same capture.
        if a.pick=='on':
            from sim.control import Controller
            import inspect
            kwargs=dict(env=env)
            supports='gt_assist' in inspect.signature(Controller).parameters
            if supports:kwargs['gt_assist']=a.gt_assist=='on'
            elif a.gt_assist=='off':raise RuntimeError('GT-assist off API unavailable')
            ctl=Controller(env.model,env.data,**kwargs)
            estimated_world=env.T_world_cam()@latest
            obj=lambda:env.T_world_obj(full)
            picked=ctl.pick_object(estimated_world,env.registry[full].bounds,object_pose_fn=obj)
            r['pick_success']=bool(picked['ok']);r['pick_result']=picked
            if r['pick_success']:
                placed=ctl.place_object((.50,-.12 if estimated_world[1,3]>0 else .12),obj)
                r['place_result']=placed;r['place_success']=bool(placed['err_mm']<20 and placed['upright']>.95)
            else:r['place_success']=False
            if not r['pick_success']:r['failure_reasons'].append('pick_failure')
            elif not r['place_success']:r['failure_reasons'].append('place_failure')
    except Exception as exc:
        r['success']=False;r['failure_reasons'].append(f'{type(exc).__name__}: {exc}')
    finally:
        if env is not None:env.close()
    r['trial_wall_s']=time.perf_counter()-started
    r['missing_predictions']=max(0,a.frames-len(r['frames']))
    return r


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--perception',choices=['gt','fp'],default='gt');p.add_argument('--gt-assist',choices=['on','off'],default='on')
    p.add_argument('--objects',default='mustard,box,cup');p.add_argument('--n',type=int,default=5);p.add_argument('--seeds',help='comma-separated explicit seed list; must contain n seeds')
    p.add_argument('--seed',type=int,default=0);p.add_argument('--frames',type=int,default=5);p.add_argument('--pick',choices=['on','off'],default='off')
    p.add_argument('--width',type=int,default=640);p.add_argument('--height',type=int,default=480);p.add_argument('--out',required=True);p.add_argument('--save-replay',action='store_true')
    a=p.parse_args()
    names=a.objects.split(',')
    if a.n<1 or a.frames<1 or any(n not in NAMES for n in names):p.error('invalid n, frames, or object')
    seeds=[int(s) for s in a.seeds.split(',')] if a.seeds else list(range(a.seed,a.seed+a.n))
    if len(seeds)!=a.n or len(set(seeds))!=a.n:p.error('seeds must contain n distinct seeds')
    out=Path(a.out);out.mkdir(parents=True,exist_ok=False)
    git_hash=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    manifest=dict(config=vars(a),seeds=seeds,git_hash=git_hash,dirty=subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True),python=sys.version,gt_disclosure='GT supplies target identity and nearest-visible-centroid click only for fp; all GT poses score-only except explicitly enabled control assistance. SAM chooses argmax model score.')
    manifest['source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'eval/run_benchmark.py',*sorted((ROOT/'eval/harness').glob('*.py'))]}
    manifest['dependencies']={}
    for package in ['numpy','scipy','mujoco','torch','trimesh']:
        try:manifest['dependencies'][package]=importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:manifest['dependencies'][package]=None
    manifest['upstream_git']={}
    for dep in ['FoundationPose','sam2.1']:
        try:manifest['upstream_git'][dep]=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT/dep,text=True).strip()
        except Exception:manifest['upstream_git'][dep]=None
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    client=Client() if a.perception=='fp' else None
    try:
        with (out/'trials.jsonl').open('w') as f:
            for name in names:
                for seed in seeds:
                    r=trial(a,name,seed,client,git_hash)
                    f.write(json.dumps(r,default=lambda x:x.tolist() if isinstance(x,np.ndarray) else x.item() if isinstance(x,np.generic) else str(x))+'\n');f.flush()
                    print(name,seed,r['success'],r['failure_reasons'],flush=True)
    finally:
        if client:client.close()
    report(out)
if __name__=='__main__':main()
