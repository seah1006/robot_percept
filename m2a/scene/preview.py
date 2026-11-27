"""Render a top-down PNG for inspecting placement without a simulator."""
import argparse
import json
from pathlib import Path

from m2a.common import load_layout, load_parts
from ._geometry import corners, inset, obb, size_xyz, tray_box, tray_rect


def preview(spec, output, layout=None, parts=None):
    from PIL import Image, ImageDraw, ImageFont

    layout = load_layout() if layout is None else layout
    parts = load_parts(spec['product']) if parts is None else parts
    parts = parts.get('parts', parts)
    w, h = layout['table']['size_xy']
    px = 740 / max(w, h)
    width, height = int(h*px) + 60, int(w*px) + 125
    image = Image.new('RGB', (width, height), '#f5f6f8')
    draw = ImageDraw.Draw(image)
    title, label, small = (ImageFont.load_default(size=n) for n in (22, 15, 12))
    def point(x, y):
        return width/2-y*px, 58 + (w/2-x)*px
    def bounds(rect):
        x, X, y, Y = rect
        return *point(X, Y), *point(x, y)
    color = tuple(round(c*255) for c in spec['render']['table_rgb'])
    draw.rectangle(bounds((-w/2,w/2,-h/2,h/2)), fill=color, outline='#252d37', width=2)
    draw.text((30, 18), f"M2A / {spec['level']} / {spec['situation']} / seed {spec['seed']}", fill='#252d37', font=title)
    for name, rect in layout['regions'].items():
        draw.rectangle(bounds(rect), outline='#f1ebd9', width=2)
        u, v = bounds(rect)[:2]
        draw.text((u+5,v+4), name, fill='white', font=small, stroke_width=1, stroke_fill='#473920')
    for name, tray in layout['trays'].items():
        rect = tray_rect(tray)
        draw.polygon([point(*xy) for xy in corners(tray_box(tray))], fill="#476780")
        draw.rectangle(bounds(rect), fill='#edf4f8', outline='#476780', width=3)
        draw.rectangle(bounds(inset(rect, layout['judge']['tray_margin'])), outline='#7c9baf')
        u, v = bounds(rect)[:2]
        draw.text((u+5,v+4), name, fill='#203851', font=small)
    for obj in sorted(spec['objects'], key=lambda row: row['xyz'][2] - size_xyz(parts[row['part_id']])[2]/2):
        pid, (x, y, _) = obj['part_id'], obj['xyz']
        part = parts[pid]
        color = tuple(round(c*255) for c in part['rgb'])
        if part['shape'] == 'cylinder':
            r = part['size'][0]
            draw.ellipse(bounds((x-r,x+r,y-r,y+r)), fill=color, outline='#22313e', width=2)
        else:
            poly = [point(*xy) for xy in corners(obb((x,y), size_xyz(part), obj['yaw']))]
            draw.polygon(poly, fill=color, outline='#22313e', width=2)
    by_id = {obj['oid']: obj for obj in spec['objects']}
    supporting = {obj['on'] for obj in spec['objects'] if obj['on']}
    # Keep stack base and top legible even when their centers coincide.
    labels = []
    for obj in spec['objects']:
        if obj['oid'] in supporting:
            continue
        text = f"{obj['oid']}:{obj['part_id']}"
        if obj['on']:
            base = by_id[obj['on']]
            text += f" on {base['oid']}:{base['part_id']}"
        labels.append((point(*obj['xyz'][:2]), text))
    placed_labels = []
    for (u, v), text in sorted(labels, key=lambda row: row[0][1]):
        tw = draw.textlength(text, font=small) + 6
        x = min(max(u-tw/2, 5), width-tw-5)
        for off in (0, -18, 18, -36, 36, -54, 54):
            y = v-8+off
            if not any(x < X and x+tw > a and y < Y and y+16 > b for a,b,X,Y in placed_labels):
                break
        if off:
            draw.line((u,v,x+tw/2,y+8), fill='#22313e', width=1)
        draw.rounded_rectangle((x,y,x+tw,y+16), radius=3, fill='#1b2636')
        draw.text((x+3,y+1), text, fill='white', font=small)
        placed_labels.append((x,y,x+tw,y+16))
    missing = spec['expected']['missing']
    draw.text((30,height-52), f"+x up, +y left   /   goal steps: {spec['goal_steps']}   /   missing: {missing or 'none'}",
              fill='#252d37', font=label)
    image.save(output, format='PNG')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('spec', type=Path, help='one JSON scene file')
    parser.add_argument('output', type=Path)
    args = parser.parse_args(argv)
    preview(json.loads(args.spec.read_text(encoding='utf-8')), args.output)


if __name__ == '__main__':
    main()
