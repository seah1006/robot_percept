# D 작업 보고: G-B (2026-11-27)

## 판정

**통과.** ACT·SmolVLA 모두 RX 7600 ROCm에서 fp32로 OOM 없이 optimizer 100스텝을 마쳤고, 첫→마지막 손실 및 앞→뒤 10개 평균이 모두 감소했다. 두 정책의 7차원 청크 추론도 완료했다. 이 판정은 아래 설정의 합성 데이터에 한정한다.

## 실측: RX 7600 8GB (gfx1102), WSL ROCm

| 정책 | dtype / 배치 / 청크 | 완료 스텝 | 학습 피크 allocated / reserved (GiB) | 스텝 중앙값 | 손실 처음→끝 (앞/뒤 10개 평균) | 청크 추론 p50 / p95 |
|---|---|---:|---:|---:|---:|---:|
| ACT + wrist 마스크 | fp32 / 4 / 20 | 100 | 0.994 / 1.088 | 141.04 ms | 63.6275→6.5755 (27.4126→6.7182) | 29.41 / 32.16 ms |
| SmolVLA base, wrist 256 | fp32 / 1 / 50 | 100 | 3.287 / 3.422 | 308.11 ms | 40.0874→0.3263 (11.5502→0.3736) | 589.56 / 599.39 ms |

GPU 동기화 측정; 학습은 파일 I/O와 collate 제외. 추론은 배치 1, 모델 청크 1회, 워밍업 3회 뒤 20회(p95 nearest rank)이며 전처리 제외. 피크는 PyTorch allocator 기준. ACT 손실은 L1+VAE KL, SmolVLA는 확률적 flow matching이므로 절댓값 비교 불가. 합성 패턴을 맞춘 실측이며 파지 성공률이나 일반화 성능을 뜻하지 않는다.

혼합정밀도는 파라미터 fp32 유지 + autocast를 사용한 별도 스모크다. FP16: 전·역전파와 청크 예측 1회 정상, 초기 GradScaler overflow로 optimizer update 스킵(`amp_update_skipped=true`); 지속 학습 미검증. BF16: 전·역전파, optimizer update 및 청크 예측 1회 완료; 지속 학습 미검증. PyTorch가 gfx1102의 native BF16을 `True`로 리포트했다. 100스텝 판정에는 fp32 결과만 사용. 로그: `smol-fp16-v2.log`, `smol-bf16-v2.log`.

## 설치·우회

- 원본을 변경하지 않고 `conda create -y --name m2a_lerobot --clone robot_percept_rocm`으로 복제. ROCm 플래그 및 `$CONDA_PREFIX/lib` 적용. 최종 `torch 2.14.0+rocm10.1.0`, `torch.cuda.is_available() == True`, `transformers 4.57.6` 유지. 기기 리포트 RX 7600 `gfx1102`, 8150MB, torch가 보고한 HIP `7.16.26385`.
- 처음 `lerobot==0.5.1 --no-deps` 설치했으나 SmolVLA extra가 Transformers 5.3.0을 요구해 실행 전 `0.4.4 --no-deps`로 변경. ROCm torch와 Transformers를 constraints에 고정했다. PyAV `15.1.0`, datasets `4.8.5`, Hub `0.35.3`, accelerate `1.16.0`, draccus `0.10.0`, einops `0.8.2`, PyArrow `26.0.1`, NumPy `2.2.6`, OpenCV headless `4.12.0.88`, num2words `0.5.14`, pyserial `3.5`, wandb `0.24.2` 등. 전이 의존성 전체는 `pip-final.txt`, 추가 설치 명령은 `m2a/learn/README.md`.
- AMD 인덱스 `torchvision 0.26.0+rocm7.13.0` 및 CPU `0.25.0+cpu`에서 `RuntimeError: operator torchvision::nms does not exist`. 최종 CPU torchvision을 유지하고 `M2A_TORCHVISION_PYTHON_ONLY=1`에서 사용하지 않는 NMS fake 등록만 건너뛰었다(가짜 op/결과 없음). 미사용 `torchvision/image.so` 로딩 경고가 남는다. 영상은 PyAV, 모델 계산은 ROCm torch. LeRobot이 명시한 torch 상한을 벗어나며 전체 패키지 호환을 뜻하지 않는다.
- LeRobot의 초기 `ModuleNotFoundError: No module named 'serial'`은 pyserial 설치 후 해결. SmolVLA `draccus.utils.DecodingError: The fields `type` are not valid for SmolVLAConfig`는 구체 subclass 대신 `PreTrainedConfig.from_pretrained`로 읽어서 해결했다. H.264 별칭 `libx264`은 create API에서 거부되어 `h264` 사용.
- 토큰 없이 공개 `lerobot/smolvla_base` revision `5e8d12a6e2975b0e5e5fce7c8caf47c371d257b6`와 SmolVLM2 config/tokenizer 캐싱. 전체 정책 safetensors strict 로딩 사용; 중복 VLM 가중치 대신 구조만 초기화했다.

