### O3-knn dev60 (A4 중간판) (runs: m2a/notes/wse_runs/e3-main-o3knn-a4mid2)
| 구성 | 상황 | n | 성공 [Wilson 95% CI] | 엄격 | avg_progress | 거짓 완료 | MISID 에피소드/집기 | fail_code | 실패 층 | 평균 에피소드 s |
|---|---|---:|---|---:|---:|---:|---|---|---|---:|
| B1 | missing | 12 | 0/12 [0.0%, 24.2%] | 0 | 0.017 | 0 | 1/1 | {'GRASP_SLIP': 10, 'IK_FAIL': 1, 'MISID': 1} | {'skill': 11, 'percept': 1} | 6.1 |
| B1 | pretray | 12 | 0/12 [0.0%, 24.2%] | 0 | 0.251 | 0 | 0/0 | {'IK_FAIL': 8, 'GRASP_SLIP': 4} | {'skill': 12} | 6.9 |
| B1 | reach | 12 | 0/12 [0.0%, 24.2%] | 0 | 0.062 | 1 | 0/0 | {'GRASP_SLIP': 9, 'IK_FAIL': 2, 'FALSE_COMPLETION': 1} | {'skill': 11, 'other': 1} | 5.7 |
| B1 | stacked | 12 | 0/12 [0.0%, 24.2%] | 0 | 0.042 | 2 | 2/2 | {'FALSE_COMPLETION': 2, 'IK_FAIL': 4, 'GRASP_SLIP': 5, 'MISID': 1} | {'percept': 2, 'skill': 9, 'other': 1} | 6.1 |
| B1 | standard | 12 | 0/12 [0.0%, 24.2%] | 0 | 0.075 | 0 | 0/0 | {'GRASP_SLIP': 8, 'IK_FAIL': 4} | {'skill': 12} | 6.8 |
| B1c | missing | 12 | 0/12 [0.0%, 24.2%] | 0 | 0.017 | 1 | 0/0 | {'GRASP_SLIP': 10, 'FALSE_COMPLETION': 1, 'PERCEPT_MISS': 1} | {'skill': 11, 'other': 1} | 6.0 |
| B1c | pretray | 12 | 0/12 [0.0%, 24.2%] | 0 | 0.272 | 1 | 0/0 | {'IK_FAIL': 8, 'GRASP_SLIP': 3, 'FALSE_COMPLETION': 1} | {'skill': 11, 'other': 1} | 8.4 |
| B1c | reach | 12 | 0/12 [0.0%, 24.2%] | 0 | 0.062 | 1 | 0/0 | {'GRASP_SLIP': 9, 'IK_FAIL': 2, 'FALSE_COMPLETION': 1} | {'skill': 11, 'other': 1} | 6.7 |
| B1c | stacked | 12 | 0/12 [0.0%, 24.2%] | 0 | 0.042 | 2 | 2/2 | {'FALSE_COMPLETION': 2, 'IK_FAIL': 3, 'PERCEPT_MISS': 2, 'GRASP_SLIP': 4, 'MISID': 1} | {'percept': 2, 'skill': 9, 'other': 1} | 7.1 |
| B1c | standard | 12 | 0/12 [0.0%, 24.2%] | 0 | 0.118 | 0 | 0/0 | {'GRASP_SLIP': 6, 'PERCEPT_MISS': 2, 'IK_FAIL': 4} | {'skill': 12} | 8.5 |
| B4 | missing | 12 | 0/12 [0.0%, 24.2%] | 0 | 0.000 | 0 | 0/0 | {'IK_FAIL': 3, 'GRASP_SLIP': 5, 'PERCEPT_MISS': 3, 'PLAN_VIOLATION': 1} | {'skill': 9, 'other': 2, 'plan': 1} | 9.3 |
| B4 | pretray | 12 | 0/12 [0.0%, 24.2%] | 0 | 0.217 | 1 | 0/0 | {'IK_FAIL': 3, 'PERCEPT_MISS': 7, 'GRASP_SLIP': 1, 'FALSE_COMPLETION': 1} | {'skill': 10, 'other': 2} | 13.7 |
| B4 | reach | 12 | 0/12 [0.0%, 24.2%] | 0 | 0.021 | 2 | 0/0 | {'GRASP_SLIP': 3, 'PERCEPT_MISS': 4, 'FALSE_COMPLETION': 2, 'IK_FAIL': 3} | {'skill': 8, 'other': 4} | 7.2 |
| B4 | stacked | 12 | 0/12 [0.0%, 24.2%] | 0 | 0.021 | 1 | 1/1 | {'MISID': 1, 'IK_FAIL': 2, 'PERCEPT_MISS': 4, 'FALSE_COMPLETION': 1, 'GRASP_SLIP': 4} | {'percept': 1, 'skill': 6, 'other': 5} | 7.6 |
| B4 | standard | 12 | 0/12 [0.0%, 24.2%] | 0 | 0.037 | 0 | 0/0 | {'PERCEPT_MISS': 9, 'GRASP_SLIP': 2, 'PLAN_VIOLATION': 1} | {'other': 4, 'skill': 7, 'plan': 1} | 10.1 |

쌍체 B4 - B1 (같은 장면 60개, 부트스트랩 10000회 95% CI, 임의 지정):
- 성공: +0.000 [+0.000, +0.000]
- 엄격 성공: +0.000 [+0.000, +0.000]
- avg_progress: -0.030 [-0.056, -0.010]

쌍체 B1c - B1 (같은 장면 60개, 부트스트랩 10000회 95% CI, 임의 지정):
- 성공: +0.000 [+0.000, +0.000]
- 엄격 성공: +0.000 [+0.000, +0.000]
- avg_progress: +0.013 [-0.009, +0.038]
