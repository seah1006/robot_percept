# FoundationPose compat notes (S5 research, v2, 2026-10-26)
Target: WSL2 Ubuntu 24.04, Python 3.12 (conda), torch 2.14+cu130, CUDA toolkit 13.x, gcc 13.3, RTX 2080 SUPER (sm_75, 8GB), driver 610.88

## TL;DR top risks -> fixes
1. torch 2.14 extensions compile with `-std=c++20`; pytorch3d setup.py hard-codes `-std=c++17` -> patch to c++20 (same as professor's MD). nvdiffrast main has no -std flag -> OK.
2. Use pytorch3d **git main** (it already adds CUDA-13 nvcc flags `--device-entity-has-hidden-visibility=false -static-global-template-stub=false`). Old releases (0.7.8) will likely fail on CUDA 13.
3. CUDA 13 moved Thrust/CUB/libcu++ headers to `$CUDA_HOME/include/cccl/` and removed `cub::Max/Sum/...`. nvcc finds them automatically; if a host-only .cpp fails with `thrust/... No such file`, `export CPATH=$CUDA_HOME/include/cccl:$CPATH`.
4. sm_75 IS supported by CUDA 13 (only Maxwell/Pascal/Volta dropped). Set `TORCH_CUDA_ARCH_LIST="7.5"` to build only for the 2080S (faster, smaller).
5. mycpp: Boost >= 1.89 removed `boost_system` -> `find_package(Boost COMPONENTS system ...)` in mycpp/CMakeLists.txt fails. Fix: delete `system` from COMPONENTS (or pin `libboost-devel=1.84` / `boost-cpp` (max 1.85) / apt Boost 1.83).
6. Utils.py swallows import errors: `mycpp=None`, `wp=None` silently -> later cryptic errors (`'NoneType' has no attribute cluster_poses`, `NameError: erode_depth`). Always run the import smoke test below.
7. VRAM 8GB: register() renders+refines+scores 252 hypotheses at once; scorer runs ALL hypotheses in one forward (cross-hypothesis attention). Known OOM on 10GB 3080 for larger images. Use 640x480 frames, reduce hypotheses (section 5), `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`, keep SAM2 off GPU (or small) during register.
8. torch>=2.6 `torch.load` defaults `weights_only=True` -> FP checkpoint load may fail -> `weights_only=False` (official trusted weights).

## 0. Upstream repo state (fetched 2026-10-26)
- Upstream main is MODERNIZED vs 2024 docker-era:
  - requirements.txt: `numpy>=2`, kornia>=0.7, warp-lang, open3d, pyrender, no pinned torch. src: https://raw.githubusercontent.com/NVlabs/FoundationPose/main/requirements.txt
  - environment.yml: conda-forge python=3.11, cmake, ninja, eigen, boost-cpp, pybind11, cxx-compiler. src: https://raw.githubusercontent.com/NVlabs/FoundationPose/main/environment.yml
  - build_all_conda.sh builds ONLY mycpp (cmake). bundlesdf/mycuda omitted (model-free/NeRF only). src: https://raw.githubusercontent.com/NVlabs/FoundationPose/main/build_all_conda.sh
  - README: Kaolin OPTIONAL (model-free only). src: https://github.com/NVlabs/FoundationPose
- => Model-based (CAD/mesh given, our use case): torch + pytorch3d + nvdiffrast + warp-lang + mycpp + requirements.txt. SKIP kaolin and bundlesdf/mycuda.
- FoundationPose uses `dr.RasterizeCudaContext()` only -> no OpenGL/EGL needed. nvdiffrast v0.4.0 removed the GL backend anyway and now compiles at pip-install time (needs torch>=2.7). src: https://github.com/NVlabs/nvdiffrast/releases , https://nvlabs.github.io/nvdiffrast

## 1. Build checklist (model-based only)
```bash
conda activate <env>                     # existing py3.12 env OK (open3d>=0.19 supports py3.12 + numpy2)
# --- CUDA toolkit: match torch major (13). 13.0 preferred (torch cu130); 13.2 also OK (minor mismatch = warning only)
#   Option A (conda): conda install -c nvidia cuda-toolkit=13.0 -y ; export CUDA_HOME=$CONDA_PREFIX
#     conda layout puts headers in $CONDA_PREFIX/targets/x86_64-linux/include -> if "cuda_runtime.h not found":
#     export CPATH=$CONDA_PREFIX/targets/x86_64-linux/include:$CPATH ; export LIBRARY_PATH=$CONDA_PREFIX/targets/x86_64-linux/lib:$LIBRARY_PATH
#   Option B (apt, NVIDIA wsl-ubuntu repo, needs sudo): cuda-toolkit-13-0 -> /usr/local/cuda-13.0 (clean layout). NEVER install cuda-drivers inside WSL.
export PATH=$CUDA_HOME/bin:$PATH
nvcc --version                           # must say 13.x
export TORCH_CUDA_ARCH_LIST="7.5"
export MAX_JOBS=4                        # 15GB RAM; cc1plus OOM-kill seen with high jobs (nvdiffrast issue #183)
python -m pip install -U setuptools wheel ninja

# --- pytorch3d (git main + C++20 patch)
git clone https://github.com/facebookresearch/pytorch3d.git pytorch3d-cxx20
cd pytorch3d-cxx20 && sed -i 's/-std=c++17/-std=c++20/g' setup.py
python -m pip install --no-build-isolation -v .   # ~10-25 min
cd ..

# --- nvdiffrast
python -m pip install --no-build-isolation "git+https://github.com/NVlabs/nvdiffrast.git"

# --- FoundationPose python deps
cd FoundationPose
python -m pip install -r requirements.txt         # if pyOpenGL_accelerate fails to build on py3.12: drop it (pyrender/pyOpenGL not used by model-based path - verify with grep below)

# --- mycpp (Boost fix first)
sed -i 's/COMPONENTS system program_options/COMPONENTS program_options/' mycpp/CMakeLists.txt
conda install -c conda-forge cmake ninja eigen pybind11 libboost-devel -y   # or boost-cpp
export CMAKE_PREFIX_PATH="$(python -c 'import pybind11;print(pybind11.get_cmake_dir())'):$CONDA_PREFIX:$CMAKE_PREFIX_PATH"
bash build_all_conda.sh
```
- pytorch3d setup.py (CUDA13 flags, PYTORCH3D_NO_EXTENSION, CUB_HOME logic): https://github.com/facebookresearch/pytorch3d/blob/main/setup.py
- torch cpp_extension passes `-std=c++20` by default: https://github.com/pytorch/pytorch/blob/main/torch/utils/cpp_extension.py , https://docs.pytorch.org/docs/main/cpp_extension.html
- CCCL 3.0 header move / removed cub APIs: https://nvidia.github.io/cccl/unstable/cccl/3.0_migration_guide.html
- CUDA 13.0 release notes (Turing..Blackwell supported, pre-Turing dropped): https://docs.nvidia.com/cuda/archive/13.0.0/cuda-toolkit-release-notes/index.html
- torch 2.14 ships cu130 (stable) + cu132 (default); 2.15 plans to drop cu130 -> pin torch 2.14 in this env: https://github.com/pytorch/pytorch/issues/190385
- Boost 1.89 removed System stub; remove `system` from components: https://www.boost.org/releases/1.89.0
- NVlabs GRAIL guide pins libboost 1.84 for exactly this FoundationPose mycpp break, and uses pybind11.get_cmake_dir(): https://nvlabs.github.io/GRAIL/installation.html

## 2. Smoke tests (run in order; each catches a silent-failure path)
```bash
python -c "import torch;print(torch.__version__,torch.version.cuda,torch.cuda.get_device_capability())"
python -c "import torch; torch.set_default_tensor_type('torch.cuda.FloatTensor'); print('set_default_tensor_type OK')"   # exists (deprecated) in docs up to 2.11; verify on 2.14
python -c "import pytorch3d, pytorch3d._C; from pytorch3d.transforms import so3_exp_map; print('p3d OK')"
python -c "import nvdiffrast.torch as dr, torch; ctx=dr.RasterizeCudaContext(); print('nvdiffrast OK')"
python -c "import warp as wp; wp.init(); print(wp.get_cuda_devices())"     # if this fails, Utils sets wp=None -> NameError later
cd FoundationPose && PYTHONPATH=mycpp/build python -c "import mycpp; print('mycpp OK')"
python -c "import Utils as U; print('mycpp', U.mycpp is not None, 'warp', U.wp is not None, 'kornia', U.kornia is not None)"
```

## 3. Code patches for torch 2.14 / py3.12 (from source reading)
| File | Issue | Patch |
|---|---|---|
| learning/training/predict_score.py, predict_pose_refine.py | `torch.load(ckpt_dir)`; torch>=2.6 default `weights_only=True` | `torch.load(ckpt_dir, map_location='cuda', weights_only=False)` |
| predict_pose_refine.py `predict()`, Utils.py `compute_crop_window_tf_batch()` | `torch.set_default_tensor_type('torch.cuda.FloatTensor')` (deprecated since 2.1). Code RELIES on it (torch.eye/torch.tensor without device must land on cuda). | If removed/erroring: replace with `torch.set_default_device('cuda'); torch.set_default_dtype(torch.float32)`. Do NOT just delete. Side effect is process-global -> run FP in its own process (not shared with SAM2/web). |
| both predictors | `torch.cuda.amp.autocast(enabled=...)` deprecated (FutureWarning) | `torch.autocast('cuda', dtype=torch.float16, enabled=self.amp)` (sm_75 has no bf16 -> keep fp16) |
| estimater.py `make_rotation_grid` | `mycpp.cluster_poses` -> crash if mycpp None; segfaults reported (issue #293); demo works without it | `if mycpp is not None: rot_grid = mycpp.cluster_poses(...)` (asymmetric object + identity symmetry -> clustering ~no-op: 252 stays 252) |
| run_demo.py | `cv2.imshow` when `--debug>=1` (needs GUI; fails with opencv-headless) | run `--debug 0` headless, or replace imshow with imwrite |
| Utils.py | imports `pytorch3d.renderer` (needs compiled `_C`) though model-based path only uses `pytorch3d.transforms` | Fallback if pytorch3d CUDA build is impossible: `PYTORCH3D_NO_EXTENSION=1 pip install --no-build-isolation .` then comment out `pytorch3d.renderer*` / `structures` imports in Utils.py (verify unused with grep below) |

Verification greps:
```bash
grep -rnE "np\.(float|int|bool|object)\b|np\.(NaN|Inf|NINF)\b" --include=*.py . | grep -v bundlesdf    # numpy2 removals (upstream claims numpy>=2 OK)
grep -rnE "^\s*(import imp\b|from distutils|import distutils)" --include=*.py .                       # py3.12 removals
grep -rnE "Meshes|MeshRasterizer|PerspectiveCameras|HardPhongShader|barycentric_coordinates|pyrender" --include=*.py . | grep -vE "^./Utils.py:1[0-9]:"
```
Sources: https://raw.githubusercontent.com/NVlabs/FoundationPose/main/learning/training/predict_score.py , .../predict_pose_refine.py , .../Utils.py , .../estimater.py , .../run_demo.py ; https://docs.pytorch.org/docs/2.10/generated/torch.set_default_tensor_type.html ; https://github.com/pytorch/pytorch/issues/130659 ; https://github.com/NVlabs/FoundationPose/issues/293

## 4. Python 3.12 / package notes
- open3d >= 0.19 supports Python 3.12 and NumPy 2: https://www.open3d.org/news/open3d-v0-19-is-out-with-new-features-and-more-gpu-support/
- environment.yml says python 3.11; nothing found that hard-requires 3.11 (run the greps). If a dep blocks, create a 3.11 env and reinstall torch 2.14 cu130.
- requirements.txt installs `opencv-python`; the `ai` env already has opencv-python 5.0 -> fine. Do NOT mix with opencv-python-headless.
- open3d import needs libGL.so.1 (present: libgl1).

## 5. VRAM knobs (8GB)
From estimater.py / predictors:
- Hypotheses: `make_rotation_grid(min_n_views=40, inplane_step=60)`. `sample_views_icosphere` starts at subdivision=1 (42 verts), so ANY min_n_views<=42 gives 42 views -> 42 x 6 = 252. To reduce:
  - `inplane_step=90` -> 168, `inplane_step=120` -> 126 (call `est.make_rotation_grid(min_n_views=40, inplane_step=90)` after constructing FoundationPose).
  - 12 views needs a patch: `sample_views_icosphere(n_views, subdivisions=0)` -> 12 x 6 = 72 (accuracy drops; ok for sim).
- Refiner: render chunk `bs=512` (make_crop_data_batch), network chunk `bs=1024` -> lower both to 64/128 to cut refiner peak.
- Scorer: `find_best_among_pairs` uses `bs = all hypotheses` (ScoreNetMultiPair attends across all) -> only lever is fewer hypotheses. NVIDIA's TRT runtime docs confirm "ScoreNet uses cross-hypothesis attention and always runs at full batch".
- Image size: network crops are cfg.input_resize (160x160); full frame size matters for depth filtering and the per-hypothesis kornia warp of the full frame (B x 3 x H x W expand) -> OOM reports (3080 10GB, "Tried to allocate 2.60 GiB") fixed by downscaling frames (`shorter_side=480`). Render sim camera at 640x480 (or 480x360).
- Iterations: `register(iteration=5)` / `track_one(iteration=2)` (run_demo defaults) -> time only, not peak memory.
- `export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`; `torch.cuda.empty_cache()` already called after predict.
- Peak only during register (seconds); tracking is 1 hypothesis -> small.
- Run SAM2 (1.4GB for large) in another process; consider base_plus or unloading while register runs.
Sources: https://github.com/NVlabs/FoundationPose/issues/26 , https://raw.githubusercontent.com/NVlabs/FoundationPose/main/Utils.py (sample_views_icosphere), https://github.com/nvidia-isaac/foundation-pose-inference-library

## 6. Plan B (if source build fails): NVIDIA FoundationPose Inference Library
- https://github.com/nvidia-isaac/foundation-pose-inference-library (Apache-2.0): GPU-resident C ABI + Python bindings, TensorRT, built-in CUDA rasterizer (no nvdiffrast/pytorch3d), ONNX weights from https://huggingface.co/nvidia/foundationpose
- Requires driver >= 580 (have 610.88 OK), CC >= 7.5 (2080S OK), Docker + NVIDIA Container Toolkit (container nvcr.io/nvidia/pytorch:26.05-py3, CUDA 13.2, TRT 10.16). Docker Desktop distro exists on this PC (stopped).
- `RuntimeConfig(n_hypotheses=252, batch_size=42)` micro-batching for RefineNet; TRT engine build at batch 252 needs ~6.1GB workspace (tight on 8GB; lower batch_size + workspace). Register ~148ms, track ~2ms on Blackwell.
- Downsides: container-only build, TRT engine build time, less hackable for teaching.

## 7. Weights / demo data
- Refiner `2023-10-28-18-33-37`, scorer `2024-01-11-20-02-45` from Google Drive (README link). Demo data `mustard0` (640x480 RGB-D, mask, cam_K.txt) from README demo_data link. gdown may hit Drive quota; fallback: manual browser download.
