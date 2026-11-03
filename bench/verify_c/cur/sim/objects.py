"""Mesh registry; all vertices retain their original OBJ frame (metres)."""
from dataclasses import dataclass
from pathlib import Path
import re
import numpy as np
import trimesh
ROOT = Path(__file__).resolve().parents[1]
@dataclass
class ObjectSpec:
    name: str
    visual_obj: str
    collision_objs: tuple
    mass: float
    rgba: tuple
    texture: str | None
    bounds: np.ndarray

def mesh_spec(name, visual_obj, collision_objs=None, mass=.1, rgba=None, texture=None):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_-]*',name):
        raise ValueError('Object name must be a safe XML identifier')
    visual = Path(visual_obj).resolve()
    mesh = trimesh.load(visual,force='mesh',process=False)
    bounds = np.asarray(mesh.bounds,float)
    if not np.isfinite(bounds).all() or max(mesh.extents)<=0 or max(mesh.extents)>2:
        raise ValueError(f'{name}: expected finite mesh in metres; bounds={bounds}')
    if isinstance(collision_objs,(str,Path)):
        collision_objs=[collision_objs]
    if not collision_objs:
        out=ROOT/'assets/objects'/name
        out.mkdir(parents=True,exist_ok=True)
        hull=out/'collision_hull.obj'
        mesh.convex_hull.export(hull)
        collision_objs=[hull]
    paths=tuple(str(Path(p).resolve()) for p in collision_objs)
    for p in paths:
        if not Path(p).is_file(): raise FileNotFoundError(p)
    if mass<=0: raise ValueError('Mass must be positive')
    return ObjectSpec(name,str(visual),paths,float(mass),tuple(rgba) if rgba is not None else (.25,.6,.85,1),str(texture) if texture else None,bounds)

def default_registry():
    mustard=ROOT/'downloads/demo_data/mustard0/mesh'
    registry={'mustard':mesh_spec('mustard',mustard/'textured_simple.obj',mass=.25,texture=mustard/'texture_map.png')}
    for d in sorted((ROOT/'cad_uploads/converted').glob('*')):
        visual=d/(d.name+'.obj')
        if visual.is_file():
            registry[d.name]=mesh_spec(d.name,visual,sorted(d.glob('*_collision_coacd_*.obj')) or None)
    return registry
