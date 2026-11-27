"""에피소드 1개를 실행하면서 프레임을 모아 자막을 합성하고 mp4로 만든다 (데모 영상, 로그 뷰어 U1 재료).

m2a/run 코드는 수정하지 않는다. 훅 3개를 m2a/viz 안에서 감싼다:
  1) env.step 오버라이드: 시뮬 시간 interval마다 front/head/wrist 렌더를 캡처(물리는 그대로)
  2) runner_factory 프록시: 스킬 시작/종료 표시(현재 스킬 번호 k, phase)
  3) Perturbation 서브클래스: 교란 직전/직후 프레임을 따로 잡고 자막 배너를 단다
영상 인코딩은 m2a_lerobot env의 PyAV(libx264)를 subprocess로 호출(설치 없음). 없으면 PNG 시퀀스만 남긴다.

사용(repo 루트, env robot_percept + gl_env.sh):
  python -m m2a.viz.record_episode --name d1_L0_B1 --seed 10000 --level L0 --situation standard --config B1
  python -m m2a.viz.record_episode --name d3 --seed 10001 --level L0 --situation standard --config B4 \
      --perturb teleport:1
"""
from __future__ import annotations

import argparse
import io
import json
import math
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import captions as C

W, H = 1600, 900
FRONT = (10, 52, 1040, 780)       # x, y, w, h
HEAD = (1060, 52, 530, 398)
WRIST_L = (1060, 458, 260, 260)
WRIST_R = (1330, 458, 260, 260)
PANEL_XY = (1060, 726)
FONT_PATHS = ('/mnt/c/Windows/Fonts/malgun.ttf', '/mnt/c/Windows/Fonts/NanumGothic.ttf',
              '/usr/share/fonts/truetype/nanum/NanumGothic.ttf')
FONT_BOLD = ('/mnt/c/Windows/Fonts/malgunbd.ttf',) + FONT_PATHS
LERobot_PY = os.path.expanduser('~/miniforge3/envs/m2a_lerobot/bin/python')
DEFAULT_OUT = os.path.expanduser('~/m2a_data/demo')

# 임의 지정: 캡처 간격(시뮬 초)·영상 fps·최대 길이
DEFAULT_INTERVAL = 0.05
DEFAULT_FPS = 20
DEFAULT_MAX_S = 55.0


# ----------------------------------------------------------------- 캡처 훅
class Recorder:
    """프레임 수집기. env/runner/perturb 훅이 공유한다."""

    def __init__(self, interval=DEFAULT_INTERVAL):
        self.interval = interval
        self.k = 0
        self.phase = 'idle'
        self.banner = ''
        self.frames = []
        self.env = None
        self._next_t = 0.0
        self.on = True
        self.perturb_after = None   # 교란이 주입되는 스킬 번호
        self.perturbed = False

    def snapshot(self, hold=0.0, banner=None):
        from PIL import Image
        env = self.env
        if env is None or not self.on:
            return
        jp = {}
        for cam in ('front', 'head', 'wrist_l', 'wrist_r'):
            rgb = env.render(cam)[0]
            buf = io.BytesIO()
            Image.fromarray(rgb).save(buf, 'JPEG', quality=88)
            jp[cam] = buf.getvalue()
        pre = self.perturb_after == self.k and not self.perturbed and self.phase == 'idle'
        self.frames.append(dict(t=float(env.data.time), k=self.k, phase=self.phase, pre_perturb=pre,
                                banner=self.banner if banner is None else banner, hold=hold, jpg=jp))


def make_env_class(rec):
    from m2a.sim.g1_manip_env import G1ManipEnv

    class RecEnv(G1ManipEnv):
        def reset(self, spec):
            super().reset(spec)
            rec.env = self
            rec._next_t = 0.0
            rec.snapshot()
            rec._next_t = rec.interval

        def step(self, n=1):
            if rec.env is not self or not rec.on:
                return super().step(n)
            dt = self.model.opt.timestep
            while n > 0:
                need = max(1, math.ceil((rec._next_t - float(self.data.time)) / dt - 1e-9))
                chunk = min(n, need)
                super().step(chunk)
                n -= chunk
                if float(self.data.time) >= rec._next_t - 1e-9:
                    rec.snapshot()
                    rec._next_t += rec.interval
                    if rec._next_t < float(self.data.time):
                        rec._next_t = float(self.data.time) + rec.interval
    return RecEnv


