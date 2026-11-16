import sys, numpy as np, cv2, json
sys.path.insert(0,'bench/verify_w2'); sys.path.insert(0,'tools')
import verify_w2 as V, calibrate_camera as cc
from perception.localize import Localizer
size=(1280,720); K=np.array([[1010.,0,648],[0,1003.,352],[0,0,1]]); out={}
def run(name, views):
    try: m,r=cc.estimate(views,(9,6),.025); out[name]='ACCEPT rms=%.3f'%r['rms_px']
    except Exception as e: out[name]='REJECT '+repr(e)[:90]
def mk(n,rscale,tspread=.0,noise=0.,blur=0.):
    v=[]
    for i in range(n):
        r=np.array([V.rng.uniform(-1,1)*rscale,V.rng.uniform(-1,1)*rscale,V.rng.uniform(-1,1)*.1]); t=np.array([-.11+V.rng.uniform(-1,1)*tspread,-.06+V.rng.uniform(-1,1)*tspread,.58+V.rng.uniform(-1,1)*tspread])
        v.append(V.render_board(K,(r,t),size,(9,6),.025,None,noise,blur))
    return v
run('good_diverse_rot0.5', mk(10,.5,.05))
run('near_identical_poses', mk(10,.01,.002))
run('small_rot_0.05rad(~3deg)', mk(10,.05,.05))
run('rot_0.12rad', mk(10,.12,.05))
run('heavy_noise_sigma25_blur3', mk(10,.5,.05,25,3))
run('too_few_5', mk(5,.5,.05))
# incidence gate: camera at height H, ground distance D -> incidence angle from plane
for ang in (8,9.5,10.5,12):
    d=1.0/np.tan(np.radians(ang)); T=V.lookat_cv([0,0,1.30],[d,0,.30]); cam=V.make_cam(np.array([[900.,0,639.5],[0,900.,359.5],[0,0,1]]),T,size); L=Localizer(cam)
    r=L.localize(V.det(cam,size,(620,300,660,360)),anchor=(639.5,359.5)); out['incidence_%.1fdeg(range %.1fm)'%(ang,d/np.cos(0)*1.0)]=r.error or ('OK '+str(np.round(r.xyz_m,2).tolist()))
for rng_ in (2.9,3.1):
    T=V.lookat_cv([0,0,1.30],[rng_*.8,0,.30]); cam=V.make_cam(np.array([[900.,0,639.5],[0,900.,359.5],[0,0,1]]),T,size); L=Localizer(cam)
    r=L.localize(V.det(cam,size,(620,300,660,360)),anchor=(639.5,359.5)); out['range_target_%.1f'%rng_]=r.error or 'OK x=%.2f'%r.xyz_m[0]
print(json.dumps(out,indent=1)); json.dump(out,open('bench/verify_w2/out_gates.json','w'),indent=1)
