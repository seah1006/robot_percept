from collections import Counter
from itertools import combinations
from math import isclose

import numpy as np
import pytest
from m2a.common import load_layout, load_parts
from m2a.scene._geometry import contains, corners, obb, overlaps, size_xyz, tray_box, tray_rect
from m2a.scene.cli import mixed_situation
from m2a.scene.generator import GAP, LEVELS, STACK_MARGIN, SITUATIONS, generate, scene_digest
from m2a.scene.symbolic import symbolic, symbolic_from_gt

LAYOUT = load_layout()
CATALOG = load_parts()
PARTS = CATALOG['parts']


def check_geometry(scene):
    boxes = {}
    by_id = {obj['oid']: obj for obj in scene['objects']}
    assert len(by_id) == len(scene['objects'])
    for oid, obj in by_id.items():
        dim = size_xyz(PARTS[obj['part_id']])
        box = boxes[oid] = obb(obj['xyz'], dim, obj['yaw'])
        rect = (tray_rect(LAYOUT['trays'][obj['in_tray']]) if obj['in_tray']
                else LAYOUT['regions'][obj['region']])
        assert all(contains(rect, xy) for xy in corners(box))
        if not obj['in_tray']:
            assert all(not overlaps(box, tray_box(t), GAP)
                       for t in LAYOUT['trays'].values())
        if obj['on']:
            base = by_id[obj['on']]
            height = size_xyz(PARTS[base['part_id']])[2]
            assert isclose(obj['xyz'][2] - base['xyz'][2], (dim[2]+height)/2)
            assert PARTS[base['part_id']]['shape'] == 'box'
            bx, by, a, b, c, sn = obb(base['xyz'], size_xyz(PARTS[base['part_id']]), base['yaw'])
            for x, y in corners(box):
                assert abs((x-bx)*c+(y-by)*sn) <= a-STACK_MARGIN+1e-12
                assert abs(-(x-bx)*sn+(y-by)*c) <= b-STACK_MARGIN+1e-12
    for a, b in combinations(by_id, 2):
        if a != by_id[b]['on'] and b != by_id[a]['on']:
            assert not overlaps(boxes[a], boxes[b], GAP)
    assert symbolic_from_gt(by_id, LAYOUT, CATALOG) == symbolic(scene, LAYOUT)


@pytest.mark.parametrize('level', LEVELS)
@pytest.mark.parametrize('situation', SITUATIONS)
def test_situation_properties(level, situation):
    scene = generate(10047, level, situation, 'dev')
    duplicate = generate(10047, level, situation, 'dev')
    assert duplicate == scene and scene_digest(duplicate) == scene_digest(scene)
    check_geometry(scene)
    trays = scene['expected']['goal']['trays']
    requested = sum((Counter(t) for t in trays.values()), Counter())
    counts = Counter(obj['part_id'] for obj in scene['objects'])
    assert scene['expected']['missing'] == dict(requested - counts)
    if level == 'L0':
        assert sum(requested.values()) == 1
        assert 1 <= len(scene['objects']) - (situation != 'missing') <= 3
    elif level == 'L1':
        assert 4 <= sum(requested.values()) <= 6 and 1 <= len(trays) <= 2
        assert 4 <= len(scene["objects"]) <= 6
    else:
        assert 6 <= len(scene['objects']) <= 10 and 2 <= len(trays) <= 3
        assert all(counts[pid] for pid in ('P01', 'P02', 'D01'))
    if situation == 'missing':
        assert sum(scene['expected']['missing'].values()) == 1
    if situation == 'pretray':
        preplaced = [obj for obj in scene['objects'] if obj['in_tray']]
        assert len(preplaced) == 2
        assert sum(obj['part_id'] in trays.get(obj['in_tray'], {}) for obj in preplaced) == 1
        assert all(obj['region'] is None for obj in preplaced)
    if situation == 'stacked':
        assert sum(obj['on'] is not None for obj in scene['objects']) == 1
    if situation == 'reach':
        case = scene['expected']['reach']
        obj = next(obj for obj in scene['objects'] if obj['oid'] == case['oid'])
        assert obj['part_id'] in requested
        assert obj['region'] in LAYOUT['reach'][case['required_pick_arm']]
        assert obj['region'] not in LAYOUT['reach'][case['nominal_arm']]


def test_seed_boundary():
    assert generate(0, 'L0', 'standard', 'train')['seed'] == 0
    for seed, split in ((5000, 'train'), (9999, 'dev'), (10200, 'dev'), (90000, 'test'),
                        (90000, 'train'), (True, 'train')):
        with pytest.raises(ValueError):
            generate(seed, 'L0', 'standard', split)
    # Exercise the positive gate without generating from the sealed holdout in routine tests.
    from m2a.scene.generator import validate_seed
    validate_seed(90000, 'test', final_test=True)


