import json,glob,numpy as np
W="/mnt/c/Users/my/rp_tracker/out_vj/long/"; O="out/long/"
rows=[]
env=open(O+"env.txt").read()
for i in range(1,5):
    m=json.load(open(W+f"seg{i}.metrics.json",encoding="utf-8-sig"))
    rows.append(m)
    print(f"seg{i}: transport={m['transport']} ratio={m['processed_input_ratio']*100:.3f}% updates={m['updates']}/{m['source_frames_due']} hz={m['hz']} sent={m['sent_updates']} post_p50={m['post_ms_p50']:.2f} p95={m['post_ms_p95']:.2f} err={m['network_errors']} hand={m['hand_detection_rate']*100:.2f} neural_p95={m['stages_ms']['neural']['p95']:.1f} sec={m['seconds']}")
# 서버 수신 Hz per segment: status.csv, segments by env done times
import re
done=[float(x) for x in re.findall(r"seg\d done \S+ rc=0 t=([\d.]+)",env)]
S=[l.strip().split(",") for l in open(O+"mon/status.csv")]
S=[(float(a),b,c) for a,_,b,c,*r in S if b not in("ERR","None")]
# 각 세그먼트: 완료시각-300 ~ 완료시각 안에서 input_count 증가분
prev=0;
for i,d in enumerate(done,1):
    w=[(t,int(c)) for t,c,_ in S if d-295<=t<=d]
    ch=[x for x in w if x[1]>w[0][1]]
    a0=ch[0]; a1=next(x for x in w if x[1]==w[-1][1])
    print(f"seg{i} server recv: {(a1[1]-a0[1])/(a1[0]-a0[0]):.3f} Hz span {a1[0]-a0[0]:.1f}s count {a1[1]-a0[1]}")
print("minute log:")
M=[json.loads(l) for l in open(O+"mon/minute.jsonl")]
for k,r in enumerate(M,1): print(k,{x:r.get(x) for x in("g1_fps_last_min","threads_main","fd_main","rss_main_mb","rss_tree_mb","threads_tree","fd_tree","procs_tree")}, r["load"][0])
for key in("rss_main_mb","rss_tree_mb","threads_tree","fd_tree","threads_main","fd_main"):
    y=np.array([r[key] for r in M],float); x=np.arange(len(y)); print(key,"slope/min=%.3f"%np.polyfit(x,y,1)[0],"first",y[0],"last",y[-1],"min",y.min(),"max",y.max())
