"""GT-free foreground proposals; optional Grounding DINO box fusion."""
from typing import Protocol

import numpy as np


class TextSegmenter(Protocol):
    def segment_text(self, rgb: np.ndarray, prompts: list[str]) -> tuple[np.ndarray, np.ndarray]:
        """Return bool [N,H,W] masks and float [N] scores, in image pixel space."""
        ...


class SAM31Adapter:
    def segment_text(self, rgb, prompts):
        raise NotImplementedError('SAM 3.1 gated weights: provide an approved local snapshot and implement processor adapter')


def box_of(mask):
    v, u = np.nonzero(mask)
    return [int(u.min()), int(v.min()), int(u.max()+1), int(v.max()+1)] if len(u) else [0]*4


def box_iou(a, b):
    aw, ah = a[2]-a[0], a[3]-a[1]
    bw, bh = b[2]-b[0], b[3]-b[1]
    i = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    return i / max(aw*ah + bw*bh - i, 1e-9)


def components(mask, minimum=14):
    """4-connected run union; NumPy-only so ROCm and EGL envs both work."""
    edges = np.pad(mask, ((0, 0), (1, 1)))
    starts, ends = np.nonzero(edges[:, 1:] & ~edges[:, :-1]), np.nonzero(edges[:, :-1] & ~edges[:, 1:])
    runs = list(zip(starts[0].tolist(), starts[1].tolist(), ends[1].tolist()))
    parents = list(range(len(runs)))
    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i
    prev = []
    curr = []
    row = -2
    j = 0
    for i, (v, a, b) in enumerate(runs):
        if v != row:
            prev, curr = (curr if row == v-1 else []), []
            row, j = v, 0
        while j < len(prev) and runs[prev[j]][2] <= a:
            j += 1
        k = j
        while k < len(prev) and runs[prev[k]][1] < b:
            parents[root(i)] = root(prev[k]); k += 1
        curr.append(i)
    groups = {}
    for i, run in enumerate(runs):
        groups.setdefault(root(i), []).append(run)
    for group in groups.values():
        if sum(b-a for _, a, b in group) >= minimum:
            out = np.zeros_like(mask)
            for v, a, b in group:
                out[v, a:b] = True
            yield out


def support_surface(x, y, layout):
    """Known calibrated table/tray fixtures, not object poses or render IDs."""
    base = np.zeros(np.broadcast_shapes(np.shape(x), np.shape(y)))
    for t in layout['trays'].values():
        tx, ty = t['center']; w, h = np.asarray(t['inner'])/2
        base = np.where((abs(x-tx) < w) & (abs(y-ty) < h), t.get('floor_z', 0), base)
    return base


def depth_proposals(depth, cloud, layout, exclude=None):
    x, y, z = cloud.transpose(2, 0, 1)
    sx, sy = np.asarray(layout['table']['size_xy'])/2
    surface = support_surface(x, y, layout)
    valid = np.isfinite(depth) & (depth > 0) & (abs(x)<sx) & (abs(y)<sy) & (z > surface+.007) & (z < .135)
    # Exclude known tray walls only at their physical heights.
    for t in layout['trays'].values():
        tx, ty = t['center']; w, h = np.asarray(t['inner'])/2
        dw = t.get('wall_thickness', .006) + .001
        dx, dy = abs(x-tx), abs(y-ty)
        wall = (dx < w+dw) & (dy < h+dw) & ((dx >= w-.001) | (dy >= h-.001))
        valid &= ~(wall & (z <= t.get('floor_z', 0)+t['wall_h']+.002))
    if exclude is not None:
        valid &= ~exclude
    # Suppress robot pixels over the board by requiring a part-sized horizontal
    # top surface; use multiple peaks to resolve one-level supported stacks.
    for mask in components(valid):
        values = z[mask] - surface[mask]
        counts, edges = np.histogram(values, bins=np.arange(0, .141, .0025))
        if not len(counts) or counts.max() < 12:
            continue
        peaks = []
        for i in np.argsort(counts)[::-1]:
            target = (edges[i]+edges[i+1])*.5
            if target < .015 or counts[i] < max(12, counts.max()*.075):
                break
            if all(abs(target-p) >= .014 for p in peaks):
                peaks.append(target)
        if not peaks:
            continue
        if len(peaks) == 1:
            yield mask, .5
            continue
        assignments = np.zeros_like(z, dtype=np.uint8)
        peaks.sort()
        assignments[mask] = np.searchsorted(np.asarray(peaks[:-1])+.007, values, side='right')
        for i, peak in enumerate(peaks):
            for piece in components(mask & (assignments == i)):
                if np.count_nonzero(abs(z[piece]-surface[piece]-peak) < .004) >= 8:
                    yield piece, .5


