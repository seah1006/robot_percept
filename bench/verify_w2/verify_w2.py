"""V-W2 independent verification. Usage: python bench/verify_w2/verify_w2.py {A|B|C|D|E}
A projection round trip / error codes, B unflip+scale, C checkerboard calibration, D sim eval, E DTO contract.
Independent of I-W2 test/bench code: own camera, own renderer, own GT projection."""
import sys, json, math, time
from pathlib import Path
import numpy as np, cv2
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from perception.interfaces import CameraModel, Detection, FrameMeta, ErrorCode, unflip_center, unflip_box, Localization
from perception.localize import Localizer
import perception.preview_transform as pt
OUT = Path(__file__).parent
rng = np.random.default_rng(20261116)

def pct(a):
    a = np.asarray(a, float)
    return dict(n=int(a.size), p50=float(np.percentile(a, 50)), p95=float(np.percentile(a, 95)), max=float(a.max()), mean=float(a.mean()))

def lookat_cv(eye, target, up=(0, 0, 1.)):
    eye = np.asarray(eye, float); z = np.asarray(target, float) - eye; z /= np.linalg.norm(z)
    xr = np.cross(z, up); xr /= np.linalg.norm(xr); yd = np.cross(z, xr)
    T = np.eye(4); T[:3, :3] = np.stack([xr, yd, z], 1); T[:3, 3] = eye; return T

def make_cam(K, T, size, dist=(0., 0., 0., 0., 0.), plane=(0, 0, 1, -.30), cid='cal_v'):
    fov = tuple(float(np.degrees(2 * np.arctan(size[i] / (2 * K[i, i])))) for i in range(2))
    return CameraModel(cid, tuple(map(tuple, K)), tuple(dist), tuple(map(tuple, T)), tuple(plane), tuple(size), (0, 0, *size), fov, 'offline')

def meta(cam, size, cid='same', mirrored=False, overlay=False):
    return FrameMeta('f1', 0, 'test', 1.0, 1.0, mirrored, cam.calibration_id if cid == 'same' else cid, size[0], size[1], overlay)

def det(cam, size, box, cls='mug', **kw):
    return Detection('d', 'q', cls, .9, tuple(box), meta(cam, size, **{k: v for k, v in kw.items() if k in ('cid', 'mirrored', 'overlay')}),
                     kw.get('error'))

def project(K, T, dist, X):  # independent numpy pinhole + cv2 distortion
    Tc = np.linalg.inv(T); r = cv2.Rodrigues(Tc[:3, :3])[0]
    return cv2.projectPoints(np.asarray(X, float).reshape(-1, 1, 3), r, Tc[:3, 3], K, np.asarray(dist, float))[0].reshape(-1, 2)

