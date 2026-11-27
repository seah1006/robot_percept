"""Optional local-only models; invoke in the ROCm worker, never beside EGL."""
from pathlib import Path

import numpy as np

from perception.grounding import MODEL_ID, REVISION, phrase_token_spans
from .v1 import box_iou

DINO_ID = 'facebook/dinov2-small'
DINO_REV = 'ed25f3a31f01632728cabb09d1542f84ab7b0056'
HUB = Path.home() / 'm2a_data/models/hf/hub'


def snapshot(model, revision):
    path = HUB / ('models--' + model.replace('/', '--')) / 'snapshots' / revision
    if not (path / 'model.safetensors').is_file():
        raise FileNotFoundError(path)
    return str(path)


class GroundingTiny:
    def __init__(self, device='cuda', threshold=.21):  # 임의 지정
        import torch
        from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor
        p = snapshot(MODEL_ID, REVISION)
        self.torch = torch
        self.device = device
        self.threshold = threshold
        self.processor = AutoProcessor.from_pretrained(p, local_files_only=True)
        self.model = AutoModelForZeroShotObjectDetection.from_pretrained(p, local_files_only=True).eval().to(device)

    def __call__(self, rgb, prompts):
        prompt = ' . '.join(prompts) + ' .'
        spans = phrase_token_spans(prompt, prompts, self.processor.tokenizer(prompt, return_offsets_mapping=True)['offset_mapping'])
        inputs = self.processor(images=rgb, text=prompt, return_tensors='pt', do_resize=False).to(self.device)
        with self.torch.inference_mode():
            out = self.model(**inputs)
            probs = out.logits[0].sigmoid()
            conf = self.torch.stack([probs[:, span].amin(1) for span in spans], dim=1).amax(1)
            cand = self.torch.cat([out.pred_boxes[0], conf[:, None]], dim=1).cpu().numpy()
        h, w = rgb.shape[:2]
        kept = []
        for x, y, bw, bh, score in sorted(cand, key=lambda a: -a[-1]):
            if score < self.threshold:
                break
            box = np.clip([(x-bw/2)*w, (y-bh/2)*h, (x+bw/2)*w, (y+bh/2)*h], 0, [w,h,w,h]).tolist()
            if (box[2]-box[0])*(box[3]-box[1]) > .15*w*h or any(box_iou(box, b) > .55 for b, _ in kept):
                continue
            kept.append((box, float(score)))
        return kept


class DinoSmall:
    def __init__(self, device='cuda', crop_size=224):
        import torch
        from transformers import AutoImageProcessor, AutoModel
        p = snapshot(DINO_ID, DINO_REV)
        if crop_size < 14 or crop_size % 14:
            raise ValueError('crop_size must be a multiple of DINOv2 patch width (14)')
        self.crop_size = crop_size
        self.device = device
        self.torch = torch
        self.processor = AutoImageProcessor.from_pretrained(p, local_files_only=True)
        self.model = AutoModel.from_pretrained(p, local_files_only=True).eval().to(device)

    def __call__(self, images):
        x = self.processor(images=images, return_tensors='pt', do_center_crop=False,
                           size={'height': self.crop_size, 'width': self.crop_size}).to(self.device)
        with self.torch.inference_mode():
            z = self.model(**x).last_hidden_state[:, 0]
            return self.torch.nn.functional.normalize(z).cpu().numpy()
