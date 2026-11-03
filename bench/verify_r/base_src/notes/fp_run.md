# FoundationPose run log

Smoke: torch 2.14+cu130, Utils.mycpp=True, Utils.wp=True, estimater import OK.
Existing build patches: trusted checkpoint weights_only=False and torch.autocast already present.
New run_demo.py patch: --max_frames, CUDA-synchronized runtime and peak memory JSON, headless debug>=1 writes PNG, compose axes on box image.

First default 252-hypothesis demo failed in refiner convolution: CUDA driver device not ready / Failed to create GPU mapping (not explicit torch OOM). Retry: crop render chunks=32 for both predictors, refiner network chunk=32; inplane step=120 (126 hypotheses); environment override FP_INPLANE_STEP available.

Added perception/fp_runner.py and __init__.py. Dedicated-process CLI: python -m perception.fp_runner DATASET --out OUTPUT. Public FPRunner register/track returns mesh-origin T_cam_obj, depth meters. Default FP_INPLANE_STEP=120; override 60 for upstream hypotheses. CLI writes input-frame stems, runtime.json and pred-red/GT-green box+axis overlays; no GT used in inference. Sim datasets use zero-padded six-digit IDs. Network autocast remains fp16 on sm_75. No dependencies changed. No sim/eval files edited.

## Verified simulation results
Means over every exported frame. AUC normalized over 0..100 mm.
|Scene|Frames|Translation mm|Rotation deg|ADD mm|ADD-S mm|ADD AUC|ADD-S AUC|Register s|Track FPS|Torch peak GiB|nvidia-smi MiB|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|mustard_static|30|0.7772|1.6215|1.1252|0.9807|0.988748|0.990193|4.737|7.488|3.069|4406|
|mustard_push|120|1.6195|0.7890|1.7248|1.2351|0.982752|0.987649|3.431|9.455|3.069|4225|

Predictions, overlays, runtime.json, metrics.json: data/fp_results/<scene>/. Whole-device VRAM samples: data/fp_results/<scene>_vram.csv (200 ms). Concurrent other-agent rendering/desktop means whole-device usage is not FP-exclusive.
Optional CAD run not attempted; required official + both MuJoCo scenes prioritized.

Official mustard0 headless smoke: 6 frames, register 3.090 s, tracking 10.069 FPS, torch peak 2.894 GiB, nvidia-smi peak 3949 MiB. Default upstream 252-hypothesis attempt failed as noted; successful runs all use 126 hypotheses/chunks32. Runtime excludes model loading. Official smoke is first six frames, not full sequence.
