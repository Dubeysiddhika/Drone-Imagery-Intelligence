"""Create a repaired VisDrone source staging tree without changing the source."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path
from typing import Any

if __package__:
    from .verify_visdrone_source import (
        CATEGORY_NAMES,
        REQUIRED_SPLITS,
        _find_split_directory,
        verify_source,
    )
else:
    from verify_visdrone_source import (
        CATEGORY_NAMES,
        REQUIRED_SPLITS,
        _find_split_directory,
        verify_source,
    )


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "dataset_visdrone10"
REPAIR_SPLIT = "VisDrone2019-DET-train"
REPAIR_FILENAME = "9999974_00000_d_0000053.txt"


def _line_ending(line: str) -> str:
    if line.endswith("\r\n"):
        return "\r\n"
    if line.endswith("\n"):
        return "\n"
    if line.endswith("\r"):
        return "\r"
    return ""


def _valid_repaired_row(row: list[str]) -> bool:
    if len(row) != 8:
        return False
    try:
        values = [int(value.strip()) for value in row]
    except ValueError:
        return False
    return (
        0 <= values[5] <= 11
        and values[2] > 0
        and values[3] > 0
    )


def _normalise_trailing_comma_file(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        original_lines = handle.readlines()

    repaired_lines: list[str] = []
    changed_rows: list[dict[str, Any]] = []
    for line_number, original_line in enumerate(original_lines, start=1):
        ending = _line_ending(original_line)
        content = original_line[: len(original_line) - len(ending)] if ending else original_line
        try:
            parsed = next(csv.reader([content]))
        except (csv.Error, StopIteration):
            repaired_lines.append(original_line)
            continue

        if (
            parsed
            and parsed[-1].strip() == ""
            and content.rstrip().endswith(",")
        ):
            candidate = parsed[:-1]
            if _valid_repaired_row(candidate):
                repaired_content = ",".join(value.strip() for value in candidate)
                repaired_lines.append(repaired_content + ending)
                changed_rows.append(
                    {
                        "line": line_number,
                        "original_row": content,
                        "staged_row": repaired_content,
                    }
                )
                continue
        repaired_lines.append(original_line)

    if changed_rows:
        with path.open("w", encoding="utf-8", newline="") as handle:
            handle.writelines(repaired_lines)
    return changed_rows


def stage_source(source_directory: Path | str, output_directory: Path | str) -> dict[str, Any]:
    source = Path(source_directory).expanduser().resolve()
    output = Path(output_directory).expanduser().resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"Source directory does not exist: {source}")
    if output == source or source in output.parents or output in source.parents:
        raise ValueError("Source and staging directories must not contain each other.")
    if output.exists():
        raise FileExistsError(
            f"Staging directory already exists; refusing to overwrite: {output}"
        )

    source_report = verify_source(source)
    for split_name in REQUIRED_SPLITS:
        split = source_report["splits"][split_name]
        if not split["available"] or not split["images_directory_present"] or not split["annotations_directory_present"]:
            raise ValueError(
                f"Source split is incomplete and cannot be staged: {split_name}"
            )

    output.mkdir(parents=True, exist_ok=False)
    changed_files: list[str] = []
    changed_rows: list[dict[str, Any]] = []

    for split_name in (*REQUIRED_SPLITS, "VisDrone2019-DET-test-dev"):
        split_root = _find_split_directory(source, split_name)
        if split_root is None:
            if split_name in REQUIRED_SPLITS:
                raise ValueError(f"Missing split directory: {split_name}")
            continue
        staged_split = output / split_name
        shutil.copytree(split_root / "images", staged_split / "images")
        shutil.copytree(split_root / "annotations", staged_split / "annotations")

        if split_name == REPAIR_SPLIT:
            staged_annotation = staged_split / "annotations" / REPAIR_FILENAME
            if staged_annotation.is_file():
                file_changes = _normalise_trailing_comma_file(staged_annotation)
                if file_changes:
                    changed_files.append(f"{split_name}/annotations/{REPAIR_FILENAME}")
                    changed_rows.extend(
                        {
                            "file": f"{split_name}/annotations/{REPAIR_FILENAME}",
                            **change,
                        }
                        for change in file_changes
                    )

    staged_verification = verify_source(output)
    zero_area_annotations = [
        {
            "split": split_name,
            "file_line": example,
            "exclude_from_generated_training_labels": True,
            "reason": "zero-area box; source row is preserved unchanged",
        }
        for split_name, split_report in staged_verification["splits"].items()
        for example in split_report["zero_area_box_examples"]
    ]
    report: dict[str, Any] = {
        "source": str(source),
        "staging_directory": str(output),
        "changed_files": changed_files,
        "changed_row_count": len(changed_rows),
        "changed_rows": changed_rows,
        "zero_area_box_count": sum(
            split_report["zero_area_box_count"]
            for split_report in staged_verification["splits"].values()
        ),
        "zero_height_box_count": sum(
            split_report["zero_height_box_count"]
            for split_report in staged_verification["splits"].values()
        ),
        "zero_area_annotations": zero_area_annotations,
        "zero_area_training_label_policy": (
            "Exclude zero-width or zero-height boxes from generated YOLO labels. "
            "Do not alter source/staged annotation rows or invent coordinates."
        ),
        "source_categories": CATEGORY_NAMES,
        "verification": staged_verification,
    }
    report_path = output / "repair_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = stage_source(args.source, args.output)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
