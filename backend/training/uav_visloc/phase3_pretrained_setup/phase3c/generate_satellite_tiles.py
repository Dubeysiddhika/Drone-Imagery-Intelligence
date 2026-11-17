from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from PIL import Image
from rasterio.windows import Window

from phase3c_common import BASE_DIR, load_config, read_csv, write_csv_atomic, write_json_atomic

METADATA_FIELDS = [
    "tile_id",
    "parent_satellite_map_id",
    "parent_tile_id",
    "parent_tiff_filename",
    "source_flight_or_region",
    "source_file",
    "source_width_px",
    "source_height_px",
    "parent_affine_transform",
    "parent_min_lon",
    "parent_min_lat",
    "parent_max_lon",
    "parent_max_lat",
    "tile_width_px",
    "tile_height_px",
    "tile_row_offset_px",
    "tile_col_offset_px",
    "crs",
    "affine_transform",
    "transform_a",
    "transform_b",
    "transform_c",
    "transform_d",
    "transform_e",
    "transform_f",
    "pixel_to_geographic_mapping",
    "min_lon",
    "min_lat",
    "max_lon",
    "max_lat",
    "geo_corners_json",
    "adjacency_group",
    "parent_tile_status",
    "image_relative_path",
]


def valid_transform(transform: rasterio.Affine) -> bool:
    values = (transform.a, transform.b, transform.c, transform.d, transform.e, transform.f)
    determinant = transform.a * transform.e - transform.b * transform.d
    return all(math.isfinite(value) for value in values) and math.isfinite(determinant) and determinant != 0


def window_starts(dimension: int, tile_size: int, stride: int) -> list[int]:
    if dimension <= tile_size:
        return [0]
    starts = list(range(0, dimension - tile_size + 1, stride))
    final_start = dimension - tile_size
    if starts[-1] != final_start:
        starts.append(final_start)
    return starts


def parent_map_id(tile_name: str, supplied_id: str) -> str:
    if supplied_id:
        return supplied_id
    match = re.match(r"^(satellite\d+)", Path(tile_name).stem)
    return match.group(1) if match else Path(tile_name).stem


def verify_flight09(source_rows: list[dict[str, str]]) -> dict[str, Any]:
    rows = [row for row in source_rows if row["flight_number"].strip() == "09"]
    if len(rows) != 4:
        raise ValueError(f"Expected four Phase 2A Flight 09 source tiles; found {len(rows)}.")

    bounds: list[tuple[float, float, float, float]] = []
    crs_values: set[str] = set()
    for row in rows:
        with rasterio.open(row["source_file"]) as source:
            if source.crs is None or not valid_transform(source.transform):
                raise ValueError(f"Flight 09 source has invalid georeferencing: {row['source_file']}")
            bounds.append((source.bounds.left, source.bounds.bottom, source.bounds.right, source.bounds.top))
            crs_values.add(str(source.crs))
    if len(crs_values) != 1:
        raise ValueError(f"Flight 09 source tiles have inconsistent CRS values: {crs_values}")

    x_edges = sorted({round(value, 12) for box in bounds for value in (box[0], box[2])})
    y_edges = sorted({round(value, 12) for box in bounds for value in (box[1], box[3])})
    if len(x_edges) != 3 or len(y_edges) != 3:
        raise ValueError("Flight 09 bounds do not form a 2x2 grid.")
    cells: set[tuple[int, int]] = set()
    tolerance = 1e-9
    for left, bottom, right, top in bounds:
        col = next((i for i in range(2) if abs(left - x_edges[i]) < tolerance and abs(right - x_edges[i + 1]) < tolerance), None)
        row = next((i for i in range(2) if abs(bottom - y_edges[i]) < tolerance and abs(top - y_edges[i + 1]) < tolerance), None)
        if col is None or row is None or (row, col) in cells:
            raise ValueError("Flight 09 tiles overlap, have gaps, or do not form four adjoining grid cells.")
        cells.add((row, col))
    if cells != {(0, 0), (0, 1), (1, 0), (1, 1)}:
        raise ValueError(f"Flight 09 does not cover all four 2x2 positions: {cells}")
    return {
        "source_tile_count": len(rows),
        "arrangement": "2x2",
        "crs": next(iter(crs_values)),
        "bounds": bounds,
        "shared_edges_verified": True,
    }


def is_empty_patch(array: np.ndarray, valid_mask: np.ndarray) -> bool:
    if valid_mask.size == 0 or not np.any(valid_mask):
        return True
    valid_pixels = array[:, valid_mask]
    return not np.any(valid_pixels)


def valid_existing_patch(path: Path, expected_size: tuple[int, int]) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    try:
        with Image.open(path) as image:
            if image.size != expected_size:
                return False
            image.verify()
        return True
    except (OSError, ValueError):
        return False


