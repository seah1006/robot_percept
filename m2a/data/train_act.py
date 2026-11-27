"""Train ACT on D1, with uniform frame sampling and a resumable local checkpoint."""
from __future__ import annotations
import argparse
from collections import OrderedDict
from hashlib import sha256
import json
from pathlib import Path
import math
from time import perf_counter
import statistics
import numpy as np
from m2a.learn.bench_policy import emit
from m2a.learn.make_synth_dataset import MASK_VIDEO
from m2a.learn.rocm_compat import torchvision_import
from .recorder import FPS, MASK, REPO_ID, STATE, WRIST, dataset_class, mirror_action, mirror_state


def act_api():
    with torchvision_import():
        from lerobot.configs.types import FeatureType, PolicyFeature
        from lerobot.policies.act.configuration_act import ACTConfig
        from lerobot.policies.act.modeling_act import ACTPolicy
        from lerobot.policies.act.processor_act import make_act_pre_post_processors
    return FeatureType, PolicyFeature, ACTConfig, ACTPolicy, make_act_pre_post_processors


def tensors(wrist, mask, state):
    import torch
    return {WRIST:wrist.float(), STATE:state.float(),
            MASK_VIDEO:mask.permute(2,0,1).float().div(255).expand(3,-1,-1).contiguous()}


def dataset_stats(root, ds, manifest):
    import pyarrow.parquet as pq
    stats = dict(ds.meta.stats)
    paths = sorted((root/'data').rglob('*.parquet'))
    columns = {k:[] for k in (STATE,'action')}
    for path in paths:
        tab = pq.read_table(path,columns=['episode_index', STATE, 'action'])
        arm = np.array([manifest[i]['arm']=='left' for i in tab['episode_index'].to_pylist()])
        for k, mirror in ((STATE,mirror_state),('action',mirror_action)):
            col = np.asarray(tab[k].to_pylist(), dtype=np.float32)
            col[arm] = mirror(col[arm])
            columns[k].append(col)
    for k, chunks in columns.items():
        col = np.concatenate(chunks)
        stats[k] = dict(mean=col.mean(0),std=np.maximum(col.std(0),1e-6),
                        min=col.min(0),max=col.max(0))
    if WRIST in stats:
        stats[MASK_VIDEO] = {v:np.full_like(sample, value) for v,value in [('mean',.5),('std',.5)]
                             for sample in [stats[WRIST]['mean']]}
    return stats


