import json,random,statistics
p='bench/flask_perf/out/quick_ab.json';rows=json.load(open(p));rng=random.Random(7)
def ci(d):
 b=[statistics.mean(rng.choice(d) for _ in d) for _ in range(2000)];b.sort();return [round(statistics.mean(d),3),round(b[49],3),round(b[1949],3)]
http=[rows[0],rows[2]];hy=[rows[1],rows[3]]
out={}
for key in ('update','preview'):out[key+'_p95_hybrid_minus_http']=ci([hy[i][key]['p95']-http[i][key]['p95'] for i in range(2)])
poll=[rows[4],rows[6]];push=[rows[5],rows[7]]
out['status_cpu_push_minus_poll']=ci([push[i]['server_main_cpu_pct']-poll[i]['server_main_cpu_pct'] for i in range(2)])
print(json.dumps(out,indent=2))
