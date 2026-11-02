#!/usr/bin/env python3
"""
STEP(.stp/.step) -> mesh (METERS) for FoundationPose / MuJoCo

  python stp_to_mesh.py part.step                      # out: <same dir>/<name>/ (obj, stl, collision, json)
  python stp_to_mesh.py part.step -o out_dir --center bbox --collision coacd
  python stp_to_mesh.py part.step --unit in            # header unit wrong? treat raw numbers as inches

Outputs (all in meters):
  <name>.obj              visual mesh for FoundationPose (trimesh.load) / MuJoCo visual geom
  <name>.stl              same mesh, binary STL
  <name>_collision*.obj   MuJoCo collision: hull (1 convex), decimate (1 simplified), coacd (N convex parts)
  <name>.json             unit info, extents, center offset, triangle counts, watertight, volume

Unit handling
  OCCT converts STEP coordinates from the file's length unit (read from the header, e.g. MILLIMETRE / METRE / INCH)
  to the reader "system length unit". We set that to metres (SetSystemLengthUnit(1000) = 1 unit = 1000 mm).
  NOTE (OCCT 7.9 / cadquery-ocp 7.9.3): it must be called AFTER ReadFile() - before, it is reset to mm.
  --unit X overrides the header (raw numbers are reinterpreted as X).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import trimesh

from OCP.BRepTools import BRepTools
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader
from OCP.TColStd import TColStd_SequenceOfAsciiString

import cadquery as cq

# length unit name (STEP header / user flag) -> metres
UNIT_TO_M = {
    "m": 1.0, "metre": 1.0, "meter": 1.0,
    "mm": 1e-3, "millimetre": 1e-3, "millimeter": 1e-3,
    "cm": 1e-2, "centimetre": 1e-2, "centimeter": 1e-2,
    "um": 1e-6, "micrometre": 1e-6, "micron": 1e-6,
    "km": 1e3, "kilometre": 1e3,
    "in": 0.0254, "inch": 0.0254,
    "ft": 0.3048, "foot": 0.3048, "feet": 0.3048,
}


def unit_factor(name):
    if name is None:
        return None
    return UNIT_TO_M.get(name.strip().lower().replace(" ", ""))


def read_step_meters(path, unit_override=None):
    """Return (cq.Shape in metres, info dict)."""
    reader = STEPControl_Reader()
    status = reader.ReadFile(str(path))
    if status != IFSelect_RetDone:
        raise RuntimeError(f"STEP read failed (status={status}): {path}")
    reader.SetSystemLengthUnit(1000.0)   # AFTER ReadFile: system unit in mm -> 1 unit = 1 m

    lengths, angles, solids = (TColStd_SequenceOfAsciiString() for _ in range(3))
    reader.FileUnits(lengths, angles, solids)
    header_units = [lengths.Value(i).ToCString() for i in range(1, lengths.Length() + 1)]
    header_unit = header_units[0] if header_units else None

    reader.TransferRoots()
    shape = cq.Shape.cast(reader.OneShape())
    if shape is None or shape.wrapped.IsNull():
        raise RuntimeError("STEP has no transferable shape")

    # safety: whatever system unit OCCT actually used -> metres
    sys_mm = reader.SystemLengthUnit()
    if abs(sys_mm - 1000.0) > 1e-9:
        shape = shape.scale(sys_mm / 1000.0)

    scale = 1.0
    if unit_override:
        f_over = unit_factor(unit_override)
        if f_over is None:
            raise ValueError(f"unknown unit: {unit_override}")
        f_head = unit_factor(header_unit) or 1e-3   # header missing -> OCCT assumes mm
        # shape is (raw * f_head) metres; we want raw * f_over
        scale = f_over / f_head
        if abs(scale - 1.0) > 1e-12:
            shape = shape.scale(scale)
    info = dict(header_length_units=header_units, header_unit=header_unit,
                unit_override=unit_override, override_scale=scale,
                system_length_unit_mm=sys_mm)
    return shape, info


def tessellate(shape, tol_m=None, ang_tol=0.2):
    bb = shape.BoundingBox()
    diag = float(np.linalg.norm([bb.xlen, bb.ylen, bb.zlen]))
    if tol_m is None:
        tol_m = max(diag * 1e-3, 1e-5)        # 0.1% of diagonal, at least 10 um
    BRepTools.Clean_s(shape.wrapped)          # drop cached triangulation, else a coarser re-mesh is ignored
    verts, tris = shape.tessellate(tol_m, ang_tol)
    v = np.array([[p.x, p.y, p.z] for p in verts], dtype=np.float64)
    f = np.array(tris, dtype=np.int64).reshape(-1, 3)
    mesh = trimesh.Trimesh(vertices=v, faces=f, process=True)   # merges shared edge vertices
    mesh.merge_vertices()
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.remove_unreferenced_vertices()
    trimesh.repair.fix_normals(mesh)
    return mesh, tol_m


def center_mesh(mesh, mode):
    if mode == "none":
        return np.zeros(3)
    if mode == "bbox":
        offset = -mesh.bounds.mean(axis=0)
    elif mode == "centroid":
        offset = -(mesh.center_mass if mesh.is_watertight else mesh.centroid)
    else:
        raise ValueError(mode)
    mesh.apply_translation(offset)
    return offset


def collision_meshes(mesh, mode, coarse=None, coacd_threshold=0.08, coacd_max_hulls=16):
    """MuJoCo collision geometry. MuJoCo uses the convex hull of every mesh geom for collision,
    so concave parts need decomposition (coacd) to collide correctly.
    decimate = coarse re-tessellation of the CAD shape (quadric decimation via fast-simplification
    does not reduce CAD tessellations at all - tested, 2284 -> 2284 faces)."""
    out = []
    if mode == "none":
        return out
    if mode in ("hull", "all"):
        out.append(("hull", mesh.convex_hull))
    if mode in ("decimate", "all") and coarse is not None:
        out.append(("decimate", coarse))
    if mode in ("coacd", "all"):
        try:
            import coacd
            coacd.set_log_level("error")
            parts = coacd.run_coacd(coacd.Mesh(mesh.vertices, mesh.faces), threshold=coacd_threshold,
                                    max_convex_hull=coacd_max_hulls)
            for i, (pv, pf) in enumerate(parts):
                out.append((f"coacd_{i:02d}", trimesh.Trimesh(pv, pf)))
        except ImportError:
            print("coacd not installed -> falling back to hull")
            out.append(("hull", mesh.convex_hull))
    return out


def mesh_stats(m):
    return dict(vertices=int(len(m.vertices)), triangles=int(len(m.faces)),
                watertight=bool(m.is_watertight), winding_consistent=bool(m.is_winding_consistent),
                volume_m3=float(m.volume) if m.is_watertight else None,
                extents_m=[round(float(x), 6) for x in m.extents])


def convert(step_path, out_dir=None, unit=None, center="bbox", collision="hull", tol_m=None, name=None):
    step_path = Path(step_path)
    name = name or step_path.stem
    out_dir = Path(out_dir) if out_dir else step_path.parent / name
    out_dir.mkdir(parents=True, exist_ok=True)

    shape, uinfo = read_step_meters(step_path, unit)
    mesh, tol_used = tessellate(shape, tol_m)
    offset = center_mesh(mesh, center)
    coarse = None
    if collision in ("decimate", "all"):
        coarse, _ = tessellate(shape, tol_used * 10, 0.6)   # low-poly LOD from the CAD itself
        coarse.apply_translation(offset)

    obj_path = out_dir / f"{name}.obj"
    stl_path = out_dir / f"{name}.stl"
    mesh.export(obj_path)
    mesh.export(stl_path)

    col_files = []
    for tag, cm in collision_meshes(mesh, collision, coarse):
        p = out_dir / f"{name}_collision_{tag}.obj"
        cm.export(p)
        col_files.append(dict(file=p.name, **mesh_stats(cm)))

    meta = dict(
        source=str(step_path), name=name, units="m", **uinfo,
        tessellation_tol_m=tol_used, center_mode=center,
        center_offset_m=[round(float(x), 6) + 0.0 for x in offset],   # added to original coords
        bounds_m=[[round(float(x), 6) + 0.0 for x in b] for b in mesh.bounds],
        mesh=mesh_stats(mesh), files=dict(obj=obj_path.name, stl=stl_path.name, collision=col_files),
    )
    (out_dir / f"{name}.json").write_text(json.dumps(meta, indent=2))
    return meta


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step")
    ap.add_argument("-o", "--out-dir")
    ap.add_argument("--name")
    ap.add_argument("--unit", help="override STEP length unit: mm|cm|m|in|ft (default: from file header)")
    ap.add_argument("--center", default="bbox", choices=["none", "bbox", "centroid"])
    ap.add_argument("--collision", default="hull", choices=["none", "hull", "decimate", "coacd", "all"])
    ap.add_argument("--tol", type=float, help="linear tessellation tolerance in metres (default 0.1%% of diagonal)")
    a = ap.parse_args()
    meta = convert(a.step, a.out_dir, a.unit, a.center, a.collision, a.tol, a.name)
    m = meta["mesh"]
    ex = m["extents_m"]
    print(f"{meta['name']}: header unit={meta['header_unit']} override={meta['unit_override']}")
    print(f"  extents [m] = {ex[0]:.4f} x {ex[1]:.4f} x {ex[2]:.4f}   ({ex[0]*1000:.1f} x {ex[1]*1000:.1f} x {ex[2]*1000:.1f} mm)")
    print(f"  triangles={m['triangles']} watertight={m['watertight']} volume={m['volume_m3']}")
    print(f"  center_offset={meta['center_offset_m']}  collision={[c['file'] for c in meta['files']['collision']]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
