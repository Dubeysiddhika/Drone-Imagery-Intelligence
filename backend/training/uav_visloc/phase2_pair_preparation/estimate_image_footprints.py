from __future__ import annotations

import csv
from pathlib import Path

from PIL import Image

PHASE1_DIR = Path(r"E:\Drone-image-intelligence\backend\training\uav_visloc\phase1_validation\outputs")
DATASET_ROOT = Path(r"E:\Drone-image-intelligence\UAV_VisLoc_dataset")
OUTPUT_DIR = Path(r"E:\Drone-image-intelligence\backend\training\uav_visloc\phase2_pair_preparation")


def main() -> None:
    metadata_csv = PHASE1_DIR / "consolidated_drone_metadata.csv"
    if not metadata_csv.exists():
        raise FileNotFoundError(f"Missing metadata export: {metadata_csv}")

    rows: list[dict[str, object]] = []
    with metadata_csv.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            flight_number = str(row["flight_number"])
            image_name = str(row["image_filename"])
            image_path = DATASET_ROOT / flight_number / "drone" / image_name
            image_width = image_height = None
            if image_path.exists():
                with Image.open(image_path) as img:
                    image_width, image_height = img.size

            altitude_m = row.get("height")
            has_altitude = altitude_m not in (None, "")
            has_pose = all(row.get(field) not in (None, "") for field in ("omega", "kappa", "phi1", "phi2"))
            has_intrinsics = False
            rows.append(
                {
                    "flight_number": flight_number,
                    "image_filename": image_name,
                    "image_path": str(image_path),
                    "image_width_px": image_width,
                    "image_height_px": image_height,
                    "altitude_m": altitude_m,
                    "has_altitude": has_altitude,
                    "has_pose_angles": has_pose,
                    "has_camera_intrinsics": has_intrinsics,
                    "footprint_estimation_status": "not_feasible_without_intrinsics",
                    "required_assumptions": "camera focal length, sensor size, and terrain elevation model required; no calibration metadata is documented in the dataset",
                }
            )

    output = OUTPUT_DIR / "footprint_estimation_summary.csv"
    fieldnames = [
        "flight_number",
        "image_filename",
        "image_path",
        "image_width_px",
        "image_height_px",
        "altitude_m",
        "has_altitude",
        "has_pose_angles",
        "has_camera_intrinsics",
        "footprint_estimation_status",
        "required_assumptions",
    ]
    with output.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "total_images": len(rows),
        "with_altitude": sum(1 for row in rows if row["has_altitude"]),
        "with_pose_angles": sum(1 for row in rows if row["has_pose_angles"]),
        "with_camera_intrinsics": 0,
        "not_feasible_without_intrinsics": sum(1 for row in rows if row["footprint_estimation_status"] == "not_feasible_without_intrinsics"),
    }

    print(summary)
    print(f"Wrote footprint assessment to {output}")


if __name__ == "__main__":
    main()
