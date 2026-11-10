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
