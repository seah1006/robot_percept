"""CPU checks; independent verifier owns its own tests."""
import numpy as np
from eval.harness.metrics import wilson,score,diameter_mm
v=np.array([[x,y,z] for x in [-.025,.025] for y in [-.015,.015] for z in [-.01,.01]])
T=np.eye(4);R=T.copy();R[:2,:2]=[[-1,0],[0,-1]]
m=score(R,T,v,'box',diameter_mm(v))
assert m['success'] and m['symmetry_rotation_deg']<1e-6
assert abs(m['rotation_deg']-180)<1e-6
bad=T.copy();bad[0,3]=1
assert not score(bad,T,v,'box',diameter_mm(v))['success']
lo,hi=wilson(0,30);assert lo<1e-10 and 0<hi<.2
lo,hi=wilson(30,30);assert .8<lo<1 and abs(hi-1)<1e-10
print('metric checks PASS')

flip=T.copy();flip[:3,:3]=np.diag([1,-1,-1])
assert not score(flip,T,v,'mustard',diameter_mm(v))['success']
assert not score(flip,T,v,'cup',diameter_mm(v))['success']
assert score(flip,T,v,'box',diameter_mm(v))['symmetry_rotation_deg']<1e-6
