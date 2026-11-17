from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path

import numpy as np

from phase3c_common import (
    BASE_DIR,
    feature_signature,
    load_config,
    metadata_by_tile_id,
    read_csv,
    sorted_shards,
    write_json_atomic,
    write_npz_atomic,
)


def validate_tile_metadata(rows: list[dict[str, str]]) -> None:
    seen: set[str] = set()
    for row in rows:
        tile_id = row["tile_id"]
        if not tile_id or tile_id in seen:
            raise ValueError(f"Missing or duplicate tile ID in metadata: {tile_id}")
        seen.add(tile_id)
        if not row["parent_tile_id"] or not row["parent_satellite_map_id"] or not row["crs"]:
            raise ValueError(f"Missing parent or CRS metadata for tile {tile_id}")
        if int(row["tile_width_px"]) <= 0 or int(row["tile_height_px"]) <= 0:
            raise ValueError(f"Invalid patch dimensions for tile {tile_id}")
        for field in ("affine_transform", "parent_affine_transform"):
            transform = json.loads(row[field])
            if len(transform) != 6 or not all(math.isfinite(float(value)) for value in transform):
                raise ValueError(f"Invalid {field} for tile {tile_id}")
            a, b, _, d, e, _ = map(float, transform)
            if a * e - b * d == 0:
                raise ValueError(f"Non-invertible {field} for tile {tile_id}")
        bounds = [
            float(row[key])
            for key in (
                "min_lon",
                "min_lat",
                "max_lon",
                "max_lat",
                "parent_min_lon",
                "parent_min_lat",
                "parent_max_lon",
                "parent_max_lat",
            )
        ]
        if not all(math.isfinite(value) for value in bounds):
            raise ValueError(f"Invalid geographic bounds for tile {tile_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a NumPy cosine-similarity satellite index.")
    parser.add_argument("--config", type=Path, default=BASE_DIR / "index_config.yaml")
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Build a clearly marked partial index for smoke testing only.",
    )
    args = parser.parse_args()
    config, paths = load_config(args.config)
    tile_rows = read_csv(paths["tile_metadata"])
    validate_tile_metadata(tile_rows)
    metadata = metadata_by_tile_id(paths)
    expected_ids = {row["tile_id"] for row in tile_rows}
    shard_paths = sorted_shards(
        paths["global_features"] / "dinov2_complete_shards", "dinov2"
    )
    if not shard_paths:
        raise FileNotFoundError("No DINOv2 feature shards found; run extract_dinov2_features.py first.")

    found: dict[str, np.ndarray] = {}
    dimension: int | None = None
    expected_signature = feature_signature(config, "dinov2")
    for shard_path in shard_paths:
        with np.load(shard_path, allow_pickle=False) as shard:
            ids = shard["tile_ids"].astype(str).tolist()
            descriptors = shard["descriptors"]
            signature = str(shard["config_signature"].item())
        if signature != expected_signature:
            raise ValueError(
                f"Feature shard {shard_path.name} was generated with a different model/configuration."
            )
        if descriptors.ndim != 2 or descriptors.shape[0] != len(ids):
            raise ValueError(f"Malformed DINOv2 shard: {shard_path}")
        if dimension is None:
            dimension = descriptors.shape[1]
        if descriptors.shape[1] != dimension or not np.isfinite(descriptors).all():
            raise ValueError(f"Invalid DINOv2 descriptor array in {shard_path}")
        if not np.allclose(np.linalg.norm(descriptors, axis=1), 1.0, atol=1e-4):
            raise ValueError(f"Descriptors are not L2-normalized in {shard_path}")
        for tile_id, descriptor in zip(ids, descriptors):
            if tile_id in found:
                raise ValueError(f"Duplicate cached descriptor for tile {tile_id}")
            if tile_id not in metadata:
                raise ValueError(f"Cached descriptor has no metadata row: {tile_id}")
            found[tile_id] = descriptor.astype(np.float32, copy=False)

    if not found or dimension is None:
        raise ValueError("No valid DINOv2 descriptors were found in the feature shards.")
    missing = expected_ids - found.keys()
    unexpected = found.keys() - expected_ids
    if unexpected:
        raise ValueError(f"Cached features refer to tiles absent from metadata: {sorted(unexpected)[:5]}")
    if missing and not args.allow_incomplete:
        raise RuntimeError(
            f"Refusing to build an incomplete index: {len(missing)} of {len(expected_ids)} "
            "tiles have no DINOv2 descriptor. Finish resumable extraction or pass "
            "--allow-incomplete for a smoke test."
        )
    ordered_ids = [row["tile_id"] for row in tile_rows if row["tile_id"] in found]
    descriptors_array = np.stack([found[tile_id] for tile_id in ordered_ids])
    index_path = paths["global_features"] / "satellite_index.npz"
    pilot_index_path = paths["global_features"] / "satellite_index_partial_pilot.npz"
    if index_path.is_file() and not pilot_index_path.exists():
        with np.load(index_path, allow_pickle=False) as existing:
            existing_ids = existing["tile_ids"].astype(str)
        if len(existing_ids) < len(expected_ids):
            shutil.copy2(index_path, pilot_index_path)
    write_npz_atomic(
        index_path,
        tile_ids=np.asarray(ordered_ids, dtype=np.str_),
        descriptors=descriptors_array,
    )
    complete = not missing
    manifest = {
        "index_file": str(index_path),
        "descriptor_count": len(ordered_ids),
        "expected_tile_count": len(expected_ids),
        "descriptor_dimension": dimension,
        "normalized": True,
        "complete": complete,
        "missing_tile_count": len(missing),
        "every_metadata_tile_indexed": complete and len(found) == len(expected_ids),
        "duplicate_tile_ids": 0,
        "unknown_feature_id_count": 0,
        "geospatial_metadata_validated": True,
        "similarity": "cosine similarity of L2-normalized DINOv2 descriptors",
        "model": config["dinov2"]["entrypoint"],
        "model_version": config["dinov2"]["model_version"],
        "config_signature": expected_signature,
        "metadata_file": str(paths["tile_metadata"]),
        "warning": None
        if complete
        else "PARTIAL SMOKE-TEST INDEX; retrieval scores are not an exhaustive search.",
    }
    write_json_atomic(paths["index_metadata"] / "satellite_index_manifest.json", manifest)
    if complete:
        validation_report = (
            "# Complete Satellite Index Validation\n\n"
            "Status: **COMPLETE AND VALIDATED**\n\n"
            f"- Satellite patches with metadata: {len(expected_ids):,}\n"
            f"- Unique indexed tile IDs: {len(ordered_ids):,}\n"
            f"- Missing features: {len(missing):,}\n"
            "- Unknown feature IDs: 0\n"
            "- Duplicate feature IDs: 0\n"
            f"- Descriptor dimensions: {dimension}\n"
            "- All descriptors finite and L2-normalized: yes\n"
            "- Parent/patch geospatial transforms and geographic bounds: validated\n"
            f"- Index file: `{index_path}`\n\n"
            "Cosine ranking is retrieval only; it is not, by itself, a verified geographic match "
            "or localization result.\n"
        )
        (BASE_DIR / "complete_index_validation.md").write_text(
            validation_report, encoding="utf-8"
        )
    print(
        f"Built {'complete' if complete else 'PARTIAL'} index with {len(ordered_ids)} "
        f"of {len(expected_ids)} tile descriptors: {index_path}"
    )


if __name__ == "__main__":
    main()
