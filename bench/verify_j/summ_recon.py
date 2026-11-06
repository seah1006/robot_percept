import json, re
O = "out/recon/"; W = "/mnt/c/Users/my/rp_tracker/out_vj/recon/"
env = open(O + "env.txt").read()
for n in (1, 2, 3):
    try: m = json.load(open(W + f"r{n}.metrics.json", encoding="utf-8-sig"))
    except Exception as e: print(f"r{n}: no metrics", e); continue
    t = re.search(rf"r{n} sigterm=([\d.]+) exited=([\d.]+)", env); u = re.search(rf"r{n} restart_cmd=([\d.]+) up=([\d.]+)", env)
    S = [l.strip().split(",") for l in open(O + f"mon_r{n}/status.csv")]
    S = [(float(w), float(mo), c) for w, mo, c, *r in S]
    err = [x for x in S if x[2] in ("ERR", "None", "")]
    ok = [(w, mo, int(c)) for w, mo, c in S if c not in ("ERR", "None", "")]
    sig = float(t.group(1)); upc = float(u.group(1)); up = float(u.group(2))
    post = [x for x in ok if x[0] > up - 1]
    first = None
    for a, b in zip(post, post[1:]):
        if b[2] > a[2] and b[2] > 0: first = b; break
    pre = [x for x in ok if x[0] < sig]
    lastpre = [b for a, b in zip(pre, pre[1:]) if b[2] > a[2]][-1] if pre else None
    print(f"r{n}: transport={m['transport']} fallback={m.get('transport_fallback','n/a')} updates={m['updates']}/{m['source_frames_due']} ratio={m['processed_input_ratio']*100:.2f}% hz={m['hz']} sent={m['sent_updates']} net_errors={m['network_errors']} post_p95={m['post_ms_p95']:.1f}")
    print(f"   서버 SIGTERM 후 종료 {float(t.group(2))-sig:.2f}s, 10초 대기 후 재기동 완료까지 {up-upc:.2f}s (SIGTERM 대비 서버 다운 총 {up-sig:.2f}s)")
    if first and lastpre: print(f"   마지막 입력(kill 전) {lastpre[0]-sig:+.2f}s, 재기동 후 첫 입력 증가 {first[0]-sig:+.2f}s -> 서버 up 후 {first[0]-up:+.2f}s, 처리 끊김 총 {first[0]-lastpre[0]:.2f}s")
    else: print("   재개 감지 실패", bool(first), bool(lastpre))
    print("   마지막 input_count:", ok[-1][2], " monitor ERR 샘플:", len(err))