def run(a):
    import torch
    from torch.utils.data import default_collate
    torch.set_num_threads(2)
    torch.manual_seed(41)
    if not torch.cuda.is_available():
        raise RuntimeError('ROCm GPU unavailable; no CPU training fallback')
    torch.cuda.reset_peak_memory_stats()
    t0 = perf_counter()
    manifest_path = a.root/'meta'/'m2a_arms.json'
    manifest = json.loads(manifest_path.read_text())
    identity = sha256(manifest_path.read_bytes() + (a.root/'meta'/'info.json').read_bytes()).hexdigest()
    ds = dataset_class()(REPO_ID,root=a.root,video_backend='pyav',
                         delta_timestamps={'action':[i/FPS for i in range(a.chunk)]})
    # Per-sample H.264 seek cost ~0.7 s; decode the one wrist video sequentially into RAM once (~4 s).
    import av
    frames = []
    for path in sorted((a.root/'videos'/WRIST).rglob('*.mp4')):
        with av.open(str(path)) as ct:
            frames += [fr.to_ndarray(format='rgb24') for fr in ct.decode(video=0)]
    if len(frames)!=ds.num_frames:
        raise ValueError(f'decoded {len(frames)} frames != dataset {ds.num_frames}')
    wrist_cache = torch.from_numpy(np.stack(frames)).permute(0,3,1,2)
    del frames
    # ds[i] also re-reads 20 mask rows for the action chunk (~0.6 s); load columns once and build chunks here.
    import pyarrow.parquet as pq
    tabs = [pq.read_table(p,columns=[MASK,STATE,'action','episode_index']) for p in sorted((a.root/'data').rglob('*.parquet'))]
    def flat(col):
        c = col.combine_chunks(); 
        while hasattr(c,'values'): c = c.values
        return c.to_numpy(zero_copy_only=False)
    mask_all = torch.from_numpy(np.concatenate([flat(t[MASK]).reshape(len(t),256,256,1) for t in tabs]))
    state_all = np.concatenate([np.asarray(t[STATE].to_pylist(),np.float32) for t in tabs])
    action_all = np.concatenate([np.asarray(t['action'].to_pylist(),np.float32) for t in tabs])
    ep_all = np.concatenate([np.asarray(t['episode_index'].to_pylist()) for t in tabs])
    ep_end = {e:int(np.flatnonzero(ep_all==e).max()) for e in np.unique(ep_all)}
    if len(ep_all)!=ds.num_frames or len(mask_all)!=ds.num_frames:
        raise ValueError('parquet rows != dataset frames')
    F,P,Config,Policy,processors = act_api()
    cfg = Config(device='cuda',push_to_hub=False,chunk_size=a.chunk,n_action_steps=a.chunk,
                 pretrained_backbone_weights=None,input_features={STATE:P(F.STATE,(15,)),
                    WRIST:P(F.VISUAL,(3,256,256)),MASK_VIDEO:P(F.VISUAL,(3,256,256))},
                 output_features={'action':P(F.ACTION,(7,))})
    model = Policy(cfg).float().cuda().train()
    stats = dataset_stats(a.root, ds, manifest)
    pre,post = processors(cfg,stats)
    opt = torch.optim.AdamW(model.get_optim_params(),lr=cfg.optimizer_lr,
                            weight_decay=cfg.optimizer_weight_decay)
    rng = np.random.default_rng(41)
    losses=[]; compute=[]; previous_peaks=(0,0)
    a.output.mkdir(parents=True,exist_ok=True)
    cp = a.output/'training_state.pt'
    if a.resume:
        prev = torch.load(cp,map_location='cpu',weights_only=True)
        if prev['identity']!=identity or (prev['chunk'],prev['batch'])!=(a.chunk,a.batch):
            raise ValueError('Resume checkpoint and dataset/ACT configuration mismatch')
        model.load_state_dict(prev['model']); opt.load_state_dict(prev['opt'])
        rng.bit_generator.state = prev['rng']
        torch.set_rng_state(prev['cpu_rng']); torch.cuda.set_rng_state(prev['gpu_rng'])
        losses,compute,previous_peaks = prev['losses'], prev['compute'], prev['peaks']
    elif cp.exists():
        raise FileExistsError(f'{cp} exists; resume explicitly')
    emit(event='config',root=str(a.root),episodes=ds.num_episodes,frames=ds.num_frames,
         batch=a.batch,chunk=a.chunk,steps=a.steps,dtype='fp32',lr=cfg.optimizer_lr,
         gpu=torch.cuda.get_device_name(0),hip=torch.version.hip,resume_step=len(losses))
    cache = OrderedDict()

    def get(i):
        if i in cache:
            cache.move_to_end(i)
            return cache[i]
        idx = np.arange(i,i+a.chunk); pad = idx>ep_end[ep_all[i]]
        idx = np.minimum(idx,ep_end[ep_all[i]])   # same padding rule as LeRobot delta_timestamps
        x = dict(episode_index=torch.tensor(int(ep_all[i])),action_is_pad=torch.from_numpy(pad))
        wrist,mask = wrist_cache[i].float().div(255), mask_all[i]
        state,action = torch.from_numpy(state_all[i].copy()), torch.from_numpy(action_all[idx])
        if manifest[x['episode_index'].item()]['arm']=='left':
            wrist,mask = wrist.flip(-1),mask.flip(1)
            state = torch.from_numpy(mirror_state(state.numpy()))
            action = torch.from_numpy(mirror_action(action.numpy()).astype(np.float32))
        entry = dict(tensors(wrist,mask,state),action=action,action_is_pad=x['action_is_pad'])
        cache[i] = entry
        if len(cache)>64:
            cache.popitem(last=False)
        return entry

    for step in range(len(losses),a.steps):
        if perf_counter()-t0 >= a.budget:
            break
        batch = default_collate([get(int(i)) for i in rng.integers(ds.num_frames,size=a.batch)])
        torch.cuda.synchronize()
        t1 = perf_counter()
        opt.zero_grad(set_to_none=True)
        loss,_ = model(pre(batch))
        if not math.isfinite(loss.item()):
            raise RuntimeError('Non-finite ACT loss')
        loss.backward(); opt.step(); torch.cuda.synchronize()
        compute.append(perf_counter()-t1); losses.append(loss.detach().item())
        emit(event='step',step=step+1,loss=losses[-1],compute_s=compute[-1],elapsed_s=perf_counter()-t0)
    if not losses:
        raise RuntimeError('No completed steps')
    peaks = [max(a,b) for a,b in zip(previous_peaks,(torch.cuda.max_memory_allocated(),
                 torch.cuda.max_memory_reserved()),strict=True)]
    tmp = cp.with_suffix('.tmp')
    torch.save(dict(identity=identity,model=model.state_dict(),opt=opt.state_dict(),losses=losses,
        compute=compute,peaks=peaks,rng=rng.bit_generator.state,cpu_rng=torch.get_rng_state(),
        gpu_rng=torch.cuda.get_rng_state(),chunk=a.chunk,batch=a.batch),tmp)
    tmp.replace(cp)
    policy_path = a.output/'policy'
    model.save_pretrained(policy_path); pre.save_pretrained(policy_path); post.save_pretrained(policy_path)
    torch.save({k:{n:torch.as_tensor(v) for n,v in d.items()} for k,d in stats.items()},policy_path/'m2a_stats.pt')
    emit(event='summary',steps=len(losses),first_loss=losses[0],last_loss=losses[-1],
         first10_mean=statistics.mean(losses[:10]),last10_mean=statistics.mean(losses[-10:]),
         step_median_s=statistics.median(compute),elapsed_s=perf_counter()-t0,
         peak_allocated=peaks[0],peak_reserved=peaks[1],completed=len(losses)==a.steps)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('root',type=Path); p.add_argument('output',type=Path)
    p.add_argument('--batch',type=int,default=4); p.add_argument('--chunk',type=int,default=20)
    p.add_argument('--steps',type=int,default=100); p.add_argument('--budget',type=float,default=240)
    p.add_argument('--resume',action='store_true')
    a=p.parse_args()
    if min(a.batch,a.chunk,a.steps)<=0 or not 0<a.budget<=260:
        p.error('Positive batch/chunk/steps and budget ≤260 s required')
    run(a)


if __name__=='__main__':
    main()
