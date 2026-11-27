"""Import every UAV-VisLoc row from the consolidated metadata CSV.

The default is a dry run. Use --commit only after reviewing the validation
summary. The import is idempotent and does not require the source image files
to be inside the repository; metadata remains useful even when the dataset is
stored on another drive.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.config import resolve_project_path  # noqa: E402
from app.models.database import SessionLocal, engine  # noqa: E402
from app.models.models import UAVVisLocRecord  # noqa: E402

CONSOLIDATED_CSV = resolve_project_path(
    os.environ.get("UAV_VISLOC_CONSOLIDATED_CSV"),
    "backend/training/uav_visloc/phase1_validation/outputs/consolidated_drone_metadata.csv",
)
DEFAULT_JSON_EXPORT = (
    PROJECT_ROOT
    / "backend"
    / "training"
    / "uav_visloc"
    / "phase1_validation"
    / "outputs"
    / "uav_visloc_metadata_export.json"
)

REQUIRED_COLUMNS = {
    "flight_number",
    "image_filename",
    "capture_time_raw",
    "latitude",
    "longitude",
}


def _number(value: Any, field: str, context: str, *, required: bool) -> float | None:
    raw = (value or "").strip()
    if not raw:
        if required:
            raise ValueError(f"{context}: missing {field}")
        return None
    try:
        number = float(raw)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{context}: invalid {field} value {raw!r}") from error
    if not math.isfinite(number):
        raise ValueError(f"{context}: non-finite {field}")
    return number


def load_metadata_rows(csv_path: Path = CONSOLIDATED_CSV) -> list[dict[str, Any]]:
    """Validate every consolidated metadata row and normalize it for SQL storage."""
    if not csv_path.is_file():
        raise FileNotFoundError(f"Consolidated UAV-VisLoc metadata CSV not found: {csv_path}")

    records: list[dict[str, Any]] = []
    errors: list[str] = []
    seen_paths: set[str] = set()

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - headers
        if missing:
            raise ValueError(f"Metadata CSV is missing required columns: {sorted(missing)}")

        for row_number, row in enumerate(reader, start=2):
            flight = (row.get("flight_number") or "").strip()
            filename = (row.get("image_filename") or "").strip()
            context = f"CSV row {row_number} ({filename or 'unnamed image'})"
            try:
                if not flight or flight in {".", ".."} or "/" in flight or "\\" in flight:
                    raise ValueError(f"{context}: invalid flight_number")
                if not filename or Path(filename).name != filename or "/" in filename or "\\" in filename:
                    raise ValueError(f"{context}: invalid image_filename")

                relative_path = (Path(flight) / "drone" / filename).as_posix()
                if relative_path in seen_paths:
                    raise ValueError(f"{context}: duplicate dataset image path {relative_path}")
                seen_paths.add(relative_path)

                latitude = _number(row.get("latitude"), "latitude", context, required=True)
                longitude = _number(row.get("longitude"), "longitude", context, required=True)
                if latitude is None or not -90 <= latitude <= 90:
                    raise ValueError(f"{context}: latitude is out of range")
                if longitude is None or not -180 <= longitude <= 180:
                    raise ValueError(f"{context}: longitude is out of range")

                capture_time = (row.get("capture_time_raw") or "").strip()
                metadata_csv = (row.get("source_csv") or f"{flight}/{flight}.csv").strip()
                if not metadata_csv:
                    raise ValueError(f"{context}: missing source_csv")

                records.append({
                    "relative_path": relative_path,
                    "filename": filename,
                    "capture_time_raw": capture_time or None,
                    "latitude": latitude,
                    "longitude": longitude,
                    "height": _number(row.get("height"), "height", context, required=False),
                    "omega": _number(row.get("omega"), "omega", context, required=False),
                    "kappa": _number(row.get("kappa"), "kappa", context, required=False),
                    "phi1": _number(row.get("phi1"), "phi1", context, required=False),
                    "phi2": _number(row.get("phi2"), "phi2", context, required=False),
                    "metadata_csv": metadata_csv.replace("\\", "/"),
                    "flight_number": flight,
                    "image_path": (row.get("image_path") or "").strip() or None,
                    "satellite_map": (row.get("satellite_map") or "").strip() or None,
                    "source_row": (row.get("source_row") or "").strip() or None,
                })
            except ValueError as error:
                errors.append(str(error))

    if errors:
        preview = "\n".join(f"  - {message}" for message in errors[:10])
        raise ValueError(
            f"Metadata validation failed for {len(errors)} row(s). No records were imported.\n"
            f"First errors:\n{preview}"
        )
    if not records:
        raise ValueError("The consolidated metadata CSV contains no image records.")
    return records


def write_json_export(records: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(records, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def import_records(records: list[dict[str, Any]], *, commit: bool) -> tuple[int, int, int]:
    """Insert new records and refresh existing rows by their stable relative path."""
    if not commit:
        return len(records), 0, 0

    UAVVisLocRecord.__table__.create(bind=engine, checkfirst=True)
    inserted = 0
    updated = 0
    with SessionLocal() as session:
        try:
            existing = {
                record.relative_path: record
                for record in session.query(UAVVisLocRecord).all()
            }
            model_fields = (
                "filename",
                "capture_time_raw",
                "latitude",
                "longitude",
                "height",
                "omega",
                "kappa",
                "phi1",
                "phi2",
                "metadata_csv",
            )
            for row in records:
                values = {key: row[key] for key in model_fields}
                current = existing.get(row["relative_path"])
                if current is None:
                    session.add(UAVVisLocRecord(
                        relative_path=row["relative_path"],
                        **values,
                    ))
                    inserted += 1
                    continue
                changed = any(getattr(current, key) != value for key, value in values.items())
                if changed:
                    for key, value in values.items():
                        setattr(current, key, value)
                    updated += 1
            session.commit()
            total = session.query(UAVVisLocRecord).count()
        except Exception:
            session.rollback()
            raise
    return inserted, updated, total


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate/export/import all UAV-VisLoc consolidated metadata rows."
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Write metadata rows to the configured application database.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=DEFAULT_JSON_EXPORT,
        help="Path for a normalized JSON export containing every dataset image record.",
    )
    args = parser.parse_args()

    records = load_metadata_rows()
    complete_orientation = sum(
        all(record[field] is not None for field in ("omega", "kappa", "phi1", "phi2"))
        for record in records
    )
    print(f"Source CSV: {CONSOLIDATED_CSV}")
    print(f"Validated UAV-VisLoc image records: {len(records)}")
    print(f"Records with complete orientation: {complete_orientation}")
    print(f"Records with partial orientation: {len(records) - complete_orientation}")
    print(f"Records with valid GPS coordinates: {len(records)}")

    write_json_export(records, args.json_output)
    print(f"JSON metadata export: {args.json_output}")

    if not args.commit:
        print("\nDRY RUN: database was not changed.")
        print("Review the counts and JSON export, then rerun with --commit to populate the website.")
        return

    inserted, updated, total = import_records(records, commit=True)
    print("\nUAV-VisLoc metadata import completed.")
    print(f"New database records: {inserted}")
    print(f"Existing records updated: {updated}")
    print(f"Total UAV-VisLoc records in application database: {total}")
    print("Open the UAV-VisLoc Dataset page to browse all records (25 per page).")


if __name__ == "__main__":
    main()
