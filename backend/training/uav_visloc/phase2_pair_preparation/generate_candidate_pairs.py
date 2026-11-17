from __future__ import annotations

import csv
import math
from pathlib import Path

DATASET_ROOT = Path(r"E:\Drone-image-intelligence\UAV_VisLoc_dataset")
PHASE1_DIR = Path(r"E:\Drone-image-intelligence\backend\training\uav_visloc\phase1_validation\outputs")
OUTPUT_DIR = Path(r"E:\Drone-image-intelligence\backend\training\uav_visloc\phase2_pair_preparation")
MIN_NEGATIVE_DISTANCE_KM = 75.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def read_metadata() -> list[dict[str, str]]:
    path = PHASE1_DIR / "consolidated_drone_metadata.csv"
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def read_tile_metadata() -> dict[str, list[dict[str, str]]]:
    path = OUTPUT_DIR / "satellite_tile_metadata.csv"
    tiles_by_flight: dict[str, list[dict[str, str]]] = {}
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            flight = str(row["flight_number"])
            tiles_by_flight.setdefault(flight, []).append(row)
    return tiles_by_flight


def read_validation_lookup() -> dict[tuple[str, str], dict[str, str]]:
    path = PHASE1_DIR / "drone_coordinate_validation.csv"
    with path.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    result: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        result[(str(row["flight"]), str(row["image_filename"]))] = row
    return result


def tile_contains(tile: dict[str, str], lat: float, lon: float) -> bool:
    north = max(float(tile["max_lat"]), float(tile["min_lat"]))
    south = min(float(tile["max_lat"]), float(tile["min_lat"]))
    east = max(float(tile["max_lon"]), float(tile["min_lon"]))
    west = min(float(tile["max_lon"]), float(tile["min_lon"]))
    return south <= lat <= north and west <= lon <= east


def make_positive_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    tiles_by_flight = read_tile_metadata()
    metadata_rows = read_metadata()
    validation_lookup = read_validation_lookup()

    for row in metadata_rows:
        flight = str(row["flight_number"])
        image_name = str(row["image_filename"])
        validation_row = validation_lookup.get((flight, image_name))
        if validation_row is None or validation_row.get("satellite_coverage_status") != "inside":
            continue
        lat = float(row["latitude"])
        lon = float(row["longitude"])
        matching_tiles = [tile for tile in tiles_by_flight.get(flight, []) if tile_contains(tile, lat, lon)]
        for tile in matching_tiles:
            mid_lat = (float(tile["max_lat"]) + float(tile["min_lat"])) / 2
            mid_lon = (float(tile["max_lon"]) + float(tile["min_lon"])) / 2
            distance_to_center = haversine_km(lat, lon, mid_lat, mid_lon)
            rows.append(
                {
                    "drone_image_filename": image_name,
                    "flight_number": flight,
                    "satellite_map_id": str(tile["parent_satellite_map_id"]),
                    "satellite_tile_id": str(tile["tile_id"]),
                    "drone_latitude": f"{lat:.8f}",
                    "drone_longitude": f"{lon:.8f}",
                    "pair_type": "candidate_positive",
                    "geographic_distance_km": f"{distance_to_center:.3f}",
                    "coverage_status": "center_inside_tile_bounds",
                    "overlap_or_coverage_status": "center_in_map_bounds",
                    "source_capture_time_raw": str(row.get("capture_time_raw", "")),
                    "source_height_m": str(row.get("height", "")),
                    "source_omega": str(row.get("omega", "")),
                    "source_kappa": str(row.get("kappa", "")),
                    "source_phi1": str(row.get("phi1", "")),
                    "source_phi2": str(row.get("phi2", "")),
                    "validation_status": "candidate_positive",
                }
            )
    return rows


