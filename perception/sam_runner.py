"""GT-free SAM2 candidate selection from RGB-D evidence.

The predictor score estimates mask quality, not whether a mask covers the whole
clicked object. Keep the score winner when click depth is unavailable. Otherwise
prefer the largest connected, depth-compatible candidate with a plausible score.
"""
from __future__ import annotations
import numpy as np
import cv2


def select_candidate(masks, scores, click, depth=None):
    masks = np.asarray(masks, dtype=bool)
    scores = np.asarray(scores, dtype=float)
    if masks.ndim != 3 or scores.shape != (len(masks),):
        raise ValueError('Expected N masks and N scores')
    x, y = map(int, click)
    h, w = masks.shape[1:]
    if not 0 <= x < w or not 0 <= y < h:
        raise ValueError('Click outside image')
    best = int(np.argmax(scores))
    if depth is None:
        return best
    depth = np.asarray(depth)
    if depth.shape != (h, w):
        raise ValueError('Depth and mask dimensions differ')
    z = float(depth[y, x])
    if not np.isfinite(z) or z <= 0:
        # SimEnv zeros depth at discontinuities. Neighboring unmasked pixels
        # may be the table, so prefer valid pixels inside the click-containing
        # score-best mask before looking outside it.
        support = depth[masks[best]] if masks[best, y, x] else np.empty(0)
        valid_support = support[np.isfinite(support) & (support > 0)]
        if valid_support.size:
            z = float(np.median(valid_support))
        else:
            for radius in (1, 4, 10):
                patch = depth[max(0,y-radius):min(h,y+radius+1),
                              max(0,x-radius):min(w,x+radius+1)]
                valid = patch[np.isfinite(patch) & (patch > 0)]
                if valid.size:
                    z = float(np.median(valid))
                    break
            else:
                return best
    plausible = []
    for i, mask in enumerate(masks):
        if (not mask[y, x] or scores[i] < .05 or
                mask.sum() > min(12 * masks[best].sum(), .25 * h * w) or
                (i != best and mask.sum() < 1.3 * masks[best].sum())):
            continue
        # SAM can return disconnected scene fragments. Reject those unless the
        # clicked component is dominant; the reported mask is never GT-clipped.
        u8 = mask.astype(np.uint8)
        bx, by, bw, bh = cv2.boundingRect(u8)
        n, labels, stats, _ = cv2.connectedComponentsWithStats(u8[by:by+bh, bx:bx+bw], 8)
        label = labels[y-by, x-bx]
        if label == 0 or stats[label, cv2.CC_STAT_AREA] < .8 * mask.sum():
            continue
        values = depth[mask]
        consistent = np.count_nonzero(np.isfinite(values) & (values > 0) & (np.abs(values - z) < .12)) / max(len(values), 1)
        if consistent >= .55:
            plausible.append((int(mask.sum()), float(scores[i]), i))
    return max(plausible)[2] if plausible else best
