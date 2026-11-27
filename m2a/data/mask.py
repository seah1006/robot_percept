"""Rasterize the GT 3D box silhouette without segmentation or occlusion masking."""
from itertools import product
import numpy as np

_SIGNS = np.array(list(product((-1, 1), repeat=3)))
_EDGES = [(i, j) for i in range(8) for j in range(i+1, 8)
          if np.count_nonzero(_SIGNS[i] != _SIGNS[j]) == 1]


def box_size(part):
    if part['shape'] == 'box':
        return np.asarray(part['size'], float)
    radius, height = part['size']
    return np.array([2*radius, 2*radius, height])


def _hull(points):
    pts = sorted(set(map(tuple, points)))
    def half(seq):
        out = []
        for p in seq:
            while len(out) >= 2:
                a,b = out[-2:]
                if (b[0]-a[0])*(p[1]-a[1]) > (b[1]-a[1])*(p[0]-a[0]):
                    break
                out.pop()
            out.append(p)
        return out[:-1]
    return half(pts) + half(reversed(pts))


def project_box(center, rotation, size, K, T_table_cam, shape=(256,256), near=1e-4):
    """Return (HxWx1 uint8 0/255, mask_lost). Rotation maps local box to table.

    Clip edges at the positive camera near plane (0.1 mm, arbitrary), then
    rasterize the convex hull at integer-indexed pixel centers; no depth test.
    """
    center, rotation, size, K, T = map(np.asarray, (center, rotation, size, K, T_table_cam))
    if near <= 0 or np.any(size <= 0) or not all(np.isfinite(a).all() for a in (center, rotation, size, K, T)):
        raise ValueError('Invalid box or calibration')
    corners = (_SIGNS * (size/2)) @ rotation.T + center
    cam = (corners - T[:3,3]) @ T[:3,:3]
    keep = cam[:,2] >= near
    pts = list(cam[keep])
    for i,j in _EDGES:
        if keep[i] != keep[j]:
            a,b = cam[[i,j]]
            pts.append(a + (near-a[2])/(b[2]-a[2])*(b-a))
    out = np.zeros((*shape, 1), dtype=np.uint8)
    if not pts:
        return out, True
    uvw = np.asarray(pts) @ K.T
    hull = _hull(uvw[:,:2] / uvw[:,2,None])
    if len(hull) < 3:
        return out, True
    polygon = np.asarray(hull)
    x0,y0 = np.maximum(0,np.ceil(polygon.min(0))).astype(int)
    x1,y1 = np.minimum(np.array(shape[::-1])-1,np.floor(polygon.max(0))).astype(int)
    if x0 > x1 or y0 > y1:
        return out, True
    x,y = np.arange(x0,x1+1)[None,:], np.arange(y0,y1+1)[:,None]
    inside = np.ones((y1-y0+1,x1-x0+1), bool)
    for a,b in zip(polygon,np.roll(polygon,-1,axis=0),strict=True):
        dx,dy = b-a
        inside &= dx*(y-a[1]) - dy*(x-a[0]) >= -1e-8
    out[y0:y1+1,x0:x1+1,0] = inside*255
    return out, not inside.any()


def wrist_gt_mask(env, oid, cam):
    """Use MuJoCo's full GT body pose, including tilt during the lift."""
    body = env.data.body(env.object_bodies[oid])
    R = env.T_world_table[:3,:3].T @ body.xmat.reshape(3,3)
    return project_box(env.to_table(body.xpos), R, box_size(env.parts[env.object_parts[oid]]),
                       env.camera_K(cam), env.T_table_cam(cam))
