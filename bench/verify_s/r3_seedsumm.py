import json
d = json.load(open('/home/user/work/robot_percept/bench/humanoid_s4_out/c6_seed_diagnose/result.json'))
print(type(d), list(d.keys())[:20] if isinstance(d, dict) else len(d))
def walk(x, path='', depth=0):
    if isinstance(x, dict):
        for k, v in x.items():
            if isinstance(v, (dict, list)) and depth < 3: walk(v, path + '/' + str(k), depth + 1)
            else: print(path + '/' + str(k), str(v)[:160])
    elif isinstance(x, list):
        print(path, 'list', len(x), str(x[0])[:300] if x else '')
walk(d)