def A():
    res = {}
    size = (1280, 720); K = np.array([[900., 0, 639.5], [0, 905., 359.5], [0, 0, 1]])
    T = lookat_cv([1.35, .05, .95], [.55, 0, .30])
    for tag, dist in [('nodist', (0, 0, 0, 0, 0)), ('dist', (-.18, .06, .0008, -.0006, 0.))]:
        cam = make_cam(K, T, size, dist); L = Localizer(cam)
        pts = []
        while len(pts) < 3000:
            p = np.array([rng.uniform(.38, .75), rng.uniform(-.3, .3), .30])
            uv = project(K, T, dist, [p])[0]
            if 25 < uv[0] < 1255 and 25 < uv[1] < 695: pts.append(p)
        pts = np.array(pts); uv = project(K, T, dist, pts)
        errs = []; errs_int = []
        for p, q in zip(pts, uv):  # bottom contact, anchor given via box so box default path is exercised
            box = (q[0] + .5 - 20, q[1] + .5 - 30, q[0] + .5 + 20, q[1] + .5)
            r = L.localize(det(cam, size, box)); assert r.error is None, r
            errs.append(np.linalg.norm(np.array(r.xyz_m) - p) * 1e3)
            qi = np.round(q)
            box = (qi[0] + .5 - 20, qi[1] + .5 - 30, qi[0] + .5 + 20, qi[1] + .5)
            r = L.localize(det(cam, size, box)); errs_int.append(np.linalg.norm(np.array(r.xyz_m) - p) * 1e3)
        res[tag + '_bottom_roundtrip_mm'] = pct(errs); res[tag + '_bottom_int_pixel_rounding_mm'] = pct(errs_int)
        # top_center with height correction ON / OFF
        for cls, h in [('mug', .06), ('mustard', .191408), ('block', .045)]:
            e_on = []; e_off = []; bias_ex = []
            for p, in zip(pts[:600]):
                top = p + [0, 0, h]; q = project(K, T, dist, [top])[0]
                if not (0 <= q[0] < 1280 and 0 <= q[1] < 720): continue
                box = (max(q[0] - 20, 0), max(q[1] - 5, 0), min(q[0] + 20, 1280), min(q[1] + 30, 720))
                r_on = L.localize(det(cam, size, box, cls), anchor=q, anchor_kind='top_center')
                r_off = L.localize(det(cam, size, box, cls), anchor=q, anchor_kind='top_center', height_correction=False)
                assert r_on.error is None and r_off.error is None, (r_on, r_off)
                e_on.append(np.linalg.norm(np.array(r_on.xyz_m) - p) * 1e3)
                # expected OFF = ray through top pixel hitting plane z=.30, independent numpy
                nd = cv2.undistortPoints(q.reshape(1, 1, 2), K, np.array(dist)).reshape(2)
                d = T[:3, :3] @ np.array([*nd, 1.]); o = T[:3, 3]
                hit = o + (.30 - o[2]) / d[2] * d
                e_off.append(np.linalg.norm(np.array(r_off.xyz_m) - hit) * 1e3)  # should be 0 (matches independent)
                bias_ex.append(np.linalg.norm(hit - p) * 1e3)
            res[f'{tag}_top_{cls}'] = {'ON_err_mm': pct(e_on), 'OFF_vs_independent_hit_mm': pct(e_off), 'OFF_true_bias_mm': pct(bias_ex)}
    # T_base_world rigid
    cam = make_cam(K, T, size); a = rng.uniform(-1, 1, 3); Rb = cv2.Rodrigues(a)[0]; Tb = np.eye(4); Tb[:3, :3] = Rb; Tb[:3, 3] = [.1, -.2, .3]
    L0 = Localizer(cam); L1 = Localizer(cam, T_base_world=Tb)
    p = np.array([.55, .1, .30]); q = project(K, T, (0,) * 5, [p])[0]
    box = (q[0] + .5 - 20, q[1] + .5 - 30, q[0] + .5 + 20, q[1] + .5)
    r0 = np.array(L0.localize(det(cam, size, box)).xyz_m); r1 = np.array(L1.localize(det(cam, size, box)).xyz_m)
    res['base_transform_err_mm'] = float(np.linalg.norm(Tb[:3, :3] @ r0 + Tb[:3, 3] - r1) * 1e3)
    # tilted/non-horizontal plane (plane normal tilted, offset)
    n = np.array([.05, -.03, 1.]); n /= np.linalg.norm(n); P0 = np.array([.55, 0, .30]); plane = (*n, -float(n @ P0))
    camT = make_cam(K, T, size, plane=plane); LT = Localizer(camT); ok = []
    for _ in range(300):
        s = rng.uniform(-.15, .15, 2); basis = np.cross(n, [1, 0, 0]); basis /= np.linalg.norm(basis); b2 = np.cross(n, basis)
        X = P0 + s[0] * basis + s[1] * b2; q = project(K, T, (0,) * 5, [X])[0]
        box = (q[0] + .5 - 20, q[1] + .5 - 30, q[0] + .5 + 20, q[1] + .5)
        ok.append(np.linalg.norm(np.array(LT.localize(det(camT, size, box)).xyz_m) - X) * 1e3)
    res['tilted_plane_mm'] = pct(ok)
    # error codes
    cam = make_cam(K, T, size); L = Localizer(cam); q = project(K, T, (0,) * 5, [[.55, 0, .30]])[0]
    box = (q[0] - 20, q[1] - 30, q[0] + 20, q[1])
    codes = {}
    def code(name, r): codes[name] = r.error or ('OK flags=' + ','.join(r.quality_flags))
    code('ok', L.localize(det(cam, size, box)))
    code('cal_id_mismatch', L.localize(det(cam, size, box, cid='other')))
    code('size_mismatch', L.localize(Detection('d', 'q', 'mug', .9, (10, 10, 50, 50), FrameMeta('f', 0, 's', 1., 1., False, cam.calibration_id, 640, 360, False))))
    code('mirrored', L.localize(det(cam, size, box, mirrored=True)))
    code('overlay', L.localize(det(cam, size, box, overlay=True)))
    code('det_error_NO_DETECTION', L.localize(det(cam, size, box, error='NO_DETECTION')))
    code('unknown_class', L.localize(det(cam, size, box, cls='zzz')))
    code('anchor_outside', L.localize(det(cam, size, box), anchor=(2000, 100)))
    code('anchor_nan', L.localize(det(cam, size, box), anchor=(float('nan'), 100)))
    code('top_center_no_anchor', L.localize(det(cam, size, box), anchor_kind='top_center'))
    code('bad_anchor_kind', L.localize(det(cam, size, box), anchor_kind='x'))
    code('above_horizon', L.localize(det(cam, size, (600, 0, 640, 10)), anchor=(620, 2)))
    code('capture_at_none', L.localize(Detection('d', 'q', 'mug', .9, box, FrameMeta('f', 0, 's', None, 1., False, cam.calibration_id, 1280, 720, False))))
    code('anchor_on_edge_1280', L.localize(det(cam, size, box), anchor=(1280., 100)))
    code('anchor_just_inside', L.localize(det(cam, size, box), anchor=(1279.99, 719.99)))
    res['codes'] = codes
    r = L.localize(det(cam, size, box)); res['dto_fields'] = r.to_dict()
    res['gt_assist'] = r.gt_assist
    json.dump(res, open(OUT / 'out_A.json', 'w'), indent=1, default=float); print(json.dumps(res, indent=1, default=float))

