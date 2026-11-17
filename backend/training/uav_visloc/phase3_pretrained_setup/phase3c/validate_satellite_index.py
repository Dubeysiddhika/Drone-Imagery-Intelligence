from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any

import numpy as np
import psutil

from phase3c_common import (
    BASE_DIR,
    configure_cpu,
    dinov2_descriptor,
    load_config,
    load_dinov2,
    metadata_by_tile_id,
    read_csv,
    write_csv_atomic,
    write_json_atomic,
)
from search_satellite_index import search


def point_inside_tile(row: dict[str, str], longitude: float, latitude: float) -> bool:
    a, b, c, d, e, f = json.loads(row["affine_transform"])
    determinant = a * e - b * d
    if determinant == 0:
        raise ValueError(f"Non-invertible tile affine transform: {row['tile_id']}")
    dx, dy = longitude - c, latitude - f
    pixel_col = (e * dx - b * dy) / determinant
    pixel_row = (-d * dx + a * dy) / determinant
    return (
        0 <= pixel_col <= int(row["tile_width_px"])
        and 0 <= pixel_row <= int(row["tile_height_px"])
    )


def parent_map_ids(raw_association: str) -> set[str]:
    parent_ids: set[str] = set()
    for filename in raw_association.split(";"):
        match = re.match(r"^(satellite\d+)", Path(filename.strip()).stem)
        if match:
            parent_ids.add(match.group(1))
    return parent_ids


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the five-flight initial retrieval experiment.")
    parser.add_argument("--config", type=Path, default=BASE_DIR / "index_config.yaml")
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Run an explicitly non-exhaustive pilot against a partial smoke-test index.",
    )
    args = parser.parse_args()
    config, paths = load_config(args.config)
    with (paths["index_metadata"] / "satellite_index_manifest.json").open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not manifest["complete"] and not args.allow_partial:
        raise RuntimeError(
            "Representative retrieval validation requires a complete tile index; "
            f"{manifest['missing_tile_count']} tile descriptors are missing."
        )
    with np.load(paths["global_features"] / "satellite_index.npz", allow_pickle=False) as index:
        index_ids = index["tile_ids"].astype(str)
        index_vectors = index["descriptors"].astype(np.float32)
    tile_metadata = metadata_by_tile_id(paths)
    drone_rows = read_csv(paths["phase1_metadata"])
    required_flights = ("01", "05", "09", "02", "10")
    representatives: dict[str, dict[str, str]] = {}
    for flight in required_flights:
        candidates = [row for row in drone_rows if row["flight_number"] == flight]
        if not candidates:
            raise ValueError(f"No Phase 1 drone metadata rows found for Flight {flight}")
        representatives[flight] = candidates[0]

    device = configure_cpu(config)
    model = load_dinov2(config, device)
    process = psutil.Process()
    results: list[dict[str, Any]] = []
    for flight in required_flights:
        drone = representatives[flight]
        image_path = Path(drone["image_path"])
        if not image_path.is_file():
            raise FileNotFoundError(f"Representative Flight {flight} image is missing: {image_path}")
        rss_before = process.memory_info().rss
        started = time.perf_counter()
        query = dinov2_descriptor(model, image_path, config, device)
        hits = search(
            query,
            index_ids,
            index_vectors,
            int(config["inference"]["retrieval_top_k"]),
        )
        latency_ms = (time.perf_counter() - started) * 1000
        rss_after = process.memory_info().rss
        expected_parents = parent_map_ids(drone["satellite_map"])
        if not expected_parents:
            raise ValueError(f"No satellite map association for Flight {flight}: {drone['satellite_map']}")
        expected_parent = sorted(expected_parents)[0]
        hit_rows: list[dict[str, Any]] = []
        for rank, (tile_id, score) in enumerate(hits, start=1):
            metadata = tile_metadata[tile_id]
            hit_rows.append(
                {
                    "rank": rank,
                    "tile_id": tile_id,
                    "cosine_similarity": score,
                    "parent_satellite_map_id": metadata["parent_satellite_map_id"],
                    "candidate_center_inside_tile": point_inside_tile(
                        metadata, float(drone["longitude"]), float(drone["latitude"])
                    ),
                    "parent_map_matches_ground_truth": metadata["parent_satellite_map_id"]
                    in expected_parents,
                }
            )
        results.append(
            {
                "flight_number": flight,
                "image_filename": drone["image_filename"],
                "expected_satellite_map": expected_parent,
                "latitude": float(drone["latitude"]),
                "longitude": float(drone["longitude"]),
                "retrieval_latency_ms": latency_ms,
                "rss_before_bytes": rss_before,
                "rss_after_bytes": rss_after,
                "top5": hit_rows,
            }
        )
        print(
            f"Flight {flight} {drone['image_filename']}: "
            f"{latency_ms:.1f} ms; RSS {rss_after / (1024 * 1024):.1f} MiB",
            flush=True,
        )

    paths["reports"].mkdir(parents=True, exist_ok=True)
    json_path = paths["reports"] / "retrieval_validation.json"
    csv_path = BASE_DIR / "retrieval_validation.csv"
    write_json_atomic(
        json_path,
        {
            "experiment_type": "initial pretrained retrieval experiment, not localization accuracy",
            "index_complete": manifest["complete"],
            "coverage_warning": manifest.get("warning"),
            "flights": list(required_flights),
            "results": results,
        },
    )
    flattened = []
    for result in results:
        for hit in result["top5"]:
            flattened.append(
                {
                    "flight_number": result["flight_number"],
                    "image_filename": result["image_filename"],
                    "expected_satellite_map": result["expected_satellite_map"],
                    "latitude": result["latitude"],
                    "longitude": result["longitude"],
                    "retrieval_latency_ms": result["retrieval_latency_ms"],
                    "rss_before_bytes": result["rss_before_bytes"],
                    "rss_after_bytes": result["rss_after_bytes"],
                    "index_complete": manifest["complete"],
                    **hit,
                }
            )
    write_csv_atomic(
        csv_path,
        [
            "flight_number",
            "image_filename",
            "expected_satellite_map",
            "latitude",
            "longitude",
            "retrieval_latency_ms",
            "rss_before_bytes",
            "rss_after_bytes",
            "index_complete",
            "rank",
            "tile_id",
            "cosine_similarity",
            "parent_satellite_map_id",
            "candidate_center_inside_tile",
            "parent_map_matches_ground_truth",
        ],
        flattened,
    )
    print(f"Wrote {json_path} and {csv_path}")


if __name__ == "__main__":
    main()
