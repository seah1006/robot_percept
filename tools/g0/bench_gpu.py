# 부모 세션 임시 측정 스크립트 (tools/g0/bench_cpu.py의 GPU 판). Codex 복귀 후 tools/g0로 정식화 예정.
import argparse, hashlib, json, os, platform, time
from pathlib import Path
import numpy as np
import torch
from PIL import Image
from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection
REV = 'a2bb814dd30d776dcf7e30523b00659f4f141c71'
p = argparse.ArgumentParser(); p.add_argument('--n', type=int, default=20); p.add_argument('--output', default='bench/g0/rocm_gpu.json'); a = p.parse_args()
dev = 'cuda'
image_path = Path('sim_test/results/egl_d3d12/rgb.png')
image = Image.open(image_path).convert('RGB').resize((640, 360))
def dev_used():
    f, t = torch.cuda.mem_get_info(); return t - f
base_used = dev_used()
t = time.perf_counter()
processor = AutoProcessor.from_pretrained('IDEA-Research/grounding-dino-tiny', revision=REV)
model = AutoModelForZeroShotObjectDetection.from_pretrained('IDEA-Research/grounding-dino-tiny', revision=REV).eval().to(dev)
torch.cuda.synchronize(); load = time.perf_counter() - t
print(f'loaded {load:.1f}s', flush=True)
peak_dev = [dev_used()]
def run():
    inputs = processor(images=image, text='a red cube. a blue cube.', return_tensors='pt', do_resize=False).to(dev)
    with torch.inference_mode(): out = model(**inputs)
    torch.cuda.synchronize(); peak_dev.append(dev_used())
    return inputs, out
torch.cuda.reset_peak_memory_stats()
t = time.perf_counter(); inputs, out = run(); first = time.perf_counter() - t
print(f'first {first:.1f}s', flush=True)
for i in range(2):
    t2 = time.perf_counter(); run(); print(f'warm{i} {time.perf_counter()-t2:.2f}s', flush=True)
samples = []
for _ in range(a.n):
    t = time.perf_counter(); run(); samples.append((time.perf_counter() - t) * 1000)
res = processor.post_process_grounded_object_detection(out, inputs.input_ids, threshold=0.35, text_threshold=0.25, target_sizes=[(360, 640)])[0]
dets = [dict(label=str(l), score=round(float(s), 4), box=[round(float(v), 1) for v in b]) for s, l, b in zip(res['scores'], res.get('text_labels', res.get('labels')), res['boxes'])]
r = dict(source='[시뮬인식]', gt_assisted=False, revision=REV, torch=torch.__version__, hip=torch.version.hip, device=torch.cuda.get_device_name(0),
         python=platform.python_version(), load_seconds=load, first_inference_ms=first * 1000, warmup=2, n=a.n, samples_ms=samples,
         p50_ms=float(np.percentile(samples, 50)), p95_ms=float(np.percentile(samples, 95)),
         device_used_before_mib=base_used / 2**20, device_used_peak_sampled_mib=max(peak_dev) / 2**20,
         process_max_allocated_mib=torch.cuda.max_memory_allocated() / 2**20, process_max_reserved_mib=torch.cuda.max_memory_reserved() / 2**20,
         vram_note='device_used는 mem_get_info 샘플(추론 직후), 장치 전체(다른 프로세스·Windows 포함). AMD 집 측정은 NVIDIA 회사 합격 증거 아님.',
         image=str(image_path), image_sha256=hashlib.sha256(image_path.read_bytes()).hexdigest(), detections=dets)
Path(a.output).write_text(json.dumps(r, indent=2, ensure_ascii=False) + '\n')
print(json.dumps({k: v for k, v in r.items() if k != 'samples_ms'}, ensure_ascii=False), flush=True)