def B():
    res = {}
    orig = (1280, 720); prev = (640, 360)
    # (1) algebra: all integer preview pixels roundtrip, borders
    e = 0
    for u in list(range(0, 640)) + [639]:
        for v in (0, 1, 179, 359):
            o = pt.preview_point_to_original((u, v)); b = pt.original_point_to_preview(o)
            e = max(e, abs(b[0] - u), abs(b[1] - v))
    res['point_roundtrip_max_px'] = e
    res['border'] = {'prev(0,0)->orig': pt.preview_point_to_original((0, 0)), 'prev(639,359)->orig': pt.preview_point_to_original((639, 359)),
                     'prev(0,0) nomirror': pt.preview_point_to_original((0, 0), mirrored=False), 'interfaces.unflip_center(0,0,640)': unflip_center(0, 0, 640)}
    # (2) empirical: blobs through cv2.flip + cv2.resize
    errs = []
    for _ in range(300):
        ox, oy = rng.uniform(30, 1250), rng.uniform(30, 690)
        img = np.zeros((720, 1280), np.float32)
        yy, xx = np.mgrid[:720, :1280]; img[:] = np.exp(-((xx - ox) ** 2 + (yy - oy) ** 2) / (2 * 4. ** 2))
        pv = cv2.resize(cv2.flip(img, 1), prev)
        yy, xx = np.mgrid[:360, :640]; w = pv; cx = (w * xx).sum() / w.sum(); cy = (w * yy).sum() / w.sum()
        m = pt.preview_point_to_original((cx, cy)); errs.append(math.hypot(m[0] - ox, m[1] - oy))
    res['empirical_blob_flip_resize_to_orig_px'] = pct(errs)
    # edge blobs near borders
    eb = []
    for ox, oy in [(2, 2), (1277, 717), (2, 717), (1277, 2), (640, 360), (1, 360)]:
        img = np.zeros((720, 1280), np.float32); yy, xx = np.mgrid[:720, :1280]; img[:] = np.exp(-((xx - ox) ** 2 + (yy - oy) ** 2) / (2 * 3. ** 2))
        pv = cv2.resize(cv2.flip(img, 1), prev); yy, xx = np.mgrid[:360, :640]
        cx = (pv * xx).sum() / pv.sum(); cy = (pv * yy).sum() / pv.sum(); m = pt.preview_point_to_original((cx, cy)); eb.append(math.hypot(m[0] - ox, m[1] - oy))
    res['edge_blob_err_px'] = eb
    # (3) boxes: rectangle in original -> preview box via image ops
    be = []
    for _ in range(200):
        x1 = int(rng.integers(0, 1100)); y1 = int(rng.integers(0, 600)); x2 = x1 + int(rng.integers(8, 170)) * 2 // 2 * 2; y2 = y1 + int(rng.integers(8, 100)) * 2
        x2 = min(x2, 1280); y2 = min(y2, 720)
        img = np.zeros((720, 1280), np.float32); img[y1:y2, x1:x2] = 1
        pv = cv2.resize(cv2.flip(img, 1), prev)
        xs = np.where(pv.sum(0) > .5 * pv.sum(0).max())[0]; ys = np.where(pv.sum(1) > .5 * pv.sum(1).max())[0]
        pb = (xs[0], ys[0], xs[-1] + 1, ys[-1] + 1)  # preview box half-open
        ob = pt.preview_box_to_original(pb)
        be.append(max(abs(ob[0] - x1), abs(ob[1] - y1), abs(ob[2] - x2), abs(ob[3] - y2)))
        rb = pt.original_box_to_preview((x1, y1, x2, y2))
        assert abs(rb[0] - pb[0]) <= 1 and abs(rb[2] - pb[2]) <= 1 and abs(rb[1] - pb[1]) <= 1, (rb, pb)
        back = pt.preview_box_to_original(rb)
        assert max(abs(np.array(back) - [x1, y1, x2, y2])) < 1e-9
    res['box_empirical_vs_orig_edge_max_px'] = pct(be)
    # interfaces.unflip_box vs preview_box mirrored-only (same size scale 1)
    ub = unflip_box((10, 5, 50, 40), 640); pb = pt.preview_box_to_original((10, 5, 50, 40), original=(640, 360), preview=(640, 360))
    res['unflip_box_vs_transform_scale1'] = {'interfaces': ub, 'preview_transform': pb}
    c = pt.preview_point_to_original((10, 5), (640, 360), (640, 360)); res['unflip_center_vs_transform_scale1'] = {'interfaces': unflip_center(10, 5, 640), 'preview_transform': c}
    # (4) K scaling: project a 3D point with K_orig; blob in orig image -> flip/resize; scaled K projection should match
    K = np.array([[900., 0, 639.5], [0, 900., 359.5], [0, 0, 1]]); Ks = pt.scaled_intrinsics(K)
    ke = []
    for _ in range(100):
        X = np.array([rng.uniform(-.3, .3), rng.uniform(-.2, .2), 1.0]); uv = (K @ X)[:2] / X[2]
        img = np.zeros((720, 1280), np.float32); yy, xx = np.mgrid[:720, :1280]; img[:] = np.exp(-((xx - uv[0]) ** 2 + (yy - uv[1]) ** 2) / (2 * 4. ** 2))
        pv = cv2.resize(img, prev); yy, xx = np.mgrid[:360, :640]
        c = ((pv * xx).sum() / pv.sum(), (pv * yy).sum() / pv.sum()); s = (Ks @ X)[:2] / X[2]
        ke.append(math.hypot(c[0] - s[0], c[1] - s[1]))
    res['scaled_K_vs_resized_blob_px'] = pct(ke); res['Ks'] = Ks.tolist()
    # round-trip of a mirrored K: u' = W-1-u  => cx' = W-1-cx
    json.dump(res, open(OUT / 'out_B.json', 'w'), indent=1, default=float); print(json.dumps(res, indent=1, default=float))

