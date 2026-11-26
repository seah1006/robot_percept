# M2A R-GRASP 조사 결과 (추정은 '추정' 표기)

## 1. MuJoCo 마찰 파지 안정화 (공식 문서)
출처: https://mujoco.readthedocs.io/en/latest/modeling.html , https://mujoco.readthedocs.io/en/stable/XMLreference.html
- cone=elliptic + impratio=10 (조작용). 문서의 "권장 초기값" 표: integrator implicitfast, solref[0] 0.004~0.01, solimp[0] 0.9(필요시 0.95), 파지 패드 condim 4 또는 6.
- impratio는 elliptic에서만 크게. pyramidal에서 큰 impratio 비권장.
- 잔류 slow slip: noslip_iterations 1~3 (스텝 약 2배 비용, 과구속 파지에서 chatter 가능).
- 슬립 억제 순서(문서): elliptic + 큰 impratio + Newton 작은 tolerance -> 그래도 안 되면 noslip.
- condim: 1 슬립 실패, 3 이상 필요, 4/6은 비틀림/구름 마찰 추가. 사례: https://github.com/Nas01010101/mujoco-cable-grasp (cone이 결정적, impratio 무차이, condim 4가 약간 깔끔)
- 이슈 https://github.com/google-deepmind/mujoco/issues/3328 : cone=elliptic impratio=10에서도 45g 물체가 ~50-155 um/s로 creep, 1/impratio에 비례, noslip 10이면 ~110배 감소. 2초 유지 시 최대 ~0.3mm라 허용 가능(추정), noslip 병행 권장.
- 불안정 파지 이슈 https://github.com/google-deepmind/mujoco/issues/786 : timestep 1e-3 이하, noslip 3, condim 6, elliptic, multiccd, impratio, 물체/패드 friction 증가.
- mesh -> 원시형: 문서는 상세 mesh는 시각용(contype/conaffinity 분리)으로 두고 충돌은 단순화 권장. capsule/box 지오메트리는 접촉점 안정(추정: mesh는 볼록 hull 및 다중 접촉점 불안정).
- 질량/관성 하한: 공식 하한 수치는 못 찾음(추정: 로봇 손가락 링크 20~90g 대비 물체 20g은 질량비 문제 없음. 관성은 형상에서 자동 계산 사용, 0이나 수동 극소값 금지).

## 2. Menagerie g1_with_hands (직접 확인)
출처: https://github.com/google-deepmind/mujoco_menagerie/blob/main/unitree_g1/g1_with_hands.xml , README(https://github.com/google-deepmind/mujoco_menagerie/blob/main/unitree_g1/README.md)
- option: integrator=implicitfast만 지정(cone/impratio/timestep 기본값 -> pyramidal, impratio 1, 0.002).
- 모든 actuator는 <position> (kp=500, dampratio=1, inheritrange=1). joint armature=0.01, frictionloss=0.3.
- 손 forcerange: thumb_0 +-2.45, 나머지 손가락 +-1.4 N.m (kp 500에 비해 낮음; 토크 포화 주의).
- 손 충돌: palm/thumb0/thumb2/index/middle 전부 mesh(class collision), thumb_1만 box. group 3. 손가락 geom 마찰 지정 없음(기본 1 0.005 0.0001).
- README: 액추에이터는 "needs tuning" 명시.
- 우측 손가락 관절 범위 부호: 우측 index/middle 0~+1.57/+1.745, 좌측은 음수; 우 thumb_1 -1.05~0.72, thumb_2 -1.745~0, 좌 thumb_2 0~1.745. 좌우 반대 주의.
- GitHub issues: 손 관련 특정 이슈는 검색에서 확인 못함(미확인).
- Dex3 파지 사례: 
  - 시뮬 예시: https://inematds.github.io/formacao-fth-corpo-inteiro-v72/en/aulas/maos (Menagerie scene_with_hands에서 pelvis 고정, 4cm 원기둥 고정 물체를 손가락 PD로 쥐어 접촉력 측정 - 들기 검증은 아님)
  - unitree_sim_isaaclab: Isaac-PickPlace-Cylinder/RedBlock-G129-Dex3 태스크 (Isaac, MuJoCo 아님) https://github.com/AlexandreBrown/G1-Playground
  - LeRobot: https://huggingface.co/lerobot/unitree-g1-mujoco 에 Dex1-1(기본), Dex3 MJCF(scene_hands_cameras.xml), URDF 포함.
  - ManiSkill/RoboCasa의 G1+Dex3 사례는 미확인.
- Dex1 MJCF 공개: 예. LeRobot unitree-g1-mujoco 저장소(scene_33dof.xml, URDF 파생 gripper MJCF, 2 prismatic finger). Unitree URDF: https://github.com/unitreerobotics/unitree_ros/blob/master/robots/README.md (dex1_1 URDF).

## 3. 접촉 조건부 weld ("부착 근사")
출처: https://mujoco.readthedocs.io/en/latest/XMLreference.html (equality/weld), https://github.com/google-deepmind/mujoco/discussions/2323 , https://github.com/google-deepmind/mujoco/discussions/2149
- XML에 weld를 active="false"로 미리 정의, 런타임에 data.eq_active[i]=1로 켜고 끔 (공식 문서에 body를 world에 weld 후 eq_active로 임시 고정 명시).
- 주의: (a) weld는 모델 정의 시점의 상대 자세(relpose/eq_data)를 강제 -> 켜는 순간 물체-손 상대 자세가 달라 점프함. 켤 때 eq_data[:6/7]에 현재 상대 pos/quat를 써야 함(MjSpec로 추가 시 오프셋 자동 계산 안 됨). (b) 물체는 free body, 로봇 링크와 body1/body2 지정. (c) solref/solimp로 부드럽게(추정: 켜는 순간 임펄스 방지). (d) 조건(접촉 2개 이상 손가락 + 힘 임계 + 일정 프레임 유지)로 켠 경우 마찰 파지가 아님을 결과에 명시해야 함(추정). (e) MJX는 eq_active 이슈 있음(CPU MuJoCo는 무관).
- 결론: 순수 마찰 파지 시험엔 사용 금지, 폴백/비교군으로만.

## 4. 권장 초기값 표 (추정 포함; 근거는 위 문서 값 + 이슈 사례)
| 물체 | friction(손가락 패드/물체) | condim | timestep | impratio | cone | noslip |
|---|---|---|---|---|---|---|
| 0.12x0.05x0.025 판 (20~80g) | 1.0~1.5 0.005 0.0001 (패드·물체 모두; MuJoCo는 두 geom 중 max 사용) | 4 (패드 6 가능) | 0.001 (0.002 허용 후 비교) | 10 (슬립 시 20~50) | elliptic | 2 |
| 지름 2.4cm 원기둥 | 1.2~1.5 0.005 0.0001 | 6 (구름 억제) | 0.001 | 10~20 | elliptic | 3 |
| 4cm 정육면체 | 1.0 0.005 0.0001 | 4 | 0.001 | 10 | elliptic | 2 |
공통: integrator implicitfast, solref 0.005 1 (접촉), solimp 0.95 0.99 0.001, 테이블 friction 0.8 이상, 손가락 충돌은 capsule/box(반경 ~5~8mm)로 교체하고 mesh는 visual로, 손가락 condim 4. 파지력은 position 액추에이터 ctrl을 관절 한계 쪽으로 더 밀어 forcerange(1.4N.m) 포화 사용. 얇은 판(25mm)은 위에서 집기 위해 손가락 패드 간격/접근 높이 주의(추정).
