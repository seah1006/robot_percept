"""DINOv2-S embedder in a separate process (rocm env, CPU by default) so the EGL render process and the model stay apart.

Client: SubprocessEmbedder()(images) -> float32 [N, D]. Protocol: length-prefixed pickles on stdin/stdout.
"""
import os
import pickle
import struct
import subprocess
import sys

PYTHON = os.path.expanduser('~/miniforge3/envs/robot_percept_rocm/bin/python')


def _read(stream):
    head = stream.read(8)
    if len(head) < 8:
        return None
    return pickle.loads(stream.read(struct.unpack('<Q', head)[0]))


def _write(stream, obj):
    data = pickle.dumps(obj, protocol=4)
    stream.write(struct.pack('<Q', len(data)) + data)
    stream.flush()


def serve(device='cpu'):
    out = os.fdopen(os.dup(1), 'wb')
    os.dup2(2, 1)  # library prints must not corrupt the protocol stream
    from m2a.percept.models import DinoSmall
    model = DinoSmall(device)
    _write(out, 'ready')
    inp = sys.stdin.buffer
    while (images := _read(inp)) is not None:
        _write(out, model(images))


class SubprocessEmbedder:
    def __init__(self, device='cpu', root=None, threads=2):
        root = root or os.getcwd()
        env = dict(os.environ, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PYTHONPATH=root,
                   LD_LIBRARY_PATH=os.path.dirname(os.path.dirname(PYTHON))+'/lib', OMP_NUM_THREADS=str(threads))
        env.pop('MUJOCO_GL', None)
        self.proc = subprocess.Popen([PYTHON, '-m', 'm2a.run.embed_server', device], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, env=env, cwd=root)
        if _read(self.proc.stdout) != 'ready':
            raise RuntimeError('embedder failed to start')

    def __call__(self, images):
        import numpy as np
        _write(self.proc.stdin, [np.ascontiguousarray(i) for i in images])
        return _read(self.proc.stdout)

    def close(self):
        if self.proc.poll() is None:
            self.proc.stdin.close()
            self.proc.wait(timeout=10)


if __name__ == '__main__':
    serve(sys.argv[1] if len(sys.argv) > 1 else 'cpu')
