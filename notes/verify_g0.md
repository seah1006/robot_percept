# V-G0 검증 노트 (검증자 Claude)

## 판정: NEEDS WORK (기본값, 구현자 보고 미도착)

## 기준선 (2026-11-10)
- 원본 env robot_percept pip freeze: 87줄, sha256 bc113d72322218c3e8f5811652e1f21beb80240c00a2adaf22704e86b3226ac6
- 파일: bench/verify_g0/baseline_freeze.txt
- git HEAD 2859663, 시작 시 git status: bench/verify_g0/ 만 untracked (내 파일)
- conda env 목록: base, robot_percept 뿐 (복제 env·robot_percept_rocm 아직 없음)
- tools/g0, notes/g0_results.md 아직 없음

## 재개 지점
구현자(I-G0, EBVS8SuEZUg2cb0s) 보고 도착 후: 1) freeze 해시 비교 2) 복제 env torch/numpy 버전·GroundingDino 추론 재현 3) HF sha·라이선스 WebFetch 4) ROCm 재현 5) CPU 지연 락 내 재측정(±20%) 6) 스크립트 멱등·git status·크기

## 중간 확인 (2차)
- 원본 env freeze 재측정: sha256 bc113d72...6ac6 = 기준과 동일 (불변, 87줄, torch/transformers 0건)
- HF API 직접 확인: IDEA-Research/grounding-dino-tiny sha a2bb814dd30d776dcf7e30523b00659f4f141c71 (구현자 주장 일치), license apache-2.0, 비게이트
- env 목록: robot_percept_g0, robot_percept_rocm 생성됨. 구현자 주장: 원본에 torch 부재(확인: freeze에 torch 0건), transformers 4.57.6 설치 로그 bench/g0/install_transformers_4.57.6.log, ROCm 설치 진행 중, CPU 벤치용 robot_percept_cpu 예정
- 미완: 복제 env 추론 재현, ROCm, CPU 지연 재측정, 스크립트 멱등성, 대용량 점검
- 주의: 브리프는 "복제 env에서 torch 버전 불변"이라 했으나 원본에 torch가 없음 -> 불변 비교 대상 재정의 필요
- git status: tools/g0, bench/g0 등 untracked (미커밋, 정상). notes/plan_r5... M 은 구현자 아닌 부모 가능성, 미확인

## 판정: NEEDS WORK (유지)

## 재개 지점
구현자 최종 보고 후 robot_percept_g0/_cpu/_rocm 대상으로 추론·ROCm·지연(락 내 ±20%)·멱등·크기 재현

