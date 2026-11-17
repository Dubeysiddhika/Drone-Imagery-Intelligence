from __future__ import annotations

import argparse
import json
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from phase3c_common import (
    BASE_DIR,
    ResourceMonitor,
    configure_cpu,
    checkpoint_number,
    dinov2_descriptor,
    feature_signature,
    load_config,
    load_dinov2,
    read_csv,
    tile_image_path,
    write_csv_atomic,
    write_json_atomic,
    write_npz_atomic,
)

FAILURE_FIELDS = ["tile_id", "image_path", "error_type", "error_message"]


def load_valid_features(
    path: Path,
    expected_ids: set[str],
    dimension: int,
    signature: str,
) -> dict[str, np.ndarray]:
    if not path.is_file():
        return {}
    try:
        with np.load(path, allow_pickle=False) as shard:
            ids = shard["tile_ids"].astype(str).tolist()
            descriptors = shard["descriptors"]
            cached_signature = str(shard["config_signature"].item())
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        print(f"Skipping unreadable DINOv2 cache shard {path.name}: {exc}", flush=True)
        return {}
    if cached_signature != signature or descriptors.shape != (len(ids), dimension):
        print(f"Skipping incompatible DINOv2 cache shard {path.name}.", flush=True)
        return {}
    if len(set(ids)) != len(ids):
        print(f"Skipping DINOv2 cache shard with duplicate IDs: {path.name}.", flush=True)
        return {}
    valid: dict[str, np.ndarray] = {}
    for index, tile_id in enumerate(ids):
        if tile_id not in expected_ids:
            continue
        vector = descriptors[index].astype(np.float32, copy=False)
        norm = float(np.linalg.norm(vector))
        if (
            np.isfinite(vector).all()
            and np.isfinite(norm)
            and norm > 0
            and abs(norm - 1.0) <= 1e-4
        ):
            valid[tile_id] = vector
    return valid


