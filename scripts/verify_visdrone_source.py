"""Inspect an extracted VisDrone2019-DET source without changing its files."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
REQUIRED_SPLITS = ("VisDrone2019-DET-train", "VisDrone2019-DET-val")
OPTIONAL_SPLITS = ("VisDrone2019-DET-test-dev",)
EXPECTED_CATEGORY_IDS = set(range(1, 11))
VALID_CATEGORY_IDS = set(range(0, 12))
CATEGORY_NAMES = {
    1: "pedestrian",
    2: "people",
    3: "bicycle",
    4: "car",
    5: "van",
    6: "truck",
    7: "tricycle",
    8: "awning-tricycle",
    9: "bus",
    10: "motor",
    11: "others",
}


def _split_directory_candidates(source: Path, split_name: str) -> list[Path]:
    candidates = [source / split_name, source / split_name / split_name]
    if source.name == split_name:
        candidates.extend((source, source / split_name))

    unique_candidates: list[Path] = []
    for candidate in candidates:
        if candidate not in unique_candidates:
            unique_candidates.append(candidate)
    return unique_candidates


def _find_split_directory(source: Path, split_name: str) -> Path | None:
    for candidate in _split_directory_candidates(source, split_name):
        if (candidate / "images").is_dir() or (candidate / "annotations").is_dir():
            return candidate
    return None


def _inspect_split(
    source: Path,
    split_name: str,
    *,
    required: bool,
) -> dict[str, Any]:
    split_root = _find_split_directory(source, split_name)
    if split_root is None:
        return {
            "available": False,
            "required": required,
            "images_directory_present": False,
            "annotations_directory_present": False,
            "image_count": 0,
            "annotation_file_count": 0,
            "annotation_row_count": 0,
            "malformed_row_count": 0,
            "malformed_row_examples": [],
            "zero_area_box_count": 0,
            "zero_height_box_count": 0,
            "zero_area_box_examples": [],
            "negative_bbox_size_count": 0,
            "category_ids": [],
            "unsupported_category_ids": [],
            "images_without_annotations": [],
            "annotations_without_images": [],
            "errors": [f"Missing {split_name}/images and {split_name}/annotations."],
        }

    image_dir = split_root / "images"
    annotation_dir = split_root / "annotations"
    images = (
        sorted(
            path
            for path in image_dir.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        )
        if image_dir.is_dir()
        else []
    )
    annotation_files = (
        sorted(annotation_dir.glob("*.txt"))
        if annotation_dir.is_dir()
        else []
    )
    image_stems = {path.stem for path in images}
    annotation_stems = {path.stem for path in annotation_files}
    observed_category_ids: set[int] = set()
    malformed_examples: list[str] = []
    annotation_row_count = 0
    malformed_row_count = 0
    zero_area_box_count = 0
    zero_height_box_count = 0
    zero_area_box_examples: list[str] = []
    negative_bbox_size_count = 0

    for annotation_file in annotation_files:
        with annotation_file.open("r", encoding="utf-8-sig", newline="") as handle:
            for line_number, row in enumerate(csv.reader(handle), start=1):
                if not row or not any(value.strip() for value in row):
                    continue
                annotation_row_count += 1

                category_id: int | None = None
                if len(row) > 5:
                    try:
                        category_id = int(row[5].strip())
                    except ValueError:
                        pass
                    else:
                        observed_category_ids.add(category_id)

                malformed = len(row) != 8
                values: list[int] | None = None
                if not malformed:
                    try:
                        values = [int(value.strip()) for value in row]
                    except ValueError:
                        malformed = True
                    else:
                        if values[5] not in VALID_CATEGORY_IDS:
                            malformed = True

                if malformed:
                    malformed_row_count += 1
                    if len(malformed_examples) < 10:
                        malformed_examples.append(
                            f"{annotation_file.name}:{line_number}"
                        )
                elif values is not None:
                    width, height = values[2], values[3]
                    if width < 0 or height < 0:
                        negative_bbox_size_count += 1
                    elif width == 0 or height == 0:
                        zero_area_box_count += 1
                        if height == 0:
                            zero_height_box_count += 1
                        zero_area_box_examples.append(
                            f"{annotation_file.name}:{line_number}"
                        )

    unsupported_category_ids = sorted(
        observed_category_ids - VALID_CATEGORY_IDS
    )
    errors: list[str] = []
    images_without_annotations = sorted(image_stems - annotation_stems)
    annotations_without_images = sorted(annotation_stems - image_stems)

    if not image_dir.is_dir():
        errors.append(f"Missing {split_name}/images directory.")
    if required and not annotation_dir.is_dir():
        errors.append(f"Missing {split_name}/annotations directory.")
    if required and not images:
        errors.append(f"No supported images found in {split_name}.")
    if required and not annotation_files:
        errors.append(f"No original annotation files found in {split_name}.")
    if required and images_without_annotations:
        errors.append(
            f"{len(images_without_annotations)} image(s) have no annotation file."
        )
    if annotations_without_images:
        errors.append(
            f"{len(annotations_without_images)} annotation file(s) have no matching image."
        )
    if malformed_row_count:
        errors.append(f"Found {malformed_row_count} malformed annotation row(s).")
    if negative_bbox_size_count:
        errors.append(
            f"Found {negative_bbox_size_count} annotation row(s) with negative "
            "bounding-box dimensions."
        )
    if zero_area_box_count:
        errors.append(
            f"Found {zero_area_box_count} zero-area annotation box(es) "
            f"({zero_height_box_count} with zero height); these rows must be "
            "excluded from generated training labels."
        )
    if unsupported_category_ids:
        errors.append(
            "Unsupported category ID(s): "
            + ", ".join(map(str, unsupported_category_ids))
            + "."
        )

    return {
        "available": True,
        "required": required,
        "images_directory_present": image_dir.is_dir(),
        "annotations_directory_present": annotation_dir.is_dir(),
        "image_count": len(images),
        "annotation_file_count": len(annotation_files),
        "annotation_row_count": annotation_row_count,
        "malformed_row_count": malformed_row_count,
        "malformed_row_examples": malformed_examples,
        "zero_area_box_count": zero_area_box_count,
        "zero_height_box_count": zero_height_box_count,
        "zero_area_box_examples": zero_area_box_examples,
        "negative_bbox_size_count": negative_bbox_size_count,
        "category_ids": sorted(observed_category_ids),
        "unsupported_category_ids": unsupported_category_ids,
        "images_without_annotations": images_without_annotations,
        "annotations_without_images": annotations_without_images,
        "errors": errors,
    }


def verify_source(source_directory: Path | str) -> dict[str, Any]:
    """Return dataset inventory and readiness findings; never write to the source."""
    source = Path(source_directory).expanduser().resolve()
    if not source.is_dir():
        return {
            "source": str(source),
            "ready_for_ten_class_conversion": False,
            "observed_category_ids": [],
            "missing_required_category_ids": sorted(EXPECTED_CATEGORY_IDS),
            "splits": {},
            "errors": [f"Source directory does not exist: {source}"],
        }

    splits = {
        split_name: _inspect_split(source, split_name, required=True)
        for split_name in REQUIRED_SPLITS
    }
    for split_name in OPTIONAL_SPLITS:
        if _find_split_directory(source, split_name) is not None:
            splits[split_name] = _inspect_split(
                source,
                split_name,
                required=False,
            )

    observed_category_ids = sorted(
        {
            category_id
            for split in splits.values()
            for category_id in split["category_ids"]
        }
    )
    train_validation_category_ids = {
        category_id
        for split_name in REQUIRED_SPLITS
        for category_id in splits[split_name]["category_ids"]
    }
    missing_category_ids = sorted(
        EXPECTED_CATEGORY_IDS - train_validation_category_ids
    )
    errors = [
        f"{split_name}: {error}"
        for split_name, split in splits.items()
        for error in split["errors"]
    ]
    if missing_category_ids:
        errors.append(
            "Required VisDrone object category ID(s) not observed in original "
            "annotations: "
            + ", ".join(map(str, missing_category_ids))
            + "."
        )

    ready = not errors and not missing_category_ids
    return {
        "source": str(source),
        "ready_for_ten_class_conversion": ready,
        "zero_area_training_label_policy": (
            "Exclude zero-width or zero-height rows from generated training "
            "labels; preserve the original rows in the staged annotations."
        ),
        "observed_category_ids": observed_category_ids,
        "train_validation_category_ids": sorted(train_validation_category_ids),
        "category_names_observed": {
            str(category_id): CATEGORY_NAMES[category_id]
            for category_id in observed_category_ids
            if category_id in CATEGORY_NAMES
        },
        "missing_required_category_ids": missing_category_ids,
        "splits": splits,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Directory containing extracted VisDrone2019-DET split folders.",
    )
    args = parser.parse_args()
    report = verify_source(args.source)
    print(json.dumps(report, indent=2))
    return 0 if report["ready_for_ten_class_conversion"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
