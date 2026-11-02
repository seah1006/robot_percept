# Simulation object assets

`mustard/collision_hull.obj` is generated from the unmodified YCB mustard OBJ.
Visual mesh and texture are loaded from `downloads/demo_data/mustard0/mesh/`.
Source bounds: approximately 0.09715 x 0.06662 x 0.19141 metres.
No visual or collision vertices are recentered or rescaled.
MuJoCo internally aligns mesh principal axes; its geom transform compensates this.
`T_world_obj` uses the free body transform, which remains the original OBJ frame.

CAD objects are discovered in `cad_uploads/converted/<name>/<name>.obj`.
Existing `*_collision_coacd_*.obj` parts are used, retaining the same source frame.
`add_object_from_mesh` registers custom geometry for compilation on the next reset.
The `object_ids` mapping uses zero-based insertion order. Background segmentation is -1.

Run validation from the project root:

    source sim_test/gl_env.sh
    PYTHONPATH=. .venvs/mj/bin/python tests/test_env.py

Dependencies used: mujoco, numpy, opencv-python-headless, trimesh, scipy, rtree.
The validation uses rtree for exact mesh closest-point queries.
Depth edges are invalidated to zero while segmentation remains a full silhouette.
Both front (contract name) and rgbd (legacy compatibility) refer to the fixed camera.
The TCP site is at hand z=0.1034 m, between the fingertip contact pads.