def render_board(K, Rt, size, pattern, sq, dist=None, noise=0., blur=0.):
    cols, rows = pattern; tile = 100
    tex = np.zeros(((rows + 1) * tile, (cols + 1) * tile), np.uint8)
    for y in range(rows + 1):
        for x in range(cols + 1): tex[y * tile:(y + 1) * tile, x * tile:(x + 1) * tile] = 235 if (x + y) % 2 else 25
    outer = np.array([[-1, -1, 0], [cols, -1, 0], [cols, rows, 0], [-1, rows, 0]], np.float32) * sq
    # inner corner (i,j) at (i*sq, j*sq). squares between; texture cell (x,y) spans [(x-1)*sq, x*sq]
    r, t = Rt
    dst = cv2.projectPoints(outer, r, t, K, None)[0].reshape(4, 2).astype(np.float32)
    src = np.array([[0, 0], [tex.shape[1], 0], [tex.shape[1], tex.shape[0]], [0, tex.shape[0]]], np.float32) - .5
    H = cv2.getPerspectiveTransform(src - .5 + .5, dst + .5 - .5)
    img = cv2.warpPerspective(tex, H, size, flags=cv2.INTER_AREA if False else cv2.INTER_LINEAR, borderValue=128)
    # supersample for antialiasing
    big = cv2.warpPerspective(tex, np.array([[2, 0, .5], [0, 2, .5], [0, 0, 1.]]) @ H, (size[0] * 2, size[1] * 2), flags=cv2.INTER_LINEAR, borderValue=128)
    img = cv2.resize(big, size, interpolation=cv2.INTER_AREA)
    if dist is not None and np.any(dist):
        xs, ys = np.meshgrid(np.arange(size[0], dtype=np.float32), np.arange(size[1], dtype=np.float32))
        pts = np.stack([xs, ys], -1).reshape(-1, 1, 2)
        und = cv2.undistortPoints(pts, K, np.asarray(dist, float), P=K).reshape(size[1], size[0], 2).astype(np.float32)
        img = cv2.remap(img, und[..., 0], und[..., 1], cv2.INTER_LINEAR, borderValue=128)
    if blur: img = cv2.GaussianBlur(img, (0, 0), blur)
    if noise: img = np.clip(img.astype(float) + rng.normal(0, noise, img.shape), 0, 255).astype(np.uint8)
    return img