## 데이터 및 입력 호환

- 공식 API로 저장·finalize·재로딩한 v3.0 데이터셋: 10fps, 5×50 = 250프레임, wrist 영상 256×256×3. head는 선택(480×640×3), 기본 측정에서 제외. 메타 6종, state 15/action 7, 영어 task `pick up the long board`.
- 별도 `observation.wrist_roi_mask` 저장 **가능**. Parquet leaf `uint8`; LeRobot 로더가 `torch.int64`로 승격하나 `[256,256,1]`과 픽셀 값이 정확히 보존됐다. ACT에 넣을 때 CHW로 바꾸고 `[0,1]` 정규화 후 RGB 3채널로 복제하여 별도 VISUAL `observation.images.wrist_mask`로 등록. 마스크를 영상으로 대체할 필요 없음(`--video-mask`는 선택 폴백, 영상 저장 경로 실측에 사용하지 않음).
- SmolVLA는 wrist + state + 영어 task를 입력. 정책의 `input_features`/`output_features` 및 정규화 통계 교체. state 15와 action 7을 각각 내부 32로 오른쪽 패딩, 추론 반환 `[1,50,7]`. `freeze_vision_encoder=True`, `train_expert_only=True`, state projection 학습 유지. 임의 지정: SmolVLA 256 입력(공개 설정 512 대신), ACT 청크 20 및 무작위 ResNet 초기화, seed 41, 시작점 에피소드별 6개. 학습 루프는 실제 데이터 저장본을 읽지만 250개 전부를 시작점으로 쓰지는 않는다.
- CPU 스키마 테스트 3건 통과. 데이터: `/home/my/.cache/m2a_d_synth` (본 측정), `/home/my/.cache/m2a_d_synth_verified` (생성기 재현).

## 원자료와 남은 문제

- 세션 원자료 디렉터리: `C:\Users\my\.aside\u\0\sessions\2026-11-27_OfwYPEKLh10ZnxP9\tmp\ws-d\`. 파일 `act-b4.log`, `smol-b1-v2.log`(스텝·추론 샘플·VRAM), `dataset-verified.log`, `mask-verify.log`, `tests-verified.log`, `install.log`, `compat.log`, `tv.log`, `tv-cpu.log`, `additional.log`, `pip-final.txt`, `model-download.log`, `model-config.log`.
- 보존용 원자료 묶음: 세션 `artifacts/m2a-gb-raw-logs.zip`.
- Colab/Kaggle용 `m2a/learn/cloud_smolvla_train.py`와 업로드·실행·체크포인트 다운로드 절차 준비. 클라우드 실행·업로드 없음.
- 남은 일: 시뮬레이터 시연 데이터로 재측정 및 파지 성공률 확인, 운영용 torchvision ABI 조합 확정. 이 gate는 합성 데이터에서의 학습·추론 가능성까지만 판정한다.

## 면접에서 이렇게 설명하면 됨

파지 정책의 실물 적용 전에, 같은 LeRobot v3 합성 데이터로 RX 7600에서 학습과 청크 추론을 검증했다. 마스크는 저장 형식을 유지하면서 ACT 입력 시 보조 이미지로 바꿨다. 합성 데이터에서 학습 가능성은 빠르게 확인했지만, 실제 작업 성공률은 시뮬레이터 시연과 별도 검증이 필요하다.