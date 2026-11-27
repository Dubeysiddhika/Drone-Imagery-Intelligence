"""Preflight checks for an AeroVision checkout on a new machine.

Run from the repository root:
    python scripts/check_environment.py
The script distinguishes required Python packages from optional model/data assets.
"""

from __future__ import annotations

import importlib.util
import os
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=False)
except ImportError:
    pass

REQUIRED_MODULES = {
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "multipart": "python-multipart",
    "ultralytics": "ultralytics",
    "torch": "torch",
    "torchvision": "torchvision",
    "numpy": "numpy",
    "cv2": "opencv-python",
    "PIL": "Pillow",
    "sqlalchemy": "SQLAlchemy",
    "geoalchemy2": "GeoAlchemy2",
    "psycopg": "psycopg[binary]",
    "yaml": "PyYAML",
    "httpx": "httpx",
    "argon2": "argon2-cffi",
    "jwt": "PyJWT",
    "pyproj": "pyproj",
    "rasterio": "rasterio",
    "psutil": "psutil",
}


def configured_path(variable: str, default: str) -> Path:
    value = os.getenv(variable, default)
    path = Path(value).expanduser()
    return (path if path.is_absolute() else ROOT / path).resolve()


def main() -> int:
    print("AEROVISION ENVIRONMENT PREFLIGHT")
    print(f"Platform: {platform.platform()}")
    print(f"Python:   {sys.version.split()[0]}")
    print(f"Root:     {ROOT}")
    print()

    missing = []
    for module, package in REQUIRED_MODULES.items():
        available = importlib.util.find_spec(module) is not None
        print(
            f"[{'OK' if available else 'MISSING'}] Python module: {module}"
            + ("" if available else f" (install {package})")
        )
        if not available:
            missing.append(package)

    print()
    assets = [
        (
            "Ten-class YOLO checkpoint",
            configured_path(
                "VISDRONE10_MODEL_PATH",
                "backend/app/models/weights/visdrone10_yolo11n_best.pt",
            ),
            True,
        ),
        (
            "Baseline YOLO checkpoint",
            configured_path(
                "BASELINE_MODEL_PATH",
                "runs/drone_person_vehicle/weights/best.pt",
            ),
            False,
        ),
        (
            "UAV-VisLoc source dataset",
            configured_path("UAV_VISLOC_DATASET_DIR", "UAV_VisLoc_dataset"),
            False,
        ),
        (
            "UAV-VisLoc Phase 3C index",
            configured_path(
                "UAV_VISLOC_PHASE3C_DIR",
                "backend/training/uav_visloc/phase3_pretrained_setup/phase3c",
            ),
            False,
        ),
    ]
    for label, path, recommended in assets:
        exists = path.exists()
        status = "OK" if exists else ("MISSING" if recommended else "OPTIONAL")
        print(f"[{status}] {label}: {path}")
        if exists and path.is_file() and path.suffix.lower() == ".pt" and path.stat().st_size < 1024:
            try:
                pointer = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                pointer = ""
            if pointer.startswith("version https://git-lfs.github.com/spec/v1"):
                print("       This is a Git LFS pointer, not model weights. Run: git lfs pull")

    print()
    if missing:
        print("Missing required packages. Install: python -m pip install -r backend/requirements.txt")
        return 1

    print("Required Python modules are present. Optional model/data features depend on the assets above.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