class RunnerProxy:
    def __init__(self, rec, runner):
        self._rec, self._runner = rec, runner

    def run(self, skill, arm, oid=None, target=None, **kw):
        rec = self._rec
        rec.k += 1
        rec.phase = 'skill'
        rec.banner = ''
        rec.snapshot()
        try:
            return self._runner.run(skill, arm, oid, target, **kw)
        finally:
            rec.phase = 'idle'
            rec.snapshot()

    def __getattr__(self, name):
        return getattr(self._runner, name)


def make_perturbation(rec, kind, after_skill, parts_of, names, oid=None, region=None):
    from m2a.run.perturb import Perturbation

    @dataclass(frozen=True)
    class HookedPerturbation(Perturbation):
        def apply(self, env, obs, call, upcoming):
            rec.snapshot(hold=1.0, banner='')                      # 교란 직전
            info = super().apply(env, obs, call, upcoming)
            rec.perturbed = True
            text = C.perturb_text(info, parts_of, names)
            if text:
                rec.banner = text
            rec.snapshot(hold=2.0, banner=rec.banner)               # 교란 직후
            return info
    rec.perturb_after = after_skill
    return HookedPerturbation(kind=kind, after_skill=after_skill, oid=oid, region=region)


# ----------------------------------------------------------------- 합성
_fonts = {}


def font(size, bold=False):
    from PIL import ImageFont
    key = (size, bold)
    if key not in _fonts:
        for p in (FONT_BOLD if bold else FONT_PATHS):
            if os.path.exists(p):
                _fonts[key] = ImageFont.truetype(p, size)
                break
        else:
            _fonts[key] = ImageFont.load_default()
    return _fonts[key]


def _wrap(draw, text, fnt, width):
    lines, cur = [], ''
    for ch in text:
        if draw.textlength(cur + ch, font=fnt) > width and cur:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    return lines + [cur] if cur else lines


STATUS_STYLE = {'done': ('[완료] ', (120, 220, 140)), 'active': ('[진행] ', (255, 214, 90)),
                'failed': ('[실패] ', (255, 110, 110)), 'todo': ('[대기] ', (150, 155, 165))}


def compose(frame, cap, *, condition, speed, final=None, sim_t=0.0):
    """프레임 dict + 자막 dict -> PIL RGB 이미지(W x H)."""
    from PIL import Image, ImageDraw
    img = Image.new('RGB', (W, H), (18, 20, 26))
    for cam, (x, y, w, h) in (('front', FRONT), ('head', HEAD), ('wrist_l', WRIST_L), ('wrist_r', WRIST_R)):
        im = Image.open(io.BytesIO(frame['jpg'][cam])).convert('RGB').resize((w, h), Image.LANCZOS)
        img.paste(im, (x, y))
    d = ImageDraw.Draw(img, 'RGBA')
    d.text((12, 10), condition, font=font(22), fill=(235, 235, 240))
    tag = f'sim {sim_t:5.1f}s' + (f' · {speed:g}배속' if abs(speed - 1) > 0.05 else ' · 1배속')
    d.text((W - 12 - d.textlength(tag, font=font(22)), 10), tag, font=font(22), fill=(190, 195, 205))
    for label, (x, y, w, h) in (('front 카메라', FRONT), ('head 카메라', HEAD), ('왼손목', WRIST_L), ('오른손목', WRIST_R)):
        d.rectangle((x, y, x + d.textlength(label, font=font(16)) + 12, y + 22), fill=(0, 0, 0, 150))
        d.text((x + 6, y + 2), label, font=font(16), fill=(255, 255, 255))
        d.rectangle((x, y, x + w - 1, y + h - 1), outline=(70, 75, 90))
    # 자막(front 하단)
    x0, y0, fw, fh = FRONT
    rows = [(f'지시: {cap["instr"]}', (255, 255, 255)),
            (cap['step'], (255, 224, 120))]
    res_text = final[0] if final else cap['result']
    res_col = (255, 255, 255)
    if final:
        res_col = (130, 235, 150) if final[1] else (255, 120, 120)
    elif '성공' in cap['result']:
        res_col = (130, 235, 150)
    elif '실패' in cap['result']:
        res_col = (255, 120, 120)
    if res_text:
        rows.append((res_text, res_col))
    if cap['replan'] and not final:
        rows.append((cap['replan'], (120, 210, 255)))
    if cap['banner']:
        rows.append((cap['banner'], (255, 170, 80)))
    fnt = font(23, True)
    lines = []
    for text, col in rows:
        for part in _wrap(d, text, fnt, fw - 28):
            lines.append((part, col))
    lh = 31
    bh = lh * len(lines) + 14
    d.rectangle((x0, y0 + fh - bh, x0 + fw, y0 + fh), fill=(0, 0, 0, 175))
    for i, (text, col) in enumerate(lines):
        d.text((x0 + 14, y0 + fh - bh + 7 + i * lh), text, font=fnt, fill=col)
    # 계획 패널
    px, py = PANEL_XY
    title = f'작업 계획 #{cap["plan_no"]}' if cap['plan_no'] else '작업 계획'
    d.text((px, py), title, font=font(19, True), fill=(235, 235, 240))
    fnt2 = font(17)
    for i, (text, status) in enumerate(cap['panel'][:7]):
        mark, col = STATUS_STYLE[status]
        d.text((px, py + 28 + i * 20), mark + text, font=fnt2, fill=col)
    return img


