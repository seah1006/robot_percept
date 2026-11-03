"""On-demand selected-object inspection; no producer runs without a viewer."""
from pathlib import Path
import threading, time
import cv2
import numpy as np
from flask import Blueprint, current_app, jsonify, Response, abort, send_file

focus = Blueprint("focus", __name__)
_cache_lock = threading.Lock()
_cache = {}

def runtime():
    return current_app.extensions["sim_runtime"]

def selected(rt):
    with rt.state_lock:
        return rt.selected, None if rt.estimate is None else np.asarray(rt.estimate).copy(), None if rt.mask is None else rt.mask.copy(), rt.generation

@focus.get("/focus/status")
def focus_status():
    rt = runtime(); name, est, _, generation = selected(rt); st = dict(rt.status)
    obj = st.get("objects", {}).get(name)
    if not obj:
        return jsonify(selected=None, generation=generation)
    world = np.asarray(st["T_world_cam"]) @ est if est is not None else None
    rpy = None
    if world is not None:
        r = world[:3, :3]
        rpy = np.degrees([np.arctan2(r[2,1], r[2,2]), np.arctan2(-r[2,0], np.hypot(r[0,0],r[1,0])), np.arctan2(r[1,0],r[0,0])]).tolist()
    return jsonify(selected=name, generation=generation, size_mm=(np.asarray(obj["extents"])*1000).tolist(),
                   T_world_obj_est=None if world is None else world.tolist(), rpy_deg=rpy,
                   mesh_url=f"/objects/{name}/mesh/{Path(obj['mesh']).name}",
                   grasp_mode=st.get("grasp_mode") or st.get("grasp_assist_mode"))

@focus.get("/objects/<name>/mesh/<path:filename>")
def mesh_file(name, filename):
    obj = dict(runtime().status).get("objects", {}).get(name)
    if not obj: abort(404)
    root = Path(obj["mesh"]).resolve().parent
    target = (root / filename).resolve()
    if not target.is_relative_to(root) or target.suffix.lower() not in {".obj", ".mtl", ".png", ".jpg", ".jpeg", ".webp"} or not target.is_file():
        abort(404)
    return send_file(target, conditional=True)

@focus.get("/focus.jpg")
def focus_jpg():
    rt = runtime(); name, est, mask, generation = selected(rt)
    if not name: return Response(status=204)
    # Share one JPEG among simultaneous clients for 125 ms. No background thread.
    with _cache_lock:
        key = (id(rt), name, generation)
        cached = _cache.get(key)
        if cached and time.monotonic()-cached[0] < .125:
            return Response(cached[1], mimetype="image/jpeg", headers={"Cache-Control":"no-store"})
        st = dict(rt.status); rgb = rt.frame(rgb_only=True); h,w = rgb.shape[:2]
        obj = st.get("objects", {}).get(name, {}); points = None
        # Projection follows the CURRENT estimated pose, unlike the registration mask.
        if est is not None and obj.get("bounds") is not None:
            b = np.asarray(obj["bounds"])
            corners = np.array([[b[i,0],b[j,1],b[k,2]] for i in (0,1) for j in (0,1) for k in (0,1)])
            cam = corners @ est[:3,:3].T + est[:3,3]
            if np.all(cam[:,2] > .001):
                uv = cam @ np.asarray(st["camera_K"]).T
                points = uv[:,:2]/uv[:,2:3]
        visible = np.zeros((h,w), np.uint8)
        if points is not None and np.isfinite(points).all():
            points = np.clip(points, -10000,10000).astype(np.int32)
            cv2.fillConvexPoly(visible, cv2.convexHull(points), 255)
        elif mask is not None and mask.shape == (h,w):
            visible[mask.astype(bool)] = 255
        ys,xs = np.where(visible)
        if not len(xs): return Response(status=204)
        x0,x1,y0,y1 = int(xs.min()),int(xs.max()),int(ys.min()),int(ys.max())
        px,py = max(12,int((x1-x0)*.3)),max(12,int((y1-y0)*.3))
        x0,x1,y0,y1 = max(0,x0-px),min(w,x1+px+1),max(0,y0-py),min(h,y1+py+1)
        image = cv2.cvtColor(rgb[y0:y1,x0:x1],cv2.COLOR_RGB2BGR)
        region = visible[y0:y1,x0:x1]
        image[region==0] = (image[region==0]*.3).astype(np.uint8)
        contours,_ = cv2.findContours(region,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(image,contours,-1,(153,255,90),1,cv2.LINE_AA)
        scale = min(1.,480/max(image.shape[:2])); image = cv2.resize(image,None,fx=scale,fy=scale)
        ok,jpg = cv2.imencode(".jpg",image,[cv2.IMWRITE_JPEG_QUALITY,80])
        if not ok: abort(503)
        data = jpg.tobytes(); _cache.clear(); _cache[key] = (time.monotonic(),data)
        return Response(data,mimetype="image/jpeg",headers={"Cache-Control":"no-store", "X-Focus-Outline":"estimated-bbox" if points is not None else "mask"})
