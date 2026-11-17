from __future__ import annotations

import csv
import re
from pathlib import Path

import rasterio

DATASET_ROOT = Path(r"E:\Drone-image-intelligence\UAV_VisLoc_dataset")
OUTPUT_DIR = Path(r"E:\Drone-image-intelligence\backend\training\uav_visloc\phase2_pair_preparation")
PHASE1_DIR = Path(r"E:\Drone-image-intelligence\backend\training\uav_visloc\phase1_validation\outputs")


def parent_map_id(tile_name: str) -> str:
    stem = Path(tile_name).stem
    match = re.match(r"^(satellite\d+)", stem)
    if match:
        return match.group(1)
    return stem


def main() -> None:
    source_csv = PHASE1_DIR / "satellite_map_metadata.csv"
    if not source_csv.exists():
        raise FileNotFoundError(f"Missing phase 1 metadata file: {source_csv}")

    tile_rows: list[dict[str, object]] = []
    with source_csv.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            flight_number = str(row["flight_number"]).strip()
            tile_name = str(row["filename"]).strip()
            source_path = DATASET_ROOT / flight_number / tile_name
            if not source_path.exists():
                raise FileNotFoundError(f"Missing source TIFF: {source_path}")

            with rasterio.open(source_path) as ds:
                row_data = {
                    "flight_number": flight_number,
                    "parent_satellite_map_id": parent_map_id(tile_name),
                    "tile_id": tile_name,
                    "source_file": str(source_path),
                    "crs": str(ds.crs) if ds.crs else "",
                    "width_px": int(ds.width),
                    "height_px": int(ds.height),
                    "min_lon": float(ds.bounds.left),
                    "min_lat": float(ds.bounds.bottom),
                    "max_lon": float(ds.bounds.right),
                    "max_lat": float(ds.bounds.top),
                    "pixel_resolution_x": float(ds.res[0]),
                    "pixel_resolution_y": float(ds.res[1]),
                    "nodata_value": "" if ds.nodata is None else str(ds.nodata),
                    "affine_transform": str(ds.transform),
                    "adjacency_group": "flight09_2x2" if flight_number == "09" else "single_tile",
                    "tile_status": "adjacent_tile" if flight_number == "09" else "standard",
                }
                tile_rows.append(row_data)

    output_csv = OUTPUT_DIR / "satellite_tile_metadata.csv"
    fieldnames = [
        "flight_number",
        "parent_satellite_map_id",
        "tile_id",
        "source_file",
        "crs",
        "width_px",
        "height_px",
        "min_lon",
        "min_lat",
        "max_lon",
        "max_lat",
        "pixel_resolution_x",
        "pixel_resolution_y",
        "nodata_value",
        "affine_transform",
        "adjacency_group",
        "tile_status",
    ]
    with output_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(tile_rows)

    print(f"Prepared {len(tile_rows)} satellite tile records to {output_csv}")
    print(f"Flight 09 tile count: {sum(1 for row in tile_rows if row['flight_number'] == '09')}")


if __name__ == "__main__":
    main()
