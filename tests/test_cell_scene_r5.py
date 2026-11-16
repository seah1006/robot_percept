import json
import numpy as np
import pytest
import trimesh
from sim.cell_scene import catalog, scene_plan, ROOT, ZONES, CellCamera
from sim.cell_scene_eval import generate_manifest, open_evaluation_scene

def test_determinism():
    for seed in range(100): assert scene_plan(seed)==scene_plan(seed)

def test_split():
    m=generate_manifest(); a=m['sets']['tuning']; b=m['sets']['evaluation']
    assert len(b)>=100
    assert not {x['seed'] for x in a}&{x['seed'] for x in b}
    assert not {x['scene_hash'] for x in a}&{x['scene_hash'] for x in b}
    assert len({x['scene_hash'] for x in b})==100

@pytest.mark.parametrize('name',list(catalog()))
def test_mesh_dimensions(name):
    s=catalog()[name]; mesh=trimesh.load(ROOT/s['visual'],force='mesh',process=False)
    assert np.allclose(mesh.extents,s['dimensions_m'],atol=2e-6)
    assert np.allclose(mesh.bounds,s['bounds_m'],atol=2e-6)
    assert s['grasp_policy']==('strict_top' if s['height_m']<=.07 else 'side_preferred')

def test_clearance():
    cat=catalog()
    for seed in range(100000,100100):
        items=scene_plan(seed)['objects']
        for i,a in enumerate(items):
            ra=np.linalg.norm(cat[a['class_id']]['dimensions_m'][:2])/2
            for b in items[i+1:]:
                rb=np.linalg.norm(cat[b['class_id']]['dimensions_m'][:2])/2
                assert np.linalg.norm(np.array(a['xy_m'])-b['xy_m'])>ra+rb

@pytest.mark.parametrize('seed',range(100000,100050))
def test_settled(seed):
    e=open_evaluation_scene(seed)
    try:
        d=e.diagnostics()
        assert d['interobject_penetrations']==0
        assert d['interobject_contacts']==0
        assert d['max_bottom_gap_m']<.002
        assert d['max_speed']<.01
        assert d['max_linear_speed_m_s']<.01
        assert d['max_angular_speed_rad_s']<.01
        assert d['settle_converged']
    finally: e.close()

def test_gt_not_exposed():
    c=CellCamera(lambda:np.zeros((2,2,3),np.uint8),lambda:None)
    assert set(c.capture())=={'rgb','source','gt_assist','identity_assist'}
    for attr in ('model','data','objects','ground_truth','object_ids','object_mask','T_world_obj','seed','plan'):
        assert not hasattr(c,attr)
    assert 'cell_scene_eval' not in (ROOT/'sim/cell_scene.py').read_text().split('import')[-1]

def test_zones():
    assert len(ZONES)==2
    for z in ZONES.values(): assert z['capacity']==len(z['slots'])==2 and z['layers']==1
