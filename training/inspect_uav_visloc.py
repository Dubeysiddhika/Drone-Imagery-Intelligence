from pathlib import Path
import csv
from datetime import datetime

PROJECT_ROOT = Path(
    r"C:\Users\HP\GithubProjects\Drone-Imagery-Intelligence"
)

DATASET_ROOT = PROJECT_ROOT / "dataset2_clean" / "uav_visloc"


def parse_capture_time(value):
    """Parse known UAV-VisLoc date formats without inventing a time."""
    value = (value or "").strip()

    if not value:
        return None

    formats = (
        "%Y-%m-%dT%H:%M:%S",
        "%Y%m%d%H%M%S",
        "%Y%m%d%H%M%S%f",
    )

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).isoformat()
        except ValueError:
            continue

    return None


def find_image(folder, filename):
    """Find an image in the numbered folder or its drone subfolder."""
    if not filename:
        return None

    candidates = (
        folder / "drone" / filename,
        folder / filename,
    )

    for image_path in candidates:
        if image_path.is_file():
            return image_path

    return None


def main():
    if not DATASET_ROOT.is_dir():
        raise FileNotFoundError(
            f"Dataset folder not found: {DATASET_ROOT}"
        )

    csv_files = sorted(
        p for p in DATASET_ROOT.glob("*/*.csv")
        if p.name.lower() != "satellite_coordinates_range.csv"
    )

    total_rows = 0
    matched_images = 0
    missing_images = []
    invalid_coordinates = []
    missing_dates = []
    unparsed_dates = []
    height_missing = 0
    orientation_missing = 0

    print(f"Dataset: {DATASET_ROOT}")
    print(f"Metadata CSV files: {len(csv_files)}")

    for csv_path in csv_files:
        folder = csv_path.parent

        with csv_path.open(
            "r", encoding="utf-8-sig", newline=""
        ) as file:
            reader = csv.DictReader(file)

            required = {"filename", "date", "lat", "lon", "height"}
            if not required.issubset(set(reader.fieldnames or [])):
                print(f"WARNING: unexpected columns in {csv_path}")
                continue

            for row in reader:
                total_rows += 1
                filename = (row.get("filename") or "").strip()

                # FIX: Images are stored in the "drone" subfolder.
                image_path = find_image(folder, filename)

                if image_path is not None:
                    matched_images += 1
                else:
                    missing_images.append(
                        f"{csv_path.parent.name}/{filename}"
                    )

                try:
                    lat = float(row["lat"])
                    lon = float(row["lon"])

                    if not (
                        -90 <= lat <= 90
                        and -180 <= lon <= 180
                    ):
                        raise ValueError("coordinate out of range")

                except (ValueError, TypeError):
                    invalid_coordinates.append(
                        f"{csv_path.parent.name}/{filename}"
                    )

                date_value = (row.get("date") or "").strip()

                if not date_value:
                    missing_dates.append(
                        f"{csv_path.parent.name}/{filename}"
                    )
                elif parse_capture_time(date_value) is None:
                    unparsed_dates.append(
                        f"{csv_path.parent.name}/{filename}: "
                        f"{date_value}"
                    )

                if not (row.get("height") or "").strip():
                    height_missing += 1

                orientation_fields = {
                    "Omega", "Kappa", "Phi1", "Phi2"
                }

                if not orientation_fields.issubset(row.keys()):
                    orientation_missing += 1

    print("\n===== UAV-VisLoc inspection =====")
    print(f"Metadata rows: {total_rows}")
    print(f"Rows matching images: {matched_images}")
    print(f"Missing image files: {len(missing_images)}")
    print(
        f"Invalid/missing coordinates: "
        f"{len(invalid_coordinates)}"
    )
    print(f"Missing dates: {len(missing_dates)}")
    print(f"Unparsed dates: {len(unparsed_dates)}")
    print(f"Rows missing height: {height_missing}")
    print(
        f"Rows without orientation columns: "
        f"{orientation_missing}"
    )

    for title, items in (
        ("Missing images", missing_images),
        ("Invalid coordinates", invalid_coordinates),
        ("Unparsed dates", unparsed_dates),
    ):
        if items:
            print(f"\n{title} (first 10):")
            for item in items[:10]:
                print(f"  {item}")

    print("\nInspection complete. No files were modified.")


if __name__ == "__main__":
    main()
