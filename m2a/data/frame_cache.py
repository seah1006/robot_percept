"""Bounded-RSS LeRobot v3 cache, published atomically after validation."""
from __future__ import annotations
from contextlib import closing, ExitStack
import fcntl
from hashlib import sha256
import json
import mmap
import os
from pathlib import Path
import tempfile
from time import perf_counter, sleep
import numpy as np
from m2a.learn.make_synth_dataset import MASK, STATE, WRIST

NAMES = {'wrist':'wrist.u8.npy', 'mask':'mask.u8.npy', 'state':'state.npy',
         'action':'action.npy', 'index':'index.npy'}
V = f'videos/{WRIST}'
VERSION = 1


def wait_memory(min_gib=0, deadline=None):
    if not min_gib:
        return True
    announced = False
    while True:
        with open('/proc/meminfo') as f:
            available = next(int(line.split()[1]) for line in f if line.startswith('MemAvailable:'))
        if available >= min_gib * 1024**2:
            return True
        if not announced:
            print(f'waiting: MemAvailable={available} KiB, floor={min_gib} GiB', flush=True)
            announced = True
        if deadline is not None and perf_counter() >= deadline:
            return False
        sleep(5 if deadline is None else max(0,min(5,deadline-perf_counter())))


def discard(array):
    """Drop process RSS, not filesystem cache. Copy samples before calling."""
    if hasattr(array._mmap, 'madvise'):
        array._mmap.madvise(mmap.MADV_DONTNEED)


def _signature(root):
    h = sha256()
    for name in ('info.json', 'm2a_arms.json', 'stats.json'):
        h.update((root/'meta'/name).read_bytes())
    sources = [root/'meta/tasks.parquet']
    for directory, suffix in [('meta/episodes','parquet'), ('data','parquet'), (V,'mp4')]:
        sources.extend(sorted((root/directory).rglob(f'*.{suffix}')))
    for p in sources:
        st = p.stat()
        h.update(f'{p.relative_to(root)}:{st.st_size}:{st.st_mtime_ns}\n'.encode())
    return h.hexdigest()


def _sample_hash(array):
    h = sha256()
    for i in np.linspace(0,len(array)-1,min(len(array),33),dtype=int):
        h.update(np.ascontiguousarray(array[i]).tobytes())
    return h.hexdigest()


def _spec(n, info):
    return {k: ((n,*info['features'][src]['shape']),dtype) for k,src,dtype in
            [('wrist',WRIST,'uint8'),('mask',MASK,'uint8'),('state',STATE,'float32'),
             ('action','action','float32')]} | {'index':((n,3),'int64')}


def open_cache(path, signature, info, limit=None):
    manifest = json.loads((path/'manifest.json').read_text())
    n = manifest['frames']
    if (manifest['version'],manifest['source'],manifest['limit']) != (VERSION,signature,limit):
        raise ValueError(f'{path}: cache version/source/episode selection mismatch')
    episodes = limit if limit is not None else info['total_episodes']
    if (not 0 < n <= info['total_frames'] or (limit is None and n != info['total_frames'])
            or manifest['episodes'] != episodes):
        raise ValueError(f'{path}: invalid frame/episode count')
    maps = {}
    for k,(shape,dtype) in _spec(n,info).items():
        a = np.load(path/NAMES[k],mmap_mode='r',allow_pickle=False)
        if a.shape != shape or a.dtype != np.dtype(dtype) or _sample_hash(a) != manifest['hash'][k]:
            raise ValueError(f'{path}: {k} shape, dtype or sampled checksum mismatch')
        discard(a)
        maps[k] = a
    if maps['index'][-1,2] != n-1 or maps['index'][-1,0]+1 != episodes:
        raise ValueError(f'{path}: inconsistent index extent')
    return maps, manifest


def _parquet_arrays(file):
    cols = ['index','episode_index','task_index',STATE,'action',MASK]
    for batch in file.iter_batches(batch_size=16,columns=cols,use_threads=False):
        vals = []
        for k in range(len(cols)):
            arr = batch.column(k)
            if k >= 3:
                while hasattr(arr,'flatten'):
                    arr = arr.flatten()  # honors offsets of sliced Arrow lists
            vals.append(arr.to_numpy(zero_copy_only=False))
        yield vals


def _rgb_frames(path):
    import av
    with av.open(str(path)) as ct:
        ct.streams.video[0].codec_context.thread_count = 1
        for fr in ct.decode(video=0):
            yield fr.to_ndarray(format='rgb24')


