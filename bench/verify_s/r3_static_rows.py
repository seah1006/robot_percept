import json, sys
d = json.load(open('/home/user/work/robot_percept/bench/verify_s/' + sys.argv[1]))
for r in d['static']['rows']:
    print('%-12s gap %6.1f | L u1 %5.2f u2 %5.2f w %5.2f | R u1 %5.2f u2 %5.2f w %5.2f' % (r['pose'], r['gap_mm'], r['left']['u1_deg'], r['left']['u2_deg'], r['left']['wrist_mm_actualS'], r['right']['u1_deg'], r['right']['u2_deg'], r['right']['wrist_mm_actualS']))
print(d.get('release'))
