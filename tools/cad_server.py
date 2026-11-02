#!/usr/bin/env python3
"""
Minimal CAD upload server (Phase 0 smoke test)
  POST /upload   multipart field 'file' (.stp/.step), optional form: unit, center, collision
                 -> saves to cad_uploads/<name>_<id>/ , converts to metre meshes, returns JSON
  GET  /health   -> {"ok": true, ...}
  GET  /files/<path>  -> download converted files

  python tools/cad_server.py --port 5050
  curl -F file=@part.step -F collision=coacd http://127.0.0.1:5050/upload
"""
import argparse
import sys
import time
import traceback
import uuid
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stp_to_mesh import convert  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
UPLOADS = ROOT / "cad_uploads"
ALLOWED = {".stp", ".step"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024   # 100 MB


@app.get("/health")
def health():
    return jsonify(ok=True, uploads=str(UPLOADS))


@app.post("/upload")
def upload():
    f = request.files.get("file")
    if f is None or not f.filename:
        return jsonify(ok=False, error="multipart field 'file' required"), 400
    name = secure_filename(f.filename)
    stem, ext = Path(name).stem, Path(name).suffix.lower()
    if ext not in ALLOWED:
        return jsonify(ok=False, error=f"unsupported extension {ext} (use .stp/.step)"), 400

    job = f"{stem}_{uuid.uuid4().hex[:6]}"
    job_dir = UPLOADS / job
    job_dir.mkdir(parents=True, exist_ok=True)
    src = job_dir / f"{stem}{ext}"
    f.save(src)

    t0 = time.time()
    try:
        meta = convert(src, out_dir=job_dir, unit=request.form.get("unit") or None,
                       center=request.form.get("center", "bbox"),
                       collision=request.form.get("collision", "hull"), name=stem)
    except Exception as e:
        traceback.print_exc()
        return jsonify(ok=False, error=f"{type(e).__name__}: {e}"), 422
    files = [meta["files"]["obj"], meta["files"]["stl"]] + [c["file"] for c in meta["files"]["collision"]]
    return jsonify(
        ok=True, job=job, convert_s=round(time.time() - t0, 3),
        header_unit=meta["header_unit"], unit_override=meta["unit_override"],
        extents_m=meta["mesh"]["extents_m"], triangles=meta["mesh"]["triangles"],
        watertight=meta["mesh"]["watertight"], volume_m3=meta["mesh"]["volume_m3"],
        center_offset_m=meta["center_offset_m"],
        n_collision_parts=len(meta["files"]["collision"]),
        files=[f"/files/{job}/{x}" for x in files],
    )


@app.get("/files/<path:p>")
def files(p):
    return send_from_directory(UPLOADS, p)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=5050)
    a = ap.parse_args()
    app.run(host=a.host, port=a.port, threaded=True)
