import re
env=open("out/recon/env.txt").read()
for n in (1,2,3):
    S=[l.strip().split(",") for l in open(f"out/recon/mon_r{n}/status.csv")]
    ok=[(float(mo),int(c),st) for w,mo,c,h,st,f in S if c not in("ERR","None","")]
    inc=[(a,b) for a,b in zip(ok,ok[1:]) if b[1]!=a[1]]
    # 최대 간격: 서버 재기동 경계(input_count 가 0으로 리셋)
    best=max(((b[0]-a[0],a,b) for a,b in zip(ok,ok[1:]) if b[1]<a[1] or b[0]-a[0]>1),key=lambda x:x[0])
    errs=[x for x in S if x[2]=="ERR"]
    em=[float(x[1]) for x in errs]
    last_inc_before=[a for a,b in zip(ok,ok[1:]) if b[1]>a[1] and b[0]<=em[0]][-1]
    first_after=[b for a,b in zip(ok,ok[1:]) if a[0]>=em[-1] and b[1]>a[1]][0]
    first_ok_after=[x for x in ok if x[0]>em[-1]][0]
    print(f"r{n}: 마지막 정상 입력→재기동 후 첫 응답 {first_ok_after[0]-last_inc_before[0]:.2f}s, 첫 응답 후 첫 입력 증가까지 {first_after[0]-first_ok_after[0]:.2f}s, 총 처리 중단 {first_after[0]-last_inc_before[0]:.2f}s; monitor 상태 ERR {len(errs)}샘플({em[-1]-em[0]+0.25:.1f}s); 재기동 후 상태 {first_ok_after[2]}; 재기동 후 입력 {ok[-1][1]}건")