def make_uncertain_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    metadata_rows = read_metadata()
    validation_lookup = read_validation_lookup()

    for row in metadata_rows:
        flight = str(row["flight_number"])
        image_name = str(row["image_filename"])
        validation_row = validation_lookup.get((flight, image_name))
        if validation_row and validation_row.get("satellite_coverage_status") == "outside":
            rows.append(
                {
                    "drone_image_filename": image_name,
                    "flight_number": flight,
                    "satellite_map_id": str(validation_row.get("satellite_map", "")),
                    "satellite_tile_id": "",
                    "drone_latitude": str(row.get("latitude", "")),
                    "drone_longitude": str(row.get("longitude", "")),
                    "pair_type": "uncertain",
                    "geographic_distance_km": "",
                    "coverage_status": "outside_validated_coverage",
                    "overlap_or_coverage_status": "requires_manual_verification",
                    "source_capture_time_raw": str(row.get("capture_time_raw", "")),
                    "source_height_m": str(row.get("height", "")),
                    "source_omega": str(row.get("omega", "")),
                    "source_kappa": str(row.get("kappa", "")),
                    "source_phi1": str(row.get("phi1", "")),
                    "source_phi2": str(row.get("phi2", "")),
                    "validation_status": "uncertain",
                }
            )
    return rows


def make_negative_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    metadata_rows = read_metadata()
    validation_lookup = read_validation_lookup()
    all_tiles = []
    with (OUTPUT_DIR / "satellite_tile_metadata.csv").open("r", encoding="utf-8", newline="") as fh:
        all_tiles = list(csv.DictReader(fh))

    for row in metadata_rows:
        flight = str(row["flight_number"])
        image_name = str(row["image_filename"])
        validation_row = validation_lookup.get((flight, image_name))
        if validation_row and validation_row.get("satellite_coverage_status") == "outside":
            continue

        lat = float(row["latitude"])
        lon = float(row["longitude"])
        candidates: list[tuple[float, dict[str, str]]] = []
        for tile in all_tiles:
            if str(tile["flight_number"]) == flight:
                continue
            mid_lat = (float(tile["max_lat"]) + float(tile["min_lat"])) / 2
            mid_lon = (float(tile["max_lon"]) + float(tile["min_lon"])) / 2
            distance = haversine_km(lat, lon, mid_lat, mid_lon)
            if distance >= MIN_NEGATIVE_DISTANCE_KM:
                candidates.append((distance, tile))
        if not candidates:
            continue
        distance, tile = max(candidates, key=lambda item: item[0])
        rows.append(
            {
                "drone_image_filename": image_name,
                "flight_number": flight,
                "satellite_map_id": str(tile["parent_satellite_map_id"]),
                "satellite_tile_id": str(tile["tile_id"]),
                "drone_latitude": f"{lat:.8f}",
                "drone_longitude": f"{lon:.8f}",
                "pair_type": "candidate_negative",
                "geographic_distance_km": f"{distance:.3f}",
                "coverage_status": "distant_geo_region",
                "overlap_or_coverage_status": "no_overlap_expected",
                "source_capture_time_raw": str(row.get("capture_time_raw", "")),
                "source_height_m": str(row.get("height", "")),
                "source_omega": str(row.get("omega", "")),
                "source_kappa": str(row.get("kappa", "")),
                "source_phi1": str(row.get("phi1", "")),
                "source_phi2": str(row.get("phi2", "")),
                "validation_status": "candidate_negative",
            }
        )
    return rows


def write_csv(rows: list[dict[str, str]], name: str) -> None:
    fields = [
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
    path = OUTPUT_DIR / name
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    positive_rows = make_positive_rows()
    uncertain_rows = make_uncertain_rows()
    negative_rows = make_negative_rows()

    write_csv(positive_rows, "positive_pairs.csv")
    write_csv(negative_rows, "negative_pairs.csv")
    write_csv(uncertain_rows, "uncertain_pairs.csv")

    print(f"Positive pairs: {len(positive_rows)}")
    print(f"Negative pairs: {len(negative_rows)}")
    print(f"Uncertain pairs: {len(uncertain_rows)}")


if __name__ == "__main__":
    main()