def tile_record(
    source: rasterio.DatasetReader,
    source_row: dict[str, str],
    tile_id: str,
    parent_map: str,
    window: Window,
    output_path: Path,
    tile_root: Path,
) -> dict[str, Any]:
    transform = source.window_transform(window)
    corners = [
        transform * (0, 0),
        transform * (window.width, 0),
        transform * (window.width, window.height),
        transform * (0, window.height),
    ]
    xs = [point[0] for point in corners]
    ys = [point[1] for point in corners]
    a, b, c, d, e, f = tuple(transform)[:6]
    relative = output_path.relative_to(tile_root).as_posix()
    return {
        "tile_id": tile_id,
        "parent_satellite_map_id": parent_map,
        "parent_tile_id": source_row["tile_id"],
        "parent_tiff_filename": Path(source_row["source_file"]).name,
        "source_flight_or_region": source_row["flight_number"],
        "source_file": source_row["source_file"],
        "source_width_px": source.width,
        "source_height_px": source.height,
        "parent_affine_transform": json.dumps(tuple(source.transform)[:6], separators=(",", ":")),
        "parent_min_lon": source.bounds.left,
        "parent_min_lat": source.bounds.bottom,
        "parent_max_lon": source.bounds.right,
        "parent_max_lat": source.bounds.top,
        "tile_width_px": int(window.width),
        "tile_height_px": int(window.height),
        "tile_row_offset_px": int(window.row_off),
        "tile_col_offset_px": int(window.col_off),
        "crs": str(source.crs),
        "affine_transform": json.dumps([a, b, c, d, e, f], separators=(",", ":")),
        "transform_a": a,
        "transform_b": b,
        "transform_c": c,
        "transform_d": d,
        "transform_e": e,
        "transform_f": f,
        "pixel_to_geographic_mapping": f"X={a}*col+{b}*row+{c};Y={d}*col+{e}*row+{f}",
        "min_lon": min(xs),
        "min_lat": min(ys),
        "max_lon": max(xs),
        "max_lat": max(ys),
        "geo_corners_json": json.dumps(corners, separators=(",", ":")),
        "adjacency_group": source_row.get("adjacency_group", "single_tile"),
        "parent_tile_status": source_row.get("tile_status", "standard"),
        "image_relative_path": relative,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate georeferenced, overlapping satellite patches.")
    parser.add_argument("--config", type=Path, default=BASE_DIR / "index_config.yaml")
    args = parser.parse_args()
    config, paths = load_config(args.config)
    source_rows = read_csv(paths["phase2_tile_metadata"])
    if len(source_rows) != 14:
        raise ValueError(f"Expected 14 Phase 2A TIFF records; found {len(source_rows)}.")
    flight09_check = verify_flight09(source_rows)

    tile_size = int(config["tiling"]["size_px"])
    overlap = float(config["tiling"]["overlap_fraction"])
    if tile_size <= 0 or not 0 <= overlap < 1:
        raise ValueError("Tile size must be positive and overlap must be in [0, 1).")
    stride = max(1, round(tile_size * (1.0 - overlap)))
    output_rows: list[dict[str, Any]] = []
    skipped_empty = 0
    for source_row in source_rows:
        source_path = Path(source_row["source_file"])
        if not source_path.is_file():
            raise FileNotFoundError(f"Phase 2A source TIFF is missing: {source_path}")
        with rasterio.open(source_path) as source:
            if source.count < 3 or source.crs is None or not valid_transform(source.transform):
                raise ValueError(f"Cannot preserve RGB georeferencing for {source_path}")
            parent_id = parent_map_id(source_path.name, source_row.get("parent_satellite_map_id", ""))
            parent_stem = source_path.stem
            x_starts = window_starts(source.width, tile_size, stride)
            y_starts = window_starts(source.height, tile_size, stride)
            for row_offset in y_starts:
                for col_offset in x_starts:
                    width = min(tile_size, source.width - col_offset)
                    height = min(tile_size, source.height - row_offset)
                    window = Window.from_slices(
                        (row_offset, row_offset + height),
                        (col_offset, col_offset + width),
                    )
                    tile_id = (
                        f"{source_row['flight_number']}_{parent_stem}"
                        f"_r{row_offset:06d}_c{col_offset:06d}"
                    )
                    relative_image = (
                        Path(source_row["flight_number"])
                        / parent_stem
                        / f"{tile_id}.jpg"
                    )
                    output_path = paths["satellite_tiles"] / relative_image
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    if not valid_existing_patch(output_path, (width, height)):
                        pixels = source.read(indexes=(1, 2, 3), window=window, out_dtype="uint8")
                        valid_mask = source.dataset_mask(window=window) > 0
                        if is_empty_patch(pixels, valid_mask):
                            skipped_empty += 1
                            continue
                        image = Image.fromarray(np.moveaxis(pixels, 0, -1))
                        image.save(
                            output_path,
                            format="JPEG",
                            quality=int(config["tiling"]["jpeg_quality"]),
                            optimize=False,
                        )
                    record = tile_record(
                        source,
                        source_row,
                        tile_id,
                        parent_id,
                        window,
                        output_path,
                        paths["satellite_tiles"],
                    )
                    output_rows.append(record)
                    if len(output_rows) % 1000 == 0:
                        print(f"Recorded {len(output_rows)} generated tiles", flush=True)

    write_csv_atomic(paths["tile_metadata"], METADATA_FIELDS, output_rows)
    manifest = {
        "source_tiff_count": len(source_rows),
        "generated_tile_count": len(output_rows),
        "skipped_empty_patch_count": skipped_empty,
        "tile_size_px": tile_size,
        "overlap_fraction": overlap,
        "stride_px": stride,
        "flight09_verification": flight09_check,
        "tile_metadata_csv": str(paths["tile_metadata"]),
    }
    write_json_atomic(paths["index_metadata"] / "tile_generation_manifest.json", manifest)
    print(
        f"Generated metadata for {len(output_rows)} tiles "
        f"({skipped_empty} empty patches skipped); Flight 09 2x2 arrangement verified."
    )


if __name__ == "__main__":
    main()
