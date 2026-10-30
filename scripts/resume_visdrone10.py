"""Resume the isolated ten-class VisDrone run from its saved last checkpoint."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from typing import Any

import yaml
from ultralytics import YOLO, settings

if __package__:
    from .create_visdrone10_dataset_manifest import checkpoint_metadata
    from .train_visdrone10 import (
        EXPECTED_CLASS_NAMES,
        PROJECT_ROOT,
        resolve_project_path,
    )
else:
    from create_visdrone10_dataset_manifest import checkpoint_metadata
    from train_visdrone10 import (
        EXPECTED_CLASS_NAMES,
        PROJECT_ROOT,
        resolve_project_path,
    )


DEFAULT_CHECKPOINT = Path("runs/visdrone10_yolo11n/weights/last.pt")
DEFAULT_DATASET = Path("configs/visdrone10.yaml")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATASET)
    return parser


def validate_dataset(
    data_path: Path,
    project_root: Path = PROJECT_ROOT,
) -> list[str]:
    if not data_path.is_file():
        raise FileNotFoundError(f"Dataset YAML not found: {data_path}")
    with data_path.open("r", encoding="utf-8") as handle:
        config: dict[str, Any] = yaml.safe_load(handle) or {}
    names = config.get("names")
    if isinstance(names, dict):
        try:
            class_names = [str(names[index]) for index in range(len(names))]
        except KeyError as error:
            raise ValueError("Dataset YAML class IDs must be contiguous from 0.") from error
    elif isinstance(names, list):
        class_names = [str(name) for name in names]
    else:
        raise ValueError("Dataset YAML must define ten class names.")
    if class_names != EXPECTED_CLASS_NAMES:
        raise ValueError("Dataset YAML class names/order do not match VisDrone10.")

    dataset_root = Path(config.get("path") or data_path.parent)
    if not dataset_root.is_absolute():
        dataset_root = project_root / dataset_root
    for split in ("train", "val"):
        split_path = config.get(split)
        if not isinstance(split_path, str) or not split_path:
            raise ValueError(f"Dataset YAML must define a {split} image path.")
        image_directory = Path(split_path)
        if not image_directory.is_absolute():
            image_directory = dataset_root / image_directory
        if not image_directory.is_dir():
            raise FileNotFoundError(
                f"Dataset {split} image directory not found: {image_directory.resolve()}"
            )
    return class_names


def write_runtime_dataset_yaml(
    data_path: Path,
    output_path: Path,
    project_root: Path = PROJECT_ROOT,
) -> Path:
    with data_path.open("r", encoding="utf-8") as handle:
        config: dict[str, Any] = yaml.safe_load(handle) or {}
    dataset_root = Path(config.get("path") or data_path.parent)
    if not dataset_root.is_absolute():
        dataset_root = project_root / dataset_root
    config["path"] = str(dataset_root.resolve())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        yaml.safe_dump(config, handle, sort_keys=False)
    return output_path


def resume_training(checkpoint_path: Path, data_path: Path) -> None:
    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"Resume checkpoint not found: {checkpoint_path}")
    class_names = validate_dataset(data_path)
    metadata = checkpoint_metadata(checkpoint_path)
    if metadata["class_names"] != class_names:
        raise ValueError("Checkpoint and dataset class names/order do not match.")

    settings["runs_dir"] = str(PROJECT_ROOT / "runs")
    settings["datasets_dir"] = str(PROJECT_ROOT)
    print(
        "Resuming from saved checkpoint: "
        f"epoch index {metadata['epoch_index']} "
        f"({metadata['completed_epochs']} completed of "
        f"{metadata['target_epochs']} planned); "
        f"Ultralytics {metadata['ultralytics_version']}."
    )
    model = YOLO(str(checkpoint_path))
    with tempfile.TemporaryDirectory(prefix="visdrone10-") as temporary_directory:
        runtime_data_path = write_runtime_dataset_yaml(
            data_path,
            Path(temporary_directory) / "data.yaml",
        )
        model.train(
            resume=str(checkpoint_path),
            data=str(runtime_data_path),
            save_dir=str(PROJECT_ROOT / "runs" / "visdrone10_yolo11n"),
        )


def main() -> int:
    args = build_parser().parse_args()
    resume_training(
        resolve_project_path(args.checkpoint),
        resolve_project_path(args.data),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