## 3차: 독립 재현 (2026-11-10 22:15~22:22, 락 준수, 재현물 bench/verify_g0/)
- 원본 env freeze 재해시: bc113d72...6ac6 = 기준과 동일 (불변). 원본에 torch/transformers 없음.
- ROCm probe: LD_LIBRARY_PATH 없이 => ImportError libgomp.so.1 (rc=1, probe_nold.log 재현). 있으면 available True, RX 7600, matmul_sum 32768 (rc=0, probe.log). 결함: tools/g0/install_rocm.sh에 LD_LIBRARY_PATH 미설정, probe_gpu.py·벤치 래퍼도 동일. HSA_ENABLE_DXG_DETECTION=1은 스크립트에 있음.
- GPU 지연 (부모 bench_gpu.py, n=20, 이중 락): p50 296.2ms (주장 298.7, -0.8%), p95 316.8ms (주장 306.2, +3.4%), 첫 추론 7.7s (주장 21s, 이번엔 캐시/워밍 영향), max_alloc 1016.2MiB 동일, 장치 peak 3745MiB(주장 3721). ±20% 이내 PASS.
- CPU 지연: bench/g0/cpu.json은 env robot_percept_cpu 의 torch 2.14.0+cpu, numpy 2.5.3, transformers 4.57.6, 4스레드. 재측정(loadavg 시작 0.62, 측정 중 2.9): p50 3049ms (주장 3349, -9%), p95 3301ms (주장 3754, -12%). ±20% 이내 PASS. 단 원 측정은 loadavg 6이라 조용하지 않았음; 재측정치가 더 정확. 보고 기준값은 재측정 3.05s 권장.
- 검출(GPU 재현): red cube 0.7141 [326.9,153.0,357.3,186.8], blue cube 0.4944 [112.6,135.2,528.4,305.3] — 주장과 소수점까지 동일. 이미지(rgb.png 640x480)에는 빨간 큐브 1개만 있고 파란 큐브 없음. blue 박스는 테이블 상판 전체(약 416x170px)를 덮는 오검출(false positive, 점수 0.49). 박스 크기/면적 비율 필터 또는 임계 0.5 이상 필요, 결과 문서에 오검출로 명기해야 함.
- ROCm env transformers 설치 전후: torch 2.14.0+rocm10.1.0 불변. numpy는 설치 전 부재 -> 후 2.5.3 추가(transformers 의존). "numpy 불변"이 아니라 "추가"임을 g0_results에 정확히 쓸 것. 설치 전 torch가 numpy 없이 "Failed to initialize NumPy" 경고를 냄.
- 대용량: bench/g0 124K, tools/g0 20K. 가중치는 ~/.cache/huggingface(1.3G, 저장소 밖)이라 저장소 유입 없음. git status는 untracked 신규 파일들만 + notes/plan_r5 M(+9줄, 구현자/부모 편집으로 보임, 확인 필요).
- 미검증: 스크립트 멱등성 전체 재실행(install_g0.sh, install_rocm.sh 재실행 미수행), HF 라이선스 카드 본문(API cardData apache-2.0는 확인), g0_results.md 미작성(Codex 몫), 복제 env robot_percept_g0에서 추론 직접 재현(대신 robot_percept_cpu에서 CPU 추론 수행됨).
- 개선 지적: (1) LD_LIBRARY_PATH 누락 (2) blue cube 오검출 명기 (3) numpy 표현 (4) cpu.json loadavg 6 재측정 반영 (5) bench_gpu를 tools/g0로 정식화 (6) 원본 대비 torch 불변 기준 재정의

## 판정: NEEDS WORK (측정·원본불변·HF sha/라이선스는 PASS, 스크립트 결함·멱등성 미검증·g0_results 미작성)

## 재개 지점
Codex 복귀(11-12 13:50 경) 후: 위 개선 6건 반영 확인 -> install_g0.sh/install_rocm.sh 재실행 멱등 검사(락 안) -> g0_results.md 수치가 bench/verify_g0 재측정값과 ±20%인지 대조 -> git status 재확인

## 회사 PC 기준선 (2026-11-16 12:14, r5 G0c, HEAD ebbb8f4)
- 원본 env robot_percept(Python 3.12.14) pip freeze: 149줄, sha256 5212c735e645c4f948fd3b8de873dac69ba55a772396ec56e85a6e3de685ec00 (bench/verify_g0/company_freeze.txt). 집 env(87줄, bc113d72...)와 다름.
- 주요: torch 2.14.0+cu130, torchvision 0.29.0+cu130, triton 3.8.0, nvidia-cudnn-cu13 9.24.0.43, numpy 2.5.3(conda 로컬 wheel). notes/constraints/cu130.txt는 numpy 2.5.3·opencv 5.0.0.93·torch 2.14.0+cu130 고정.
- numpy dist-info 중복: site-packages에 numpy-2.5.2.dist-info(2026-10-26 14:08:23, REQUESTED/direct_url 없음, INSTALLER/RECORD 있음)와 numpy-2.5.3.dist-info(14:08:57, REQUESTED+direct_url=conda 로컬 wheel)가 공존. numpy/ 패키지 디렉터리는 1개, import numpy = 2.5.3. pip freeze는 2.5.3만 표시. 실사용 영향 없음(잔재 dist-info), 삭제하지 않음. 원본 env 불변 비교 시 이 중복 상태도 기준에 포함.
- nvidia-smi: RTX 2080 SUPER(Bus 65:00.0) 드라이버 610.57.01, CUDA UMD 13.3, 8192MiB 중 1010MiB 사용(데스크톱 점유, 프로세스 목록 없음=WSL), util 35%, 23W, 31C. 즉 장치 peak 판정 시 기저 ~1010MiB를 빼거나 명시해야 함. loadavg 2.04/0.67/0.23.
- git status: bench/verify_g0/(내 파일), notes/TEAM_R5.md untracked만. 구현자 파일 아직 없음.