# ---- V1 plateau segmentation (replaces the height-histogram splitter) -------------------
# 임의 지정 thresholds: top-facing normal nz>.95, flat step 3 mm, min plateau 20 px,
# side-growth depth step 15 mm.
def _sh(a, dy, dx):
    """out[p] = a[p-d]; zero fill."""
    out = np.zeros_like(a)
    H, W = a.shape
    out[max(dy, 0):H+min(dy, 0), max(dx, 0):W+min(dx, 0)] = a[max(-dy, 0):H+min(-dy, 0), max(-dx, 0):W+min(-dx, 0)]
    return out


def foreground(depth, cloud, layout):
    """Table plane + known tray floor/walls removed; returns (valid, surface z)."""
    x, y, z = cloud.transpose(2, 0, 1)
    sx, sy = np.asarray(layout['table']['size_xy'])/2
    surface = support_surface(x, y, layout)
    valid = np.isfinite(depth) & (depth > 0) & (abs(x) < sx) & (abs(y) < sy) & (z > surface+.007) & (z < .135)
    for t in layout['trays'].values():
        tx, ty = t['center']; w, h = np.asarray(t['inner'])/2
        dw = t.get('wall_thickness', .006) + .001
        dx, dy = abs(x-tx), abs(y-ty)
        wall = (dx < w+dw) & (dy < h+dw) & ((dx >= w-.001) | (dy >= h-.001))
        valid &= ~(wall & (z <= t.get('floor_z', 0)+t['wall_h']+.002))
    return valid, surface


def top_facing(cloud, valid, nz_min=.95, step=.003):
    """Pixels on flat, upward-facing surfaces, cut where the height steps (stack edges)."""
    rows, cols = np.nonzero(valid)
    if not len(rows):
        return np.zeros_like(valid)
    H, W = valid.shape
    y0, y1, x0, x1 = max(rows.min()-2, 0), min(rows.max()+3, H), max(cols.min()-2, 0), min(cols.max()+3, W)
    out = np.zeros_like(valid)
    out[y0:y1, x0:x1] = _top_facing(cloud[y0:y1, x0:x1], valid[y0:y1, x0:x1], nz_min, step)
    return out


def _top_facing(cloud, valid, nz_min, step):
    z = cloud[..., 2]
    # one-sided at the image border so cut surfaces keep a valid normal up to the last pixel
    dx = np.gradient(cloud, axis=1)*2
    dy = np.gradient(cloud, axis=0)*2
    n = np.cross(dx, dy)
    ln = np.linalg.norm(n, axis=-1)
    nz = abs(n[..., 2]) / np.maximum(ln, 1e-12)
    smooth = (np.linalg.norm(dx, axis=-1) < .02) & (np.linalg.norm(dy, axis=-1) < .02)
    top = valid & smooth & (nz > nz_min)
    jump = np.zeros_like(top)
    for sy_, sx_ in ((0, 1), (1, 0)):
        nb = _sh(z, sy_, sx_); nbt = _sh(top, sy_, sx_)
        j = top & nbt & (abs(z-nb) > step)
        jump |= j | _sh(j, -sy_, -sx_)
    return top & ~jump


