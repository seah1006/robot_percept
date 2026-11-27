"""Prediction-only O3 adapter (V1 segmentation -> V2 identity -> V3 pose -> V4 symbolic state).

Input: live env (render/camera_K/T_table_cam) or a mapping {rgb, depth, K, T_table_cam}.
Never reads GT. Live EGL inputs use CPU depth by default; the optional models run in the ROCm worker.
"""
from collections.abc import Mapping
from time import perf_counter

import numpy as np

from m2a.common import load_layout, load_parts
from m2a.scene.symbolic import symbolic_from_gt
from .geometry import backproject, edge_angle, fit_pose, norm_yaw
from .v1 import (box_iou, box_of, depth_proposals, dilate4, plateau_proposals,
                 rescue_proposals, support_surface)

PROMPTS = ['wooden board', 'dowel', 'cam lock', 'metal bracket', 'blue block']
TOL_LONG, TOL_SHORT = .014, .009  # 임의 지정 (m)
W_COLOR, W_KNN, W_PRIOR = 14., 5., .6  # 임의 지정 loss weights
# 추정: train 0-199 GT 개수 비율 반올림. 잘린 판재의 길이 동점 처리에만 쓴다.
DEFAULT_PRIOR = dict(P01=.19, P02=.20, P03=.10, P04=.17, P05=.17, P06=.10, D01=.08)


def crop(rgb, mask):
    x0, y0, x1, y1 = box_of(mask)
    return np.where(mask[y0:y1, x0:x1, None], rgb[y0:y1, x0:x1], 127).astype(np.uint8)


def chroma(rgb):
    return rgb / np.maximum(np.sum(rgb, axis=-1, keepdims=True), 1e-6)


def part_dims(part):
    size = part['size']
    d = np.asarray(size[:2], float) if part['shape'] == 'box' else np.full(2, 2*size[0])
    return float(max(d)), float(min(d))


def describe(top, cut, cloud, ztop=None):
    """Top-face frame: edge-angle axes (u, v), visible spans, which ends are cut by border/occluder."""
    pts = cloud[top]
    contour = top & dilate4(~top, 1)  # top pixels with a non-top 4-neighbour
    keep = contour & ~dilate4(cut, 2)
    if keep.sum() < 8:
        keep = contour
    theta = edge_angle(cloud[keep][:, :2])
    if theta is None:
        theta = float(fit_pose(pts)[1] % (np.pi/2))
    c, s = np.cos(theta), np.sin(theta)
    rot = np.array([[c, -s], [s, c]])  # columns = u, v
    uv = pts[:, :2] @ rot
    lo, hi = np.quantile(uv, [.003, .997], axis=0)
    cut_ends = np.zeros((2, 2), bool)  # [axis][lo, hi]
    if cut.any():
        cuv = cloud[cut][:, :2] @ rot
        cut_ends[:, 0] = (cuv < lo+.004).any(0)
        cut_ends[:, 1] = (cuv > hi-.004).any(0)
    z_top = float(np.median(pts[:, 2])) if ztop is None else float(ztop)
    return dict(theta=float(theta), rot=rot, lo=lo, hi=hi, span=hi-lo, cut_ends=cut_ends, ztop=z_top,
                cut_fraction=float(cut.sum()/max(top.sum(), 1)))


