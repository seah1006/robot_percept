"""Randomized Panda pick/place regression with CAD and mixed scenes.

Run: MUJOCO_GL=egl python tests/test_pick_place.py --trials 20
"""
import argparse
import json
import time
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np
from sim.env import SimEnv
from sim.control import Controller
from sim.grasp import choose_grasp

NAMES = ('mustard', 'box_fillet_50x30x20mm', 'cup_d70_h60mm')
STRIP = Path('/home/user/work/robot_percept/data/c1_check/multi_strip.png')

def run_one(env, ctl, name, xy):
    obj = lambda: env.T_world_obj(name)
    original = obj()
    start = time.perf_counter()
    try:
        result = ctl.pick_object(original, env.registry[name].bounds, object_pose_fn=obj)
        result['pick'] = bool(result['ok'])
        if result['pick']:
            place = ctl.place_object(xy, obj)
            result['place'] = bool(place['err_mm'] < 20 and place['upright'] > .95)
            result.update(place)
            if result['place']:
                home = ctl.return_home(obj)
                result['home'] = bool(home['joint_error'] < .02 and home['object_displacement'] < .005)
                result.update(home)
        else:
            result['place'] = False
    except Exception as exc:
        result = {'pick': False, 'place': False, 'error': str(exc)}
    result['elapsed_s'] = round(time.perf_counter()-start, 2)
    return result

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--trials', type=int, default=20)
    ap.add_argument('--no-gt-assist', action='store_true', help='disable grasp weld and true-pose motion corrections')
    ap.add_argument('--suite', choices=('all','single','multi','latency'), default='all')
    args = ap.parse_args()
    records = {}
    if args.suite in ('all','single'):
        for name in NAMES:
            rows=[]
            for seed in range(args.trials):
                with SimEnv(objects=(name,), seed=seed) as env:
                    ctl=Controller(env.model, env.data, env=env, gt_assist=not args.no_gt_assist)
                    pos=env.T_world_obj(name)[:2,3]
                    r=run_one(env,ctl,name,(.50,-.12 if pos[1]>0 else .12))
                    rows.append(r)
                    if not r['pick'] or not r['place']: print('FAIL',name,seed,r,flush=True)
            records[name]=rows
            print('SUMMARY',name, sum(r['pick'] for r in rows),'pick,',sum(r['place'] for r in rows),'place /',len(rows),flush=True)
    if args.suite in ('all','multi'):
        rows=[]
        for seed in range(args.trials):
            with SimEnv(objects=NAMES, seed=seed, width=480, height=360) as env:
                ctl=Controller(env.model,env.data,env=env, gt_assist=not args.no_gt_assist)
                frames=[]
                if seed==0: frames.append(env.render_rgbd()['rgb'])
                trial=[]
                # y=-.31 remains on the table and outside randomized spawn range.
                for name,xy in zip(NAMES, ((.48,-.29),(.56,-.29),(.50,.29))):
                    r=run_one(env,ctl,name,xy)
                    trial.append(r)
                    if seed==0: frames.append(env.render_rgbd()['rgb'])
                    if not r['pick'] or not r['place']: print('FAIL multi',seed,name,r,flush=True)
                rows.append(trial)
                if seed==0:
                    frame=np.concatenate(frames,axis=1)
                    cv2.imwrite(str(STRIP),cv2.cvtColor(frame,cv2.COLOR_RGB2BGR))
            print('MULTI TRIAL',seed,[(n,r['pick'],r['place']) for n,r in zip(NAMES,trial)],flush=True)
        records['multi']=rows
        for i,name in enumerate(NAMES):
            print('SUMMARY multi',name,sum(t[i]['pick'] for t in rows),'pick,',sum(t[i]['place'] for t in rows),'place /',len(rows),flush=True)
        print('SUMMARY multi all-three',sum(all(r['pick'] and r['place'] for r in t) for t in rows),'/',len(rows),flush=True)
    if args.suite in ('all','latency'):
        times={}
        for name in NAMES:
            ts=[]
            for seed in range(args.trials):
                with SimEnv(objects=(name,),seed=seed) as env:
                    t=time.perf_counter()
                    choose_grasp(env.model,env.data,env.T_world_obj(name),env.registry[name].bounds)
                    ts.append(time.perf_counter()-t)
            times[name]={'median_s':round(float(np.median(ts)),3),'p95_s':round(float(np.quantile(ts,.95)),3),'max_s':round(float(max(ts)),3)}
        print('LATENCY',json.dumps(times),flush=True)
    out=Path('/home/user/work/robot_percept/data/c1_check')
    out.mkdir(exist_ok=True)
    result_file = out/'results.json'
    previous = json.loads(result_file.read_text()) if result_file.exists() else {}
    previous.update({("off_" if args.no_gt_assist else "on_")+key: value for key,value in records.items()})
    result_file.write_text(json.dumps(previous,indent=2))

if __name__=='__main__': main()