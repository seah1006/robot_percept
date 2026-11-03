"""Generate decimated copies of the Unitree G1 visual meshes for real-time rendering.

The menagerie G1 meshes total ~630k triangles which costs ~38 ms per frame on the
WSL d3d12 GL path.  Quadric decimation (open3d) to ~12% keeps the silhouette.
Output: assets/g1_lowpoly/<same names>.STL (binary).  Run once:
    python tools/g1_lowpoly.py [--ratio 0.12]
"""
import argparse
from pathlib import Path
import numpy as np
import open3d as o3d

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'assets/mujoco_menagerie/unitree_g1/assets'
DST = ROOT / 'assets/g1_lowpoly'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--ratio', type=float, default=.12); ap.add_argument('--min-faces', type=int, default=1500)
    a = ap.parse_args(); DST.mkdir(parents=True, exist_ok=True); tot0 = tot1 = 0
    for f in sorted(SRC.glob('*.STL')):
        m = o3d.io.read_triangle_mesh(str(f)); n0 = len(m.triangles)
        target = max(a.min_faces, int(n0 * a.ratio))
        if n0 > target:
            m = m.simplify_quadric_decimation(target_number_of_triangles=target)
            m.remove_degenerate_triangles(); m.remove_unreferenced_vertices()
        m.compute_triangle_normals(); m.compute_vertex_normals()
        o3d.io.write_triangle_mesh(str(DST / f.name), m)
        tot0 += n0; tot1 += len(m.triangles)
    print(f'faces {tot0} -> {tot1}')


if __name__ == '__main__':
    main()
