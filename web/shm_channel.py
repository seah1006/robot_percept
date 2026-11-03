"""Single-writer shared-memory byte blob with a seqlock header (no Manager IPC).

Layout: [seq u64][len u32][pad u32][payload ...].  seq is odd while the writer is
copying; readers retry until they observe the same even seq before and after.
"""
from __future__ import annotations
import struct, time, uuid
from multiprocessing import shared_memory

HDR = 16


class Blob:
    def __init__(self, name=None, size=1 << 16, create=False):
        if create and name is None:
            name = 'rp_humanoid_' + uuid.uuid4().hex[:16]
        self.shm = shared_memory.SharedMemory(name=name, create=create, size=size if create else 0)
        self.buf = self.shm.buf; self.size = self.shm.size; self.name = self.shm.name
        if create:
            struct.pack_into('<QI', self.buf, 0, 0, 0)

    def write(self, data: bytes):
        n = len(data)
        if n > self.size - HDR:
            raise ValueError(f'blob payload {n} > {self.size - HDR}')
        seq = struct.unpack_from('<Q', self.buf, 0)[0]
        if seq & 1: seq += 1
        struct.pack_into('<Q', self.buf, 0, seq + 1)
        self.buf[HDR:HDR + n] = data
        struct.pack_into('<QI', self.buf, 0, seq + 2, n)
        return seq + 2

    def seq(self):
        return struct.unpack_from('<Q', self.buf, 0)[0]

    def read(self, last_seq=None):
        """Return (seq, bytes|None).  None if unchanged since last_seq or torn 5x."""
        for _ in range(8):
            s1, n = struct.unpack_from('<QI', self.buf, 0)
            if last_seq is not None and s1 == last_seq:
                return s1, None
            if s1 & 1 or s1 == 0:
                if s1 == 0: return 0, None
                time.sleep(0); continue
            data = bytes(self.buf[HDR:HDR + n])
            if struct.unpack_from('<Q', self.buf, 0)[0] == s1:
                return s1, data
        return last_seq, None

    def close(self, unlink=False):
        try:
            self.buf = None; self.shm.close()
        except Exception:
            pass
        if unlink:
            try: self.shm.unlink()
            except FileNotFoundError: pass
