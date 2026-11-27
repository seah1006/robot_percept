import importlib.util
from pathlib import Path

import pytest

_path = Path(__file__).resolve().parents[2] / "m2a/learn/make_synth_dataset.py"
_spec = importlib.util.spec_from_file_location("m2a_d_synth_schema", _path)
_schema = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_schema)
EPISODES, FPS, FRAMES = _schema.EPISODES, _schema.FPS, _schema.FRAMES
HEAD, MASK, MASK_VIDEO, META = _schema.HEAD, _schema.MASK, _schema.MASK_VIDEO, _schema.META
STATE, TASK, WRIST, features, frame = _schema.STATE, _schema.TASK, _schema.WRIST, _schema.features, _schema.frame


def test_v3_contract():
    spec = features()
    assert (FPS, EPISODES, FRAMES) == (10, 5, 50)
    assert (spec[WRIST]["dtype"], spec[WRIST]["shape"]) == ("video", (256, 256, 3))
    assert (spec[MASK]["dtype"], spec[MASK]["shape"]) == ("uint8", (256, 256, 1))
    assert spec[STATE]["shape"] == (15,) and spec[STATE]["dtype"] == "float32"
    assert spec["action"]["shape"] == (7,) and spec["action"]["dtype"] == "float32"
    assert all(spec[k]["shape"] == (1,) and spec[k]["dtype"] == d for k, d in META.items())
    assert HEAD not in spec and features(head=True)[HEAD]["shape"] == (480, 640, 3)
    assert MASK not in features(video_mask=True)
    assert features(video_mask=True)[MASK_VIDEO]["shape"] == (256, 256, 3)


@pytest.mark.parametrize("head,video_mask", [(False, False), (True, True)])
def test_generated_frame_matches_declared_schema(head, video_mask):
    np = pytest.importorskip("numpy")
    row = frame(4, 49, head, video_mask)
    assert row.pop("task") == TASK == "pick up the long board"
    spec = features(head, video_mask)
    assert row.keys() == spec.keys()
    for k, v in row.items():
        assert v.shape == spec[k]["shape"]
        assert v.dtype == np.dtype("uint8" if spec[k]["dtype"] == "video" else spec[k]["dtype"])