# ----------------------------------------------------------------- 실행/출력
def parse_perturb(text):
    if not text:
        return None
    kind, _, after = text.partition(':')
    return dict(kind=kind, after_skill=int(after or 1))


def goal_sentence(goal):
    """기대 목표와 같은 목표로 해석되는 자연어 지시(없으면 None). 계약 §4 파서 문법."""
    from m2a.plan import parser_ko
    steps = [int(t[1:]) for grp in goal.get('step_order', []) for t in grp]
    if not steps:
        return None
    steps = sorted(steps)
    if steps == list(range(steps[0], steps[-1] + 1)):
        text = f'{steps[0]}단계 준비해' if len(steps) == 1 else f'{steps[0]}~{steps[-1]}단계 준비해'
    else:
        text = ', '.join(f'{s}단계' for s in steps) + ' 준비해'
    got = parser_ko.parse(text)
    keys = ('trays', 'step_order', 'allowed_arms', 'unusable_trays', 'excluded_parts')
    if got.get('ok') is not False and all(got.get(k) == goal.get(k) for k in keys):
        return text
    return None


def record(name, seed, level, situation, config, perturb=None, *, split='dev', R=3, out_dir=DEFAULT_OUT,
           interval=DEFAULT_INTERVAL, fps=DEFAULT_FPS, max_s=DEFAULT_MAX_S, observation='O0', keep_frames=False):
    if split != 'dev':
        raise SystemExit('데모는 dev seed만 사용한다 (test 금지)')
    from m2a.common import load_layout, load_parts
    from m2a.run.episode import run_episode
    from m2a.scene.generator import generate
    from m2a.sim.skills import SkillRunner

    layout = load_layout()
    spec = generate(seed, level, situation, split, layout=layout)
    parts = load_parts(spec['product'])
    names = {pid: p['name_ko'] for pid, p in parts['parts'].items()}
    parts_of = {o['oid']: o['part_id'] for o in spec['objects']}
    instr = goal_sentence(spec['expected']['goal'])

    rec = Recorder(interval)
    env = make_env_class(rec)(layout)
    pert = None
    if perturb:
        pert = make_perturbation(rec, perturb['kind'], perturb['after_skill'], parts_of, names,
                                 perturb.get('oid'), perturb.get('region'))
    try:
        result = run_episode(seed, split, level, situation, config, instr=instr, R=R, perturb=pert, env=env,
                             runner_factory=lambda e, grasp_mode: RunnerProxy(rec, SkillRunner(e, grasp_mode=grasp_mode)),
                             layout=layout)
        rec.phase = 'idle'
        rec.snapshot(hold=3.0)
    finally:
        rec.on = False
        env.close()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    logs = result['logs']
    if rec.k != len(logs['episodes']):
        print(f'경고: 스킬 호출 {rec.k} != 에피소드 로그 {len(logs["episodes"])} (handover 등)', file=sys.stderr)
    meta = dict(name=name, seed=seed, level=level, situation=situation, config=config, perturb=perturb,
                instr=instr, sim_seconds=round(rec.frames[-1]['t'], 1) if rec.frames else 0,
                success=result['judge']['success'], fail_code=result['fail_code'], replans=result['replans'],
                num_skills=result['num_skills'], termination=result['termination'], n_frames_raw=len(rec.frames),
                condition=C.condition_line(observation))
    return result, rec, meta, names, parts_of, instr


