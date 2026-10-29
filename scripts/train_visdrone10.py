"""Train the ten-class VisDrone YOLO model in an isolated run directory."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path
from typing import Any

import torch
import ultralytics
import yaml
from ultralytics import YOLO, settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = Path("training") / "yolo11n.pt"
DEFAULT_DATASET = Path("dataset_visdrone10_yolo") / "data.yaml"
DEFAULT_PROJECT = PROJECT_ROOT / "runs"
DEFAULT_RUN_NAME = "visdrone10_yolo11n"
EXPECTED_CLASS_NAMES = [
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument(
        "--batch",
        type=int,
        default=2,
        help="Batch size (2 is conservative for the currently verified CPU-only environment).",
    )
    parser.add_argument("--device", choices=("auto", "cpu", "0"), default="auto")
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--name", default=DEFAULT_RUN_NAME)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--deterministic",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--patience", type=int, default=100)
    return parser


def resolve_project_path(path: Path | str, project_root: Path = PROJECT_ROOT) -> Path:
    resolved = Path(path).expanduser()
    if not resolved.is_absolute():
        resolved = project_root / resolved
    return resolved.resolve()


def select_device(requested: str, cuda_available: bool) -> str:
    if requested == "auto":
        return "0" if cuda_available else "cpu"
    if requested == "0" and not cuda_available:
        raise ValueError("CUDA device 0 was requested, but CUDA is unavailable.")
    return requested


def validate_model_path(model_path: Path, project_root: Path = PROJECT_ROOT) -> Path:
    resolved_model = model_path.resolve()
    protected_checkpoint = (
        project_root / "runs" / "drone_person_vehicle" / "weights" / "best.pt"
    ).resolve()
    if resolved_model == protected_checkpoint:
        raise ValueError(
            "The existing two-class checkpoint is protected and cannot be used "
            "as the ten-class model initialization."
        )
    if not resolved_model.is_file():
        raise FileNotFoundError(f"Initial pretrained checkpoint not found: {resolved_model}")
    return resolved_model


def validate_dataset(data_path: Path) -> list[str]:
    if not data_path.is_file():
        raise FileNotFoundError(f"Dataset YAML not found: {data_path}")
    with data_path.open("r", encoding="utf-8") as handle:
        dataset = yaml.safe_load(handle) or {}

    names = dataset.get("names")
    if isinstance(names, dict):
        try:
            class_names = [str(names[index]) for index in range(len(names))]
        except KeyError as error:
            raise ValueError("Dataset YAML class IDs must be contiguous from 0.") from error
    elif isinstance(names, list):
        class_names = [str(name) for name in names]
    else:
        raise ValueError("Dataset YAML must define class names as a list or indexed mapping.")

    if class_names != EXPECTED_CLASS_NAMES:
        raise ValueError(
            "Dataset YAML class names/order do not match the expected VisDrone ten classes."
        )

    dataset_root = Path(dataset.get("path", data_path.parent))
    if not dataset_root.is_absolute():
        dataset_root = data_path.parent / dataset_root
    for split in ("train", "val"):
        split_path = dataset.get(split)
        if not isinstance(split_path, str) or not split_path:
            raise ValueError(f"Dataset YAML must define a {split} image path.")
        image_path = Path(split_path)
        if not image_path.is_absolute():
            image_path = dataset_root / image_path
        if not image_path.is_dir():
            raise FileNotFoundError(
                f"Dataset {split} image directory not found: {image_path.resolve()}"
            )
    return class_names


def validate_run_target(
    project_root: Path,
    run_project: Path,
    run_name: str,
) -> Path:
    if not run_name or Path(run_name).name != run_name or run_name in {".", ".."}:
        raise ValueError("Run name must be a single non-empty directory name.")

    project = run_project.resolve()
    run_directory = (project / run_name).resolve()
    legacy_run = (project_root / "runs" / "drone_person_vehicle").resolve()
    baseline_checkpoint = legacy_run / "weights" / "best.pt"
    if (
        run_directory == legacy_run
        or run_directory in legacy_run.parents
        or legacy_run in run_directory.parents
        or run_directory == baseline_checkpoint
    ):
        raise ValueError(
            f"Run directory conflicts with the protected two-class run: {run_directory}"
        )
    if run_directory.exists():
        raise FileExistsError(
            f"Run directory already exists; refusing to overwrite: {run_directory}"
        )
    return run_directory


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def train(args: argparse.Namespace) -> Path:
    model_path = validate_model_path(resolve_project_path(args.model))
    data_path = resolve_project_path(args.data)
    project_path = resolve_project_path(args.project)
    class_names = validate_dataset(data_path)
    device = select_device(args.device, torch.cuda.is_available())
    run_directory = validate_run_target(PROJECT_ROOT, project_path, args.name)

    if not torch.cuda.is_available():
        print(
            "WARNING: CUDA is unavailable. CPU training is supported, but full "
            "100-epoch training may take a long time."
        )

    settings["runs_dir"] = str(project_path)
    settings["datasets_dir"] = str(PROJECT_ROOT)

    # Create this new run directory exclusively; never reuse an existing run.
    run_directory.mkdir(parents=True, exist_ok=False)
    training_config = {
        "model": str(model_path),
        "dataset": str(data_path),
        "class_names": class_names,
        "imgsz": args.imgsz,
        "epochs": args.epochs,
        "batch": args.batch,
        "device": device,
        "workers": args.workers,
        "project": str(project_path),
        "name": args.name,
        "seed": args.seed,
        "deterministic": args.deterministic,
        "patience": args.patience,
        "fraction": 1.0,
        "val": True,
        "save": True,
    }
    environment = {
        "python": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "ultralytics": ultralytics.__version__,
        "torch": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cuda_version": torch.version.cuda,
        "torchvision": __import__("torchvision").__version__,
        "runs_dir": str(settings["runs_dir"]),
        "datasets_dir": str(settings["datasets_dir"]),
    }
    _write_json(run_directory / "training_config.json", training_config)
    _write_json(run_directory / "environment.json", environment)

    model = YOLO(str(model_path))
    model.train(
        data=str(data_path),
        imgsz=args.imgsz,
        epochs=args.epochs,
        batch=args.batch,
        device=device,
        workers=args.workers,
        project=str(project_path),
        name=args.name,
        seed=args.seed,
        deterministic=args.deterministic,
        patience=args.patience,
        fraction=1.0,
        val=True,
        save=True,
        exist_ok=True,
    )

    weights_directory = run_directory / "weights"
    for weight_name in ("best.pt", "last.pt"):
        if not (weights_directory / weight_name).is_file():
            raise FileNotFoundError(
                f"Training returned without saving expected weights: "
                f"{weights_directory / weight_name}"
            )
    print(f"Training complete. Run directory: {run_directory}")
    print(f"Best weights: {weights_directory / 'best.pt'}")
    print(f"Last weights: {weights_directory / 'last.pt'}")
    return run_directory


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    for option in ("imgsz", "epochs", "batch"):
        if getattr(args, option) <= 0:
            parser.error(f"--{option} must be a positive integer")
    if args.workers < 0:
        parser.error("--workers must be non-negative")
    if args.patience < 0:
        parser.error("--patience must be non-negative")
    try:
        train(args)
    except (FileNotFoundError, FileExistsError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