def C():
    sys.path.insert(0, str(ROOT / 'tools'))
    import calibrate_camera as cc
    res = {}
    size = (1280, 720); pattern = (9, 6); sq = .025
    scenarios = {'clean': dict(dist=None, noise=0, blur=0), 'noise2_blur0.8': dict(dist=None, noise=2, blur=.8), 'dist_k1-0.15': dict(dist=(-.15, .05, .0005, -.0004, 0), noise=1, blur=.6)}
    Ktrue = np.array([[1010., 0, 648.], [0, 1003., 352.], [0, 0, 1]])
    # board in world: origin (first inner corner) at world Twb; arbitrary rigid
    Twb = np.eye(4); Twb[:3, :3] = cv2.Rodrigues(np.array([0, 0, .4]))[0]; Twb[:3, 3] = [.45, -.1, .30]
    for name, sc in scenarios.items():
        # 12 views with diverse poses; board-cam pose (rvec,tvec) maps board->cam
        views = []; poses = []
        for i in range(12):
            r = np.array([rng.uniform(-.55, .55), rng.uniform(-.55, .55), rng.uniform(-.5, .5)])
            t = np.array([rng.uniform(-.17, -.05), rng.uniform(-.1, -.02), rng.uniform(.45, .7)])
            views.append(render_board(Ktrue, (r, t), size, pattern, sq, sc['dist'], sc['noise'], sc['blur'])); poses.append((r, t))
        try:
            model, rep = cc.estimate(views, pattern, sq, Twb)
        except Exception as ex:
            res[name] = {'exception': repr(ex)}; continue
        K = np.array(model.K); T = np.array(model.T_world_cam)
        # GT: first accepted view. determine which views accepted by independent detection
        acc = [i for i, v in enumerate(views) if cv2.findChessboardCornersSB(v, pattern, cv2.CALIB_CB_NORMALIZE_IMAGE)[0]]
        r0, t0 = poses[acc[0]]
        Rbc = cv2.Rodrigues(r0)[0]
        Tcb = np.eye(4); Tcb[:3, :3] = Rbc; Tcb[:3, 3] = t0  # board->cam
        # NOTE: render_board places board origin at outer-first-square corner offset: inner corner(0,0) is board origin, projectPoints used same frame
        Tgt = Twb @ np.linalg.inv(Tcb)
        pos_err = np.linalg.norm(T[:3, 3] - Tgt[:3, 3]) * 1e3
        Rrel = T[:3, :3].T @ Tgt[:3, :3]; ang = math.degrees(math.acos(max(-1, min(1, (np.trace(Rrel) - 1) / 2))))
        # plane check: board origin and a far corner lie on the plane
        pl = np.array(model.table_plane); pe = max(abs(pl[:3] @ (Twb @ np.array([x, y, 0, 1.]))[:3] + pl[3]) for x, y in [(0, 0), (.2, .1), (.1, .125)])
        # world-point reprojection check with estimated model vs true: board corners
        obj = cc.board_points(pattern, sq); Xw = (Twb @ np.c_[obj, np.ones(len(obj))].T).T[:, :3]
        dist_est = np.array(model.distortion)
        uv_est = project(K, T, dist_est, Xw); uv_true = project(Ktrue, np.linalg.inv(Tcb) if False else Twb @ np.linalg.inv(Tcb), sc['dist'] or (0,) * 5, Xw)
        res[name] = {'accepted_views_indep': len(acc), 'report': rep, 'K_est': {'fx': K[0, 0], 'fy': K[1, 1], 'cx': K[0, 2], 'cy': K[1, 2]},
                     'K_err': {'fx': K[0, 0] - Ktrue[0, 0], 'fy': K[1, 1] - Ktrue[1, 1], 'cx': K[0, 2] - Ktrue[0, 2], 'cy': K[1, 2] - Ktrue[1, 2]},
                     'dist_est': dist_est.tolist(), 'cam_pos_err_mm': pos_err, 'cam_rot_err_deg': ang, 'plane_residual_m': pe,
                     'reproj_vs_true_px': pct(np.linalg.norm(uv_est - uv_true, axis=1)), 'validation_error_m': model.validation_error_m}
        # localize round trip using the calibrated model on the board plane
        L = Localizer(model); ee = []
        for p in Xw[::5]:
            q = project(Ktrue, Twb @ np.linalg.inv(Tcb), sc['dist'] or (0,) * 5, [p])[0]
            if not (2 < q[0] < 1277 and 2 < q[1] < 717): continue
            d = Detection('d', 'q', 'mug', .9, (max(q[0] + .5 - 20, 0), max(q[1] + .5 - 30, 0), min(q[0] + .5 + 20, 1280), q[1] + .5), FrameMeta('f', 0, 's', 1., 1., False, model.calibration_id, 1280, 720, False))
            r = L.localize(d); ee.append(np.linalg.norm(np.array(r.xyz_m) - p) * 1e3 if r.error is None else 999)
        res[name]['localize_with_calibrated_model_mm'] = pct(ee)
    json.dump(res, open(OUT / 'out_C.json', 'w'), indent=1, default=float); print(json.dumps(res, indent=1, default=float))

