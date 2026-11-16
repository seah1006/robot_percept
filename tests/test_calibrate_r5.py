import numpy as np
import pytest
import yaml
from tools.calibrate_camera import estimate,synthetic_views,save_calibration

def test_synthetic_checkerboard(tmp_path):
    K=np.array([[850.,0,640],[0,850,360],[0,0,1]])
    images,poses=synthetic_views(K)
    model,report=estimate(images)
    assert report['accepted_views']==14
    assert report['rms_px']<.5
    assert np.max(np.abs(np.array(model.K)-K))<8
    r,t=poses[0]
    import cv2
    R=cv2.Rodrigues(r)[0]
    # SB may choose reversed corner ordering for symmetric board. Fixture has
    # fixed black/white orientation, so compare camera center geometrically.
    expected=-R.T@t
    assert np.linalg.norm(np.array(model.T_world_cam)[:3,3]-expected)<.012
    out=tmp_path/'calibration.yaml'; save_calibration(out,model,report)
    assert yaml.safe_load(out.read_text())['camera']['calibration_id']==model.calibration_id

def test_insufficient():
    with pytest.raises(ValueError): estimate([np.zeros((720,1280),np.uint8)])

def test_duplicate_views_rejected():
    K=np.array([[850.,0,640],[0,850,360],[0,0,1]])
    images,_=synthetic_views(K)
    with pytest.raises(ValueError,match='quality'):
        estimate([images[0]]*8)

def test_owner_check_unavailable(monkeypatch):
    import subprocess
    from tools.calibrate_camera import camera_owner
    class Result: returncode=127
    monkeypatch.setattr(subprocess,'run',lambda *a,**kw:Result())
    with pytest.raises(RuntimeError,match='unavailable'):
        with camera_owner(98765): pass
