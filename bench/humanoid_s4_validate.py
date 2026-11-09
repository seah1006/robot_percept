"""GT 보조 수정판 순차12자세·복귀 및 OFF/ON 4패턴. 외부 measure 락 필요."""
from bench.humanoid_s4_function import main
from bench.humanoid_s4_async import main as dynamic
if __name__=='__main__':
    import subprocess,sys
    from pathlib import Path
    with Path('bench/humanoid_s4_out/round4/pytest_timing_retry.txt').open('w') as log:
        subprocess.run(['flock','-w','10','/tmp/rp_gpu.lock',sys.executable,'-m','pytest','-q','tests/test_shutdown.py::test_server_sigkill_during_startup_reaps_spawn_children'],stdout=log,stderr=subprocess.STDOUT,timeout=35)
    main()
    dynamic()