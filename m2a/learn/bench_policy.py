"""Single-GPU local training and synchronized chunk latency measurement."""
import argparse
from contextlib import nullcontext
import json
import math
from pathlib import Path
import statistics
from time import perf_counter

from .make_synth_dataset import FPS, MASK, MASK_VIDEO, STATE, WRIST


def options(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("policy", choices=["act", "smolvla"])
    p.add_argument("root", type=Path)
    p.add_argument("--batch", type=int)
    p.add_argument("--steps", type=int, default=100)
    p.add_argument("--infer-runs", type=int, default=20)
    p.add_argument("--dtype", choices=["fp32", "fp16", "bf16"], default="fp32")
    p.add_argument("--chunk", type=int)
    p.add_argument("--smol-image-size", type=int, default=256)
    p.add_argument("--mask", action="store_true")
    p.add_argument("--checkpoint", type=Path)
    p.add_argument("--resume", action="store_true")
    return p.parse_args(argv)


def emit(**values):
    print(json.dumps(values, sort_keys=True), flush=True)


def run(a):
    import torch
    from torch.utils.data import default_collate
    from lerobot.configs.types import FeatureType, PolicyFeature
    from .rocm_compat import torchvision_import
    with torchvision_import():
        from lerobot.datasets.lerobot_dataset import LeRobotDataset

    torch.manual_seed(41)  # arbitrary reproducibility seed
    torch.set_num_threads(2)
    if not torch.cuda.is_available():
        raise RuntimeError("GPU is required; no CPU fallback")
    emit(event="device", torch=torch.__version__, hip=torch.version.hip,
         gpu=str(torch.cuda.get_device_properties(0)),
         bf16_native=torch.cuda.is_bf16_supported(including_emulation=False))
    torch.cuda.reset_peak_memory_stats()
    batch_size = a.batch or (4 if a.policy == "act" else 1)
    chunk = a.chunk or (20 if a.policy == "act" else 50)  # ACT chunk is a gate setting, not LeRobot default.
    ds = LeRobotDataset("m2a/synth_grasp_lift", root=a.root, video_backend="pyav",
                         delta_timestamps={"action": [i / FPS for i in range(chunk)]})
    camera_keys = [WRIST]
    if a.mask:
        camera_keys.append(MASK_VIDEO)
    inputs = {STATE: PolicyFeature(FeatureType.STATE, (15,)),
              **{k: PolicyFeature(FeatureType.VISUAL, (3, 256, 256)) for k in camera_keys}}
    outputs = {"action": PolicyFeature(FeatureType.ACTION, (7,))}
    base = dict(device="cuda", input_features=inputs, output_features=outputs, push_to_hub=False)
    if a.policy == "act":
        from lerobot.policies.act.configuration_act import ACTConfig
        from lerobot.policies.act.modeling_act import ACTPolicy
        from lerobot.policies.act.processor_act import make_act_pre_post_processors

        cfg = ACTConfig(**base, chunk_size=chunk, n_action_steps=chunk, pretrained_backbone_weights=None)
        policy = ACTPolicy(cfg)
        pre, post = make_act_pre_post_processors(cfg, ds.meta.stats)
        act_params = policy.get_optim_params()
    else:
        from lerobot.configs.policies import PreTrainedConfig
        from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy
        from lerobot.policies.smolvla.processor_smolvla import make_smolvla_pre_post_processors

        model_id = "lerobot/smolvla_base"
        cfg = PreTrainedConfig.from_pretrained(model_id, token=False)
        for k, v in base.items():
            setattr(cfg, k, v)
        cfg.chunk_size = cfg.n_action_steps = chunk
        cfg.resize_imgs_with_padding = (a.smol_image_size, a.smol_image_size)
        cfg.freeze_vision_encoder = cfg.train_expert_only = True
        # Full policy checkpoint already includes the truncated VLM; do not download a second set of weights.
        cfg.load_vlm_weights = False
        policy = SmolVLAPolicy.from_pretrained(model_id, config=cfg, strict=True, token=False)
        pre, post = make_smolvla_pre_post_processors(cfg, ds.meta.stats)
        act_params = [p for p in policy.parameters() if p.requires_grad]
    policy = policy.float().cuda()
    opt = torch.optim.AdamW(act_params, lr=cfg.optimizer_lr, weight_decay=cfg.optimizer_weight_decay)
    dtype = {"fp32": None, "fp16": torch.float16, "bf16": torch.bfloat16}[a.dtype]
    scale = torch.amp.GradScaler("cuda", enabled=dtype == torch.float16)
    emit(event="config", batch=batch_size, chunk=chunk, dtype=a.dtype, policy=a.policy,
         cameras=camera_keys, smol_image_size=a.smol_image_size if a.policy == "smolvla" else None,
         trainable=sum(p.numel() for p in policy.parameters() if p.requires_grad),
         param_dtypes=sorted({str(p.dtype) for p in policy.parameters()}))
    start = 0
    losses, times = [], []
    peak_a = peak_r = 0
    cache = {}

    def get(i):
        if i not in cache:
            raw = ds[i]
            item = {k: raw[k] for k in [WRIST, STATE, "action", "action_is_pad", "task"]}
            if a.mask:
                item[MASK_VIDEO] = (raw[MASK].permute(2, 0, 1).float().div(255).expand(3, -1, -1).contiguous()
                                    if MASK in raw else raw[MASK_VIDEO])
            cache[i] = item
        return cache[i]

    def autocast():
        return nullcontext() if dtype is None else torch.autocast("cuda", dtype=dtype)

    def peaks():
        return (max(peak_a, torch.cuda.max_memory_allocated()),
                max(peak_r, torch.cuda.max_memory_reserved()))

    if a.resume:
        prev = torch.load(a.checkpoint / "training_state.pt", map_location="cpu", weights_only=True)
        policy.load_state_dict(prev["policy"])
        opt.load_state_dict(prev["opt"])
        scale.load_state_dict(prev["scale"])
        start, losses, times, peak_a, peak_r = (prev[k] for k in ("step", "losses", "times", "peak_a", "peak_r"))
    policy.train()
    for step in range(start, start + a.steps):
        # A small fixed training pool exercises all episodes and fits within shared host RAM.
        indices = [50 * ((step + i) % 5) + ((step * 7 + i) % 6) for i in range(batch_size)]
        data = default_collate([get(i) for i in indices])
        torch.cuda.synchronize()
        t0 = perf_counter()
        data = pre(data)
        if a.policy == "smolvla":
            data["actions_id_pad"] = data["action_is_pad"]  # v0.4.4 expects this spelling.
        opt.zero_grad(set_to_none=True)
        with autocast():
            loss, _ = policy(data)
        scale.scale(loss).backward()
        if a.policy == "smolvla":
            scale.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(act_params, cfg.optimizer_grad_clip_norm)
        previous_scale = scale.get_scale() if scale.is_enabled() else None
        scale.step(opt)
        scale.update()
        torch.cuda.synchronize()
        seconds = perf_counter() - t0
        value = loss.detach().item()
        if not math.isfinite(value):
            raise RuntimeError(f"Nonfinite loss at step {step + 1}: {value}")
        losses.append(value)
        times.append(seconds)
        pa, pr = peaks()
        emit(event="step", step=step + 1, loss=value, seconds=seconds, peak_allocated=pa, peak_reserved=pr,
             amp_update_skipped=(scale.get_scale() < previous_scale) if previous_scale is not None else None)
    train_peaks = peaks()
    latency = []
    if a.infer_runs:
        policy.eval()
        inp = {k: v for k, v in get(0).items() if k in (*camera_keys, STATE, "task")}
        data = pre(default_collate([inp]))
        torch.cuda.reset_peak_memory_stats()
        with torch.inference_mode():
            for i in range(a.infer_runs + 3):
                policy.reset()
                torch.cuda.synchronize()
                t0 = perf_counter()
                with autocast():
                    output = policy.predict_action_chunk(data)
                torch.cuda.synchronize()
                if i >= 3:
                    latency.append((perf_counter() - t0) * 1000)
        assert output.shape == (1, chunk, 7) and torch.isfinite(output).all()
        emit(event="inference", samples_ms=latency, p50_ms=statistics.median(latency),
             p95_ms=sorted(latency)[math.ceil(.95 * len(latency)) - 1], shape=list(output.shape),
             peak_allocated=torch.cuda.max_memory_allocated(), peak_reserved=torch.cuda.max_memory_reserved())
    if a.checkpoint:
        a.checkpoint.mkdir(parents=True, exist_ok=True)
        if a.infer_runs:
            policy.save_pretrained(a.checkpoint / "policy")
            pre.save_pretrained(a.checkpoint / "policy")
            post.save_pretrained(a.checkpoint / "policy")
        target = a.checkpoint / "training_state.pt"
        stage = target.with_suffix(".tmp")
        torch.save(dict(step=len(losses), losses=losses, times=times, policy=policy.state_dict(),
                        opt=opt.state_dict(), scale=scale.state_dict(), peak_a=train_peaks[0], peak_r=train_peaks[1]), stage)
        stage.replace(target)
    if losses:
        emit(event="summary", steps=len(losses), first_loss=losses[0], last_loss=losses[-1],
             first10_mean=statistics.mean(losses[:10]), last10_mean=statistics.mean(losses[-10:]),
             step_median_s=statistics.median(times), peak_allocated=train_peaks[0], peak_reserved=train_peaks[1])


if __name__ == "__main__":
    run(options())