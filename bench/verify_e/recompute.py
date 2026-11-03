#!/usr/bin/env python3
"""V-E independent metric recompute. usage: recompute.py rows.jsonl mesh.obj  (needs fields pred_T, gt_T 4x4 lists, diameter_mm)"""
import sys, json, math, numpy as np
def verts(p): return np.array([[float(x) for x in l.split()[1:4]] for l in open(p) if l.startswith('v ')])
def wilson(k,n,z=1.96):
    if n==0: return (float('nan'),)*2
    p=k/n; d=1+z*z/n; c=p+z*z/(2*n); h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)); return ((c-h)/d,(c+h)/d)
def tf(T,v): T=np.array(T); return v@T[:3,:3].T+T[:3,3]
def add(p,g,v): return np.linalg.norm(tf(p,v)-tf(g,v),axis=1).mean()*1000
def adds(p,g,v):
    from scipy.spatial import cKDTree
    return cKDTree(tf(g,v)).query(tf(p,v))[0].mean()*1000
def rot(p,g):
    R=np.array(p)[:3,:3]@np.array(g)[:3,:3].T; return math.degrees(math.acos(max(-1,min(1,(np.trace(R)-1)/2))))
if __name__=='__main__':
    v=verts(sys.argv[2]); ok=n=0
    for l in open(sys.argv[1]):
        r=json.loads(l)
        if 'pred_T' not in r or 'gt_T' not in r: continue
        n+=1; a=adds(r['pred_T'],r['gt_T'],v); ok+=a<=0.1*r['diameter_mm']
        print(r.get('id'),'add',round(add(r['pred_T'],r['gt_T'],v),3),'adds',round(a,3),'rot',round(rot(r['pred_T'],r['gt_T']),3))
    print('success',ok,n,wilson(ok,n))