### O3-knn dev60 (A4 중간판) (runs: m2a/notes/wse_runs/e3-main-o3knn-a4mid)
| 구성 | 상황 | n | 성공 [Wilson 95% CI] | 엄격 | avg_progress | 거짓 완료 | MISID 에피소드/집기 | fail_code | 실패 층 | 평균 에피소드 s |
|---|---|---:|---|---:|---:|---:|---|---|---|---:|
| B1 | missing | 12 | 0/12 [0.0%, 24.2%] | 0 | 0.067 | 1 | 0/0 | {'GRASP_SLIP': 7, 'IK_FAIL': 4, 'FALSE_COMPLETION': 1} | {'skill': 11, 'other': 1} | 13.0 |
| B1 | pretray | 12 | 0/12 [0.0%, 24.2%] | 0 | 0.251 | 0 | 0/0 | {'IK_FAIL': 9, 'GRASP_SLIP': 3} | {'skill': 12} | 10.3 |
| B1 | reach | 12 | 0/12 [0.0%, 24.2%] | 0 | 0.183 | 5 | 0/0 | {'FALSE_COMPLETION': 5, 'GRASP_SLIP': 5, 'IK_FAIL': 2} | {'other': 5, 'skill': 7} | 11.8 |
| B1 | stacked | 12 | 0/12 [0.0%, 24.2%] | 0 | 0.056 | 3 | 1/1 | {'FALSE_COMPLETION': 3, 'IK_FAIL': 4, 'GRASP_SLIP': 5} | {'percept': 1, 'skill': 9, 'other': 2} | 9.2 |
| B1 | standard | 12 | 0/12 [0.0%, 24.2%] | 0 | 0.197 | 1 | 0/0 | {'GRASP_SLIP': 4, 'IK_FAIL': 7, 'FALSE_COMPLETION': 1} | {'skill': 11, 'other': 1} | 14.1 |
| B1c | missing | 12 | 0/12 [0.0%, 24.2%] | 0 | 0.050 | 1 | 0/0 | {'GRASP_SLIP': 8, 'IK_FAIL': 2, 'PERCEPT_MISS': 1, 'FALSE_COMPLETION': 1} | {'skill': 11, 'other': 1} | 12.9 |
| B1c | pretray | 12 | 0/12 [0.0%, 24.2%] | 0 | 0.251 | 0 | 0/0 | {'IK_FAIL': 10, 'GRASP_SLIP': 2} | {'skill': 12} | 13.1 |
| B1c | reach | 12 | 0/12 [0.0%, 24.2%] | 0 | 0.179 | 5 | 0/0 | {'FALSE_COMPLETION': 5, 'GRASP_SLIP': 5, 'IK_FAIL': 1, 'PERCEPT_MISS': 1} | {'other': 5, 'skill': 7} | 13.0 |
| B1c | stacked | 12 | 0/12 [0.0%, 24.2%] | 0 | 0.056 | 3 | 2/2 | {'FALSE_COMPLETION': 3, 'IK_FAIL': 3, 'PERCEPT_MISS': 2, 'GRASP_SLIP': 3, 'MISID': 1} | {'percept': 2, 'skill': 8, 'other': 2} | 11.5 |
| B1c | standard | 12 | 0/12 [0.0%, 24.2%] | 0 | 0.131 | 0 | 0/0 | {'GRASP_SLIP': 5, 'PERCEPT_MISS': 2, 'IK_FAIL': 5} | {'skill': 12} | 15.2 |
| B4 | missing | 12 | 0/12 [0.0%, 24.2%] | 0 | 0.050 | 0 | 0/0 | {'GRASP_SLIP': 7, 'PERCEPT_MISS': 4, 'IK_FAIL': 1} | {'skill': 10, 'other': 2} | 19.6 |
| B4 | pretray | 12 | 0/12 [0.0%, 24.2%] | 0 | 0.237 | 0 | 0/0 | {'IK_FAIL': 2, 'PERCEPT_MISS': 7, 'GRASP_SLIP': 2, 'PLAN_VIOLATION': 1} | {'skill': 12} | 26.5 |
| B4 | reach | 12 | 0/12 [0.0%, 24.2%] | 0 | 0.058 | 2 | 1/1 | {'PERCEPT_MISS': 6, 'GRASP_SLIP': 2, 'FALSE_COMPLETION': 2, 'IK_FAIL': 2} | {'skill': 7, 'other': 5} | 14.8 |
| B4 | stacked | 12 | 0/12 [0.0%, 24.2%] | 0 | 0.021 | 1 | 1/1 | {'MISID': 1, 'PERCEPT_MISS': 6, 'IK_FAIL': 2, 'FALSE_COMPLETION': 1, 'GRASP_SLIP': 2} | {'percept': 1, 'skill': 6, 'other': 5} | 14.7 |
| B4 | standard | 12 | 0/12 [0.0%, 24.2%] | 0 | 0.097 | 1 | 0/0 | {'PERCEPT_MISS': 6, 'GRASP_SLIP': 4, 'FALSE_COMPLETION': 1, 'IK_FAIL': 1} | {'other': 3, 'skill': 9} | 19.5 |

쌍체 B4 - B1 (같은 장면 60개, 부트스트랩 10000회 95% CI, 임의 지정):
- 성공: +0.000 [+0.000, +0.000]
- 엄격 성공: +0.000 [+0.000, +0.000]
- avg_progress: -0.058 [-0.100, -0.023]

쌍체 B1c - B1 (같은 장면 60개, 부트스트랩 10000회 95% CI, 임의 지정):
- 성공: +0.000 [+0.000, +0.000]
- 엄격 성공: +0.000 [+0.000, +0.000]
- avg_progress: -0.018 [-0.039, +0.000]
