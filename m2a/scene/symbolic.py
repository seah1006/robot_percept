"""Convert initial S0 metadata or simulator GT into contract v1 predicates."""
from copy import deepcopy
from ._geometry import contains, footprints_overlap, geometric_tray, obb, size_xyz

STACK_TOLERANCE = .005  # 임의 지정: distance between contacting z surfaces


def symbolic(spec, layout):
    return {'objects': {obj['oid']: {key: obj[key] for key in ('part_id', 'region', 'in_tray', 'on')}
                        for obj in spec['objects']}, 'reach': deepcopy(layout['reach'])}


def symbolic_from_gt(gt_objects, layout, parts):
    """Infer support from upright, yaw-only object geometry (no contact data)."""
    parts = parts.get('parts', parts)
    dims = {oid: size_xyz(parts[obj['part_id']]) for oid, obj in gt_objects.items()}
    boxes = {oid: obb(obj['xyz'], dims[oid], obj['yaw']) for oid, obj in gt_objects.items()}
    cylinders = {oid: parts[obj["part_id"]]["shape"] == "cylinder" for oid, obj in gt_objects.items()}
    result = {}
    for oid, obj in gt_objects.items():
        xyz = obj['xyz']
        tid = geometric_tray(xyz, layout)
        region = None if tid or xyz[2] < 0 else next((name for name, rect in
                                                     layout['regions'].items() if contains(rect, xyz)), None)
        supporters = []
        for other, below in gt_objects.items():
            dz = xyz[2] - below['xyz'][2]
            error = abs(dz - (dims[oid][2] + dims[other][2])/2)
            if (dz > 0 and error <= STACK_TOLERANCE and footprints_overlap(
                    boxes[oid], boxes[other], cylinders[oid], cylinders[other])):
                supporters.append((error, other))
        result[oid] = dict(part_id=obj['part_id'], region=region, in_tray=tid,
                           on=min(supporters)[1] if supporters else None)
    return {'objects': result, 'reach': deepcopy(layout['reach'])}
