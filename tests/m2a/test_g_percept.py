import numpy as np
import pytest

from m2a.common import load_layout
from m2a.percept.geometry import backproject, fit_pose
from m2a.percept.o3 import O3, perceive
from m2a.percept.v1 import SAM31Adapter, box_iou, components


def test_inverse_projection_includes_table_rotation_and_translation():
    K = np.array([[2., 0., 1.], [0., 4., 1.], [0., 0., 1.]])
    T = np.array([[0., -1., 0., 1.], [1., 0., 0., 2.], [0., 0., 1., 3.], [0., 0., 0., 1.]])
    d = np.full((3, 3), 2.)
    mask = np.zeros((3, 3), dtype=bool); mask[2, 0] = True
    np.testing.assert_allclose(backproject(d, K, T, mask), [[.5, 1, 5]])
    np.testing.assert_allclose(backproject(d, K, T)[mask], backproject(d, K, T, mask))


def test_pca_rotated_top_plane():
    a, b = np.meshgrid(np.linspace(-.1, .1, 50), np.linspace(-.03, .03, 20))
    yaw = .63; c, s = np.cos(yaw), np.sin(yaw)
    points = np.column_stack((a.ravel()*c-b.ravel()*s+.1, a.ravel()*s+b.ravel()*c-.3, np.full(a.size,.025)))
    xy, theta, size, zlo, zhi = fit_pose(points)
    np.testing.assert_allclose(xy, [.1,-.3], atol=1e-6)
    np.testing.assert_allclose([theta, *size, zlo, zhi], [yaw,.2,.06,.025,.025], atol=1e-6)


def test_components_are_four_connected_and_half_open_boxes():
    m = np.eye(3, dtype=bool)
    assert len(list(components(m, 1))) == 3
    m[1, 0] = m[2, 1] = True
    assert len(list(components(m, 1))) == 1
    assert box_iou([0,0,2,2], [1,0,3,2]) == pytest.approx(1/3)


def synth_board():
    # Vertical camera: camera +z points down; +v points toward -y in T.
    layout = load_layout()
    K = np.array([[300., 0, 99.5], [0, 300., 99.5], [0, 0, 1.]])
    T = np.diag([1.,-1.,-1.,1.]); T[:3,3] = [-.12,.35,.6]
    d = np.full((200,200), .6)
    on_top = (abs(np.arange(200)[:,None]-99.5) < 52) & (abs(np.arange(200)[None,:]-99.5) < 15.7)
    d[on_top] = .575
    rgb = np.zeros((200,200,3), dtype=np.uint8)
    rgb[on_top] = [204,158,102]
    return layout, dict(rgb=rgb, depth=d, K=K, T_table_cam=T)


def test_o3_contract_prediction_only_from_mapping_and_live_api():
    layout, frame = synth_board()
    state, graph = O3(layout=layout).perceive(dict(frame, gt_json='IGNORE', oids=['DO NOT USE']))
    assert state['objects'] == {'p0': dict(part_id='P01', region='left_zone', in_tray=None, on=None)}
    assert state['reach'] == layout['reach']
    obj = graph['objects']['p0']
    assert obj['top3'][0]['part_id'] == 'P01'
    assert obj['xyz'] == pytest.approx([-.12,.35,.0125])
    class Env:
        def render(self, cam):
            assert cam == 'head'
            return frame['rgb'], frame['depth']
        def camera_K(self, cam):
            return frame['K']
        def T_table_cam(self, cam):
            return frame['T_table_cam']
        def get_gt_objects(self):
            pytest.fail('prediction must never read GT')
    assert perceive(Env())[0] == state


def test_strict_box_mode_rejects_unmatched_and_sam_is_explicit():
    layout, frame = synth_board()
    assert not O3(layout=layout, detector=lambda rgb, prompts: [], require_box=True).perceive(frame)[0]['objects']
    with pytest.raises(NotImplementedError, match='gated'):
        SAM31Adapter().segment_text(frame['rgb'], ['board'])
