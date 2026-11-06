import json,numpy as np,sys
R=json.load(open("out/t2/all.json")); rng=np.random.default_rng(20261106)
def g(r,f):
    try: return f(r)
    except Exception: return None
M={"처리율(ratio)":lambda r:r["tracker"]["processed_input_ratio"]*100,"트래커 hz":lambda r:r["tracker"]["hz"],"손 검출률%":lambda r:r["tracker"]["hand_detection_rate"]*100,"자세 검출률%":lambda r:r["tracker"]["pose_detection_rate"]*100,
"neural p50":lambda r:r["tracker"]["stages_ms"]["neural"]["p50"],"neural p95":lambda r:r["tracker"]["stages_ms"]["neural"]["p95"],"post_ms p50":lambda r:r["tracker"]["post_ms_p50"],"post_ms p95":lambda r:r["tracker"]["post_ms_p95"],
"preview 전송수":lambda r:r["tracker"]["preview_sent"],"네트워크 오류":lambda r:r["tracker"]["network_errors"],"sent_updates":lambda r:r["tracker"]["sent_updates"],"source_frames_due":lambda r:r["tracker"]["source_frames_due"],"updates":lambda r:r["tracker"]["updates"],
"서버 수신Hz":lambda r:r["server"]["recv_hz"],"G1 fps":lambda r:r["server"]["g1_fps"],"G1 max gap":lambda r:r["server"]["g1_max_gap_ms"],"서버 CPU main%":lambda r:r["server"]["cpu_main_pct"],"서버 CPU tree%":lambda r:r["server"]["cpu_tree_pct"],
"Win 트래커 CPU %전체":lambda r:r["wincpu"]["proc_cpu_pct_of_total"],"Win 트래커 CPU %1코어":lambda r:r["wincpu"]["proc_cpu_pct_of_1core"],"Win 시스템 CPU 평균%":lambda r:r["wincpu"]["sys_cpu_mean_pct"]}
H=[r for r in R if r["transport"]=="http"]; W=[r for r in R if r["transport"]=="ws"]
out=["| 지표 | "+" | ".join(r["label"] for r in R)+" | 차이 ws-http 평균 | 95% CI (창 3쌍 부트스트랩) | 판정 |","|"+"-|"*(len(R)+4)]
for k,f in M.items():
    v=[g(r,f) for r in R]
    h=np.array([g(r,f) for r in H],float); w=np.array([g(r,f) for r in W],float)
    if np.isnan(h).any() or np.isnan(w).any(): out.append(f"| {k} | "+" | ".join(str(x) for x in v)+" | N/A | N/A | |"); continue
    d=w-h; bs=[d[rng.integers(0,3,3)].mean() for _ in range(20000)]; lo,hi=np.percentile(bs,[2.5,97.5])
    verdict="차이 입증 안 됨(0 포함)" if lo<=0<=hi else "0 불포함"
    out.append(f"| {k} | "+" | ".join(f"{x:.3f}" if isinstance(x,float) else str(x) for x in v)+f" | {d.mean():+.3f} | [{lo:+.3f}, {hi:+.3f}] | {verdict} |")
print("\n".join(out))
open("out/t2_summary.md","w").write("\n".join(out)+"\n")
