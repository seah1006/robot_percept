# G0 결과 (회사 측정 진행 중, 2026-11-16)

모든 입력은 [시뮬인식], GT 보조 없음. Grounding DINO tiny revision `a2bb814dd30d776dcf7e30523b00659f4f141c71`, Apache-2.0(HF metadata/card: bench/g0). 프롬프트 `a red cube. a blue cube.`. N=20, warmup=2. 집 AMD 수치는 NVIDIA 합격 근거가 아니다.

## 1. 집 기록 (11-10 원자료, 이번 PC에서 재실행하지 않음)
|환경/출처|640×360 p50/p95 ms|로드/첫 추론|프로세스 max_alloc / 장치 sampled peak|
|-|-|-|-|
|RX7600 ROCm 2.14.0, bench/g0/rocm_gpu.json|298.7 /306.2|18.30s /21.07s|1016.2 /3721.3 MiB|
|V-G0 독립 재현, bench/verify_g0/rocm_gpu.json|296.2 /316.8|첫 추론7.7s(캐시 차이)|1016.2 /3745 MiB|
|CPU 2.14.0+cpu, 4 threads, bench/g0/cpu.json|3349 /3754|21.01s /3.52s|해당 없음|
|V-G0 CPU 재측정, bench/verify_g0/cpu.json|3049 /3301|별도 원자료 참조|해당 없음|

CPU 원 측정 loadavg=6.05; V-G0 시작0.62/측정중2.9. 재측정 3049ms를 참고 기준으로 권장하되 다른 부하 조건이므로 동일 실행으로 취급하지 않는다.

오검출: 실제 빨간 큐브 1개만 있는 원본640×480에서 `a blue cube` score0.4944, box[112.6,135.2,528.4,305.3]는 테이블 상판 전체를 덮었다. 검출 성공으로 세지 않는다. 현재 bench는 raw 결과 보존, 필터 없음. G1에서 면적/임계값(예0.5) 검증 필요.

numpy: ROCm transformers 설치 전 부재, 설치 후2.5.3 **추가**. numpy 불변 아님. torch2.14.0+rocm10.1.0은 transformers 설치 직전/직후 동일.

## 2. 불변 기준
집 원본 robot_percept에는 torch가 없었다. 원본 env pip freeze 전체 전후 hash 동일(bc113d72...6ac6)이 불변 기준이며, 설치한 별도 ROCm env torch는 transformers 설치 직전/직후를 비교한다. 원본에 없던 torch와 비교해서 불변이라 하지 않는다.
회사 원본은 torch2.14.0+cu130·torchvision0.29.0+cu130 존재. 원본 freeze를 bench/g0/company/original_before/after.txt로 전체 비교한다. 복제본 torch/torchvision/numpy 보존은 별도 비교. 회사 원본 numpy2.5.2/2.5.3 dist-info 두 개 진단됨; 삭제하지 않았다. pip freeze 하나만으로 중복 메타데이터가 없다는 뜻은 아니다.

## 3. 회사 조건·판정
RTX2080 SUPER 8GB, driver610.57.01, CUDA UMD13.3, 원본 환경 torch cu130. robot_percept_g0c는 원본 clone 후 common+cu130 constraints로 transformers4.57.6 추가. 원본 freeze 전후 SHA256 `5212c735e645c4f948fd3b8de873dac69ba55a772396ec56e85a6e3de685ec00` 동일. 복제 env torch/torchvision/numpy 줄 차이 없음(`clone_initial.txt`/`clone_first_installed.txt`).

|회사 cu130 / 출처|N|p50/p95 ms|로드/첫 추론|process max_alloc / device sampled peak MiB|loadavg 시작→끝|
|-|-|-|-|-|-|
|640×360 / 구현2런+V-G0 2런|각20|p50 범위133.6~183.1 (V-G0 133.6/169.3), p95 구현239.67|구현 초기16.50s /7.077s|993.02 /2208.56 (기저1088.56)|구현1.34→1.41|
|1280×720 / company/cuda_1280.json|20|326.76 /346.04 (V-G0 346.0 /381.1)|3.708s /1.888s|1912.51 /3382.56|1.79→1.69|
|640 SAM2 small+FP 모델상주 / company/coexist.json|20|138.11 /168.55|3.494s /1.296s|1627.28 /2838.56|1.13→1.00|

640 단일 런183.1ms는 V-G0 133.6ms 대비27% 차이로 ±20% 재현 실패. 따라서 단일 대표값이 아니라 4런 p50 범위134~183ms로 보고한다. 추가 구현런(company/cuda_640_repeat.json): p50/p95=171.29/209.81ms, 로드3.310s/첫추론1.532s, load1.33→1.51, VRAM993.02/2208.56MiB. 1280 재현 p50+5.9%/p95+10.1% 이내. 회사640에서도 blue cube0.494446 테이블 박스 오검출 재현; 1280은0.575883까지 올라갔으므로 threshold0.5만으로 이 오검출을 제거하지 못한다. 640 장치 sampled 사용량은7168MiB 미만이지만 true peak/공존 워밍업 합격으로 확대하지 않는다.
원본640×480을640×360/1280×720로 강제 resize한다(종횡비 왜곡 및720 업스케일, 카메라 원본 성능/정확도 증거 아님). processor do_resize=False로 실 tensor 크기 지정.
7.0GiB=7168MiB는 Windows·타프로세스·기저 사용량 포함 **장치 전체 used** 기준. 프로세스 torch max_alloc/reserved는 별도 참고값.20ms mem_get_info 표본 peak는 순간 true peak 상한을 보장하지 않는다. 샘플링 스레드 간섭 가능; 실제 운영 합격은 재검증 필요.
coexist는 SAM2 small/FP 모델 상주 조건, SAM2/FP 실제 추론 워밍업/동시 처리 합격으로 해석 금지. FP 전역 tensor default 회귀는 아직 운영 코드 변경 없음.

## 4. 재현
`bash tools/g0/install_g0.sh` (원본 수정 금지, clone prefix 반쪽이면중단). `bash tools/g0/run_bench.sh --width 640 --height 360 --n 20 --output bench/g0/company/cuda_640.json`,1280×720도 동일. 각 실행 measure→gpu 락/timeout280초. `--coexist both`는 모델 상주 별도 시험. ROCm은 AMD 없는 회사에서 bash -n, probe/bench 재exec 환경 로직 리뷰만 실시, 실행 PASS 아님.

## 5. 회사 멱등 재실행
`bench/g0/company/idempotent.log`: transformers4.57.6 모든 의존 already satisfied, 원본 hash 동일, clone torch/torchvision/numpy freeze 동일. 회사 install_g0 2번째 실행 완료. ROCm 설치 스크립트 실행 멱등성은 AMD 부재로 검증하지 않았다.
SAM2 small+FP both 모델상주 errors=[]; warmup/register/동시추론은 미실시. 회사 2해상도·상주 조건 모두 sampled peak7168MiB 미만이나 상주만의 증거다.

## 재개 지점
exec1004·1014 모두 exit0. 회사640追加N20·1280·SAM2small+FP상주·회사install멱등 완료. V-G0 최종판정 대기. 원본env 변경0·커밋0. AMD 실행/ROCm설치멱등은 blocked(하드웨어 없음). 재측정: bash tools/g0/run_bench.sh --width 640 --height 360 --n 20 --output bench/g0/company/cuda_640_repeat.json. 운영SAM2/FP warmup 공존 합격은 별도 과제.