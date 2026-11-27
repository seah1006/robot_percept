"""Create a local-only 10 fps LeRobot v3 gate dataset (no Hub upload)."""
import argparse
from pathlib import Path

FPS = 10
EPISODES = 5
FRAMES = 50
TASK = "pick up the long board"
WRIST = "observation.images.wrist"
HEAD = "observation.images.head"
MASK = "observation.wrist_roi_mask"
MASK_VIDEO = "observation.images.wrist_mask"
STATE = "observation.state"
META = {"scene_seed": "int64", "skill_id": "int64", "target_part": "int64",
        "source": "int64", "sigma_cm": "float32", "grasp_mode": "int64"}


def features(head=False, video_mask=False):
    def video(h, w):
        return {"dtype": "video", "shape": (h, w, 3), "names": ["height", "width", "channels"]}
    out = {
        WRIST: video(256, 256),
        STATE: {"dtype": "float32", "shape": (15,), "names": [
            "ee_x", "ee_y", "ee_z", "qx", "qy", "qz", "qw", "grip", *[f"joint_{i}" for i in range(7)]]},
        "action": {"dtype": "float32", "shape": (7,), "names": ["dx", "dy", "dz", "rx", "ry", "rz", "grip"]},
        **{name: {"dtype": dtype, "shape": (1,), "names": None} for name, dtype in META.items()},
    }
    if head:
        out[HEAD] = video(480, 640)
    if video_mask:
        out[MASK_VIDEO] = video(256, 256)
    else:
        out[MASK] = {"dtype": "uint8", "shape": (256, 256, 1), "names": ["height", "width", "channels"]}
    return out


def frame(ep, t, head=False, video_mask=False):
    import numpy as np

    # Fixed scene/motion/metadata values are arbitrary synthetic gate inputs.
    phase = (t + ep * 3) / 50
    state = np.array([phase * .1, 0, .24, 0, 0, 0, 1, 1, *([phase * .1] * 7)], dtype=np.float32)
    action = np.array([.01, .007 + .004 * phase, .02, .002, .003, .004, .6], dtype=np.float32)
    mask = np.zeros((256, 256, 1), dtype=np.uint8)
    x = 20 + 3 * t
    mask[104:130, x:x + 64, :] = 255
    rgb = np.full((256, 256, 3), 48 + ep, dtype=np.uint8)
    rgb[mask[..., 0] > 0] = (154, 107, 65)
    values = (ep, 1, 1, 0, 0., 0)
    row = {WRIST: rgb, STATE: state, "action": action, "task": TASK,
           **{k: np.array([v], dtype=dtype) for (k, dtype), v in zip(META.items(), values, strict=True)}}
    if head:
        img = np.full((480, 640, 3), 65, dtype=np.uint8)
        img[225:255, 2*x:2*x + 128] = (154, 107, 65)
        row[HEAD] = img
    row[MASK_VIDEO if video_mask else MASK] = np.repeat(mask, 3, axis=2) if video_mask else mask
    return row


def create(root, head=False, video_mask=False):
    import torch
    from .rocm_compat import torchvision_import
    with torchvision_import():
        from lerobot.datasets.lerobot_dataset import LeRobotDataset

    repo_id = "m2a/synth_grasp_lift"
    ds = LeRobotDataset.create(repo_id=repo_id, root=root, fps=FPS, robot_type="unitree_g1_sim",
                               features=features(head, video_mask), use_videos=True, vcodec="h264", encoder_threads=2)
    for ep in range(EPISODES):
        for t in range(FRAMES):
            ds.add_frame(frame(ep, t, head, video_mask))
        ds.save_episode()
    ds.finalize()
    ds = LeRobotDataset(repo_id, root=root, video_backend="pyav")
    assert ds.num_frames == EPISODES * FRAMES and ds.num_episodes == EPISODES
    assert ds[0]["task"] == TASK
    if not video_mask:
        expected = torch.from_numpy(frame(0, 0)[MASK])
        actual = ds[0][MASK]
        import pyarrow as pa
        import pyarrow.parquet as pq

        storage = pq.read_schema(next((root / "data").rglob("*.parquet"))).field(MASK).type
        leaf = storage.storage_type if isinstance(storage, pa.ExtensionType) else storage
        while hasattr(leaf, "value_type"):
            leaf = leaf.value_type
        assert leaf == pa.uint8(), storage
        assert actual.shape == expected.shape and torch.equal(actual, expected), (actual.dtype, actual.shape)
        print(f"mask roundtrip: parquet_leaf={leaf} loader={actual.dtype} shape={list(actual.shape)} exact=True", flush=True)
    print(f"root={root} episodes={ds.num_episodes} frames={ds.num_frames} fps={ds.fps} mask_video={video_mask}", flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("root", type=Path)
    p.add_argument("--head", action="store_true")
    p.add_argument("--video-mask", action="store_true", help="RGB video fallback for uint8 storage")
    args = p.parse_args()
    create(args.root, args.head, args.video_mask)


if __name__ == "__main__":
    main()