def render_video(result, rec, meta, names, parts_of, instr, out_dir=DEFAULT_OUT, fps=DEFAULT_FPS,
                 max_s=DEFAULT_MAX_S, keep_frames=False):
    out = Path(out_dir)
    name = meta['name']
    logs, goal = result['logs'], result['goal']
    regular = [f for f in rec.frames if not f['hold']]
    holds = [f for f in rec.frames if f['hold']]
    hold_s = sum(f['hold'] for f in holds)
    budget = max(1.0, max_s - hold_s) * fps
    stride = max(1, math.ceil(len(regular) / budget))
    speed = rec.interval * stride * fps
    seq = []
    for f in rec.frames:
        if f['hold']:
            seq.extend([(f, False)] * int(round(f['hold'] * fps)))
        else:
            seq.append((f, True))
    # stride 적용(보류 프레임은 유지)
    kept, counter = [], 0
    for f, is_reg in seq:
        if is_reg:
            counter += 1
            if (counter - 1) % stride:
                continue
        kept.append(f)
    last = rec.frames[-1]
    final = (C.final_caption(result), result['judge']['success'])
    tmp = Path(tempfile.mkdtemp(prefix=f'rec_{name}_', dir=os.environ.get('M2A_VIZ_TMP')))
    rep = {}
    banner_seen = None
    for i, f in enumerate(kept):
        is_final = f is last
        cap = C.frame_caption(dict(k=f['k'], phase=f['phase'], pre_perturb=f.get('pre_perturb')), logs, parts_of, names, goal, instr, f['banner'])
        img = compose(f, cap, condition=meta['condition'], speed=speed,
                      final=final if is_final else None, sim_t=f['t'])
        img.save(tmp / f'{i:05d}.jpg', quality=92)
        if i == 0:
            rep['start'] = img
        if f['phase'] == 'skill' and 'mid' not in rep and cap['panel'] and f['k'] >= 2:
            rep['mid'] = img
        if f['banner'] and banner_seen is None:
            banner_seen = img
            rep['perturb'] = img
        if cap['replan'].startswith('관측 → 재계획') and 'replan' not in rep:
            rep['replan'] = img
        if is_final:
            rep['final'] = img
        # 마지막 hold 프레임은 모두 같은 내용이므로 첫 한 장만 대표로 사용
    mp4 = out / f'{name}.mp4'
    for key, im in rep.items():
        im.save(out / f'{name}_{key}.png')
    ok = encode_mp4(tmp, mp4, fps)
    meta.update(video=str(mp4) if ok else None, video_seconds=round(len(kept) / fps, 1), speed=round(speed, 2),
                fps=fps, stride=stride, rep_frames=[f'{name}_{k}.png' for k in rep])
    (out / f'{name}.json').write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding='utf-8')
    if keep_frames or not ok:
        dst = out / f'{name}_frames'
        dst.mkdir(exist_ok=True)
        for p in tmp.glob('*.jpg'):
            p.replace(dst / p.name)
    else:
        for p in tmp.glob('*.jpg'):
            p.unlink()
    try:
        tmp.rmdir()
    except OSError:
        pass
    return meta


def encode_mp4(frame_dir, mp4, fps):
    script = Path(__file__).with_name('encode_av.py')
    if not os.path.exists(LERobot_PY):
        return False
    r = subprocess.run(['nice', '-n', '10', LERobot_PY, str(script), str(frame_dir), str(mp4), str(fps)],
                       capture_output=True, text=True)
    if r.returncode:
        print('인코딩 실패:', r.stderr[-400:], file=sys.stderr)
        return False
    return True


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', required=True)
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--level', required=True)
    ap.add_argument('--situation', required=True)
    ap.add_argument('--config', required=True)
    ap.add_argument('--perturb', default=None, help='teleport:1 | drop:2 (kind:after_skill)')
    ap.add_argument('--out', default=DEFAULT_OUT)
    ap.add_argument('--interval', type=float, default=DEFAULT_INTERVAL)
    ap.add_argument('--fps', type=int, default=DEFAULT_FPS)
    ap.add_argument('--max-s', type=float, default=DEFAULT_MAX_S)
    ap.add_argument('--keep-frames', action='store_true')
    ap.add_argument('--observation', default='O0')
    a = ap.parse_args(argv)
    result, rec, meta, names, parts_of, instr = record(
        a.name, a.seed, a.level, a.situation, a.config, parse_perturb(a.perturb), out_dir=a.out,
        interval=a.interval, fps=a.fps, max_s=a.max_s, observation=a.observation)
    meta = render_video(result, rec, meta, names, parts_of, instr, a.out, a.fps, a.max_s, a.keep_frames)
    print(json.dumps(meta, ensure_ascii=False))


if __name__ == '__main__':
    main()
