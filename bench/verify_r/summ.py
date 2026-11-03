import json,glob,os
f=sorted(glob.glob('/home/user/work/robot_percept/bench/verify_r/hum_result_*.json'),key=os.path.getmtime)[-1]
d=json.load(open(f));print(f)
for k in ('robot_video','preview_relay','stream_posts','ik_time_ms','ik_pos_err_mm','limits','mirror_deg','waist_corr_signed','load_avg_before','load_avg_after'):print(k,d.get(k))
for k,v in d['status'].items():print(k,v)
print({k:v['r'] for k,v in d['finger_corr_GT_aux'].items()})