## 판정: NEEDS WORK (기본값, I-G0 묶음 미도착)

## 재개 지점 (회사 PC)
I-G0 묶음 도착 후: (1) 집 개선 6건(LD_LIBRARY_PATH, blue 오검출 명기, numpy 표현, loadavg 재측정, bench_gpu 정식화, 불변 기준) 코드 확인 (2) company_freeze sha 5212c735 재비교 + numpy 2.5.2/2.5.3 dist-info 유지 확인 (3) Grounding DINO tiny a2bb814 640x360·1280x720 N=20 ±20% 재측정(measure→gpu 락, 기저 1010MiB 차감), max_alloc/장치 peak, 7.0GiB 상한 정의 (4) g0_results.md 원자료 대조, AMD/NVIDIA 출처 구분 (5) 스크립트 멱등·대용량
## 회사 PC 2차: 묶음1 코드 리뷰 (12:20, 실행 재현 없음)
- 원본 env freeze 재해시: 5212c735...ec00 = 기준 동일(불변). 복제 env robot_percept_g0c는 아직 없음(conda env list: base, ai, robot_percept) -> --dry-run·실측 미검증.
- bash -n install_g0.sh / install_rocm.sh: 둘 다 문법 OK.
- 개선 6건: (1) LD_LIBRARY_PATH+HSA 추가 확인(install_g0/install_rocm/probe_gpu) PASS-코드 (5) bench_gpu 정식화+해상도·n·backend 자동·20ms 장치 샘플·프로세스 max_alloc 분리 확인 PASS-코드 (6) 원본 불변은 install_g0.sh가 original_before/after cmp로 정의, 코드 OK. (2)(3)(4): 코드 근거 없음, g0_results.md 대기. 
- 지적: a) clone이 timeout 280에 끊기면 반쪽 prefix가 남고 재실행 시 `conda create` 충돌(가드는 bin/python 유무만 봄). b) set -u 상태에서 conda activate 실패 가능성, 실제 재실행으로 확인 필요. c) 벤치 입력은 640x480 rgb.png를 640x360/1280x720로 강제 resize(종횡비 왜곡, 720p는 업스케일) -> 결과문서에 명기. d) 검출은 threshold .35 원본 그대로 저장, blue cube 오검출 필터 없음 -> 문서 명기. e) 20ms 샘플러 스레드가 지연에 미세 간섭 가능(지연·VRAM 별도 런 권장). f) coexist는 모델 상주만(SAM2/FP 추론 워밍 없음)이라 7.0GiB(7168MiB, 장치 전체 used, Windows 기저 ~1010MiB 포함) 판정은 하한 근사. 샘플은 진짜 순간 peak 아님(코드 주석 인정).
- 작업트리: tools/g0 4개 M, bench/g0/company 신규, 그 외 notes/verify_* 등은 타 페어 변경. 대용량 점검은 실측물 도착 후.

