from __future__ import annotations

import argparse
from pathlib import Path

import yaml
from ultralytics import YOLO


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = PROJECT_ROOT / "dataset"
DATA_PATH = DATASET_DIR / "data.yaml"
DEFAULT_MODEL = PROJECT_ROOT / "runs" / "drone_person_vehicle" / "weights" / "best.pt"


def resolve_project_path(path: Path) -> Path:
    path = path.expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate a YOLO model on the held-out test split.")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL, help="Path to the trained weights file.")
    parser.add_argument("--data", type=Path, default=DATA_PATH, help="Dataset YAML path.")
    parser.add_argument("--split", default="test", choices=["train", "val", "test"], help="Held-out split to evaluate.")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--iou", type=float, default=0.7)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.model = resolve_project_path(args.model)
    args.data = resolve_project_path(args.data)
    if not args.model.is_file():
        raise FileNotFoundError(f"Model weights not found: {args.model}")
    if not args.data.is_file():
        raise FileNotFoundError(f"Dataset YAML not found: {args.data}")

    with args.data.open("r", encoding="utf-8") as handle:
        dataset_config = yaml.safe_load(handle) or {}
    dataset_root = Path(dataset_config.get("path") or args.data.parent).expanduser()
    if not dataset_root.is_absolute():
        dataset_root = PROJECT_ROOT / dataset_root
    dataset_config["path"] = str(dataset_root.resolve())

    model = YOLO(str(args.model))
    metrics = model.val(
        data=dataset_config,
        split=args.split,
        imgsz=args.imgsz,
        batch=args.batch,
        conf=args.conf,
        iou=args.iou,
        project=str(PROJECT_ROOT / "runs" / "evaluation"),
        name=args.split,
        verbose=True,
    )

    print("\nEvaluation summary")
    print("-" * 40)
    print(f"Model: {args.model}")
    print(f"Data: {args.data}")
    print(f"Split: {args.split}")
    print(f"Precision: {metrics.box.p:.4f}")
    print(f"Recall: {metrics.box.r:.4f}")
    print(f"mAP50: {metrics.box.map50:.4f}")
    print(f"mAP50-95: {metrics.box.map:.4f}")
    print("Per-class metrics are available through the Ultralytics metrics object.")


if __name__ == "__main__":
    main()
