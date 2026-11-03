"""Local point-to-plane RGB-D correction, no GT or object-specific offsets."""
import numpy as np
import cv2
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation


def refine_pose(mesh, pose, depth, mask, K):
    import trimesh
    # Large-object registration is left to FP. Small CAD depth has enough metric
    # precision to remove the network's few-mm translation bias.
    if np.linalg.norm(mesh.extents) > .12 or np.max(mesh.extents)/max(np.min(mesh.extents), 1e-6) < 1.8:
        return pose
    support = cv2.erode(np.asarray(mask, np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    y, x = np.where(support & np.isfinite(depth) & (depth > .001))
    if len(x) < 40:
        return pose
    ix = np.linspace(0, len(x)-1, min(1500,len(x))).astype(int)
    x,y=x[ix],y[ix]
    obs = (np.linalg.inv(K) @ np.stack([x,y,np.ones(len(x))])).T * depth[y,x,None]
    points, faces = trimesh.sample.sample_surface(mesh, 18000, seed=0)
    normals = mesh.face_normals[faces]
    tree = cKDTree(points)
    initial = np.asarray(pose).copy(); T=initial.copy()
    def matches(T):
        local=(obs-T[:3,3]) @ T[:3,:3]
        dist,j=tree.query(local)
        valid=dist < .008
        p=points[j] @ T[:3,:3].T + T[:3,3]
        n=normals[j] @ T[:3,:3].T
        residual=np.sum((obs-p)*n,axis=1)
        return p,n,residual,valid
    _,_,r,v=matches(T)
    if v.sum()<40: return initial
    before=np.median(np.abs(r[v]))
    for _ in range(8):
        p,n,r,v=matches(T)
        v &= np.abs(r)<.006
        if v.sum()<40: return initial
        # Rotate around the object center for well-conditioned metric increments.
        A=np.concatenate([np.cross(p[v]-T[:3,3],n[v]),n[v]],axis=1)
        weights=1/np.maximum(np.abs(r[v]),.0005)
        delta=np.linalg.lstsq(A*weights[:,None]**.5,r[v]*weights**.5,rcond=1e-4)[0]
        if np.linalg.norm(delta[:3])>.1 or np.linalg.norm(delta[3:])>.005: return initial
        T[:3,:3]=Rotation.from_rotvec(delta[:3]).as_matrix() @ T[:3,:3]
        T[:3,3]+=delta[3:]
        if np.linalg.norm(delta[3:])<1e-6: break
    _,_,r,v=matches(T)
    if v.sum()<40 or np.median(np.abs(r[v]))>before or np.linalg.norm(T[:3,3]-initial[:3,3])>.01:
        return initial
    return T
