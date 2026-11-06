from pathlib import Path
p=Path('web/monowait.py');s=p.read_text().replace('        thread.join()\n','        thread.join(0)\n');p.write_text(s)
p=Path('bench/verify_w/crash_test.sh');s=p.read_text().replace("grep ':$PORT '", 'grep ":$PORT "');p.write_text(s)
