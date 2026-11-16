# W2 최종 결과

- 출처: [시뮬GT 박스]. GT mesh projected bbox, 검출기·가림 판정 아님.
- 튜닝: seed1000~1019,20장면. 확정 후 eval seed100000~100039 **1회**, 120물체.
- 자기 테스트: **18 PASS / 0 FAIL, 2.31초**. V-W2 전체358PASS는 게이트·bbox보정 추가 전 snapshot.
- ON: bbox 중심 광선×height/2 평행평면 교차 후 바닥중심. OFF: bbox 하단 중심×책상 평면. 계수0.5는 중간높이 기하가정, eval fitting 없음.
- 박스 규약: GT projected vertex min/max에서 [lo,max+1), anchor 경계→픽셀중심 -0.5.
- ±2px 최대이동: u/v 네 극단 평행 bbox 이동, 보정ON 무잡음 출력 대비 이동최대.
- ±2px 균일오차: 물체당100회 u/v 독립U[-2,2] bbox 평행이동, 실제GT 위치오차 pooled p95.

|물체|N|bbox ON p50/p95 mm|bbox OFF p50/p95 mm|±2px 최대이동 p50/p95 mm|±2px 균일GT오차 p95 mm|
|-|-:|-:|-:|-:|-:|
|ball|16|0.126 / 0.163|9.841 / 11.057|6.453 / 6.793|5.349|
|block|10|0.527 / 0.782|30.675 / 32.791|6.12 / 6.907|5.559|
|bottle|15|0.65 / 0.715|18.721 / 18.973|6.27 / 7.253|5.659|
|box|9|0.65 / 0.692|28.316 / 29.372|6.48 / 7.008|5.659|
|can|17|0.704 / 0.831|24.114 / 24.347|6.025 / 6.926|5.322|
|cup|14|0.91 / 1.044|36.233 / 36.375|6.301 / 6.799|5.615|
|mug|14|0.84 / 0.897|32.953 / 33.327|5.962 / 6.96|5.368|
|mustard|11|6.319 / 10.597|33.993 / 43.103|6.571 / 6.759|14.32|
|small_box|14|0.883 / 1.259|34.522 / 37.119|6.121 / 7.022|5.535|

## 보정 도구
- 셀K 합성3x supersampling·다양한 자세 체커보드14장: accepted=14,RMS=0.0535px,K최대차=3.5245px,카메라중심오차=2.7447mm.
- distortion model: k1_k2_p1_p2_k3fixed0,normal span=56.834도,normalized center span=0.183.
- 품질gate: RMS<=.5px,normal span>=10도,center span>=.03,K/왜곡합리성. plain보드180도모호성은 image-top-left endpoint 기준. 실제월드 등록과 일치 필수.
- 사거리<=3m,평면입사각>=10도. fuser rc1만 무소유 인정,도구 부재/오류 fail-closed.
- GT top anchor 높이ON 수학오차0은 별도 sanity 검증이며 실인식 성능 아님. 원자료 topON/OFF 유지.

## 제한·후속
- ArUco 외부값·독립 격자점: **[blocked: 회사 PC 실카메라]**. 이번 라운드 실카메라 사용 금지.
- 실제 preview FOV/crop 동일성·실물 오차 미검증. validation_error_m=null.
- bbox midheight는 대칭/수직물체 근사. mustard 등 비대칭형 잔여편향. yaw 미관측null.
- 실카메라0/운영파일수정0/commit0. 다른페어 운영파일diff는 W2수정 아님.

## 환경
- load: 1.44140625, 1.4658203125, 1.22900390625
- GPU(벤치는GPU사용0): name, memory.used [MiB], utilization.gpu [%]
NVIDIA GeForce RTX 2080 SUPER, 1040 MiB, 22 %
- 공유호스트 동시작업은 OS수준 통제 안 됨,측정 rp_measure 직렬화.
- 원자료 bench/w2/*.json,yaml. 재현명령 notes/w2_changes.md.