def D():
    import mujoco, trimesh
    from sim.cell_scene_eval import EvaluationScene
    W, H = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (1280, 720)
    seeds = range(100000, 100000 + (int(sys.argv[4]) if len(sys.argv) > 4 else 100))
    rows = []; t0 = time.time()
    for seed in seeds:
        ev = EvaluationScene(seed, W, H); w = ev._world; gt = ev.ground_truth()
        cid = w.model.camera('front').id; xp = w.data.cam_xpos[cid].copy(); xm = w.data.cam_xmat[cid].reshape(3, 3).copy()
        f = (H / 2) / math.tan(math.radians(58) / 2); K = np.array([[f, 0, (W - 1) / 2], [0, f, (H - 1) / 2], [0, 0, 1.]])
        T = np.eye(4); T[:3, :3] = xm @ np.diag([1, -1, -1.]); T[:3, 3] = xp
        cam = make_cam(K, T, (W, H), cid='sim_front'); L = Localizer(cam)
        for item, spec, g in zip(w.plan['objects'], w.specs, gt):
            Tm = np.array(g['T_world_obj']); import trimesh as tm
            V = np.asarray(tm.load(spec.visual_obj, force='mesh', process=False).vertices) @ Tm[:3, :3].T + Tm[:3, 3]
            uv = project(K, T, (0,) * 5, V); lo = uv.min(0); hi = uv.max(0)
            if lo[0] < 0 or lo[1] < 0 or hi[0] > W or hi[1] > H: continue
            lo3, hi3 = np.array(g['aabb_m'][0]), np.array(g['aabb_m'][1])
            gtxy = (lo3[:2] + hi3[:2]) / 2; cls = item['class_id']
            # GT top-center feature pixel: highest-z vertex centroid -> aabb xy center at top z
            topc = np.array([*gtxy, hi3[2]]); topuv = project(K, T, (0,) * 5, [topc])[0]
            row = {'seed': seed, 'cls': cls, 'gt_xy': gtxy.tolist(), 'bottom_gap': g['bottom_gap_m'], 'h_aabb': float(hi3[2] - lo3[2]), 'box': [*lo, *hi],
                   'topuv': topuv.tolist(), 'plan_xy': item['xy_m']}
            rows.append(row)
        ev.close()
    print('scenes', len(list(seeds)), 'objects', len(rows), 'sec', round(time.time() - t0, 1))
    # evaluate (separate from rendering): modes
    Wc, Hc = W, H
    def run(mode, noise_rng_seed=1):
        r_ = np.random.default_rng(noise_rng_seed); out = {}
        for row in rows:
            x1, y1, x2, y2 = row['box']
            if mode.get('plus1'): x2, y2 = min(x2 + 1, Wc), min(y2 + 1, Hc)
            def jit(v): return v + (r_.uniform(-2, 2, np.shape(v)) if noise else 0)
            noise = mode.get('noise', False)
            f = (Hc / 2) / math.tan(math.radians(58) / 2)
            if mode['kind'] == 'mid':
                box = (jit(x1), jit(y1), jit(x2), jit(y2)) if noise else (x1, y1, x2, y2)
                res = L_[0].localize(mkdet(box, row['cls']), height_correction=mode['hc'])
            elif mode['kind'] == 'bottom':
                a = (jit((x1 + x2) / 2 - .5), jit(y2 - .5)); box = (x1, y1, x2, y2); res = L_[0].localize(mkdet(box, row['cls']), anchor=a)
            else:
                a = tuple(jit(np.array(row['topuv']))); box = (x1, y1, x2, y2)
                res = L_[0].localize(mkdet(box, row['cls']), anchor=a, anchor_kind='top_center', height_correction=mode['hc'])
            if res.error: out.setdefault('errors', []).append(res.error); continue
            e = np.linalg.norm(np.array(res.xyz_m[:2]) - row['gt_xy']) * 1e3
            out.setdefault(row['cls'], []).append(e); out.setdefault('ALL', []).append(e)
        return {k: (pct(v) if k != 'errors' else len(v)) for k, v in out.items()}
    cam = make_cam(np.array([[(Hc / 2) / math.tan(math.radians(58) / 2), 0, (Wc - 1) / 2], [0, (Hc / 2) / math.tan(math.radians(58) / 2), (Hc - 1) / 2], [0, 0, 1.]]), np.eye(4), (Wc, Hc), cid='sim_front')
    # rebuild per-scene camera is identical across scenes (fixed camera) -> reuse T from last scene
    Tlast = T; cam = make_cam(K, Tlast, (Wc, Hc), cid='sim_front'); L_ = [Localizer(cam)]
    def mkdet(box, cls): return Detection('d', 'q', cls, .9, tuple(box), FrameMeta('f', 0, 's', 1., 1., False, 'sim_front', Wc, Hc, False))
    res = {'resolution': [Wc, Hc], 'n_objects': len(rows), 'tag': '[시뮬GT] GT 메시 투영 박스 사용; 실물 위치 정확도 아님'}
    for name, mode in [('bottom_contact_bbox', dict(kind='bottom')), ('bottom_contact_bbox_noise2', dict(kind='bottom', noise=True)), ('mid_ON', dict(kind='mid', hc=True)), ('mid_ON_plus1', dict(kind='mid', hc=True, plus1=True)), ('mid_ON_noise2', dict(kind='mid', hc=True, noise=True)), ('mid_OFF', dict(kind='mid', hc=False)), ('bottom_plus1_like_IW2', dict(kind='bottom', plus1=True)),
                       ('top_center_hc_ON', dict(kind='top', hc=True)), ('top_center_hc_OFF', dict(kind='top', hc=False)),
                       ('top_center_hc_ON_noise2', dict(kind='top', hc=True, noise=True)), ('top_center_hc_OFF_noise2', dict(kind='top', hc=False, noise=True))]:
        res[name] = run(mode)
    json.dump({'summary': res, 'rows': rows}, open(OUT / f'out_D_{Wc}x{Hc}.json', 'w'), default=float); print(json.dumps(res, indent=1, default=float))