def classify(obs, height, rgb, parts, embeddings=None, gallery=None, prior=None):
    """Return ranked [(loss, pid, long_axis)]. Cut axes only penalise spans longer than the part."""
    span, cut_axis = obs['span'], obs['cut_ends'].any(1)
    ranked = []
    for pid, part in parts.items():
        d1, d2 = part_dims(part)
        best = None
        for long_axis in (0, 1):
            dims = (d1, d2) if long_axis == 0 else (d2, d1)
            tol = (TOL_LONG, TOL_SHORT) if long_axis == 0 else (TOL_SHORT, TOL_LONG)
            e = 0.
            for a in (0, 1):
                over = span[a] + .002 - dims[a]  # +2 mm: top-face sampling pitch
                e += (max(0., over)/tol[a])**2 if cut_axis[a] else (over/tol[a])**2
            if best is None or e < best[0]:
                best = (e, long_axis)
        loss = best[0] + W_COLOR*np.sum((chroma(rgb)-chroma(np.asarray(part['rgb'])))**2)
        thick = part['size'][-1]
        residual = min(abs(height-thick-base)/.007 + (.65 if base else 0) for base in (0, .025, .030, .050))
        loss += min(residual**2, 20)
        if embeddings is not None and gallery is not None:
            vectors = gallery[1][gallery[0] == pid]
            if len(vectors):
                sim = vectors @ embeddings
                k = min(3, len(sim))
                loss += W_KNN*(1-float(np.partition(sim, -k)[-k:].mean()))
        if prior is not None and cut_axis.any():  # truncated spans cannot separate boards
            loss += -W_PRIOR*np.log(prior.get(pid, 1e-3))
        ranked.append((float(loss), pid, best[1]))
    ranked.sort()
    return ranked


def place(obs, part, long_axis):
    """Complete a cut axis from the catalog length (anchored at the visible end); return xy, yaw."""
    d1, d2 = part_dims(part)
    dims = (d1, d2) if long_axis == 0 else (d2, d1)
    center = (obs['lo']+obs['hi'])/2
    for a in (0, 1):
        lo_cut, hi_cut = obs['cut_ends'][a]
        if lo_cut != hi_cut and dims[a] > obs['span'][a]:
            center[a] = obs['hi'][a]-dims[a]/2 if lo_cut else obs['lo'][a]+dims[a]/2
    xy = obs['rot'] @ center
    yaw = norm_yaw(obs['theta'] + (0 if long_axis == 0 else np.pi/2)) if part['shape'] == 'box' else 0.
    return xy, yaw


