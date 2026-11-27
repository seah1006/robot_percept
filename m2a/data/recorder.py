"""10 Hz episode bridge: sim-side NPZ, then local LeRobot v3 in m2a_lerobot."""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path
import numpy as np
from m2a.learn.make_synth_dataset import FPS, MASK, META, STATE, WRIST, features as gate_features
from .mask import wrist_gt_mask

REPO_ID = 'm2a/d1_grasp_lift'
DT = 1 / FPS
REFLECT = np.array([1,-1,1])
JOINT_MIRROR = np.array([1,-1,-1,1,-1,1,-1])
PART_IDS = {f'P{i:02}':i for i in range(1,7)}
MODE_IDS = {'P-phys':0, 'P-gate':1, 'P-oracle':2, 'P-gate-strict':3}


def features(action_encoding=None):
    f = gate_features()
    f[STATE]['names'][3:7] = ['qw','qx','qy','qz']
    if action_encoding == 'ee_target_table_rotvec_v1':
        from .ee_target import ACTION_NAMES
        f['action']['names'] = ACTION_NAMES
        f['grasp_mode'] = dict(dtype='string',shape=(1,),names=None)
    return f


def mirror_action(a):
    """Left↔right: polar position, axial rotation, unchanged grip."""
    return a * np.r_[REFLECT, -REFLECT, 1]


def observation(env, arm, oid, grip):
    xyz, quat = env.ee_pose(arm)
    q = env.arm_q(arm)
    cam = {'left':'wrist_l','right':'wrist_r'}[arm]
    rgb, _ = env.render(cam)
    mask, lost = wrist_gt_mask(env, oid, cam)
    # Left camera is native orientation in storage. Mirror only when forming ACT inputs.
    quat = np.asarray(quat, float)
    if quat[np.argmax(np.abs(quat))] < 0:
        quat = -quat
    state = np.asarray([*xyz,*quat,grip,*q], dtype=np.float32)
    return {WRIST:rgb, MASK:mask, STATE:state}, lost


def mirror_state(state):
    """Canonicalize the reflected quaternion by a nonnegative major component."""
    state = (state * np.r_[REFLECT,1,-REFLECT,1,JOINT_MIRROR]).astype(np.float32)
    quat = state[...,3:7]
    pivot = np.take_along_axis(quat,np.argmax(np.abs(quat),axis=-1,keepdims=True),axis=-1)
    quat *= np.where(pivot<0,-1,1)
    return state


def policy_observation(obs, arm):
    if arm == 'right':
        return obs
    state = mirror_state(obs[STATE])
    return {WRIST:np.ascontiguousarray(obs[WRIST][:, ::-1]),
            MASK:np.ascontiguousarray(obs[MASK][:, ::-1]), STATE:state}


def write_npz(path, rows, *, seed, part, mode, arm, task, provenance=None):
    if not rows:
        raise ValueError('Empty episode')
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.with_suffix('.tmp').open('wb') as f:
        np.savez_compressed(f, **{k:np.stack([row[k] for row in rows]) for k in (WRIST,MASK,STATE,'action')},
                            metadata=json.dumps(dict(arm=arm,task=task,scene_seed=seed, skill_id=1,
                                                     target_part=PART_IDS[part], source=0, sigma_cm=0.,
                                                     grasp_mode=mode, **{k:v for k,v in (provenance or {}).items() if k != 'grasp_mode'})))
    path.with_suffix('.tmp').replace(path)


def dataset_class():
    from m2a.learn.rocm_compat import torchvision_import
    with torchvision_import():
        from lerobot.datasets.lerobot_dataset import LeRobotDataset
    return LeRobotDataset


def convert(spool, root, limit=None):
    ds_type = dataset_class()
    attempts = sorted(Path(spool).glob('*.npz'))[:limit]
    if not attempts:
        raise ValueError('No successful NPZ episodes')
    with np.load(attempts[0],allow_pickle=False) as first:
        encoding = json.loads(first['metadata'].item()).get('action_encoding')
    schema = features(encoding)
    ds = ds_type.create(repo_id=REPO_ID,root=Path(root),fps=FPS,robot_type='unitree_g1_sim',
                        features=schema,use_videos=True,vcodec='h264',encoder_threads=2)
    episode_arms = []
    try:
        for path in attempts:
            with np.load(path,allow_pickle=False) as ep:
                meta = json.loads(ep['metadata'].item())
                if meta.get('action_encoding') != encoding: raise ValueError('mixed action semantics')
                cols = {k:ep[k] for k in (WRIST,MASK,STATE,'action')}
                for k, values in cols.items():
                    f = schema[k]
                    dtype = 'uint8' if f['dtype']=='video' else f['dtype']
                    if values.dtype != np.dtype(dtype) or values.shape != (len(cols[STATE]),*f['shape']):
                        raise ValueError(f'{path}: invalid {k}')
                scalar = {k:np.array([meta[k]],dtype=d) for k,d in META.items() if k!='grasp_mode'}
                mode = meta.get('grasp_mode_name',meta['grasp_mode'])
                if 'string' == schema['grasp_mode']['dtype']:
                    if mode not in MODE_IDS: raise ValueError(f'{path}: invalid grasp mode')
                    scalar['grasp_mode'] = mode
                else:
                    scalar['grasp_mode'] = np.array([MODE_IDS[mode] if isinstance(mode,str) else mode],dtype='int64')
                for values in zip(*cols.values(),strict=True):
                    ds.add_frame(dict(zip(cols,values,strict=True),**scalar,task=meta['task']))
                ds.save_episode()
                episode_arms.append(dict(arm=meta['arm'],seed=meta['scene_seed'],source_npz=path.name, **{k: meta[k] for k in ('commit','scene_digest','distractors','grasp_mode_name','grasp_mode','action_encoding','expert_variant','source_servo') if k in meta}))
    finally:
        ds.finalize()
    sidecar = json.dumps(episode_arms,sort_keys=True,indent=2)
    (Path(root)/'meta'/'m2a_arms.json').write_text(sidecar,encoding='utf-8')
    print(json.dumps(dict(root=str(root),episodes=len(episode_arms),frames=ds.num_frames,
                          arm_manifest_sha256=sha256(sidecar.encode()).hexdigest())),flush=True)
    return ds


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('spool',type=Path)
    p.add_argument('root',type=Path)
    p.add_argument('--limit',type=int)
    a = p.parse_args()
    convert(a.spool,a.root,a.limit)


if __name__ == '__main__':
    main()
