"""JPEG/PNG 시퀀스 -> H.264 mp4. m2a_lerobot env의 PyAV(libx264)로 실행한다(설치 없음).

사용: ~/miniforge3/envs/m2a_lerobot/bin/python encode_av.py <프레임 폴더> <out.mp4> <fps>
"""
import sys
from pathlib import Path

import av
import numpy as np
from PIL import Image


def main(frame_dir, out, fps):
    files = sorted(p for p in Path(frame_dir).iterdir() if p.suffix.lower() in ('.jpg', '.jpeg', '.png'))
    if not files:
        raise SystemExit('프레임 없음')
    w, h = Image.open(files[0]).size
    w, h = w - w % 2, h - h % 2
    container = av.open(str(out), 'w')
    stream = container.add_stream('libx264', rate=fps)
    stream.width, stream.height, stream.pix_fmt = w, h, 'yuv420p'
    stream.thread_count = 2  # CPU 사용 제한(임의 지정)
    stream.options = {'crf': '21', 'preset': 'medium'}
    for p in files:
        arr = np.asarray(Image.open(p).convert('RGB'))[:h, :w]
        for packet in stream.encode(av.VideoFrame.from_ndarray(arr, format='rgb24')):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]))
