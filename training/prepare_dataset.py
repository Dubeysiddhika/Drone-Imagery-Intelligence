"""Split a YOLO image/label pair collection into train, val, and test sets."""

from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", type=Path, required=True, help="Directory containing source images")
    parser.add_argument("--labels", type=Path, required=True, help="Directory containing YOLO .txt labels")
    parser.add_argument("--output", type=Path, default=Path("dataset"), help="Dataset output directory")
    parser.add_argument("--val", type=float, default=0.2, help="Validation fraction")
    parser.add_argument("--test", type=float, default=0.1, help="Test fraction")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--copy", action="store_true", help="Copy files instead of moving them")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.val < 0 or args.test < 0 or args.val + args.test >= 1:
        raise SystemExit("--val and --test must be non-negative and sum to less than 1")

    images = sorted(path for path in args.images.iterdir() if path.suffix.lower() in IMAGE_EXTENSIONS)
    if not images:
        raise SystemExit(f"No supported images found in {args.images}")

    random.Random(args.seed).shuffle(images)
    test_count = round(len(images) * args.test)
    val_count = round(len(images) * args.val)
    splits = {
        "test": images[:test_count],
        "val": images[test_count : test_count + val_count],
        "train": images[test_count + val_count :],
    }
    transfer = shutil.copy2 if args.copy else shutil.move

    for split, split_images in splits.items():
        image_dir = args.output / "images" / split
        label_dir = args.output / "labels" / split
        image_dir.mkdir(parents=True, exist_ok=True)
        label_dir.mkdir(parents=True, exist_ok=True)
        for image in split_images:
            label = args.labels / f"{image.stem}.txt"
            if not label.exists():
                raise SystemExit(f"Missing label for image: {image.name}")
            transfer(str(image), str(image_dir / image.name))
            transfer(str(label), str(label_dir / label.name))

    print("Prepared dataset: " + ", ".join(f"{split}={len(files)}" for split, files in splits.items()))


if __name__ == "__main__":
    main()
