"""Opt-in CUDA fallback. See README.md for upload/download and platform setup."""
import argparse
import os
from pathlib import Path
import shutil

from .bench_policy import options, run


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--execute", action="store_true", help="Explicitly opt into running on a cloud GPU")
    p.add_argument("--data", type=Path, required=True, help="Extracted LeRobot v3 dataset root")
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    if not a.execute:
        p.error("Preparation only; add --execute yourself on a configured GPU runtime")
    if not (a.data / "meta" / "info.json").is_file():
        p.error("--data must contain meta/info.json")
    os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
    import torch

    if torch.version.hip is not None or not torch.cuda.is_available():
        p.error("Enable a CUDA GPU runtime; no CPU or ROCm fallback")
    run(options(["smolvla", str(a.data), "--batch", "1", "--steps", "100", "--dtype", "fp32",
                 "--checkpoint", str(a.out)]))
    archive = shutil.make_archive(str(a.out / "smolvla_policy"), "zip", root_dir=a.out / "policy")
    print(f"Download portable policy and processors from {archive}")


if __name__ == "__main__":
    main()