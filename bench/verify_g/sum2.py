import json, math, os, collections
D=os.path.expanduser("~/work/robot_percept/bench/verify_g/out")
a=json.load(open(f"{D}/openconn/all.json"))
for sig in ("SIGTERM","SIGINT"):
    r=[x for x in a if x["signal"]==sig]
    e=sorted(x["all_gone_s"] for x in r); p95=e[min(len(e)-1,math.ceil(.95*len(e))-1)]
    pe=sorted(x["parent_exit_s"] for x in r if x["parent_exit_s"] is not None)
    ends=collections.Counter((k,v["end"][:45]) for x in r for k,v in x["clients"].items())
    print(sig,"n",len(r),"children",sorted(set(x["children"] for x in r)),"left_sum",sum(x["left"] for x in r),"rc",sorted(set(x["parent_rc"] for x in r),key=str),"all_gone p50/p95/max",e[len(e)//2],p95,e[-1],"parent_exit max",pe[-1],"on_http",set(x["on_http"] for x in r))
    for k,v in sorted(ends.items()): print("   ",k,v)
    print("   missing clients:",sum(3-len(x["clients"]) for x in r), "client close lag max(s):",max(v["t"] for x in r for v in x["clients"].values()))
print("sender:",collections.Counter(x["sender_err_tail"][:90] for x in a))
for L in ("A","B"):
    r=json.load(open(f"{D}/abf/ABF_{L}.json")); g=r["g1_window"]
    print(L,"load0",r["load0"][0],"fps",g["fps_count"],g["frames"],"gap max/p95",g["max_gap_ms"],g["gap_p95_ms"],">200",g["gaps_gt200"],"cpu",r["cpu"],"proc",r["sender"].get("server_processed_ratio"),r["sender"].get("preview_processed_ratio"),"int_p95",r["server_latency_ms"]["receive_publish"]["p95"])
