"""Contract §12 backprojection and upright pose fit (all distances in metres)."""
import numpy as np


def backproject(depth, K, T_table_cam, mask=None):
    """Return HxWx3 cloud or Nx3 at mask pixels, in T axes."""
    rows, cols = np.indices(depth.shape) if mask is None else np.nonzero(mask)
    d = depth if mask is None else depth[rows, cols]
    y = (rows - K[1, 2]) / K[1, 1]
    x = (cols - K[0, 2] - K[0, 1] * y) / K[0, 0]
    rays = np.stack([x, y, np.ones_like(x)], axis=-1)
    return (rays * d[..., None]) @ T_table_cam[:3, :3].T + T_table_cam[:3, 3]


def fit_pose(points):
    """Estimate yaw by PCA on the top face; return visible XY extent/Z bounds."""
    if len(points) < 5:
        raise ValueError('need at least five depth pixels')
    z_hi = float(np.quantile(points[:, 2], .95))
    roof = points[abs(points[:, 2] - z_hi) <= .003]
    xy = (roof if len(roof) >= 5 else points)[:, :2]
    _, axes = np.linalg.eigh(np.cov(xy.T))
    axis = axes[:, -1]
    yaw = float((np.arctan2(axis[1], axis[0]) + np.pi/2) % np.pi - np.pi/2)
    c, s = np.cos(yaw), np.sin(yaw)
    rot = np.array([[c, -s], [s, c]])
    lo, hi = np.quantile(xy @ rot, [.005, .995], axis=0)
    # Extents of partially sampled top faces are lower bounds, not full geometry.
    return (lo + hi) @ rot.T / 2, yaw, hi - lo, float(np.quantile(points[:, 2], .05)), z_hi


def _peak(values, width=.0025):
    """Largest count in two adjacent bins; robust to bin phase."""
    lo = values.min()
    counts = np.bincount(np.floor((values-lo)/width).astype(int))
    return int((counts[:-1]+counts[1:]).max()) if len(counts) > 1 else int(counts[0])


def edge_angle(points_xy):
    """Dominant straight-edge direction of a rectangle contour, in [0, pi/2).
    A rectangle's contour piles into few offset bins on both axes at the right angle;
    this stays valid when one end is cut off (image border / occluder)."""
    pts = np.asarray(points_xy, dtype=float)
    if len(pts) < 8:
        return None
    def score(t):
        c, s = np.cos(t), np.sin(t)
        return _peak(pts @ [c, s]) + _peak(pts @ [-s, c])
    coarse = np.deg2rad(np.arange(0, 90, 1.))
    best = coarse[int(np.argmax([score(t) for t in coarse]))]
    fine = best + np.deg2rad(np.arange(-1, 1.01, .25))
    best = fine[int(np.argmax([score(t) for t in fine]))]
    return float(best % (np.pi/2))


def norm_yaw(a):
    return float((a + np.pi/2) % np.pi - np.pi/2)
