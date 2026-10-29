"""Convert a verified VisDrone source tree to an isolated ten-class YOLO dataset."""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

import yaml
from PIL import Image, UnidentifiedImageError

if __package__:
    from .verify_visdrone_source import (
        IMAGE_EXTENSIONS,
        REQUIRED_SPLITS,
        _find_split_directory,
        verify_source,
    )
else:
    from verify_visdrone_source import (
        IMAGE_EXTENSIONS,
        REQUIRED_SPLITS,
        _find_split_directory,
        verify_source,
    )


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT_ROOT / "dataset_visdrone10"
DEFAULT_OUTPUT = PROJECT_ROOT / "dataset_visdrone10_yolo"
CATEGORY_TO_CLASS = {category_id: category_id - 1 for category_id in range(1, 11)}
CLASS_NAMES = [
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
SPLIT_NAMES = {
    "VisDrone2019-DET-train": "train",
    "VisDrone2019-DET-val": "val",
}
SPLIT_NAMES_REVERSE = {value: key for key, value in SPLIT_NAMES.items()}
ZERO_AREA_EXCLUSION_PATHS = {
    "train/annotations/0000293_03401_d_0000939.txt:130",
    "train/annotations/9999985_00000_d_0000020.txt:12",
    "train/annotations/9999999_00590_d_0000267.txt:89",
}
BOUND_TOLERANCE = 1e-9


class ConversionError(ValueError):
    """Raised when source validation fails before dataset output is committed."""


def _resolve(path: Path | str) -> Path:
    resolved = Path(path).expanduser()
    if not resolved.is_absolute():
        resolved = PROJECT_ROOT / resolved
    return resolved.resolve()


def _check_paths(source: Path, output: Path) -> None:
    if not source.is_dir():
        raise FileNotFoundError(f"Staged source directory not found: {source}")
    if output.exists():
        raise FileExistsError(
            f"Output directory already exists; refusing to overwrite: {output}"
        )
    if source == output or source in output.parents or output in source.parents:
        raise ConversionError("Source and output directories must not contain each other.")
    protected_paths = {
        (PROJECT_ROOT / "dataset").resolve(),
        (PROJECT_ROOT / "dataset_visdrone10_source").resolve(),
        (PROJECT_ROOT / "dataset_visdrone10").resolve(),
        (PROJECT_ROOT / "runs" / "drone_person_vehicle").resolve(),
    }
    if any(
        output == protected
        or output in protected.parents
        or protected in output.parents
        for protected in protected_paths
    ):
        raise ConversionError(f"Refusing to use or contain a protected project path: {output}")


def _load_image_dimensions(image_path: Path) -> tuple[int, int]:
    try:
        with Image.open(image_path) as image:
            image.verify()
        with Image.open(image_path) as image:
            width, height = image.size
    except (OSError, UnidentifiedImageError) as error:
        raise ConversionError(f"Unreadable image {image_path}: {error}") from error
    if width <= 0 or height <= 0:
        raise ConversionError(f"Image has invalid dimensions: {image_path}")
    return width, height


def _parse_annotation_row(
    row: list[str],
    annotation_path: Path,
    row_number: int,
) -> list[int]:
    location = f"{annotation_path}:{row_number}"
    if len(row) != 8:
        raise ConversionError(
            f"{location}: expected 8 comma-separated fields, found {len(row)}"
        )
    try:
        values = [int(value.strip()) for value in row]
    except ValueError as error:
        raise ConversionError(f"{location}: expected integer fields") from error
    if values[5] not in range(12):
        raise ConversionError(f"{location}: unsupported VisDrone category {values[5]}")
    return values


def _normalize_box(
    x: int,
    y: int,
    box_width: int,
    box_height: int,
    image_width: int,
    image_height: int,
    location: str,
) -> tuple[float, float, float, float]:
    coordinates = (x, y, box_width, box_height, image_width, image_height)
    if not all(math.isfinite(value) for value in coordinates):
        raise ConversionError(f"{location}: non-finite bounding-box values")
    if box_width <= 0 or box_height <= 0:
        raise ConversionError(f"{location}: bounding-box dimensions must be positive")
    if x < 0 or y < 0 or x + box_width > image_width or y + box_height > image_height:
        raise ConversionError(
            f"{location}: bounding box lies outside image bounds "
            f"{image_width}x{image_height}"
        )

    normalized = (
        (x + box_width / 2) / image_width,
        (y + box_height / 2) / image_height,
        box_width / image_width,
        box_height / image_height,
    )
    center_x, center_y, width, height = normalized
    if not all(math.isfinite(value) for value in normalized):
        raise ConversionError(f"{location}: normalized box contains non-finite values")
    if not (
        0.0 <= center_x <= 1.0
        and 0.0 <= center_y <= 1.0
        and 0.0 < width <= 1.0
        and 0.0 < height <= 1.0
        and center_x - width / 2 >= -BOUND_TOLERANCE
        and center_y - height / 2 >= -BOUND_TOLERANCE
        and center_x + width / 2 <= 1.0 + BOUND_TOLERANCE
        and center_y + height / 2 <= 1.0 + BOUND_TOLERANCE
    ):
        raise ConversionError(f"{location}: normalized box is outside [0, 1]")
    return normalized


def _preflight(source: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    verification = verify_source(source)
    hard_errors: list[str] = []
    for split_name in REQUIRED_SPLITS:
        split_report = verification.get("splits", {}).get(split_name, {})
        for error in split_report.get("errors", []):
            if "zero-area annotation box(es)" not in error:
                hard_errors.append(f"{split_name}: {error}")
    if verification.get("missing_required_category_ids"):
        hard_errors.append(
            "Missing target categories: "
            + ", ".join(map(str, verification["missing_required_category_ids"]))
        )
    if hard_errors:
        raise ConversionError(
            "Staged source failed structural verification:\n- "
            + "\n- ".join(hard_errors)
        )

    plans: dict[str, dict[str, Any]] = {}
    total_exclusions: list[dict[str, Any]] = []
    class_counts: Counter[int] = Counter()
    ignored_category_counts: Counter[int] = Counter()
    source_annotation_rows = 0

    for source_split, output_split in SPLIT_NAMES.items():
        split_root = _find_split_directory(source, source_split)
        if split_root is None:
            raise ConversionError(f"Missing staged split: {source_split}")
        image_dir = split_root / "images"
        annotation_dir = split_root / "annotations"
        images = sorted(
            path
            for path in image_dir.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        )
        image_by_stem = {image.stem: image for image in images}
        annotations = sorted(annotation_dir.glob("*.txt"))
        annotation_by_stem = {annotation.stem: annotation for annotation in annotations}
        missing_annotations = sorted(set(image_by_stem) - set(annotation_by_stem))
        missing_images = sorted(set(annotation_by_stem) - set(image_by_stem))
        if missing_annotations or missing_images:
            raise ConversionError(
                f"{source_split}: image/annotation mismatch; "
                f"images without annotations={missing_annotations[:10]}, "
                f"annotations without images={missing_images[:10]}"
            )

        output_labels: dict[str, list[str]] = {image.name: [] for image in images}
        image_sizes = {
            image.stem: _load_image_dimensions(image)
            for image in images
        }
        split_exclusions: list[dict[str, Any]] = []
        split_class_counts: Counter[int] = Counter()
        split_ignored_counts: Counter[int] = Counter()

        for annotation in annotations:
            image = image_by_stem[annotation.stem]
            image_width, image_height = image_sizes[image.stem]
            with annotation.open("r", encoding="utf-8-sig", newline="") as handle:
                for row_number, row in enumerate(csv.reader(handle), start=1):
                    if not row or not any(value.strip() for value in row):
                        continue
                    source_annotation_rows += 1
                    values = _parse_annotation_row(row, annotation, row_number)
                    x, y, box_width, box_height, _, category_id, _, _ = values
                    location = (
                        f"{source_split}/annotations/{annotation.name}:{row_number}"
                    )

                    reasons: list[str] = []
                    if box_width < 0 or box_height < 0:
                        raise ConversionError(
                            f"{location}: negative bounding-box dimensions"
                        )
                    if box_width == 0:
                        reasons.append("zero_width_box")
                    if box_height == 0:
                        reasons.append("zero_height_box")

                    if category_id in (0, 11):
                        split_ignored_counts[category_id] += 1
                        reasons.append(
                            "ignored_region_category"
                            if category_id == 0
                            else "others_category"
                        )
                    if reasons:
                        exclusion = {
                            "split": output_split,
                            "annotation_filename": annotation.name,
                            "row_number": row_number,
                            "original_category": category_id,
                            "reason": reasons,
                        }
                        split_exclusions.append(exclusion)
                        total_exclusions.append(exclusion)
                        continue

                    class_id = CATEGORY_TO_CLASS.get(category_id)
                    if class_id is None:
                        raise ConversionError(
                            f"{location}: category {category_id} has no target mapping"
                        )
                    normalized = _normalize_box(
                        x,
                        y,
                        box_width,
                        box_height,
                        image_width,
                        image_height,
                        location,
                    )
                    split_class_counts[class_id] += 1
                    output_labels[image.name].append(
                        f"{class_id} "
                        + " ".join(f"{value:.10f}" for value in normalized)
                    )

        class_counts.update(split_class_counts)
        ignored_category_counts.update(split_ignored_counts)
        plans[output_split] = {
            "images": images,
            "labels": output_labels,
            "class_counts": split_class_counts,
            "ignored_category_counts": split_ignored_counts,
            "exclusions": split_exclusions,
        }

    conversion_data = {
        "source_annotation_row_count": source_annotation_rows,
        "class_counts": class_counts,
        "ignored_category_counts": ignored_category_counts,
        "exclusions": total_exclusions,
        "source_verification": verification,
    }
    return plans, conversion_data


def validate_converted_dataset(
    dataset_directory: Path | str,
    *,
    expected_yaml_path: Path | str | None = None,
) -> dict[str, Any]:
    root = Path(dataset_directory).resolve()
    yaml_path = root / "data.yaml"
    if not yaml_path.is_file():
        raise ConversionError(f"Dataset YAML is missing: {yaml_path}")
    with yaml_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    if config.get("names") != CLASS_NAMES:
        raise ConversionError("Dataset YAML class names/order do not match ten-class mapping.")
    expected_path = Path(expected_yaml_path).resolve() if expected_yaml_path else root
    if config.get("path") != str(expected_path):
        raise ConversionError("Dataset YAML path does not identify this dataset directory.")
    if set(config) != {"path", "train", "val", "names"}:
        raise ConversionError("Dataset YAML contains unexpected or missing keys.")

    split_counts: dict[str, dict[str, int]] = {}
    class_counts: Counter[int] = Counter()
    for split in ("train", "val"):
        image_dir = root / "images" / split
        label_dir = root / "labels" / split
        if not image_dir.is_dir() or not label_dir.is_dir():
            raise ConversionError(f"Missing generated {split} image or label directory.")
        images = sorted(
            path
            for path in image_dir.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        )
        labels = sorted(label_dir.glob("*.txt"))
        image_stems = {image.stem for image in images}
        label_stems = {label.stem for label in labels}
        if image_stems != label_stems:
            raise ConversionError(
                f"{split}: generated image/label pairs do not match; "
                f"missing labels={sorted(image_stems - label_stems)[:10]}, "
                f"orphan labels={sorted(label_stems - image_stems)[:10]}"
            )
        for label in labels:
            with label.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    values = line.split()
                    if len(values) != 5:
                        raise ConversionError(
                            f"{label}:{line_number}: expected five YOLO fields"
                        )
                    try:
                        class_id = int(values[0])
                        box = [float(value) for value in values[1:]]
                    except ValueError as error:
                        raise ConversionError(
                            f"{label}:{line_number}: invalid numeric YOLO label"
                        ) from error
                    if not 0 <= class_id < len(CLASS_NAMES):
                        raise ConversionError(
                            f"{label}:{line_number}: class ID {class_id} is outside 0-9"
                        )
                    if not all(math.isfinite(value) for value in box):
                        raise ConversionError(
                            f"{label}:{line_number}: non-finite YOLO coordinates"
                        )
                    center_x, center_y, width, height = box
                    if not (
                        0.0 <= center_x <= 1.0
                        and 0.0 <= center_y <= 1.0
                        and 0.0 < width <= 1.0
                        and 0.0 < height <= 1.0
                        and center_x - width / 2 >= -BOUND_TOLERANCE
                        and center_y - height / 2 >= -BOUND_TOLERANCE
                        and center_x + width / 2 <= 1.0 + BOUND_TOLERANCE
                        and center_y + height / 2 <= 1.0 + BOUND_TOLERANCE
                    ):
                        raise ConversionError(
                            f"{label}:{line_number}: YOLO box is outside valid bounds"
                        )
                    class_counts[class_id] += 1
        split_counts[split] = {
            "image_count": len(images),
            "label_file_count": len(labels),
            "label_row_count": _count_label_rows(labels),
        }
    return {
        "valid": True,
        "dataset_yaml": str(expected_path / "data.yaml"),
        "class_names": CLASS_NAMES,
        "splits": split_counts,
        "per_class_counts": {
            str(class_id): class_counts[class_id]
            for class_id in range(len(CLASS_NAMES))
        },
    }


def _count_label_rows(labels: list[Path]) -> int:
    count = 0
    for label in labels:
        with label.open("r", encoding="utf-8") as handle:
            count += sum(1 for line in handle if line.strip())
    return count


def convert_dataset(
    source_directory: Path | str = DEFAULT_SOURCE,
    output_directory: Path | str = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    source = _resolve(source_directory)
    output = _resolve(output_directory)
    _check_paths(source, output)
    plans, conversion_data = _preflight(source)

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_root = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.building-", dir=output.parent)
    )
    try:
        for split, plan in plans.items():
            image_output = temporary_root / "images" / split
            label_output = temporary_root / "labels" / split
            image_output.mkdir(parents=True)
            label_output.mkdir(parents=True)
            for image in plan["images"]:
                shutil.copy2(image, image_output / image.name)
                label_rows = plan["labels"][image.name]
                (label_output / f"{image.stem}.txt").write_text(
                    "\n".join(label_rows) + ("\n" if label_rows else ""),
                    encoding="utf-8",
                )

        dataset_yaml = {
            "path": str(output),
            "train": "images/train",
            "val": "images/val",
            "names": CLASS_NAMES,
        }
        (temporary_root / "data.yaml").write_text(
            yaml.safe_dump(dataset_yaml, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

        validation = validate_converted_dataset(
            temporary_root,
            expected_yaml_path=output,
        )
        expected_zero_area = {
            f"{SPLIT_NAMES_REVERSE[entry['split']]}/annotations/{entry['annotation_filename']}:{entry['row_number']}"
            for entry in conversion_data["exclusions"]
            if any(
                reason in {"zero_width_box", "zero_height_box"}
                for reason in entry["reason"]
            )
        }
        zero_area_exclusion_count = len(expected_zero_area)
        known_zero_area_files_present = all(
            (
                source
                / SPLIT_NAMES_REVERSE[path.split("/")[0]]
                / "annotations"
                / path.split("/")[2].split(":")[0]
            ).is_file()
            for path in ZERO_AREA_EXCLUSION_PATHS
        )
        observed_zero_area_paths = {
                f"{entry['split']}/annotations/{entry['annotation_filename']}:{entry['row_number']}"
                for entry in conversion_data["exclusions"]
                if any(
                    reason in {"zero_width_box", "zero_height_box"}
                    for reason in entry["reason"]
                )
        }
        known_zero_area_reported = (
            not known_zero_area_files_present
            or ZERO_AREA_EXCLUSION_PATHS <= observed_zero_area_paths
        )
        conversion_report: dict[str, Any] = {
            "source": str(source),
            "output": str(output),
            "category_mapping": {
                str(category): {
                    "class_id": class_id,
                    "name": CLASS_NAMES[class_id],
                }
                for category, class_id in CATEGORY_TO_CLASS.items()
            },
            "ignored_categories": {
                "0": {
                    "name": "ignored regions",
                    "annotation_count": conversion_data["ignored_category_counts"][0],
                    "policy": "excluded from target labels",
                },
                "11": {
                    "name": "others",
                    "annotation_count": conversion_data["ignored_category_counts"][11],
                    "policy": "excluded from target labels",
                },
            },
            "source_annotation_row_count": conversion_data["source_annotation_row_count"],
            "generated_label_counts_by_split": {
                split: {
                    str(class_id): plan["class_counts"][class_id]
                    for class_id in range(len(CLASS_NAMES))
                }
                for split, plan in plans.items()
            },
            "generated_label_counts_by_class": validation["per_class_counts"],
            "zero_area_exclusion_count": zero_area_exclusion_count,
            "zero_area_exclusions": [
                entry
                for entry in conversion_data["exclusions"]
                if any(
                    reason in {"zero_width_box", "zero_height_box"}
                    for reason in entry["reason"]
                )
            ],
            "all_exclusion_counts_by_reason": dict(
                Counter(
                    reason
                    for entry in conversion_data["exclusions"]
                    for reason in entry["reason"]
                )
            ),
            "exclusion_count": len(conversion_data["exclusions"]),
            "validation": validation,
            "known_three_zero_height_rows_reported": known_zero_area_reported,
        }
        (temporary_root / "conversion_report.json").write_text(
            json.dumps(conversion_report, indent=2),
            encoding="utf-8",
        )
        if known_zero_area_files_present and not known_zero_area_reported:
            raise ConversionError(
                "One or more of the three known zero-height source rows were not excluded."
            )
        if output.exists():
            raise FileExistsError(
                f"Output directory appeared during conversion; refusing to overwrite: {output}"
            )
        temporary_root.rename(output)
        conversion_report["validation"] = validate_converted_dataset(output)
        (output / "conversion_report.json").write_text(
            json.dumps(conversion_report, indent=2),
            encoding="utf-8",
        )
        return conversion_report
    except Exception:
        if temporary_root.exists():
            shutil.rmtree(temporary_root)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate an existing converted dataset without converting or changing it.",
    )
    args = parser.parse_args()
    if args.validate_only:
        validation = validate_converted_dataset(_resolve(args.output))
        print(json.dumps(validation, indent=2))
        return 0
    report = convert_dataset(args.source, args.output)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
