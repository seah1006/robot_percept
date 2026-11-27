# M2A G-B: ACT / SmolVLA 학습 가능성 점검

## WSL ROCm 재현

PowerShell에서 인라인 WSL 명령 대신 아래를 LF `.sh`로 저장하고 `wsl -d Ubuntu-24.04 bash /mnt/c/.../x.sh`로 실행한다. 기본 `robot_percept_rocm`은 변경하지 않는다. `m2a_lerobot`이 이미 있으면 복제 명령은 생략한다.

```bash
set -euo pipefail
cd /home/my/work/rp_m2a_d
source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda create -y --name m2a_lerobot --clone robot_percept_rocm
conda activate m2a_lerobot
export HSA_ENABLE_DXG_DETECTION=1 LD_LIBRARY_PATH="$CONDA_PREFIX/lib"
export HF_HUB_DISABLE_IMPLICIT_TOKEN=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2
pip install --no-deps lerobot==0.4.4
pip install --no-deps --index-url https://download.pytorch.org/whl/cpu 'torchvision==0.25.0+cpu'
pip freeze | grep -Ei '^(torch|torchvision|transformers)==' > "$HOME/.cache/m2a_rocm_constraints.txt"
pip install -c "$HOME/.cache/m2a_rocm_constraints.txt" \
 'datasets>=4.0,<5' 'huggingface_hub>=0.34.2,<0.36' 'accelerate>=1.10,<2' \
 'av>=15,<16' 'draccus==0.10.0' 'einops>=0.8,<0.9' 'deepdiff>=7,<9' \
 'termcolor>=2.4,<4' 'jsonlines>=4,<5' 'gymnasium>=1.1,<2' 'diffusers>=0.27,<0.36' \
 'opencv-python-headless>=4.9,<4.13' 'imageio[ffmpeg]>=2.34,<3' num2words pytest \
 'pyserial>=3.5,<4' 'wandb>=0.24,<0.25'
flock -w 900 /tmp/rp_measure.lock flock -w 900 /tmp/rp_gpu.lock timeout 30s \
 python -c 'import torch; assert torch.version.hip and torch.cuda.is_available(); print(torch.__version__,torch.cuda.get_device_properties(0))'
export M2A_TORCHVISION_PYTHON_ONLY=1
python -m pytest --import-mode=importlib -p no:cacheprovider -q tests/m2a/test_d_schema.py
```

`torchvision`은 NMS 등록에서 ABI 오류가 있었다. 명시적 환경변수 우회는 쓰지 않는 `torchvision::nms`의 fake 등록만 생략하며, NMS 구현이나 결과를 주입하지 않는다. ACT는 Python ResNet과 PyTorch 커널, 영상은 PyAV를 사용한다. 완전한 torchvision 호환으로 해석하지 말 것. 설치 당시 LeRobot 상한보다 ROCm torch가 높아서 전체 `pip check` 통과가 목표는 아니다.

## 데이터 및 측정 명령

```bash
set -o pipefail
D="$HOME/.cache/m2a_d_synth"
L="$HOME/.cache/m2a_d_logs"
mkdir -p "$L"
# 최초 한 번: create는 신규 경로 필요. --head로 선택 카메라 추가 가능.
python -u -m m2a.learn.make_synth_dataset "$D" 2>&1 | tee "$L/dataset.log"
flock -w 900 /tmp/rp_measure.lock flock -w 900 /tmp/rp_gpu.lock timeout 280s \
 python -u -m m2a.learn.bench_policy act "$D" --batch 4 --mask 2>&1 | tee "$L/act-b4.log"
flock -w 900 /tmp/rp_measure.lock flock -w 900 /tmp/rp_gpu.lock timeout 280s \
 python -u -m m2a.learn.bench_policy smolvla "$D" --batch 1 2>&1 | tee "$L/smol-b1.log"
```

시간 제한을 넘기면 `--steps 20 --infer-runs 0 --checkpoint "$C"`로 시작하고 같은 설정에 `--resume`을 더해 재개한다. 예를 들어 20스텝 5회면 최종 회차에만 `--infer-runs 20`을 준다. 각 회는 동일 이중 락과 280초 제한을 사용한다. 체크포인트에는 optimizer·loss·시간·VRAM 피크가 저장되나 RNG 일치는 보장하지 않는다. 기본은 fp32, `--dtype fp16|bf16`은 autocast를 사용하는 별도 실험이다.

ACT: 임의 지정한 청크 20, ResNet 초기 가중치 다운로드 없이 학습. 마스크는 별도 uint8 저장값을 `[0,1]` CHW RGB 3채널로 복제해서 `observation.images.wrist_mask`라는 별도 VISUAL로 입력한다. 데이터 저장 형식은 변경하지 않는다. SmolVLA: 공개 `lerobot/smolvla_base` 전체 정책 가중치를 불러오고, 기본 청크 50 및 10 denoise 유지. 해상도는 임의 지정 256, vision freeze / expert-only / state projection 학습 사용. 입력 state 15, action 7을 모델 안에서 32로 패딩한 뒤 예측은 action 7로 자른다. Base 정책의 기존 카메라 이름/차원/통계는 합성 데이터용 설정과 통계로 교체한다. 학습 루프는 5회 에피소드의 앞 6프레임을 시작점으로 사용하며 실제 250프레임 데이터셋에서 청크를 로드한다. 실세계 성능 지표가 아니다.

시간은 GPU 동기화 기준. 학습에는 전처리/전송/전·역전파/optimizer를 포함하고 파일 IO·collate는 제외한다. 추론은 배치1, warm-up 3회 후 20개 청크, 전처리 제외, GPU 동기화; p95는 nearest rank. VRAM은 PyTorch allocated/reserved 피크(프로세스 allocator 기준)라 전체 GPU 점유량이 아니다.

## 무료 클라우드 폴백 (미실행, 별도 승인 후 사용)

1. 로컬에서 `tar -czf m2a_d_synth.tar.gz -C "$HOME/.cache" m2a_d_synth`로 합성 데이터만 묶는다. `m2a/learn/` 코드도 별도 압축한다. Colab 임시 파일 또는 Kaggle 비공개 Dataset에 사용자가 업로드하고 풀어 준다(경로 `meta/info.json`이 있는 루트). 업무·개인 데이터는 업로드하지 않는다.
2. 무료 GPU 런타임(T4 권장, P100은 fp32와 패키지/드라이버 호환 확인)을 켠다. 랩톱 ROCm 우회는 쓰지 않는다. 호환된 CUDA torch/torchvision 조합에서 `pip install 'lerobot[smolvla]==0.4.4'` 후 `torch.cuda.is_available()` 확인. 공개 모델 다운로드에 인터넷이 필요하다. 토큰·gated 접근·결제가 필요하면 중단한다.
3. 압축을 푼 코드의 루트에서 `python -m m2a.learn.cloud_smolvla_train --execute --data /path/to/m2a_d_synth --out /path/to/output`을 실행한다. Kaggle 출력은 `/kaggle/working` 아래를 사용한다. Colab에서는 파일 탭에서 또는 `google.colab.files.download()`로 `smolvla_policy.zip`을 받는다. Kaggle에서는 세션 Output에서 ZIP을 받는다. ZIP은 모델 가중치/전처리/후처리를 포함하며, `training_state.pt`는 재개가 필요한 경우 별도로 다운로드한다.