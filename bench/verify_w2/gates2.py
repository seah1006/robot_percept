import sys, numpy as np, json
sys.path.insert(0,'bench/verify_w2')
import verify_w2 as V
from perception.localize import Localizer
size=(1280,720); K=np.array([[900.,0,639.5],[0,900.,359.5],[0,0,1]]); out={}
def probe(h,d):
    T=V.lookat_cv([0,0,.30+h],[d,0,.30]); cam=V.make_cam(K,T,size); L=Localizer(cam)
    r=L.localize(V.det(cam,size,(620,300,660,360)),anchor=(639.5,359.5))
    return r.error or ('OK x=%.3f'%r.xyz_m[0])
for ang in (8,9.5,10.5,12):
    h=.3; d=h/np.tan(np.radians(ang)); out['incidence_%.1fdeg slant=%.2fm'%(ang,np.hypot(h,d))]=probe(h,d)
for s in (2.9,3.1):
    h=1.0; d=np.sqrt(s*s-h*h); out['slant_%.1fm (incidence %.0fdeg)'%(s,np.degrees(np.arctan2(h,d)))]=probe(h,d)
print(json.dumps(out,indent=1)); json.dump(out,open('bench/verify_w2/out_gates2.json','w'),indent=1)