def E():
    size = (1280, 720); K = np.array([[900., 0, 639.5], [0, 900., 359.5], [0, 0, 1]])
    T = lookat_cv([1.35, 0, .95], [2.5, 0, 1.3])  # looks slightly up: rays never hit table ahead
    cam = make_cam(K, T, size); L = Localizer(cam); out = {}
    for name, a in [('center', (640, 360)), ('top', (640, 5)), ('bottom_row', (640, 715))]:
        r = L.localize(det(cam, size, (600, 300, 680, 420)), anchor=a); out[name] = r.error or ('OK ' + str(np.round(r.xyz_m, 3).tolist()))
    T2 = lookat_cv([1.35, 0, .95], [1.35, 1e-9, .30], up=(1, 0, 0))  # straight down
    cam2 = make_cam(K, T2, size); r = Localizer(cam2).localize(det(cam2, size, (600, 300, 680, 420))); out['straight_down'] = r.error or str(np.round(r.xyz_m, 3).tolist())
    cam3 = make_cam(K, lookat_cv([1.35, 0, .95], [.55, 0, .30]), size, plane=(0, 0, 0, 0)); r = Localizer(cam3).localize(det(cam3, size, (600, 300, 680, 420))); out['zero_plane'] = r.error
    print(json.dumps(out, indent=1)); json.dump(out, open(OUT / 'out_E.json', 'w'), indent=1)

if __name__ == '__main__':
    globals()[sys.argv[1]]()
