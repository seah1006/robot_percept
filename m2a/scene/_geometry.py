"""Table-frame geometry; cylinder bounding boxes are conservative."""
from math import cos, sin


def size_xyz(part):
    if part['shape'] == 'cylinder':
        radius, height = part['size']
        return 2 * radius, 2 * radius, height
    return tuple(part['size'])


def obb(xy, size, yaw=0.):
    return xy[0], xy[1], size[0]/2, size[1]/2, cos(yaw), sin(yaw)


def corners(box):
    x, y, a, b, c, s = box
    return [(x+i*a*c-j*b*s, y+i*a*s+j*b*c)
            for i, j in ((-1,-1), (1,-1), (1,1), (-1,1))]


def overlaps(a, b, margin=0.):
    """Separating-axis test; contact alone is not positive overlap."""
    dx, dy = b[0]-a[0], b[1]-a[1]
    for u, v in ((a[4], a[5]), (-a[5], a[4]), (b[4], b[5]), (-b[5], b[4])):
        ra = a[2]*abs(u*a[4]+v*a[5]) + a[3]*abs(-u*a[5]+v*a[4])
        rb = b[2]*abs(u*b[4]+v*b[5]) + b[3]*abs(-u*b[5]+v*b[4])
        if abs(u*dx + v*dy) >= ra + rb + margin:
            return False
    return True


def inset(rect, margin):
    x, X, y, Y = rect
    return x+margin, X-margin, y+margin, Y-margin


def contains(rect, xy):
    x, X, y, Y = rect
    return x <= xy[0] <= X and y <= xy[1] <= Y


def tray_rect(tray):
    x, y = tray['center']
    w, h = tray['inner']
    return x-w/2, x+w/2, y-h/2, y+h/2


def tray_box(tray):
    wall = tray.get('wall_thickness', 0.)
    return obb(tray['center'], tuple(side + 2*wall for side in tray['inner']))


def floor_z(tray):
    return tray.get('floor_z', 0.)


def geometric_tray(xyz, layout):
    settings = layout['judge']
    for tid, tray in layout['trays'].items():
        if (contains(inset(tray_rect(tray), settings['tray_margin']), xyz)
                and floor_z(tray) <= xyz[2] <= floor_z(tray) + settings['tray_z_max_above_floor']):
            return tid
    return None


def footprints_overlap(a, b, circle_a=False, circle_b=False):
    """Actual positive-area overlap for supported upright box/cylinder shapes."""
    if circle_a and circle_b:
        return (a[0]-b[0])**2 + (a[1]-b[1])**2 < (a[2]+b[2])**2
    if circle_a or circle_b:
        circle, box = (a, b) if circle_a else (b, a)
        dx, dy = circle[0]-box[0], circle[1]-box[1]
        u, v = dx*box[4]+dy*box[5], -dx*box[5]+dy*box[4]
        return max(abs(u)-box[2], 0.)**2 + max(abs(v)-box[3], 0.)**2 < circle[2]**2
    return overlaps(a, b)
