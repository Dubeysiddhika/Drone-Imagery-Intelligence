from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from ..config import PROJECT_ROOT, resolve_project_path


VISDRONE10_CLASS_NAMES = [
    "pedestrian",
    "people",
    "bicycle",
    "car",
    "van",
    "truck",
    "tricycle",
    "awning-tricycle",
    "bus",
    "motor",
]


def _baseline_model_path() -> Path:
    return resolve_project_path(
        os.environ.get("BASELINE_MODEL_PATH"),
        "runs/drone_person_vehicle/weights/best.pt",
    )


def _visdrone10_model_path() -> Path:
    return resolve_project_path(
        os.environ.get("VISDRONE10_MODEL_PATH"),
        "backend/app/models/weights/visdrone10_yolo11n_best.pt",
    )


MODEL_CATALOG: dict[str, dict[str, Any]] = {
    "baseline": {
        "model_name": "YOLO11n",
        "model_version": "drone_person_vehicle",
        "model_path": str(_baseline_model_path()),
        "class_names": ["person", "vehicle"],
        "class_count": 2,
        "framework": "Ultralytics YOLO",
        "description": "Baseline person + vehicle detector trained on the project VisDrone-derived dataset.",
    },
    "drone_person_vehicle": {
        "model_name": "YOLO11n",
        "model_version": "drone_person_vehicle",
        "model_path": str(_baseline_model_path()),
        "class_names": ["person", "vehicle"],
        "class_count": 2,
        "framework": "Ultralytics YOLO",
        "description": "Baseline person + vehicle detector trained on the project VisDrone-derived dataset.",
    },
    "visdrone10": {
        "model_name": "YOLO11n VisDrone10",
        "model_version": "visdrone10_yolo11n",
        "model_path": "",
        "class_names": VISDRONE10_CLASS_NAMES,
        "class_count": len(VISDRONE10_CLASS_NAMES),
        "framework": "Ultralytics YOLO",
        "description": "Ten-class detector trained on the dedicated VisDrone ten-class dataset.",
    },
    "visdrone10_yolo11n": {
        "model_name": "YOLO11n VisDrone10",
        "model_version": "visdrone10_yolo11n",
        "model_path": "",
        "class_names": VISDRONE10_CLASS_NAMES,
        "class_count": len(VISDRONE10_CLASS_NAMES),
        "framework": "Ultralytics YOLO",
        "description": "Ten-class detector trained on the dedicated VisDrone ten-class dataset.",
    },
}


def _read_dataset_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"names": {"0": "person", "1": "vehicle"}}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"names": {"0": "person", "1": "vehicle"}}


def get_model_metadata(model_version: str | None = None) -> dict[str, Any]:
    """Return metadata for the requested supported model or baseline default."""
    version_key = (model_version or "baseline").strip().lower()
    if version_key in MODEL_CATALOG:
        metadata = dict(MODEL_CATALOG[version_key])
        if metadata["model_version"] == "visdrone10_yolo11n":
            metadata["model_path"] = str(_visdrone10_model_path())
        elif metadata["model_version"] == "drone_person_vehicle":
            metadata["model_path"] = str(_baseline_model_path())
        return metadata

    raise ValueError(f"Unsupported model version: {model_version}")


def get_available_models() -> list[dict[str, Any]]:
    """Return public model information without exposing local filesystem paths."""
    models = []
    for model_id in ("baseline", "visdrone10_yolo11n"):
        metadata = get_model_metadata(model_id)
        models.append(
            {
                "model_id": model_id,
                "model_name": metadata["model_name"],
                "model_version": metadata["model_version"],
                "framework": metadata["framework"],
                "class_count": metadata["class_count"],
                "weights_available": Path(metadata["model_path"]).is_file(),
            }
        )
    return models


def get_default_model_version() -> str:
    return MODEL_CATALOG["baseline"]["model_version"]


def get_default_model_path() -> Path:
    return _baseline_model_path()


def get_dataset_class_names() -> list[str]:
    dataset_yaml = PROJECT_ROOT / "dataset" / "data.yaml"
    dataset_cfg = _read_dataset_yaml(dataset_yaml)
    names = dataset_cfg.get("names", {})
    if not names:
        return ["person", "vehicle"]
    ordered_names = [str(names[str(index)]) for index in range(len(names))]
    return ordered_names or ["person", "vehicle"]