def _build(root,path,info,signature,limit,min_gib):
    import pyarrow.parquet as pq
    columns = ['episode_index','length','dataset_from_index','dataset_to_index',
               'data/chunk_index','data/file_index',f'{V}/chunk_index',f'{V}/file_index',
               f'{V}/from_timestamp',f'{V}/to_timestamp']
    items = sorted((row for p in (root/'meta/episodes').rglob('*.parquet')
                    for row in pq.read_table(p,columns=columns).to_pylist()),
                   key=lambda row:row['episode_index'])
    if len(items) != info['total_episodes'] or not items or (limit is not None and not 0 < limit <= len(items)):
        raise ValueError('invalid number of episodes')
    items = items[:limit]
    expected = items[-1]['dataset_to_index']
    maps = {k:np.lib.format.open_memmap(path/NAMES[k],mode='w+',dtype=dtype,shape=shape)
            for k,(shape,dtype) in _spec(expected,info).items()}
    data_key = video_key = None
    curr = vi = j = 0
    data_seen,video_seen = set(),set()
    with ExitStack() as stack:
        data_stack = stack.enter_context(ExitStack())
        video_stack = stack.enter_context(ExitStack())
        for ep,row in enumerate(items):
            wait_memory(min_gib)
            lo,hi = row['dataset_from_index'],row['dataset_to_index']
            if ep != row['episode_index'] or curr != lo or hi-lo != row['length'] or hi <= lo:
                raise ValueError(f'invalid episode bounds {row}')
            dk = (row['data/chunk_index'],row['data/file_index'])
            if dk != data_key:
                if data_key is not None and (j != len(vals[0]) or next(data,None) is not None):
                    raise ValueError('unexpected extra parquet rows')
                if dk in data_seen:
                    raise ValueError('non-contiguous parquet file')
                data_seen.add(dk)
                data_stack.close()
                data_key = dk
                p = root/info['data_path'].format(chunk_index=dk[0],file_index=dk[1])
                pf = data_stack.enter_context(closing(pq.ParquetFile(p)))
                data = data_stack.enter_context(closing(_parquet_arrays(pf)))
                vals = next(data)
                j = 0
            vk = (row[f'{V}/chunk_index'],row[f'{V}/file_index'])
            if vk != video_key:
                if video_key is not None and next(rgb,None) is not None:
                    raise ValueError('unexpected extra video frames')
                if vk in video_seen:
                    raise ValueError('non-contiguous video file')
                video_seen.add(vk)
                video_stack.close()
                video_key,vi = vk,0
                p = root/info['video_path'].format(video_key=WRIST,chunk_index=vk[0],file_index=vk[1])
                rgb = video_stack.enter_context(closing(_rgb_frames(p)))
            start,end = [round(row[f'{V}/{k}_timestamp']*info['fps']) for k in ('from','to')]
            if start != vi or end-start != hi-lo:
                raise ValueError(f'video episode {ep} timestamp/count mismatch')
            for i in range(lo,hi):
                frame = next(rgb,None)
                if frame is None or frame.shape != maps['wrist'].shape[1:]:
                    raise ValueError(f'video frame {i} missing or wrong shape')
                maps['wrist'][i] = frame
                vi += 1
            while curr < hi:
                if j == len(vals[0]):
                    vals = next(data)
                    j = 0
                n = len(vals[0]); take = min(n-j,hi-curr)
                src,dst = slice(j,j+take),slice(curr,curr+take)
                if not np.array_equal(vals[0][src],np.arange(curr,curr+take)) or not np.all(vals[1][src] == ep):
                    raise ValueError(f'parquet index mismatch near row {curr}')
                maps['index'][dst] = np.column_stack((vals[1][src],vals[2][src],np.full(take,hi-1)))
                for key,val in zip(('state','action','mask'),vals[3:],strict=True):
                    m = maps[key]
                    m[dst] = val.reshape(n,*m.shape[1:])[src]
                curr += take
                j += take
            for key, a in maps.items():
                a.flush()
                discard(a)
                if hasattr(os, "posix_fadvise"):
                    # Reclaim just-written, already-flushed file pages as well as RSS.
                    stride = a.strides[0]
                    with (path/NAMES[key]).open("rb") as f:
                        os.posix_fadvise(f.fileno(), a.offset + lo*stride,
                                         (hi-lo)*stride, os.POSIX_FADV_DONTNEED)
            if (ep+1) % 50 == 0 or ep+1 == len(items):
                print(f'cached {ep+1}/{len(items)} episodes, {curr}/{expected} frames',flush=True)
        if len(items) == info['total_episodes'] and (curr != info['total_frames'] or
                j != len(vals[0]) or next(data,None) is not None or next(rgb,None) is not None):
            raise ValueError('cache frame total disagrees with source')
    if _signature(root) != signature:
        raise ValueError('source changed during cache build')
    manifest = dict(version=VERSION,source=signature,frames=curr,episodes=len(items),limit=limit,
                    hash={k:_sample_hash(a) for k,a in maps.items()})
    (path/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')


def ensure_cache(root,path,limit=None,min_gib=0):
    info = json.loads((root/'meta/info.json').read_text())
    path.parent.mkdir(parents=True,exist_ok=True)
    with (path.parent/f'.{path.name}.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        signature = _signature(root)
        if not path.exists():
            with tempfile.TemporaryDirectory(prefix=f'.{path.name}.',dir=path.parent) as d:
                staging = Path(d)
                _build(root,staging,info,signature,limit,min_gib)
                open_cache(staging,signature,info,limit)
                staging.rename(path)
        return open_cache(path,signature,info,limit)


def chunk_indices(i,end,chunk):
    idx = np.arange(i,i+chunk)
    return np.minimum(idx,end),idx>end


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('root',type=Path)
    p.add_argument('cache',type=Path)
    p.add_argument('--episodes',type=int)
    p.add_argument('--min-available-gib',type=int,default=0)
    a = p.parse_args()
    _,manifest = ensure_cache(a.root,a.cache,a.episodes,a.min_available_gib)
    print(json.dumps(manifest),flush=True)
