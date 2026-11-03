# Phase 0 downloads (S3)  2026-10-26 14:07

## FoundationPose weights  -> /home/user/work/robot_percept/downloads/weights
Source: professor MD / official README Google Drive folder 1DFezOAD0oD1BblsXVxqDsl8fj0qzB82i (gdown)
| dir | role | file | bytes |
|---|---|---|---|
| 2023-10-28-18-33-37 | refiner | model_best.pth | 68220109 |
| 2023-10-28-18-33-37 | refiner | config.yml | 708 |
| 2024-01-11-20-02-45 | scorer | model_best.pth | 190229389 |
| 2024-01-11-20-02-45 | scorer | config.yml | 778 |

## Demo data  -> /home/user/work/robot_percept/downloads/demo_data
Source: official README "Download demo data" Google Drive folder 1pRyFmxYXmAnpku7nGRioZaKrVJtIsroP (gdown); zips kept in /home/user/work/robot_percept/downloads/demo_raw
- mustard0: rgb 737, depth 1332 (depth has more frames than rgb; run_demo iterates the rgb list, normal), masks 1 (first frame), mesh/textured_simple.obj (+mtl, texture_map.png), cam_K.txt (640x480, fx 319.58 fy 417.12)
- kinect_driller_seq: rgb 744, depth 744, masks 1, mesh/textured_mesh.obj, cam_K.txt (1280x720, fx 603.7), ob_in_cam/, track_vis/

## Linking into FoundationPose (for S1)
```bash
cd ~/work/robot_percept/FoundationPose
ln -sfn /home/user/work/robot_percept/downloads/weights weights
ln -sfn /home/user/work/robot_percept/downloads/demo_data demo_data
```
run_demo.py defaults: --mesh_file demo_data/mustard0/mesh/textured_simple.obj --test_scene_dir demo_data/mustard0

Checksums: /home/user/work/robot_percept/downloads/SHA256SUMS.txt