## 판정: NEEDS WORK (유지)
## 재개 지점
g0c 복제 완료·회사 측정(bench/g0/company/*.json) 도착 후: dry-run, 640x360/1280x720 N=20 ±20% 독립 재측정(measure→gpu 락), g0_results 대조, install_g0.sh 재실행 멱등.
## 회사 PC 3차 (g0_results.md 초안 검토, 실측 대기)
- g0_results.md 32줄: 집 수치(298.7/306.2, 3349/3754, 재현 296.2/316.8, 3049/3301)가 내 원자료와 일치, AMD(집)와 NVIDIA(회사 [blocked]) 구분, blue 오검출·numpy 추가·torch 불변 기준·resize 왜곡·7168MiB 장치 전체 기준·상주만 한계 모두 명기 -> 문서 구조 PASS. 회사 수치 없음.
- 우려: clone이 `timeout 280`인데 7.4GB 복제가 152초 시점 진행 중. 280초 초과 시 반쪽 prefix로 exit3 가능 -> 재시도 경로 확인 필요.
- 미완: g0c 생성, dry-run, 640/1280 N=20 독립 재측정, coexist, 멱등 재실행. 판정 NEEDS WORK.
## 회사 PC 4차: 독립 재측정 (11-16, g0c env, measure→gpu 이중 락, GPU P0 1980/2100MHz, 기저 1088.6MiB)
| 항목 | I-G0 | V-G0 | 차이 |
|-|-|-|-|
| 640x360 p50 | 183.08 | 133.62 (재2: 169.33) | -27.0% (재2 -7.5%) |
| 640x360 p95 | 239.67 | 193.51 (재2: 248.22) | -19.3% (재2 +3.6%) |
| 1280x720 p50 | 326.8 | 346.0 | +5.9% PASS |
| 1280x720 p95 | 346.0 | 381.1 | +10.1% PASS |
| 640 process max_alloc | 993.02 | 993.02 | 동일 |
| 640 장치 sampled peak | 2208.56 | 2208.56 | 동일 |
| 1280 max_alloc/reserved/peak | 1912.5/2264/3382.6 | 동일 | 동일 |
- 검출(640): red 0.714, blue 0.4944(오검출) 동일. 원자료: bench/verify_g0/cuda_640{,_r2}.json, cuda_1280.json.
- 640 p50은 런 간 편차 큼(내 두 런 133.6 vs 169.3 = 27%): 단일 런 ±20% 판정 불안정. 권고: 640 보고는 3런 범위(약 134~183ms)로, 단일 점수치 금지. 1280은 안정.
- 공존(I-G0 coexist.json both, 640): p50 138.1, max_alloc 1627.3MiB, 장치 peak 2838.6MiB(기저 포함) -> 7168MiB 대비 39.6%. 모델 상주만이라 추론 워밍 미포함(문서 명기). 내 재현은 coexist 미수행.
- PYTHONPATH 공지: 내 런은 .sh 파일 안 bash 확장이라 절대경로 정상. tools/g0/run_bench.sh는 `$PWD` 사용(스크립트 안 cd라 영향 없음, 단 PowerShell 직접 호출은 위험).
- 대용량: bench/g0 신규 소용량(수 MB 이하). bench/ 큰 폴더(verify_s 133M 등)는 타 페어 이전 산출물, 이번 G0 유입 아님.
- 미완: install_g0.sh 멱등 재실행(회사), coexist 독립 재현.
## 판정: NEEDS WORK (1280·VRAM·검출·원본 불변 PASS, 640 지연 ±20% 불일치, 멱등·공존 미재현)
## 최종 (11-16) 640 p50 4런: 133.6/169.3/171.3/183.1ms(범위 134~183, 단일 ±20% 재현 실패 명기됨). run_bench 절대 PYTHONPATH 반영 확인 여부는 위 grep 참조. 판정: NEEDS WORK 유지(공존·AMD 직접 재현 불가, 640 단일치 불안정). PASS: 1280, VRAM, 검출, 원본 불변, 문서 출처 구분.

## 최종 판정 (11-16, 부모 요청 4항목)
- run_bench.sh: gl_env source 뒤 `PYTHONPATH="$PWD:$PWD/FoundationPose:..."` 재export. 절대경로 아님이지만 `cd "$(dirname "$0")/../.."`로 repo 루트 고정 후 $PWD 확장이라 PowerShell 호출에도 안전. PASS.
- 공존 both 독립(이중 락, 640): max_alloc 1627.3MiB, 장치 peak 2838.6MiB(기저 1088.6) 동일, errors [], p50 223.2/p95 275.1ms(I-G0 138.1/168.6, +62%: 지연 불일치, 지연은 공존 합격 근거로 쓰지 말 것. VRAM만 재현 PASS).
- install_g0.sh 락 안 재실행 rc=0, 원본 sha 5212c735 전(재실행 전 복사본)·후 동일, 복제 torch/torchvision/numpy 줄 불변. 재실행이 bench/g0/company/original_*.txt를 동일 내용으로 덮음. PASS.
- g0_results.md: 640 범위 표기, 공존 '모델 상주만/워밍업 미포함', AMD 멱등 blocked 표기 확인. PASS.
## 판정: 회사 GPU G0 범위 PASS(조건부: 640 지연은 범위 134~183ms, 공존 지연 불일치 미해결, 공존 VRAM은 상주만). ROCm 실행 미검증은 별도.