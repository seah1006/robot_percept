#!/usr/bin/env python3
"""6D pose errors: translation, rotation, ADD, ADD-S, and 10 cm AUC."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np


def load_vertices(path):
    vertices=[]
    with Path(path).open("r",errors="ignore") as f:
        for line in f:
            if line.startswith("v "):
                p=line.split(); vertices.append([float(p[1]),float(p[2]),float(p[3])])
    if not vertices: raise ValueError(f"No OBJ vertices found in {path}")
    return np.asarray(vertices,np.float64)

def translation_error_mm(pred,gt): return float(np.linalg.norm(np.asarray(pred)[:3,3]-np.asarray(gt)[:3,3])*1000)
def _project_so3(R):
    U,_,Vt=np.linalg.svd(np.asarray(R,dtype=float))
    Q=U@Vt
    if np.linalg.det(Q)<0: U[:,-1]*=-1; Q=U@Vt
    return Q

def rotation_error_deg(pred,gt):
    R=_project_so3(np.asarray(pred)[:3,:3])@_project_so3(np.asarray(gt)[:3,:3]).T
    return float(np.degrees(np.arccos(np.clip((np.trace(R)-1)/2,-1.,1.))))
def _transform(T,v): return (np.asarray(T)[:3,:3]@v.T).T+np.asarray(T)[:3,3]
def add_mm(pred,gt,vertices): return float(np.linalg.norm(_transform(pred,vertices)-_transform(gt,vertices),axis=1).mean()*1000)
def adds_mm(pred,gt,vertices,chunk=256):
    """Exact ADD-S nearest-neighbour distance (KD-tree, bounded fallback)."""
    a,b=_transform(pred,vertices),_transform(gt,vertices)
    try:
        from scipy.spatial import cKDTree
        distances=cKDTree(b).query(a,k=1,workers=-1)[0]
    except ImportError:
        mins=[]
        for i in range(0,len(a),chunk):
            d2=((a[i:i+chunk,None,:]-b[None,:,:])**2).sum(axis=2); mins.append(np.sqrt(d2.min(axis=1)))
        distances=np.concatenate(mins)
    return float(distances.mean()*1000)
def auc(errors_mm,max_mm=100.):
    """Normalized area under the empirical accuracy-threshold curve."""
    e=np.asarray(errors_mm,float)
    if not e.size: return float("nan")
    return float(1.-np.minimum(e,max_mm).mean()/max_mm)
def evaluate_pair(pred,gt,vertices):
    return {"translation_mm":translation_error_mm(pred,gt),"rotation_deg":rotation_error_deg(pred,gt),"add_mm":add_mm(pred,gt,vertices),"adds_mm":adds_mm(pred,gt,vertices)}
def _pose_dir(path):
    path=Path(path); return path/"ob_in_cam" if (path/"ob_in_cam").is_dir() else path
def evaluate_dirs(pred_dir,gt_dir,mesh):
    pd,gd=_pose_dir(pred_dir),_pose_dir(gt_dir); pf={p.stem:p for p in pd.glob("*.txt")}; gf={p.stem:p for p in gd.glob("*.txt")}; ids=sorted(pf.keys()&gf.keys())
    if not ids: raise FileNotFoundError(f"No matching *.txt pose names in {pd} and {gd}")
    vertices=load_vertices(mesh); frames=[]
    for stem in ids:
        pred=np.loadtxt(pf[stem]).reshape(4,4); gt=np.loadtxt(gf[stem]).reshape(4,4); frames.append({"id":stem,**evaluate_pair(pred,gt,vertices)})
    summary={"frames":len(frames),"missing_predictions":sorted(gf.keys()-pf.keys()),"extra_predictions":sorted(pf.keys()-gf.keys())}
    for key in ("translation_mm","rotation_deg","add_mm","adds_mm"):
        x=np.array([f[key] for f in frames]); summary[key]={"mean":float(x.mean()),"median":float(np.median(x))}
    summary["add_auc_10cm"]=auc([f["add_mm"] for f in frames]); summary["adds_auc_10cm"]=auc([f["adds_mm"] for f in frames])
    return {"per_frame":frames,"summary":summary}
def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("pred_dir",help="pose dir or FoundationPose debug dir containing ob_in_cam/"); p.add_argument("gt_dir",help="GT pose dir or exported scene"); p.add_argument("--mesh",required=True); p.add_argument("--out"); a=p.parse_args(); result=evaluate_dirs(a.pred_dir,a.gt_dir,a.mesh); text=json.dumps(result,indent=2)
    if a.out: Path(a.out).write_text(text)
    print(text)
if __name__=="__main__": main()