def grow_labels(labels, valid, depth, z, ztop, iters=80):
    """Assign side faces to the plateau they hang from (nearest, continuous, not above the top)."""
    labels = labels.copy()
    rows, cols = np.nonzero(valid | (labels > 0))
    if not len(rows):
        return labels
    y0, y1, x0, x1 = max(rows.min()-1, 0), rows.max()+2, max(cols.min()-1, 0), cols.max()+2
    L, V, D, Z = labels[y0:y1, x0:x1], valid[y0:y1, x0:x1], depth[y0:y1, x0:x1], z[y0:y1, x0:x1]
    for _ in range(iters):
        changed = False
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            src, sd = _sh(L, dy, dx), _sh(D, dy, dx)
            ok = (L == 0) & V & (src > 0) & (abs(D-sd) < .015) & (Z <= ztop[src]+.004)
            if ok.any():
                L[ok] = src[ok]; changed = True
        if not changed:
            break
    labels[y0:y1, x0:x1] = L
    return labels


def cut_pixels(labels, k, depth):
    """Pixels of plateau k that touch the image border or are bordered by a nearer foreign pixel."""
    own = labels == k
    cut = np.zeros_like(own)
    H, W = own.shape
    cut[0] |= own[0]; cut[-1] |= own[-1]; cut[:, 0] |= own[:, 0]; cut[:, -1] |= own[:, -1]
    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        nb_label, nb_d = _sh(labels, dy, dx), _sh(depth, dy, dx)
        valid_nb = np.ones_like(own)
        # neighbor outside the image is handled above; zero-filled shift edges excluded here
        if dy: valid_nb[0 if dy > 0 else -1] = False
        if dx: valid_nb[:, 0 if dx > 0 else -1] = False
        cut |= own & valid_nb & (nb_label != k) & (nb_d > 0) & (nb_d < depth-.004)
    return cut


def plateau_proposals(depth, cloud, layout, min_px=20, nz_min=.95, roi=None, exclude=None):
    """Yield dict(mask, top, cut, ztop): mask = plateau + hanging side faces, top = flat top only."""
    valid, surface = foreground(depth, cloud, layout)
    if exclude is not None:
        valid &= ~exclude
    top = top_facing(cloud, valid, nz_min)
    if roi is not None:
        keep = np.zeros_like(top); keep[roi[1]:roi[3], roi[0]:roi[2]] = True
        top &= keep
    z = cloud[..., 2]
    plateaus = [p for p in components(top, min_px)]
    if not plateaus:
        return []
    labels = np.zeros(depth.shape, dtype=np.int32)
    ztop = np.full(len(plateaus)+1, np.inf)
    for k, p in enumerate(plateaus, 1):
        labels[p] = k
        ztop[k] = float(np.median(z[p]))
    grown = grow_labels(labels, valid, depth, z, ztop)
    out = []
    for k, p in enumerate(plateaus, 1):
        out.append(dict(mask=grown == k, top=p, cut=cut_pixels(grown, k, depth) & p, ztop=ztop[k]))
    return out


def dilate4(mask, n=1):
    out = mask.copy()
    for _ in range(n):
        nxt = out.copy()
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nxt |= _sh(out, dy, dx)
        out = nxt
    return out


def rescue_proposals(depth, cloud, layout, existing, boxes, min_score=.3, exclude=None):
    """GDINO-guided recovery: for confident boxes that no depth proposal covers, re-run plateau
    segmentation inside the box with a looser flatness/size gate (nz>.85, 8 px; 임의 지정)."""
    taken = np.zeros(depth.shape, bool)
    for m in existing:
        taken |= m
    out = []
    for (x0, y0, x1, y1), score in boxes:
        if score < min_score:
            continue
        x0, y0, x1, y1 = int(x0), int(y0), int(np.ceil(x1)), int(np.ceil(y1))
        if taken[y0:y1, x0:x1].sum()/max((x1-x0)*(y1-y0), 1) > .15:
            continue
        for p in plateau_proposals(depth, cloud, layout, min_px=8, nz_min=.85, exclude=exclude, roi=(x0, y0, x1, y1)):
            if (p['mask'] & taken).sum() < .3*p['mask'].sum():
                p['source'] = 'gdino-rescue'
                out.append(p); taken |= p['mask']
    return out
