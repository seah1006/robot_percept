import json
from pathlib import Path
import numpy as np
import pytest
from m2a.data import frame_cache as fc


def test_memmap_round_trip_and_sample_corruption(tmp_path):
    info = {'total_frames': 5, 'total_episodes': 2, 'features': {
        fc.WRIST: {'shape': [2, 2, 3]}, fc.MASK: {'shape': [2, 2, 1]},
        fc.STATE: {'shape': [15]}, 'action': {'shape': [7]}}}
    values = {}
    for key, (shape, dtype) in fc._spec(5, info).items():
        a = np.lib.format.open_memmap(tmp_path/fc.NAMES[key], 'w+', dtype=dtype, shape=shape)
        a[:] = np.arange(a.size).reshape(a.shape)
        if key == 'index':
            a[:] = [[0, 10, 1], [0, 10, 1], [1, 12, 4], [1, 12, 4], [1, 12, 4]]
        a.flush()
        values[key] = a.copy()
    (tmp_path/'manifest.json').write_text(json.dumps(dict(version=fc.VERSION, source='src',
        frames=5, episodes=2, limit=None, hash={k: fc._sample_hash(v) for k,v in values.items()})))
    maps, m = fc.open_cache(tmp_path,'src',info)
    assert m['frames'] == 5
    for key, a in maps.items():
        assert isinstance(a,np.memmap) and not a.flags.writeable
        np.testing.assert_array_equal(a,values[key])
    idx, pad = fc.chunk_indices(0, maps['index'][0,2], 4)
    np.testing.assert_array_equal(idx, [0,1,1,1])
    np.testing.assert_array_equal(pad, [False,False,True,True])
    np.testing.assert_array_equal(maps['action'][idx][2:], np.repeat(values['action'][1:2],2,axis=0))
    with pytest.raises(ValueError, match='version/source'):
        fc.open_cache(tmp_path,'different',info)
    corrupt = np.load(tmp_path/fc.NAMES['mask'],mmap_mode='r+')
    corrupt[2] = 0
    corrupt.flush()
    with pytest.raises(ValueError, match='mask.*checksum'):
        fc.open_cache(tmp_path,'src',info)


def test_stream_build_validates_rows_and_reuses_cache(tmp_path, monkeypatch):
    pa = pytest.importorskip('pyarrow')
    pq = pytest.importorskip('pyarrow.parquet')
    root = tmp_path/'source'
    for d in ('meta/episodes','data',fc.V):
        (root/d).mkdir(parents=True)
    features = {fc.WRIST: [2,2,3], fc.MASK: [2,2,1], fc.STATE: [2], 'action': [1]}
    info = dict(total_frames=19,total_episodes=2,fps=10,
        features={k:dict(shape=v) for k,v in features.items()},
        data_path='data/{chunk_index}-{file_index}.parquet',
        video_path='videos/{video_key}/{chunk_index}-{file_index}.mp4')
    (root/'meta/info.json').write_text(json.dumps(info))
    for p in ('stats.json','m2a_arms.json','tasks.parquet'):
        (root/'meta'/p).touch()
    pq.write_table(pa.Table.from_pylist([
        {'episode_index': ep, 'length': hi-lo,'dataset_from_index':lo,'dataset_to_index':hi,
         'data/chunk_index':0,'data/file_index':0,f'{fc.V}/chunk_index':0,f'{fc.V}/file_index':0,
         f'{fc.V}/from_timestamp':lo/10,f'{fc.V}/to_timestamp':hi/10}
        for ep,(lo,hi) in enumerate([(0,3),(3,19)])]),root/'meta/episodes/0.parquet')
    rows = [{ 'index': i, 'episode_index': int(i>=3), 'task_index': int(i>=3),
        fc.STATE: [float(i),-float(i)], 'action': [2.*i], fc.MASK: [[[i],[i]],[[i],[i]]]}
        for i in range(19)]
    pq.write_table(pa.Table.from_pylist(rows),root/'data/0-0.parquet')
    (root/fc.V/'0-0.mp4').touch()
    decoded = []
    def frames(path: Path):
        assert path == root/fc.V/'0-0.mp4'
        for i in range(19):
            decoded.append(i)
            yield np.full((2,2,3),i+30,dtype=np.uint8)
    monkeypatch.setattr(fc,'_rgb_frames',frames)
    maps, m = fc.ensure_cache(root,tmp_path/'pilot',limit=1)
    assert m['frames'] == 3 and decoded == list(range(3))
    decoded.clear()
    for _ in range(2):
        maps, m = fc.ensure_cache(root,tmp_path/'full')
        assert m['frames'] == 19
        np.testing.assert_array_equal(maps['wrist'][:,0,0,0],np.arange(19)+30)
        np.testing.assert_array_equal(maps['mask'][:,0,0,0],np.arange(19))
        np.testing.assert_array_equal(maps['state'][:,1],-np.arange(19))
        np.testing.assert_array_equal(maps['action'][:,0],2*np.arange(19))
        np.testing.assert_array_equal(maps['index'][:,2],[2]*3+[18]*16)
    assert decoded == list(range(19))
