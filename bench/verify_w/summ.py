import json, sys
d = json.load(open(f'bench/verify_w/{sys.argv[1]}.json'))
print(d['off_status']); print(d['first_gap'])
print({k: (v['http'], v['state'], v['enabled']) for k, v in d['bad'].items()}, d['bad_after'], d['bad_json'], d['bad_after2'])
print(d['ready2'], d['latency'], d['load0'], d['load1'], d['concurrent'], d['final_off'])
