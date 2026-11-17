from __future__ import annotations

import csv
from pathlib import Path

OUTPUT_DIR = Path(r"E:\Drone-image-intelligence\backend\training\uav_visloc\phase2_pair_preparation")
TRAIN_FLIGHTS = {"01", "03", "04", "08", "09", "11"}
VALIDATION_FLIGHTS = {"05"}
TEST_FLIGHTS = {"02", "10"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(rows: list[dict[str, str]], target_name: str) -> None:
    fieldnames = [
        "drone_image_filename",
        "flight_number",
        "satellite_map_id",
        "satellite_tile_id",
        "drone_latitude",
        "drone_longitude",
        "pair_type",
        "geographic_distance_km",
        "coverage_status",
        "overlap_or_coverage_status",
        "source_capture_time_raw",
        "source_height_m",
        "source_omega",
        "source_kappa",
        "source_phi1",
        "source_phi2",
        "validation_status",
    ]
    path = OUTPUT_DIR / target_name
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    positive = read_csv(OUTPUT_DIR / "positive_pairs.csv")
    negative = read_csv(OUTPUT_DIR / "negative_pairs.csv")
    combined = positive + negative

    split_rows = {
        "train_pairs.csv": [],
        "validation_pairs.csv": [],
        "test_pairs.csv": [],
    }

    for row in combined:
        flight = row["flight_number"]
        if flight in TRAIN_FLIGHTS:
            split_rows["train_pairs.csv"].append(row)
        elif flight in VALIDATION_FLIGHTS:
            split_rows["validation_pairs.csv"].append(row)
        elif flight in TEST_FLIGHTS:
            split_rows["test_pairs.csv"].append(row)

    for target_name, rows in split_rows.items():
        write_csv(rows, target_name)
        print(f"{target_name}: {len(rows)} rows")

    print("Final split rationale: flight-based geographic split with validation='05', test='02 and 10', train='01,03,04,08,09,11'.")


if __name__ == "__main__":
    main()
