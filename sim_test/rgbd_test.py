"""MuJoCo offscreen RGB-D test for one MUJOCO_GL backend.
usage: VARIANT=egl MUJOCO_GL=egl python rgbd_test.py
writes results/<VARIANT>.json and results/<VARIANT>/ images
"""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

VARIANT = os.environ.get("VARIANT", os.environ.get("MUJOCO_GL", "default"))
HERE = Path(__file__).resolve().parent
OUTD = HERE / "results" / VARIANT
OUTD.mkdir(parents=True, exist_ok=True)
res = dict(variant=VARIANT, MUJOCO_GL=os.environ.get("MUJOCO_GL"),
           env={k: os.environ.get(k) for k in ("GALLIUM_DRIVER", "MESA_D3D12_DEFAULT_ADAPTER_NAME",
                                                "PYOPENGL_PLATFORM", "DISPLAY", "LIBGL_ALWAYS_SOFTWARE")})


def dump():
    (HERE / "results" / f"{VARIANT}.json").write_text(json.dumps(res, indent=2, default=float))


try:
    import cv2
    import mujoco

    m = mujoco.MjModel.from_xml_path(str(HERE / "scene_panda.xml"))
    if os.environ.get("ZNEAR"):
        m.vis.map.znear = float(os.environ["ZNEAR"])
    if os.environ.get("ZFAR"):
        m.vis.map.zfar = float(os.environ["ZFAR"])
    res["znear_zfar_rel"] = [float(m.vis.map.znear), float(m.vis.map.zfar)]
    _Renderer = mujoco.Renderer

    def make_renderer(mm, h, w):
        rr_ = _Renderer(mm, h, w)
        if os.environ.get("NOSHADOW") == "1":
            rr_.scene.flags[mujoco.mjtRndFlag.mjRND_SHADOW] = False
        if os.environ.get("NOREFLECT") == "1":
            rr_.scene.flags[mujoco.mjtRndFlag.mjRND_REFLECTION] = False
        return rr_
    res["noshadow"] = os.environ.get("NOSHADOW") == "1"
    res["noreflect"] = os.environ.get("NOREFLECT") == "1"
    d = mujoco.MjData(m)
    mujoco.mj_resetDataKeyframe(m, d, m.key("home").id)
    for _ in range(300):  # let the object settle on the table
        mujoco.mj_step(m, d)
    mujoco.mj_forward(m, d)
    cam = "rgbd"
    cid = m.camera(cam).id
    obj_bid = m.body("obj").id
    obj_gid = m.geom("obj_geom").id

    # ---------------- GL info
    t0 = time.perf_counter()
    r = make_renderer(m, 480, 640)
    res["context_create_s"] = round(time.perf_counter() - t0, 3)
    try:
        from OpenGL.GL import GL_RENDERER, GL_VENDOR, GL_VERSION, glGetString
        r._gl_context.make_current()
        res["gl_vendor"] = glGetString(GL_VENDOR).decode()
        res["gl_renderer"] = glGetString(GL_RENDERER).decode()
        res["gl_version"] = glGetString(GL_VERSION).decode()
    except Exception as e:  # noqa
        res["gl_renderer"] = f"unknown ({type(e).__name__}: {str(e)[:120]})"
    r.close()

    # ---------------- benchmark
    N = int(os.environ.get("N", "60"))
    bench = {}
    for (h, w) in [(480, 640), (720, 1280)]:
        rr = make_renderer(m, h, w)
        for mode in ("rgb", "depth", "rgb+depth"):
            def one():
                if mode in ("rgb", "rgb+depth"):
                    rr.disable_depth_rendering()
                    rr.update_scene(d, camera=cam)
                    rr.render()
                if mode in ("depth", "rgb+depth"):
                    rr.enable_depth_rendering()
                    rr.update_scene(d, camera=cam)
                    rr.render()
            for _ in range(3):
                one()
            t = time.perf_counter()
            for _ in range(N):
                one()
            bench[f"{w}x{h} {mode}"] = round(N / (time.perf_counter() - t), 1)
        rr.disable_depth_rendering()
        rr.close()
    res["fps"] = bench

    # ---------------- capture 640x480 rgb / depth / segmentation + 1280x720 rgb
    H, W = 480, 640
    rr = make_renderer(m, H, W)
    rr.update_scene(d, camera=cam)
    rgb = rr.render().copy()
    rr.enable_depth_rendering()
    rr.update_scene(d, camera=cam)
    depth = rr.render().copy()  # mujoco.Renderer already linearizes to metres (near/far = znear/zfar * extent)
    rr.disable_depth_rendering()
    rr.enable_segmentation_rendering()
    rr.update_scene(d, camera=cam)
    seg = rr.render().copy()  # [...,0]=object id, [...,1]=object type
    rr.disable_segmentation_rendering()
    rr.close()
    r7 = make_renderer(m, 720, 1280)
    r7.update_scene(d, camera=cam)
    cv2.imwrite(str(OUTD / "rgb_1280x720.png"), cv2.cvtColor(r7.render(), cv2.COLOR_RGB2BGR))
    r7.update_scene(d, camera="wrist")
    cv2.imwrite(str(OUTD / "wrist_rgb_1280x720.png"), cv2.cvtColor(r7.render(), cv2.COLOR_RGB2BGR))
    r7.close()

    extent = float(m.stat.extent)
    near, far = m.vis.map.znear * extent, m.vis.map.zfar * extent
    res["depth_near_far_m"] = [near, far]
    obj_mask = (seg[..., 0] == obj_gid) & (seg[..., 1] == int(mujoco.mjtObj.mjOBJ_GEOM))

    # ---------------- intrinsics / extrinsics (OpenCV convention)
    fovy = float(m.cam_fovy[cid])
    fy = 0.5 * H / np.tan(np.deg2rad(fovy) / 2)
    fx = fy
    cx, cy = (W - 1) / 2, (H - 1) / 2
    K = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1.0]])
    t_wc = d.cam_xpos[cid].copy()
    R_gl = d.cam_xmat[cid].reshape(3, 3).copy()          # camera(GL: x right, y up, z back) -> world
    R_cv = R_gl @ np.diag([1.0, -1.0, -1.0])             # camera(CV: x right, y down, z fwd) -> world
    T_wc = np.eye(4); T_wc[:3, :3] = R_cv; T_wc[:3, 3] = t_wc

    obj_pos = d.xpos[obj_bid].copy()
    obj_quat = d.xquat[obj_bid].copy()                   # w x y z
    T_wo = np.eye(4); T_wo[:3, :3] = d.xmat[obj_bid].reshape(3, 3); T_wo[:3, 3] = obj_pos
    T_co = np.linalg.inv(T_wc) @ T_wo                   # GT object pose in camera frame (what FoundationPose outputs)

    # ---------------- verification
    def pix_ray_world(u, v):
        dc = np.array([(u - cx) / fx, (v - cy) / fy, 1.0])
        return dc, R_cv @ dc

    # (a) projection of GT centre lands on the object mask
    pc = R_cv.T @ (obj_pos - t_wc)
    u0, v0 = fx * pc[0] / pc[2] + cx, fy * pc[1] / pc[2] + cy
    ui, vi = int(round(u0)), int(round(v0))
    res["gt_center_pixel"] = [round(u0, 2), round(v0, 2)]
    res["gt_center_pixel_on_obj_mask"] = bool(obj_mask[vi, ui])
    mask_c = np.argwhere(obj_mask).mean(0)[::-1] if obj_mask.any() else [np.nan, np.nan]
    res["obj_mask_pixels"] = int(obj_mask.sum())
    res["obj_mask_centroid_px"] = [round(float(mask_c[0]), 2), round(float(mask_c[1]), 2)]

    # (b) depth vs exact ray cast (mj_ray, visible geom groups 0-2) on random pixels + object centre pixel
    gg = np.array([1, 1, 1, 0, 0, 0], np.uint8)
    gid = np.zeros(1, np.int32)
    rng = np.random.default_rng(0)
    pts = [(ui, vi)] + [(int(rng.integers(0, W)), int(rng.integers(0, H))) for _ in range(400)]
    errs = []
    for (u, v) in pts:
        dc, dw = pix_ray_world(u, v)
        n = np.linalg.norm(dw)
        dist = mujoco.mj_ray(m, d, t_wc, dw / n, gg, 1, -1, gid)
        if dist < 0 or depth[v, u] > 0.9 * far:
            continue
        z_ray = dist / n                                   # distance along unit dir -> z (planar depth)
        errs.append(abs(z_ray - depth[v, u]))
        if (u, v) == (ui, vi):
            P_depth = t_wc + dw * depth[v, u]
            P_ray = t_wc + dw / n * dist
            res["center_pixel"] = dict(depth_m=float(depth[v, u]), ray_z_m=float(z_ray),
                                       backproj_vs_ray_mm=float(1000 * np.linalg.norm(P_depth - P_ray)),
                                       backproj_vs_gt_center_mm=float(1000 * np.linalg.norm(P_depth - obj_pos)),
                                       ray_hit_geom=mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_GEOM, int(gid[0])))
    errs = np.array(errs)
    res["depth_vs_raycast_mm"] = dict(n=int(len(errs)), mean=float(1000 * errs.mean()),
                                      p95=float(1000 * np.percentile(errs, 95)), max=float(1000 * errs.max()))

    # (c) visible-surface centroid from object mask (back-projected) vs GT centre
    vv, uu = np.nonzero(obj_mask)
    z = depth[vv, uu]
    Pc = np.stack([(uu - cx) / fx * z, (vv - cy) / fy * z, z], 1)
    Pw = (R_cv @ Pc.T).T + t_wc
    res["visible_surface_centroid_vs_gt_mm"] = float(1000 * np.linalg.norm(Pw.mean(0) - obj_pos))
    res["obj_size_m"] = [2 * float(x) for x in m.geom_size[obj_gid]]

    # ---------------- save artefacts
    cv2.imwrite(str(OUTD / "rgb.png"), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    np.save(OUTD / "depth_m.npy", depth.astype(np.float32))
    valid = depth < 0.9 * far
    dn = np.zeros_like(depth)
    lo, hi = depth[valid].min(), depth[valid].max()
    dn[valid] = (depth[valid] - lo) / (hi - lo)
    dc = cv2.applyColorMap((255 * (1 - dn)).astype(np.uint8), cv2.COLORMAP_TURBO)
    dc[~valid] = 0
    cv2.putText(dc, f"depth {lo:.2f}-{hi:.2f} m", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.imwrite(str(OUTD / "depth_color.png"), dc)
    cv2.imwrite(str(OUTD / "obj_mask.png"), obj_mask.astype(np.uint8) * 255)
    cam_json = dict(width=W, height=H, fovy_deg=fovy, K=K.tolist(),
                    T_world_cam_opencv=T_wc.tolist(), cam_pos=t_wc.tolist(),
                    depth_units="metres (planar z)", depth_near_far_m=[near, far])
    gt_json = dict(obj_pos_world=obj_pos.tolist(), obj_quat_world_wxyz=obj_quat.tolist(),
                   T_world_obj=T_wo.tolist(), T_cam_obj_opencv=T_co.tolist(), obj_size_m=res["obj_size_m"])
    (OUTD / "camera.json").write_text(json.dumps(cam_json, indent=2))
    (OUTD / "gt_pose.json").write_text(json.dumps(gt_json, indent=2))
    res["K"] = K.round(3).tolist()
    res["T_world_cam_opencv"] = T_wc.round(4).tolist()
    res["obj_pos_world"] = obj_pos.round(4).tolist()
    res["ok"] = True
except Exception as e:  # noqa
    import traceback
    res["ok"] = False
    res["error"] = f"{type(e).__name__}: {e}"
    res["trace"] = traceback.format_exc()[-1500:]
dump()
print(json.dumps({k: res.get(k) for k in ("variant", "ok", "gl_renderer", "fps", "error", "depth_vs_raycast_mm", "znear_zfar_rel", "depth_near_far_m")}, default=float))
