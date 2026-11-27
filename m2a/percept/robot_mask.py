"""Visible G1 self-mask, derived only from the robot body tree and segmentation IDs."""

import numpy as np


def robot_geom_ids(model):
    """Find the torso's top-level ancestor, then select geoms in that subtree only."""
    torso = int(model.body('torso_link').id)
    if torso <= 0:
        raise ValueError('torso_link must be a non-world body')
    parents = model.body_parentid
    root = torso
    while parents[root] != 0:
        root = int(parents[root])
    member = np.zeros(model.nbody, dtype=bool)
    member[root] = True
    for body in range(root + 1, model.nbody):
        member[body] = member[parents[body]]
    return np.flatnonzero(member[model.geom_bodyid])


def segmentation_mask(seg, robot_ids, geom_type):
    """Never return non-robot pixels, including sites and background."""
    return (seg[..., 1] == geom_type) & np.isin(seg[..., 0], robot_ids)


def render_ids(renderer, data, cam):
    import mujoco as mj

    opt = mj.MjvOption()
    opt.geomgroup[3:] = 0
    opt.sitegroup[5] = 0
    renderer.enable_segmentation_rendering()
    try:
        renderer.update_scene(data, camera=cam, scene_option=opt)
        return renderer.render()
    finally:
        renderer.disable_segmentation_rendering()


def live_robot_mask(env, cam):
    # Reuse the scene renderer created by env.render; generic RGB-D-only envs
    # need not expose MuJoCo and may instead supply a robot_mask in a frame.
    renderer = getattr(env, '_renderers', {}).get(cam)
    if renderer is None or not hasattr(env, 'model') or not hasattr(env, 'data'):
        return None
    try:
        robot_ids = robot_geom_ids(env.model)
    except (KeyError, ValueError):
        return None
    import mujoco as mj

    return segmentation_mask(render_ids(renderer, env.data, cam), robot_ids, mj.mjtObj.mjOBJ_GEOM)
