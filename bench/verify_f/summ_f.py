import json,sys
for l in sys.argv[1:]:
    try: r=json.load(open("out/%s.json"%l))
    except Exception as e: print(l,"ERR",e); continue
    w1=r["W1_sender_only"]; w2=r["W2_load"]
    if not w1 or not w2.get("sender"): print(l,"sender fail",r.get("w1_err"),r.get("w2_err")); continue
    u=w1["update"]["rtt_ms"]; p=w1["preview"]["rtt_ms"]; u2=w2["sender"]["update"]["rtt_ms"]
    print(l,r["transport"],r["status_mode"],"| W1 upd p50/p95/max",u["p50"],u["p95"],u["max"],"prev p95",p["p95"],"proc",w1["server_processed_ratio"],"rx_hz",w1["server_rx_hz"],"err",w1["update"]["err"],w1["preview"]["err"],"| W2 upd p95",u2["p95"],"cpu main/tree",w2["cpu"]["main_pct"],w2["cpu"]["tree_pct"],"| idle",r["idle_cpu"]["main_pct"],r["idle_cpu"]["tree_pct"],"| status req/s",w2["poll_total_req_per_s"],"push",w2["push"]["msgs_per_s"],w2["push"]["bytes_per_s"],"| recv_pub p95",w2["sender"]["server_latency_ms_status"]["receive_publish"]["p95"] if w2["sender"].get("server_latency_ms_status") else None,"| load",r["load0"][0],r["load1_end"][0])
