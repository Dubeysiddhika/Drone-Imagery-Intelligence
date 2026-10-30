"""Create a SHA-256 manifest for the verified VisDrone10 handoff dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import torch
import yaml

if __package__:
    from .train_visdrone10 import EXPECTED_CLASS_NAMES
else:
    from train_visdrone10 import EXPECTED_CLASS_NAMES


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = PROJECT_ROOT / "dataset_visdrone10_yolo"
DEFAULT_OUTPUT = PROJECT_ROOT / "docs" / "visdrone10_dataset_manifest.json"
DEFAULT_CHECKPOINTS = (
    ("last.pt", PROJECT_ROOT / "runs" / "visdrone10_yolo11n" / "weights" / "last.pt"),
    ("best.pt", PROJECT_ROOT / "runs" / "visdrone10_yolo11n" / "weights" / "best.pt"),
)
DATASET_DIRECTORIES = (
    "images/train",
    "images/val",
    "labels/train",
    "labels/val",
)
HANDOFF_ARTIFACTS = (
    ".gitattributes",
    "configs/visdrone10.yaml",
    "requirements-visdrone10.txt",
    "scripts/create_visdrone10_dataset_manifest.py",
    "scripts/resume_visdrone10.py",
    "scripts/train_visdrone10.py",
    "scripts/verify_visdrone10_handoff.py",
    "tests/test_verify_visdrone10_handoff.py",
    "runs/visdrone10_yolo11n/results.csv",
    "runs/visdrone10_yolo11n/args.yaml",
    "runs/visdrone10_yolo11n/resume_training.log",
    "training/evaluate.py",
    "docs/VISDRONE10_TRAINING_HANDOFF.md",
    "docs/visdrone10_conversion_report.json",
    "docs/visdrone10_repair_report.json",
)


def sha256_file(path: Path, *, normalize_crlf: bool = False) -> str:
    if normalize_crlf:
        return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dataset_names(dataset_yaml: Path) -> list[str]:
    with dataset_yaml.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    names = config.get("names")
    if isinstance(names, dict):
        try:
            result = [str(names[index]) for index in range(len(names))]
        except KeyError as error:
            raise ValueError("Dataset YAML class IDs must be contiguous from 0.") from error
    elif isinstance(names, list):
        result = [str(name) for name in names]
    else:
        raise ValueError("Dataset YAML must define class names.")
    if result != EXPECTED_CLASS_NAMES:
        raise ValueError("Dataset YAML does not match the VisDrone ten-class mapping.")
    return result


def checkpoint_metadata(path: Path) -> dict[str, Any]:
    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    if not isinstance(checkpoint, dict):
        raise ValueError(f"Checkpoint is not a training checkpoint: {path}")
    epoch = checkpoint.get("epoch")
    args = checkpoint.get("train_args") or {}
    if not isinstance(epoch, int) or epoch < 0:
        raise ValueError(f"Checkpoint has no completed epoch state: {path}")
    if not checkpoint.get("optimizer"):
        raise ValueError(f"Checkpoint has no optimizer state for resume: {path}")
    ema = checkpoint.get("ema")
    checkpoint_names = getattr(ema, "names", None)
    if not isinstance(checkpoint_names, dict):
        raise ValueError(f"Checkpoint has no EMA class-name mapping: {path}")
    names = [str(checkpoint_names[index]) for index in range(len(checkpoint_names))]
    if names != EXPECTED_CLASS_NAMES:
        raise ValueError(f"Checkpoint class names do not match VisDrone10: {path}")
    return {
        "epoch_index": epoch,
        "completed_epochs": epoch + 1,
        "target_epochs": args.get("epochs"),
        "ultralytics_version": checkpoint.get("version"),
        "class_names": names,
    }


def create_manifest(
    dataset_root: Path,
    output_path: Path,
    project_root: Path = PROJECT_ROOT,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    dataset_root = dataset_root.resolve()
    output_path = output_path.resolve()
    if not dataset_root.is_dir():
        raise FileNotFoundError(f"Dataset directory not found: {dataset_root}")
    dataset_names(dataset_root / "data.yaml")

    entries: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    total_bytes = 0
    for relative_directory in DATASET_DIRECTORIES:
        directory = dataset_root / Path(relative_directory)
        if not directory.is_dir():
            raise FileNotFoundError(f"Dataset directory not found: {directory}")
        files = sorted(path for path in directory.iterdir() if path.is_file())
        counts[relative_directory] = len(files)
        if not files:
            raise ValueError(f"Dataset directory is empty: {directory}")
        for path in files:
            size = path.stat().st_size
            entries.append(
                {
                    "path": path.relative_to(dataset_root).as_posix(),
                    "bytes": size,
                    "sha256": sha256_file(path),
                }
            )
            total_bytes += size

    checkpoints: dict[str, dict[str, Any]] = {}
    for name, path in DEFAULT_CHECKPOINTS:
        if not path.is_file():
            raise FileNotFoundError(f"Checkpoint not found: {path}")
        checkpoints[name] = {
            "path": path.relative_to(project_root.resolve()).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            **checkpoint_metadata(path),
        }

    artifacts: list[dict[str, Any]] = []
    for relative_path in HANDOFF_ARTIFACTS:
        path = project_root / Path(relative_path)
        if not path.is_file():
            raise FileNotFoundError(f"Handoff artifact not found: {path}")
        normalized_bytes = path.read_bytes().replace(b"\r\n", b"\n")
        artifacts.append(
            {
                "path": relative_path,
                "bytes": len(normalized_bytes),
                "sha256": hashlib.sha256(normalized_bytes).hexdigest(),
            }
        )

    manifest = {
        "format_version": 1,
        "artifact_hash_policy": (
            "Handoff artifact size and SHA-256 use file bytes with CRLF normalized "
            "to LF; dataset files and checkpoints use raw bytes."
        ),
        "dataset": {
            "name": "VisDrone2019-DET converted to YOLO detection format",
            "root": dataset_root.relative_to(project_root.resolve()).as_posix(),
            "yaml": "configs/visdrone10.yaml",
            "class_names": dataset_names(dataset_root / "data.yaml"),
            "files_by_directory": counts,
            "file_count": len(entries),
            "bytes": total_bytes,
            "files": entries,
        },
        "checkpoints": checkpoints,
        "artifacts": artifacts,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and not overwrite:
        raise FileExistsError(
            f"Manifest already exists; pass --overwrite to replace it: {output_path}"
        )
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    manifest = create_manifest(args.dataset, args.output, overwrite=args.overwrite)
    print(
        f"Wrote {manifest['dataset']['file_count']} file hashes "
        f"({manifest['dataset']['bytes']} bytes) to {args.output.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
