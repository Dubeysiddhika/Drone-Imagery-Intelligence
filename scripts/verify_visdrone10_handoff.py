"""Verify the VisDrone10 checkpoint and dataset against the committed manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import torch
import yaml

if __package__:
    from .create_visdrone10_dataset_manifest import checkpoint_metadata
    from .train_visdrone10 import EXPECTED_CLASS_NAMES, PROJECT_ROOT
else:
    from create_visdrone10_dataset_manifest import checkpoint_metadata
    from train_visdrone10 import EXPECTED_CLASS_NAMES, PROJECT_ROOT


DEFAULT_MANIFEST = Path("docs/visdrone10_dataset_manifest.json")
REQUIRED_FILES = (
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_names(names: Any) -> list[str]:
    if isinstance(names, dict):
        try:
            return [str(names[index]) for index in range(len(names))]
        except KeyError as error:
            raise ValueError("Class IDs must be contiguous from 0.") from error
    if isinstance(names, list):
        return [str(name) for name in names]
    raise ValueError("Class names must be a list or indexed mapping.")


def verify_handoff(
    project_root: Path,
    manifest_path: Path,
    dataset_root: Path | None = None,
) -> list[str]:
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    errors: list[str] = []
    for relative_path in REQUIRED_FILES:
        if not (project_root / Path(relative_path)).is_file():
            errors.append(f"Required handoff file missing: {relative_path}")

    for entry in manifest.get("artifacts", []):
        path = project_root / Path(entry["path"])
        if not path.is_file():
            errors.append(f"Handoff artifact missing: {path}")
            continue
        normalized_bytes = path.read_bytes().replace(b"\r\n", b"\n")
        if len(normalized_bytes) != entry["bytes"]:
            errors.append(f"Handoff artifact size mismatch: {path}")
            continue
        if hashlib.sha256(normalized_bytes).hexdigest() != entry["sha256"]:
            errors.append(f"Handoff artifact SHA-256 mismatch: {path}")

    config_path = project_root / Path(manifest["dataset"]["yaml"])
    if not config_path.is_file():
        errors.append(f"Ten-class dataset YAML missing: {config_path}")
    else:
        with config_path.open("r", encoding="utf-8") as handle:
            config = yaml.safe_load(handle) or {}
        if normalize_names(config.get("names")) != EXPECTED_CLASS_NAMES:
            errors.append("Ten-class dataset YAML names/order do not match the handoff.")

    selected_dataset_root = dataset_root or (
        project_root / Path(manifest["dataset"]["root"])
    )
    for subdirectory, expected_count in manifest["dataset"][
        "files_by_directory"
    ].items():
        directory = selected_dataset_root / Path(subdirectory)
        if not directory.is_dir():
            errors.append(f"Dataset directory missing: {directory}")
            continue
        actual_count = sum(path.is_file() for path in directory.iterdir())
        if actual_count != expected_count:
            errors.append(
                f"{directory}: expected {expected_count} files, found {actual_count}"
            )

    for entry in manifest["dataset"]["files"]:
        path = selected_dataset_root / Path(entry["path"])
        if not path.is_file():
            errors.append(f"Dataset file missing: {path}")
            continue
        if path.stat().st_size != entry["bytes"]:
            errors.append(f"Dataset file size mismatch: {path}")
            continue
        if sha256_file(path) != entry["sha256"]:
            errors.append(f"Dataset SHA-256 mismatch: {path}")

    for entry in manifest["checkpoints"].values():
        path = project_root / Path(entry["path"])
        if not path.is_file():
            errors.append(f"Checkpoint missing (run git lfs pull): {path}")
            continue
        if path.stat().st_size != entry["bytes"]:
            errors.append(f"Checkpoint size mismatch: {path}")
            continue
        if sha256_file(path) != entry["sha256"]:
            errors.append(f"Checkpoint SHA-256 mismatch: {path}")
            continue
        metadata = checkpoint_metadata(path)
        for key in ("epoch_index", "completed_epochs", "target_epochs", "class_names"):
            if metadata[key] != entry[key]:
                errors.append(f"Checkpoint metadata mismatch for {key}: {path}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--dataset-root", type=Path)
    args = parser.parse_args()
    manifest_path = args.manifest
    if not manifest_path.is_absolute():
        manifest_path = PROJECT_ROOT / manifest_path
    dataset_root = args.dataset_root
    if dataset_root is not None and not dataset_root.is_absolute():
        dataset_root = PROJECT_ROOT / dataset_root

    errors = verify_handoff(PROJECT_ROOT, manifest_path, dataset_root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("VisDrone10 handoff verified: checkpoints, class mapping, and dataset hashes match.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
