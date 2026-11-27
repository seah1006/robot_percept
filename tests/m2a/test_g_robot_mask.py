"""CPU-only self-mask, prediction allowlist, and confidence tests."""
from types import SimpleNamespace

import numpy as np
import pytest

from m2a.percept.eval import frame_input
from m2a.percept.o3 import O3, identification_confidence
from m2a.percept.robot_mask import robot_geom_ids, segmentation_mask
from m2a.percept.v1 import plateau_proposals


def test_robot_subtree_excludes_nonrobot_even_with_same_geom_type():
    model = SimpleNamespace(nbody=6, body_parentid=[0, 0, 1, 2, 0, 0],
                            geom_bodyid=np.array([0, 1, 3, 4, 5]),
                            body=lambda name: SimpleNamespace(id=2))
    ids = robot_geom_ids(model)
    assert ids.tolist() == [1, 2]
    seg = np.array([[[1, 5], [2, 5], [3, 5], [2, 6], [-1, -1]]])
    assert segmentation_mask(seg, ids, 5).tolist() == [[True, True, False, False, False]]


def test_exclude_prevents_plateau_and_mask_growth():
    depth = np.full((40, 40), .8)
    yy, xx = np.indices(depth.shape)
    cloud = np.stack([(xx-19)*.002, (yy-19)*.002, np.zeros_like(depth)], axis=-1)
    cloud[5:16, 5:16, 2] = .025
    cloud[22:34, 22:34, 2] = .025
    self_mask = (xx >= 22) & (xx < 34) & (yy >= 22) & (yy < 34)
    layout = {'table': {'size_xy': [1., 1.]}, 'trays': {}}
    assert len(plateau_proposals(depth, cloud, layout)) == 2
    out = plateau_proposals(depth, cloud, layout, exclude=self_mask)
    assert len(out) == 1
    assert not (out[0]['mask'] & self_mask).any()


def test_eval_frame_only_allowlists_input_and_checks_shape():
    frame = frame_input(dict(rgb=np.zeros((2, 3, 3)), depth=np.ones((2, 3)), K=np.eye(3), T_table_cam=np.eye(4),
                             robot_mask=np.zeros((3, 2)), masks='GT', gt_json='GT'))
    assert set(frame) == {'rgb', 'depth', 'K', 'T_table_cam', 'robot_mask'}
    with pytest.raises(ValueError, match='robot_mask'):
        O3().observe(frame)


def test_confidence_and_uncertain_reasons():
    ranked = [(0., 'P01', 0), (1., 'P02', 0), (6., 'P03', 0)]
    w, margin, reasons = identification_confidence(ranked, True, 40)
    assert margin == 1. and reasons == ['cut', 'small_top', 'small_margin']
    assert 0 < w[0] < .3
    w, margin, reasons = identification_confidence([(0., 'P01', 0), (8., 'P02', 0)], False, 89)
    assert not reasons and margin == 8. and .95 < w[0] <= 1.
