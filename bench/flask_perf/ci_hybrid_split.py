import json,random,statistics
D='bench/verify_f/out';rng=random.Random(11)
pairs=[];f2pairs=[]
for i in (1,2,3):
 h=json.load(open(f'{D}/H_Bhttp{i}.json'));p=json.load(open(f'{D}/H_Bwspoll{i}.json'));s=json.load(open(f'{D}/H_Bwspush{i}.json'));pairs.append((p,s));f2pairs.append((h,p))
def boot(vals):
 b=sorted(statistics.mean(rng.choice(vals) for _ in vals) for _ in range(5000));return {'diff':round(statistics.mean(vals),3),'ci95':[round(b[124],3),round(b[4874],3)],'pairs':[round(x,3) for x in vals]}
out={
 'F2_update_p95_ws_minus_http':boot([p['W1_sender_only']['update']['rtt_ms']['p95']-h['W1_sender_only']['update']['rtt_ms']['p95'] for h,p in f2pairs]),
 'F2_preview_p95_hybrid_minus_http':boot([p['W1_sender_only']['preview']['rtt_ms']['p95']-h['W1_sender_only']['preview']['rtt_ms']['p95'] for h,p in f2pairs]),
 'F2_main_cpu_ws_minus_http':boot([p['W2_load']['cpu']['main_pct']-h['W2_load']['cpu']['main_pct'] for h,p in f2pairs]),
 'F3_main_cpu_push_minus_poll':boot([s['W2_load']['cpu']['main_pct']-p['W2_load']['cpu']['main_pct'] for p,s in pairs]),
 'F3_tree_cpu_push_minus_poll':boot([s['W2_load']['cpu']['tree_pct']-p['W2_load']['cpu']['tree_pct'] for p,s in pairs]),
 'F3_requests_or_messages_rate':boot([s['W2_load']['push']['msgs_per_s']-p['W2_load']['poll_total_req_per_s'] for p,s in pairs]),
}
print(json.dumps(out,indent=2))
