import json, sys
tag = sys.argv[1]
for pat in sys.argv[2:]:
    d = json.load(open('/home/user/work/robot_percept/bench/verify_s/out_%s_%s.json' % (tag, pat)))
    for o in ('0', '1'):
        c = d['coll_' + o]
        print(pat, 'avoid=' + o, 'min_mm', c['min_mm'], '<0:', c['frames_below_0mm'], '<5:', c['frames_below_5mm'], 'video', d.get('coll_video_' + o), 'tick', d.get('coll_tick_' + o), 'load0', d['load0'], 'load1', d.get('load1'))