class O3:
    def __init__(self, layout=None, parts=None, detector=None, embedder=None, gallery=None, require_box=False,
                 seg='plateau', rescue=False):
        self.layout = load_layout() if layout is None else layout
        self.parts = (load_parts() if parts is None else parts)
        self.parts = self.parts.get('parts', self.parts)
        self.detector, self.embedder, self.gallery = detector, embedder, gallery
        self.require_box, self.seg, self.rescue = require_box, seg, rescue
        if gallery is not None:
            ids, counts = np.unique(gallery[0], return_counts=True)
            self.prior = dict(zip(ids.tolist(), (counts/counts.sum()).tolist()))
        else:
            self.prior = DEFAULT_PRIOR
        if require_box and detector is None:
            raise ValueError('require_box needs a detector')

    def _proposals(self, depth, cloud):
        if self.seg != 'legacy':
            return plateau_proposals(depth, cloud, self.layout)
        out = []
        z = cloud[..., 2]
        edge = np.zeros(depth.shape, bool)
        edge[0] = edge[-1] = True; edge[:, 0] = edge[:, -1] = True
        for mask, _ in depth_proposals(depth, cloud, self.layout):
            zhi = float(np.quantile(z[mask], .95))
            top = mask & (abs(z-zhi) <= .003)
            top = top if top.sum() >= 8 else mask
            out.append(dict(mask=mask, top=top, cut=top & edge, ztop=zhi))
        return out

    def observe(self, env_or_frame):
        start = perf_counter()
        if isinstance(env_or_frame, Mapping):
            frame = env_or_frame
        else:
            env = env_or_frame
            rgb, depth = env.render('head')
            frame = dict(rgb=rgb, depth=depth, K=env.camera_K('head'), T_table_cam=env.T_table_cam('head'))
        rendered = perf_counter()
        rgb, depth = np.asarray(frame['rgb']), np.asarray(frame['depth'])
        cloud = backproject(depth, np.asarray(frame['K']), np.asarray(frame['T_table_cam']))
        boxes = self.detector(rgb, PROMPTS) if self.detector else []
        pieces = [p for p in self._proposals(depth, cloud) if p['top'].sum() >= 8]
        if self.rescue and boxes:
            pieces += rescue_proposals(depth, cloud, self.layout, [p['mask'] for p in pieces], boxes)
        for p in pieces:
            p['box'] = box_of(p['mask'])
        candidates = sorted(((box_iou(p['box'], b), score, i, j)
                             for i, p in enumerate(pieces) for j, (b, score) in enumerate(boxes)), reverse=True)
        associations, claimed = {}, set()
        for iou, score, i, j in candidates:
            if iou >= .25 and i not in associations and j not in claimed:
                associations[i] = j; claimed.add(j)
        proposals = []
        for i, p in enumerate(pieces):
            if i in associations:
                det_box, det_score = boxes[associations[i]]
                proposals.append((p, det_box if self.require_box else p['box'], det_score, p.get('source', 'gdino+depth')))
            elif not self.require_box:
                proposals.append((p, p['box'], .5, p.get('source', 'depth')))
        vectors = (self.embedder([crop(rgb, p['mask']) for p, *_ in proposals])
                   if self.embedder and proposals else [None]*len(proposals))
        observations, planner_objects, masks = {}, {}, {}
        for (p, det_box, det_score, source), embedding in zip(proposals, vectors):
            obs = describe(p['top'], p['cut'], cloud, p['ztop'])
            center = obs['rot'] @ ((obs['lo']+obs['hi'])/2)
            height = obs['ztop'] - float(support_surface(*center, self.layout))
            color = np.median(rgb[p['top']].astype(float), axis=0)
            ranked = classify(obs, height, color, self.parts, embedding, self.gallery, self.prior)
            weight = np.exp(-.5*(np.asarray([r[0] for r in ranked])-ranked[0][0]))
            cut = bool(obs['cut_ends'].any())
            scale = .6 if cut else 1.
            top3 = [dict(part_id=pid, confidence=float(w/weight.sum()*scale))
                    for w, (_, pid, _) in zip(weight, ranked)][:3]
            pid, long_axis = ranked[0][1], ranked[0][2]
            part = self.parts[pid]
            xy, yaw = place(obs, part, long_axis)
            thickness = part['size'][-1]
            xyz = [float(xy[0]), float(xy[1]), float(obs['ztop']-thickness/2)]
            oid = f'p{len(observations)}'
            planner_objects[oid] = dict(part_id=pid, xyz=xyz, yaw=yaw)
            dims = [*obs['span'].tolist(), float(obs['ztop']-np.quantile(cloud[p['mask']][:, 2], .05))]
            observations[oid] = dict(**planner_objects[oid], box_xyxy=det_box, mask_box_xyxy=p['box'],
                                     detection_score=det_score, source=source, top3=top3, dimensions=dims,
                                     dimensions_xyz_catalog_z=[*obs['span'].tolist(), thickness],
                                     cut=cut, cut_fraction=obs['cut_fraction'],
                                     # 임의 지정: a cut top face with <400 px is too small for a trustworthy pose
                                     pose_reliable=bool(not cut or p['top'].sum() >= 400),
                                     consistent_parts=[q for loss, q, _ in ranked if loss <= ranked[0][0]+4],
                                     obj_pose_T=dict(xyz=xyz, yaw=yaw, size=list(part['size']), part_id=pid, shape=part['shape']))
            masks[oid] = p['mask']
        state = symbolic_from_gt(planner_objects, self.layout, self.parts)
        for oid, predicates in state['objects'].items():
            observations[oid].update(predicates)
        return state, {'schema': 'm2a.scene_graph.v1', 'camera': 'head', 'objects': observations, 'grounding_boxes': boxes,
                       'obj_pose_T': {oid: o['obj_pose_T'] for oid, o in observations.items()},
                       'render_ms': (rendered-start)*1000, 'keyframe_ms': (perf_counter()-start)*1000}, masks

    def perceive(self, env_or_frame):
        """-> (symbolic_state, scene_graph). scene_graph['obj_pose_T'][oid] feeds SkillRunner.run(obj_pose_T=...)."""
        state, graph, _ = self.observe(env_or_frame)
        return state, graph


def perceive(env_or_frame):
    """Accept live env or mapping of only RGB/depth/K/T_table_cam; return (state, graph)."""
    layout = None if isinstance(env_or_frame, Mapping) else getattr(env_or_frame, 'layout', None)
    return O3(layout=layout).perceive(env_or_frame)
