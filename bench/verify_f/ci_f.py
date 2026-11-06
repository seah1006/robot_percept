"""A/B 쌍별 차이(B-A)의 부트스트랩 95% CI (쌍 재표본 2000회, seed 1). 사용: ci_f.py  (라벨 규칙 F2_A{i}, F2_Bhttp{i}, F2_Bws{i}, G_A/G_B, F2g1_Bws)"""
import json, random, statistics
random.seed(1)
L = lambda l: json.load(open("out/%s.json" % l))
def boot(d):
    m = [statistics.mean(random.choices(d, k=len(d))) for _ in range(2000)]; m.sort(); return round(statistics.mean(d), 2), round(m[49], 2), round(m[1949], 2)
def row(name, A, B, f):
    a = [f(L(x)) for x in A]; b = [f(L(x)) for x in B]; d = [y - x for x, y in zip(a, b)]; mean, lo, hi = boot(d)
    print("%-44s A=%s B=%s diff=%+.2f CI[%+.2f,%+.2f] %s" % (name, [round(x, 2) for x in a], [round(x, 2) for x in b], mean, lo, hi, "0 포함: 차이 입증 안 됨" if lo <= 0 <= hi else ("B 증가(입증)" if lo > 0 else "B 감소(입증)")))
import sys
P = sys.argv[1] if len(sys.argv) > 1 else "F2"
if P in ("H", "J"):
    A = [P + "_A%d" % i for i in (1, 2, 3)]; BH = [P + "_Bhttp%d" % i for i in (1, 2, 3)]; BWP = [P + "_Bwspoll%d" % i for i in (1, 2, 3)]; BW = [P + "_Bwspush%d" % i for i in (1, 2, 3)]
else:
    A = ["F2_A%d" % i for i in range(1, 5)]; BH = ["F2_Bhttp%d" % i for i in range(1, 5)]; BW = ["F2_Bws%d" % i for i in range(1, 5)]; BWP = []
for tag, B in [("Bhttp(폴백)", BH)] + ([("Bws+poll (F2만)", BWP)] if BWP else []) + [("Bws+push", BW)]:
    print("== A vs", tag, "(n=4 쌍, 쌍별 차이)")
    row("W1 update RTT p95 ms", A, B, lambda r: r["W1_sender_only"]["update"]["rtt_ms"]["p95"])
    row("W1 update RTT p50 ms", A, B, lambda r: r["W1_sender_only"]["update"]["rtt_ms"]["p50"])
    row("W1 preview RTT p95 ms", A, B, lambda r: r["W1_sender_only"]["preview"]["rtt_ms"]["p95"])
    row("W1 preview 처리 수(30초)", A, B, lambda r: r["W1_sender_only"]["preview_count_delta"])
    row("W1 update 처리율", A, B, lambda r: r["W1_sender_only"]["server_processed_ratio"])
    row("W2 update RTT p95 ms", A, B, lambda r: r["W2_load"]["sender"]["update"]["rtt_ms"]["p95"])
    row("W2 서버 main CPU %", A, B, lambda r: r["W2_load"]["cpu"]["main_pct"])
    row("W2 서버 트리 CPU %", A, B, lambda r: r["W2_load"]["cpu"]["tree_pct"])
    row("유휴 main CPU %", A, B, lambda r: r["idle_cpu"]["main_pct"])
    row("내장 receive->publish p95 ms (W2)", A, B, lambda r: r["W2_load"]["sender"]["server_latency_ms_status"]["receive_publish"]["p95"])
    row("상태 요청 req/s (W2)", A, B, lambda r: r["W2_load"]["poll_total_req_per_s"] + r["W2_load"]["push"]["msgs_per_s"])
    if tag.startswith("Bhttp") or "poll" in tag:
        for p in ("/humanoid/status", "/teleop/status", "/status"): row("상태 응답 p95 " + p, A, B, lambda r, p=p: r["W2_load"]["poll"][p]["p95_ms"])
if P != "H":
  pass
if P in ("H", "J"): raise SystemExit
GA = ["F0_g1_r1", "F0_g1_r2", "G_A1", "G_A2"]; GB = ["G_B1", "G_B2"]
print("== G1 창: A(HTTP, n=4 창: F0 r1,r2 + G_A1,A2) vs B(HTTP 폴백 G_B1,B2) / B(WS F2g1_Bws1,2)")
for nm, B in (("Bhttp", GB), ("Bws", ["F2g1_Bws1", "F2g1_Bws2"])):
    for key, f in (("fps_count", lambda r: r["window"]["fps_count"]), ("max_gap_ms", lambda r: r["window"]["max_gap_ms"]), ("proxy p95", lambda r: r["window"]["proxy_post_to_next_frame_ms"]["p95"]), ("내장 p95", lambda r: r["server_latency_ms"]["receive_publish"]["p95"])):
        a = [f(L(x)) for x in GA]; b = [f(L(x)) for x in B]
        d = [y - x for x in a for y in b]; mean, lo, hi = boot(d)
        print("%-8s %-12s A=%s B=%s diff=%+.2f CI[%+.2f,%+.2f] %s" % (nm, key, a, b, mean, lo, hi, "0 포함" if lo <= 0 <= hi else "차이 있음"))
