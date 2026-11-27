import importlib.util
import numpy as np
import pytest
from m2a.data.mask import project_box, box_size
from m2a.data.recorder import MASK, STATE, WRIST, FPS, features, mirror_action, mirror_state, write_npz


def test_projection_identity():
    k=np.array([[100.,0,128],[0,100,128],[0,0,1]])
    mask,lost=project_box([0,0,2],np.eye(3),[.2,.4,.2],k,np.eye(4))
    assert not lost and mask.shape==(256,256,1) and mask.dtype==np.uint8
    y,x=np.where(mask[...,0])
    assert (x.min(),x.max(),y.min(),y.max())==(123,133,118,138)


def test_projection_rot_translated_and_lost():
    k=np.array([[100.,0,128],[0,100,128],[0,0,1]])
    t=np.eye(4); t[0,3]=1.
    r=np.array([[0,-1,0],[1,0,0],[0,0,1]])
    mask,lost=project_box([1,0,2],r,[.2,.4,.2],k,t)
    assert not lost
    y,x=np.where(mask[...,0]); assert (x.min(),x.max(),y.min(),y.max())==(118,138,123,133)
    for center in [[1,0,-2],[30,0,2]]:
        mask,lost=project_box(center,r,[.2,.4,.2],k,t)
        assert lost and not mask.any()
    mask,lost=project_box([1,0,.1],r,[.2,.4,.4],k,t)
    assert not lost and mask[128,128,0]==255
    np.testing.assert_allclose(box_size(dict(shape='cylinder',size=[.02,.1])),[.04,.04,.1])


def test_schema_and_mirror():
    assert FPS==10
    f=features()
    assert f[WRIST]['shape']==(256,256,3) and f[MASK]['shape']==(256,256,1)
    assert f[MASK]['dtype']=='uint8' and f[STATE]['shape']==(15,) and f['action']['shape']==(7,)
    assert f[STATE]['names'][3:7]==['qw','qx','qy','qz']
    a=np.arange(1,8,dtype=np.float32)
    np.testing.assert_array_equal(mirror_action(a),[1,-2,3,-4,5,-6,7])
    np.testing.assert_array_equal(mirror_action(mirror_action(a)),a)
    s=np.r_[np.arange(3),.5,.5,.5,.5,np.arange(8)].astype(np.float32)
    np.testing.assert_array_equal(mirror_state(mirror_state(s)),s)


@pytest.mark.skipif(importlib.util.find_spec('lerobot') is None,reason='LeRobot in m2a_lerobot only')
def test_lerobot_cpu_roundtrip(tmp_path):
    from m2a.data.recorder import convert,dataset_class,REPO_ID
    from m2a.learn.make_synth_dataset import frame
    import pyarrow as pa
    import pyarrow.parquet as pq
    rows=[frame(0,i) for i in range(3)]
    root=tmp_path/'dataset'; spool=tmp_path/'spool'
    write_npz(spool/'00000.npz',rows,seed=0,part='P06',mode='P-gate',arm='right',task='pick up bracket')
    convert(spool,root)
    ds=dataset_class()(REPO_ID,root=root,video_backend='pyav')
    assert ds.num_episodes==1 and ds.num_frames==3 and ds.fps==10
    x=ds[1]
    assert x[WRIST].shape==(3,256,256) and x['task']=='pick up bracket'
    np.testing.assert_array_equal(x[MASK].numpy(),rows[1][MASK])
    np.testing.assert_array_equal(x[STATE].numpy(),rows[1][STATE])
    np.testing.assert_array_equal(x['action'].numpy(),rows[1]['action'])
    assert x['target_part'].item()==6 and x['grasp_mode'].item()==1
    mask_type=pq.read_schema(next((root/'data').rglob('*.parquet'))).field(MASK).type
    mask_type=getattr(mask_type,'storage_type',mask_type)
    while hasattr(mask_type,'value_type'):
        mask_type=mask_type.value_type
    assert mask_type==pa.uint8()