def read_failures(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    return {row["tile_id"]: row for row in read_csv(path)}


def cache_bytes(directory: Path) -> int:
    return sum(path.stat().st_size for path in directory.glob("*.npz") if path.is_file())


def main() -> None:
    parser = argparse.ArgumentParser(description="Resume pretrained CPU DINOv2 satellite feature extraction.")
    parser.add_argument("--config", type=Path, default=BASE_DIR / "index_config.yaml")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--max-tiles", type=int, help="Process only the first N tiles for a smoke test.")
    selection.add_argument("--tile-ids", nargs="+", help="Process a selected tile subset for a pilot.")
    args = parser.parse_args()
    config, paths = load_config(args.config)
    device = configure_cpu(config)
    all_rows = read_csv(paths["tile_metadata"])
    rows = all_rows
    if args.max_tiles is not None:
        if args.max_tiles <= 0:
            raise ValueError("--max-tiles must be positive.")
        rows = rows[: args.max_tiles]
    if args.tile_ids:
        selected = set(args.tile_ids)
        rows = [row for row in all_rows if row["tile_id"] in selected]
        if len(rows) != len(selected):
            found = {row["tile_id"] for row in rows}
            raise ValueError(f"Unknown tile IDs: {sorted(selected - found)[:10]}")
    if not rows:
        raise ValueError("No generated tile metadata was found.")

    dimension = int(config["dinov2"]["descriptor_dim"])
    shard_size = int(config["dinov2"]["shard_size"])
    signature = feature_signature(config, "dinov2")
    pilot_directory = paths["global_features"] / "dinov2_shards"
    directory = (
        paths["global_features"] / "dinov2_complete_shards"
        if args.max_tiles is None and not args.tile_ids
        else pilot_directory
    )
    directory.mkdir(parents=True, exist_ok=True)
    checkpoint_path = paths["index_metadata"] / "dinov2_full_extraction.json"
    failure_path = paths["index_metadata"] / "dinov2_failures.csv"
    previous: dict[str, object] = {}
    if checkpoint_path.is_file():
        with checkpoint_path.open("r", encoding="utf-8") as handle:
            previous = json.load(handle)
    previous_elapsed = float(checkpoint_number(previous, "total_extraction_seconds", 0.0))
    previous_inference = float(checkpoint_number(previous, "inference_seconds", 0.0))
    previous_extracted = int(checkpoint_number(previous, "features_extracted_total", 0))
    previous_peak_rss = int(checkpoint_number(previous, "peak_rss_bytes", 0))
    previous_min_available = int(
        checkpoint_number(previous, "minimum_available_ram_bytes", 2**63 - 1)
    )
    failures = read_failures(failure_path)
    expected_ids = {row["tile_id"] for row in rows}
    pilot_features: dict[str, np.ndarray] = {}
    for pilot_path in sorted(pilot_directory.glob("dinov2_*.npz")):
        pilot_features.update(load_valid_features(pilot_path, expected_ids, dimension, signature))

    monitor = ResourceMonitor(float(config["inference"]["minimum_available_ram_gb"]))
    monitor.start()
    run_started = time.perf_counter()
    model_load_seconds = 0.0
    inference_seconds = 0.0
    newly_extracted = 0
    reused_features = 0
    completed_features = 0
    stopped_for_memory = False
    try:
        model_started = time.perf_counter()
        model = load_dinov2(config, device)
        model_load_seconds = time.perf_counter() - model_started
        print(
            f"DINOv2 ready on CPU; target={len(rows):,}, shard_size={shard_size}, "
            f"available_RAM={monitor.minimum_available_bytes / 1024**3:.2f} GiB.",
            flush=True,
        )
        for shard_number, offset in enumerate(range(0, len(rows), shard_size)):
            shard_rows = rows[offset : offset + shard_size]
            shard_ids = [row["tile_id"] for row in shard_rows]
            shard_path = directory / f"dinov2_{shard_number:05d}.npz"
            features = load_valid_features(shard_path, set(shard_ids), dimension, signature)
            if len(features) == len(shard_rows):
                completed_features += len(shard_rows)
                reused_features += len(shard_rows)
                continue

            for position, row in enumerate(shard_rows):
                tile_id = row["tile_id"]
                if tile_id in features:
                    reused_features += 1
                    continue
                if tile_id in pilot_features:
                    features[tile_id] = pilot_features[tile_id]
                    reused_features += 1
                    failures.pop(tile_id, None)
                elif monitor.memory_pressure:
                    stopped_for_memory = True
                    break
                else:
                    image_path = paths["satellite_tiles"] / row["image_relative_path"]
                    started = time.perf_counter()
                    try:
                        descriptor = dinov2_descriptor(model, tile_image_path(row, paths), config, device)
                    except (OSError, ValueError) as exc:
                        failures[tile_id] = {
                            "tile_id": tile_id,
                            "image_path": str(image_path),
                            "error_type": type(exc).__name__,
                            "error_message": str(exc),
                        }
                    else:
                        features[tile_id] = descriptor
                        failures.pop(tile_id, None)
                        newly_extracted += 1
                        inference_seconds += time.perf_counter() - started

                if (position + 1) % 64 == 0:
                    print(
                        f"DINOv2 progress: {offset + position + 1:,}/{len(rows):,}; "
                        f"new={newly_extracted:,}, reused={reused_features:,}, "
                        f"failed={len(failures):,}, peak_RSS={monitor.peak_rss_bytes / 1024**3:.2f} GiB.",
                        flush=True,
                    )

            ordered_ids = [tile_id for tile_id in shard_ids if tile_id in features]
            if ordered_ids:
                matrix = np.stack([features[tile_id] for tile_id in ordered_ids]).astype(
                    np.float32, copy=False
                )
                write_npz_atomic(
                    shard_path,
                    tile_ids=np.asarray(ordered_ids, dtype=np.str_),
                    row_indices=np.asarray(
                        [offset + shard_ids.index(tile_id) for tile_id in ordered_ids],
                        dtype=np.int64,
                    ),
                    descriptors=matrix,
                    config_signature=np.asarray(signature),
                )
            completed_features += len(ordered_ids)
            elapsed = time.perf_counter() - run_started
            total_elapsed = previous_elapsed + elapsed
            total_inference = previous_inference + inference_seconds
            write_csv_atomic(failure_path, FAILURE_FIELDS, list(failures.values()))
            write_json_atomic(
                checkpoint_path,
                {
                    "started_at_utc": previous.get(
                        "started_at_utc", datetime.now(timezone.utc).isoformat()
                    ),
                    "last_updated_at_utc": datetime.now(timezone.utc).isoformat(),
                    "status": "stopped_for_memory" if stopped_for_memory else "in_progress",
                    "device": "cpu",
                    "model": config["dinov2"]["model_version"],
                    "config_signature": signature,
                    "expected_feature_count": len(all_rows),
                    "features_completed_in_scope": completed_features,
                    "features_extracted_this_run": newly_extracted,
                    "features_reused_this_run": reused_features,
                    "failed_image_count": len(failures),
                    "missing_feature_count_in_scope": len(rows) - completed_features,
                    "descriptor_dimension": dimension,
                    "evaluation_mode": not model.training,
                    "inference_mode": True,
                    "model_load_seconds_this_run": model_load_seconds,
                    "inference_seconds_this_run": inference_seconds,
                    "total_extraction_seconds": total_elapsed,
                    "inference_seconds": total_inference,
                    "average_seconds_per_extracted_feature": (
                        total_inference / (newly_extracted + previous_extracted)
                        if newly_extracted + previous_extracted
                        else 0.0
                    ),
                    "features_extracted_total": newly_extracted + previous_extracted,
                    "peak_rss_bytes": max(monitor.peak_rss_bytes, previous_peak_rss),
                    "minimum_available_ram_bytes": min(
                        monitor.minimum_available_bytes,
                        previous_min_available,
                    ),
                    "cache_bytes": cache_bytes(directory),
                    "cache_directory": str(directory),
                },
            )
            print(
                f"DINOv2 checkpoint: {completed_features:,}/{len(rows):,} in scope; "
                f"{len(failures):,} failed; shard {shard_number + 1:,}.",
                flush=True,
            )
            if stopped_for_memory:
                print("Memory threshold reached; stopped after saving the current shard.", flush=True)
                break
    finally:
        monitor.close()

    elapsed = time.perf_counter() - run_started
    total_elapsed = previous_elapsed + elapsed
    total_inference = previous_inference + inference_seconds
    completed_status = completed_features >= len(rows) and not failures and len(rows) == len(all_rows)
    status = "complete" if completed_status else "stopped_for_memory" if stopped_for_memory else "incomplete"
    write_csv_atomic(failure_path, FAILURE_FIELDS, list(failures.values()))
    write_json_atomic(
        checkpoint_path,
        {
            "started_at_utc": previous.get("started_at_utc", datetime.now(timezone.utc).isoformat()),
            "last_updated_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "device": "cpu",
            "model": config["dinov2"]["model_version"],
            "config_signature": signature,
            "expected_feature_count": len(all_rows),
            "features_completed_in_scope": completed_features,
            "features_extracted_this_run": newly_extracted,
            "features_reused_this_run": reused_features,
            "failed_image_count": len(failures),
            "missing_feature_count_in_scope": len(rows) - completed_features,
            "descriptor_dimension": dimension,
            "evaluation_mode": True,
            "inference_mode": True,
            "model_load_seconds_this_run": model_load_seconds,
            "inference_seconds_this_run": inference_seconds,
            "total_extraction_seconds": total_elapsed,
            "inference_seconds": total_inference,
            "average_seconds_per_extracted_feature": (
                total_inference
                / (newly_extracted + previous_extracted)
                if newly_extracted + previous_extracted
                else 0.0
            ),
            "features_extracted_total": newly_extracted + previous_extracted,
            "peak_rss_bytes": max(monitor.peak_rss_bytes, previous_peak_rss),
            "minimum_available_ram_bytes": min(
                monitor.minimum_available_bytes,
                previous_min_available,
            ),
            "cache_bytes": cache_bytes(directory),
            "cache_directory": str(directory),
        },
    )
    print(
        f"DINOv2 run finished with status={status}; extracted={newly_extracted:,}, "
        f"reused={reused_features:,}, failed={len(failures):,}, "
        f"elapsed={elapsed / 60:.1f} min, peak_RSS={monitor.peak_rss_bytes / 1024**3:.2f} GiB.",
        flush=True,
    )


if __name__ == "__main__":
    main()
