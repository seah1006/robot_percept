import json
for l in ("W3_r1","W3_r2","W3_r3"):
    r=json.load(open(f"out/{l}.json")); g=r["g1_window"]; s=r["sender"]
    print(l,r["load0"][0],"fps",g["fps_count"],g["frames"],"gap",g["max_gap_ms"],g["gap_p95_ms"],g["gaps_gt200"],"proxy_send",r["proxy_ws_send_complete_to_next_frame_ms"],"proxy_recv",r["proxy_ws_reply_recv_to_next_frame_ms"],"int",r["server_latency_ms"]["receive_publish"]["p95"],"upd",s["update"]["rtt_ms"]["p50"],s["update"]["rtt_ms"]["p95"],"prev",s["preview"]["rtt_ms"]["p50"],s["preview"]["rtt_ms"]["p95"],"proc",s["server_processed_ratio"],s["preview_processed_ratio"],"cpu",r["cpu"]["main_pct"],r["cpu"]["tree_pct"],"jumps",r["walljump_count"],"push",r["push"]["msgs_per_s"])
