
"""Validate and import UAV-VisLoc metadata into the project database.

Default mode is dry-run. Pass --commit to write new records.
"""

import argparse
import csv
import math
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_ROOT = PROJECT_ROOT / "dataset2_clean" / "uav_visloc"
BACKEND_DIR = PROJECT_ROOT / "backend"

# Make the existing backend package importable when run from the project root.
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import inspect  # noqa: E402

from app.models.database import SessionLocal, engine  # noqa: E402
from app.models.models import UAVVisLocRecord  # noqa: E402


REQUIRED_COLUMNS = {"filename", "date", "lat", "lon", "height"}
ORIENTATION_COLUMNS = ("Omega", "Kappa", "Phi1", "Phi2")


def optional_float(value, field_name, context):
    """Convert a numeric field, preserving blank values as None."""
    value = (value or "").strip()

    if not value:
        return None

    try:
        number = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"{context}: invalid {field_name} value {value!r}"
        ) from exc

    if not math.isfinite(number):
        raise ValueError(f"{context}: non-finite {field_name}")

    return number


def load_and_validate_records():
    """Read every numbered-folder CSV and validate its matching image."""
    if not DATASET_ROOT.is_dir():
        raise FileNotFoundError(
            f"Dataset folder not found: {DATASET_ROOT}"
        )

    csv_files = sorted(DATASET_ROOT.glob("*/*.csv"))
    if not csv_files:
        raise FileNotFoundError(
            f"No metadata CSV files found under {DATASET_ROOT}"
        )

    records = []
    errors = []
    seen_paths = set()

    for csv_path in csv_files:
        with csv_path.open(
            "r", encoding="utf-8-sig", newline=""
        ) as csv_file:
            reader = csv.DictReader(csv_file)
            headers = set(reader.fieldnames or [])

            if not REQUIRED_COLUMNS.issubset(headers):
                errors.append(
                    f"{csv_path.relative_to(DATASET_ROOT)}: "
                    f"missing columns {sorted(REQUIRED_COLUMNS - headers)}"
                )
                continue

            for row_number, row in enumerate(reader, start=2):
                filename = (row.get("filename") or "").strip()
                context = (
                    f"{csv_path.relative_to(DATASET_ROOT)} "
                    f"row {row_number} ({filename})"
                )

                try:
                    if not filename or Path(filename).name != filename:
                        raise ValueError(
                            f"{context}: invalid filename"
                        )

                    image_path = csv_path.parent / "drone" / filename
                    if not image_path.is_file():
                        raise ValueError(
                            f"{context}: image not found at "
                            f"{image_path.relative_to(DATASET_ROOT)}"
                        )

                    relative_path = image_path.relative_to(
                        DATASET_ROOT
                    ).as_posix()

                    if relative_path in seen_paths:
                        raise ValueError(
                            f"{context}: duplicate dataset image path "
                            f"{relative_path}"
                        )
                    seen_paths.add(relative_path)

                    latitude = optional_float(
                        row.get("lat"), "latitude", context
                    )
                    longitude = optional_float(
                        row.get("lon"), "longitude", context
                    )
                    height = optional_float(
                        row.get("height"), "height", context
                    )

                    if latitude is None or not -90 <= latitude <= 90:
                        raise ValueError(
                            f"{context}: missing or out-of-range latitude"
                        )

                    if longitude is None or not -180 <= longitude <= 180:
                        raise ValueError(
                            f"{context}: missing or out-of-range longitude"
                        )

                    capture_time_raw = (
                        row.get("date") or ""
                    ).strip()

                    if not capture_time_raw:
                        raise ValueError(
                            f"{context}: missing capture date"
                        )

                    orientation = {
                        "omega": optional_float(
                            row.get("Omega"), "Omega", context
                        ),
                        "kappa": optional_float(
                            row.get("Kappa"), "Kappa", context
                        ),
                        "phi1": optional_float(
                            row.get("Phi1"), "Phi1", context
                        ),
                        "phi2": optional_float(
                            row.get("Phi2"), "Phi2", context
                        ),
                    }

                    records.append(
                        {
                            "relative_path": relative_path,
                            "filename": filename,
                            "capture_time_raw": capture_time_raw,
                            "latitude": latitude,
                            "longitude": longitude,
                            "height": height,
                            **orientation,
                            "metadata_csv": csv_path.relative_to(
                                DATASET_ROOT
                            ).as_posix(),
                        }
                    )

                except ValueError as exc:
                    errors.append(str(exc))

    print(f"Dataset directory: {DATASET_ROOT}")
    print(f"Metadata CSV files: {len(csv_files)}")
    print(f"Validated metadata rows: {len(records)}")
    print(f"Validation errors: {len(errors)}")

    if errors:
        print("\nFirst validation errors:")
        for error in errors[:10]:
            print(f"  - {error}")
        raise SystemExit(
            "Import stopped. No database records were written."
        )

    return records


def main():
    parser = argparse.ArgumentParser(
        description="Import UAV-VisLoc metadata."
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Write new records to the configured database.",
    )
    args = parser.parse_args()

    records = load_and_validate_records()

    table_exists = inspect(engine).has_table(
        UAVVisLocRecord.__tablename__
    )

    if args.commit and not table_exists:
        UAVVisLocRecord.__table__.create(
            bind=engine,
            checkfirst=True,
        )
        table_exists = True

    if table_exists:
        with SessionLocal() as session:
            existing_paths = {
                path
                for (path,) in session.query(
                    UAVVisLocRecord.relative_path
                ).all()
            }
    else:
        existing_paths = set()

    new_records = [
        record
        for record in records
        if record["relative_path"] not in existing_paths
    ]

    already_imported = len(records) - len(new_records)

    print(f"Records already in database: {already_imported}")
    print(f"New records ready to import: {len(new_records)}")

    if not args.commit:
        print("\nDRY RUN: no database records were written.")
        print("After checking the results, run with --commit to import.")
        return

    if new_records:
        with SessionLocal() as session:
            try:
                session.add_all(
                    UAVVisLocRecord(**record)
                    for record in new_records
                )
                session.commit()
            except Exception:
                session.rollback()
                raise

    with SessionLocal() as session:
        final_count = session.query(UAVVisLocRecord).count()

    print("\nImport completed.")
    print(f"Records added this run: {len(new_records)}")
    print(f"Total UAV-VisLoc records in database: {final_count}")


if __name__ == "__main__":
    main()