def test_all_dev():
    for seed in range(10000, 10200):
        level = LEVELS[(seed-10000) % len(LEVELS)]
        check_geometry(generate(seed, level, mixed_situation(seed), 'dev'))


def test_stack_requires_actual_overlap_and_surface_contact():
    # Cylinder OBBs overlap at the diagonal, but circles do not.
    lower = dict(part_id='P04', xyz=[0., .35, .03], yaw=0.)
    top = dict(part_id='P04', xyz=[.019, .369, .09], yaw=0.)
    gt = {'lower': lower, 'top': top}
    assert symbolic_from_gt(gt, LAYOUT, PARTS)['objects']['top']['on'] is None
    top['xyz'][0] = 0.
    assert symbolic_from_gt(gt, LAYOUT, PARTS)['objects']['top']['on'] == 'lower'
    top['xyz'][2] += .02
    assert symbolic_from_gt(gt, LAYOUT, PARTS)['objects']['top']['on'] is None


def test_impossible_layout_fails_without_dropping_objects():
    from copy import deepcopy
    impossible = deepcopy(LAYOUT)
    impossible['regions'] = {region: [0., .001, 0., .001] for region in LAYOUT['regions']}
    with pytest.raises(ValueError, match='S0 packing exhausted.*check layout dimensions and reach'):
        generate(10000, 'L2', 'standard', 'dev', layout=impossible)


# Frozen nominal input geometry; production layout changes should not rebaseline RNG.
GOLDEN_LAYOUT = {'table': {'size_xy': [0.5, 1.0]},
 'regions': {'left_zone': [-0.2, 0.2, 0.26, 0.48],
             'right_zone': [-0.2, 0.2, -0.48, -0.26],
             'center_zone': [-0.22, -0.04, -0.24, 0.24]},
 'trays': {'T1': {'center': [0.1, 0.16], 'inner': [0.24, 0.13], 'wall_h': 0.03},
           'T2': {'center': [0.1, 0.0], 'inner': [0.24, 0.13], 'wall_h': 0.03},
           'T3': {'center': [0.1, -0.16], 'inner': [0.24, 0.13], 'wall_h': 0.03}},
 'reach': {'left': ['left_zone', 'center_zone', 'T1', 'T2', 'T3'],
           'right': ['right_zone', 'center_zone', 'T1', 'T2', 'T3']},
 'judge': {'tray_margin': 0.01, 'tray_z_max_above_floor': 0.08, 'settle_speed': 0.02}}
GOLDEN_NUMPY = '2.5.3'


@pytest.mark.parametrize("seed,level,situation,split,digest", [
    (31, 'L0', 'standard', 'train', 'b1cadea9bcfefdc7da4d235dd57ad22831569663748faa8dd25811d018c4750c'),
    (10021, 'L1', 'pretray', 'dev', 'e060f608063de9d8b8fa6958b20f203e613f7e9c34d5d03198d22b4bed1915ae'),
    (10047, 'L2', 'stacked', 'dev', 'ce80323261ee8fad5df48c47f82ee75b19ced7d968ced468b316da8c8c66af6c'),
    (10103, 'L2', 'missing', 'dev', 'ad96ca7967321d1bd61ae643acb46be0fa08de350d84a096a1543f7c65502c3f'),
    (10179, 'L2', 'reach', 'dev', 'e9e40ab07b610f49dcc169dcac755d41f649b1bdc5ed4baf478dec5a4245c567'),
])
def test_golden_scene_sha256(seed, level, situation, split, digest):
    actual = scene_digest(generate(seed, level, situation, split, layout=GOLDEN_LAYOUT))
    assert actual == digest, f'Scene drift: NumPy baseline {GOLDEN_NUMPY}, running {np.__version__}'


def test_cli_uses_explicit_layout(tmp_path, capsys):
    from copy import deepcopy
    import json
    from m2a.scene.cli import main
    alternate = deepcopy(GOLDEN_LAYOUT)
    for tray in alternate['trays'].values():
        tray['floor_z'] = .01
    src = tmp_path / 'layout.json'
    src.write_text(json.dumps(alternate), encoding='utf-8')
    main(['--split', 'dev', '--start', '10021', '--level', 'L1', '--situation', 'pretray', '--layout', str(src)])
    actual = json.loads(capsys.readouterr().out)
    assert actual == generate(10021, 'L1', 'pretray', 'dev', layout=alternate)
    assert actual != generate(10021, 'L1', 'pretray', 'dev', layout=GOLDEN_LAYOUT)
