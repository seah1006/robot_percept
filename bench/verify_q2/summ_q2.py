import json,sys
for l in sys.argv[1:]:
    r=json.load(open(f"out/{l}.json")); s=r["sender"]; g=r["g1_window"]; u=s["update"]; p=s["preview"]
    print(l,r["load0"][0],"fps",g["fps_count"],"frames",g["frames"],"maxgap",g["max_gap_ms"],"gapp95",g["gap_p95_ms"],">200:",g["gaps_gt200"],
     "| intern p95",r["server_latency_ms"]["receive_publish"]["p95"],"| upd",u["rtt_ms"]["p50"],u["rtt_ms"]["p95"],"proc",s["server_processed_ratio"],"rx",s["server_rx_hz"],
     "| prev",p["rtt_ms"]["p50"],p["rtt_ms"]["p95"],"proc",s["preview_processed_ratio"],"| cpu",r["cpu"]["main_pct"],r["cpu"]["tree_pct"],"| jumps",r["walljump_count"],"| push/s",r["push"]["msgs_per_s"],"poll",{k:v["req_per_s"] for k,v in r["poll"].items()})
