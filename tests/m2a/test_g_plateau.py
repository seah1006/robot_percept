"""V1 plateau segmentation, edge-angle pose and cut-board completion on synthetic RGB-D (no GPU)."""
import numpy as np
import pytest

from m2a.common import load_layout, load_parts
from m2a.percept.geometry import backproject, edge_angle
from m2a.percept.o3 import O3, place
from m2a.percept.v1 import plateau_proposals

K = np.array([[300., 0, 99.5], [0, 300., 99.5], [0, 0, 1.]])
T = np.diag([1., -1., -1., 1.]); T[:3, 3] = [-.12, .35, .6]  # vertical camera, +v toward -y


def scene(boxes):
    """boxes: (x0, x1, y0, y1, top_z, rgb) in table axes; returns a frame dict."""
    d = np.full((200, 200), .6)
    rgb = np.zeros((200, 200, 3), np.uint8)
    cloud = backproject(np.full((200, 200), .6), K, T)
    for x0, x1, y0, y1, z, color in boxes:
        depth = .6 - z
        x = -.12 + (np.arange(200)[None, :]-99.5)/300*depth
        y = .35 - (np.arange(200)[:, None]-99.5)/300*depth
        m = (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)
        d[m], rgb[m] = depth, color
    return dict(rgb=rgb, depth=d, K=K, T_table_cam=T)


def test_edge_angle_survives_a_missing_end():
    a, b = np.meshgrid(np.linspace(-.1, .02, 80), np.linspace(-.03, .03, 24))  # board end cut off at +.02
    yaw = np.deg2rad(37.)
    edge = np.c_[np.r_[a[0], a[-1], a.ravel()[::7]], np.r_[b[0], b[-1], b.ravel()[::7]]]
    p = np.c_[edge[:, 0]*np.cos(yaw)-edge[:, 1]*np.sin(yaw), edge[:, 0]*np.sin(yaw)+edge[:, 1]*np.cos(yaw)]
    assert np.rad2deg(edge_angle(p)) == pytest.approx(37., abs=1.5)


def test_adjacent_objects_of_different_heights_are_two_plateaus():
    layout = load_layout()
    frame = scene([(-.17, -.07, .30, .36, .025, (200, 160, 100)), (-.07, -.01, .30, .36, .03, (140, 140, 145))])
    cloud = backproject(frame['depth'], K, T)
    pieces = plateau_proposals(frame['depth'], cloud, layout)
    assert len(pieces) == 2
    assert not (pieces[0]['mask'] & pieces[1]['mask']).any()


def test_cut_board_is_completed_from_catalog_length_and_flagged():
    layout, parts = load_layout(), load_parts()['parts']
    # P01 (.20 m) along +y with its far end outside the image (v < 0).
    frame = scene([(-.15, -.09, .30, .50, .025, (204, 158, 102))])
    # crop the top 40 rows: the image border now cuts the board at y=.464 (table edge is .5)
    frame = dict(frame, rgb=frame['rgb'][40:], depth=frame['depth'][40:], K=K - [[0, 0, 0], [0, 0, 40], [0, 0, 0]])
    model = O3(layout=layout, parts={'P01': parts['P01']})
    state, graph = model.perceive(frame)
    obj = graph['objects']['p0']
    assert obj['cut'] and obj['top3'][0]['part_id'] == 'P01'
    assert obj['xyz'][:2] == pytest.approx([-.12, .40], abs=.006)
    pose = graph['obj_pose_T']['p0']
    assert pose['part_id'] == 'P01' and pose['shape'] == 'box' and pose['size'] == parts['P01']['size']
    assert abs(abs(pose['yaw'])-np.pi/2) < .03  # long axis along y


def test_place_only_shifts_the_cut_axis():
    part = load_parts()['parts']['P02']
    obs = dict(rot=np.eye(2), lo=np.array([0., 0.]), hi=np.array([.10, .06]), span=np.array([.10, .06]),
               cut_ends=np.array([[False, True], [False, False]]), theta=0.)
    xy, yaw = place(obs, part, 0)
    assert xy == pytest.approx([.16-.08, .03]) and yaw == pytest.approx(0.)
