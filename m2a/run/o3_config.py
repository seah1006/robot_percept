"""G3 head-gallery bundle; the upstream NPZ does not carry a camera version."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path

GALLERY_VERSION = 'g3-head-v2-dinov2s-112'
GALLERY = '~/m2a_data/percept_v2/train_dinov2_gallery.npz'
GALLERY_SHA256 = 'f8182682969c12435caa3fc7842045ab09ddcf5fd3cfd83b5a51bf9f7de3d298'
CROP_SIZE = 112


def load_gallery(path=GALLERY):
    import numpy as np

    p = Path(path).expanduser()
    payload = p.read_bytes()
    if sha256(payload).hexdigest() != GALLERY_SHA256:
        raise ValueError(f'{p}: expected certified {GALLERY_VERSION} gallery; old or unknown gallery rejected')
    with np.load(BytesIO(payload), allow_pickle=False) as data:
        if int(data['crop_size']) != CROP_SIZE or not np.array_equal(data['train_seeds'], np.arange(200)):
            raise ValueError(f'{p}: {GALLERY_VERSION} crop size or train seeds mismatch')
        return data['part_ids'], data['embeddings']
