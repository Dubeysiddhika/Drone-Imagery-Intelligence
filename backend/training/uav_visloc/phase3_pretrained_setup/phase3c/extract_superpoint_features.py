from __future__ import annotations

import argparse
import json
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from lightglue import SuperPoint  # pyright: ignore[reportMissingImports]  # Installed from Phase 3B's editable checkout.

from phase3c_common import (
    BASE_DIR,
    ResourceMonitor,
    checkpoint_number,
    configure_cpu,
    feature_signature,
    load_config,
    read_csv,
    tile_image_path,
    write_csv_atomic,
    write_json_atomic,
    write_npz_atomic,
)

FAILURE_FIELDS = ["tile_id", "image_path", "error_type", "error_message"]


def load_valid_features(
    path: Path, expected_ids: set[str], signature: str
) -> dict[str, tuple[tuple[int, int], np.ndarray, np.ndarray]]:
    if not path.is_file():
        return {}
    try:
        with np.load(path, allow_pickle=False) as shard:
            ids = shard["tile_ids"].astype(str).tolist()
            offsets = shard["offsets"]
            image_sizes = shard["image_sizes"]
            keypoints = shard["keypoints"]
            descriptors = shard["descriptors"]
            cached_signature = str(shard["config_signature"].item())
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        print(f"Skipping unreadable SuperPoint cache shard {path.name}: {exc}", flush=True)
        return {}
    if (
        cached_signature != signature
        or len(set(ids)) != len(ids)
        or offsets.shape != (len(ids) + 1,)
        or image_sizes.shape != (len(ids), 2)
        or keypoints.ndim != 2
        or keypoints.shape[1] != 3
        or descriptors.ndim != 2
        or descriptors.shape[1] != 256
        or offsets[0] != 0
        or offsets[-1] != len(keypoints)
        or not np.all(np.diff(offsets) >= 0)
        or len(keypoints) != len(descriptors)
    ):
        print(f"Skipping incompatible SuperPoint cache shard {path.name}.", flush=True)
        return {}
    valid: dict[str, tuple[tuple[int, int], np.ndarray, np.ndarray]] = {}
    for index, tile_id in enumerate(ids):
        if tile_id not in expected_ids:
            continue
        start, stop = int(offsets[index]), int(offsets[index + 1])
        points = keypoints[start:stop].astype(np.float32, copy=False)
        features = descriptors[start:stop].astype(np.float32, copy=False)
        size = (int(image_sizes[index, 0]), int(image_sizes[index, 1]))
        if (
            min(size) > 0
            and len(points) <= 512
            and features.shape == (len(points), 256)
            and np.isfinite(points).all()
            and np.isfinite(features).all()
        ):
            valid[tile_id] = (size, points, features)
    return valid


def pack_features(
    rows: list[dict[str, str]],
    features: dict[str, tuple[tuple[int, int], np.ndarray, np.ndarray]],
    signature: str,
    start_index: int,
) -> dict[str, np.ndarray]:
    ids = [row["tile_id"] for row in rows if row["tile_id"] in features]
    sizes: list[tuple[int, int]] = []
    point_chunks: list[np.ndarray] = []
    descriptor_chunks: list[np.ndarray] = []
    offsets = [0]
    for tile_id in ids:
        size, points, descriptors = features[tile_id]
        sizes.append(size)
        point_chunks.append(points)
        descriptor_chunks.append(descriptors)
        offsets.append(offsets[-1] + len(points))
    keypoints = (
        np.concatenate(point_chunks, axis=0)
        if offsets[-1]
        else np.empty((0, 3), dtype=np.float32)
    )
    descriptors = (
        np.concatenate(descriptor_chunks, axis=0)
        if offsets[-1]
        else np.empty((0, 256), dtype=np.float32)
    )
    return {
        "tile_ids": np.asarray(ids, dtype=np.str_),
        "row_indices": np.asarray(
            [start_index + next(i for i, row in enumerate(rows) if row["tile_id"] == tile_id) for tile_id in ids],
            dtype=np.int64,
        ),
        "offsets": np.asarray(offsets, dtype=np.int64),
        "image_sizes": np.asarray(sizes, dtype=np.int32).reshape((-1, 2)),
        "keypoints": keypoints,
        "descriptors": descriptors,
        "config_signature": np.asarray(signature),
    }


def read_failures(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    return {row["tile_id"]: row for row in read_csv(path)}


def cache_bytes(directory: Path) -> int:
    return sum(path.stat().st_size for path in directory.glob("*.npz") if path.is_file())


def main() -> None:
    parser = argparse.ArgumentParser(description="Resume pretrained CPU SuperPoint feature extraction.")
    parser.add_argument("--config", type=Path, default=BASE_DIR / "index_config.yaml")
    parser.add_argument("--max-tiles", type=int, help="Process only the first N tiles for a smoke test.")
    args = parser.parse_args()
    config, paths = load_config(args.config)
    device = configure_cpu(config)
    all_rows = read_csv(paths["tile_metadata"])
    rows = all_rows
    if args.max_tiles is not None:
        if args.max_tiles <= 0:
            raise ValueError("--max-tiles must be positive.")
        rows = rows[: args.max_tiles]
    if not rows:
        raise ValueError("No generated tile metadata was found.")

    signature = feature_signature(config, "superpoint")
    shard_size = int(config["superpoint"]["shard_size"])
    pilot_directory = paths["local_features"] / "superpoint_shards"
    directory = (
        paths["local_features"] / "superpoint_complete_shards"
        if args.max_tiles is None
        else pilot_directory
    )
    directory.mkdir(parents=True, exist_ok=True)
    checkpoint_path = paths["index_metadata"] / "superpoint_full_extraction.json"
    failure_path = paths["index_metadata"] / "superpoint_failures.csv"
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
    pilot_features: dict[str, tuple[tuple[int, int], np.ndarray, np.ndarray]] = {}
    for pilot_path in sorted(pilot_directory.glob("superpoint_*.npz")):
        pilot_features.update(load_valid_features(pilot_path, expected_ids, signature))

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
        extractor = SuperPoint(
            max_num_keypoints=int(config["superpoint"]["max_num_keypoints"]),
            detection_threshold=float(config["superpoint"]["detection_threshold"]),
        ).to(device)
        extractor.eval()
        model_load_seconds = time.perf_counter() - model_started
        print(
            f"SuperPoint ready on CPU; target={len(rows):,}, shard_size={shard_size}, "
            f"available_RAM={monitor.minimum_available_bytes / 1024**3:.2f} GiB.",
            flush=True,
        )
        for shard_number, offset in enumerate(range(0, len(rows), shard_size)):
            shard_rows = rows[offset : offset + shard_size]
            shard_ids = [row["tile_id"] for row in shard_rows]
            shard_path = directory / f"superpoint_{shard_number:05d}.npz"
            features = load_valid_features(shard_path, set(shard_ids), signature)
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
                        with Image.open(tile_image_path(row, paths)) as image:
                            rgb = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
                        image_tensor = torch.from_numpy(rgb.transpose(2, 0, 1)).unsqueeze(0).to(device)
                        with torch.inference_mode():
                            output = extractor.extract(
                                image_tensor,
                                resize=int(config["superpoint"]["input_max_side_px"]),
                            )
                        points = output["keypoints"][0].detach().cpu().numpy().astype(
                            np.float32, copy=False
                        )
                        scores = output["keypoint_scores"][0].detach().cpu().numpy().astype(
                            np.float32, copy=False
                        )
                        descriptors = output["descriptors"][0].detach().cpu().numpy().astype(
                            np.float32, copy=False
                        )
                        if points.shape != (len(scores), 2) or descriptors.shape != (
                            len(points),
                            256,
                        ):
                            raise ValueError(f"Unexpected SuperPoint feature shapes for {tile_id}")
                        if (
                            len(points) > int(config["superpoint"]["max_num_keypoints"])
                            or not np.isfinite(points).all()
                            or not np.isfinite(scores).all()
                            or not np.isfinite(descriptors).all()
                        ):
                            raise ValueError(f"Invalid SuperPoint output for {tile_id}")
                    except (OSError, ValueError) as exc:
                        failures[tile_id] = {
                            "tile_id": tile_id,
                            "image_path": str(image_path),
                            "error_type": type(exc).__name__,
                            "error_message": str(exc),
                        }
                    else:
                        points_with_scores = np.column_stack((points, scores)).astype(
                            np.float32, copy=False
                        )
                        features[tile_id] = (
                            (int(row["tile_width_px"]), int(row["tile_height_px"])),
                            points_with_scores,
                            descriptors,
                        )
                        failures.pop(tile_id, None)
                        newly_extracted += 1
                        inference_seconds += time.perf_counter() - started

                if (position + 1) % 16 == 0:
                    print(
                        f"SuperPoint progress: {offset + position + 1:,}/{len(rows):,}; "
                        f"new={newly_extracted:,}, reused={reused_features:,}, "
                        f"failed={len(failures):,}, peak_RSS={monitor.peak_rss_bytes / 1024**3:.2f} GiB.",
                        flush=True,
                    )

            if features:
                write_npz_atomic(
                    shard_path,
                    **pack_features(shard_rows, features, signature, offset),
                )
            completed_features += len(features)
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
                    "model": config["superpoint"]["model_version"],
                    "config_signature": signature,
                    "expected_feature_count": len(all_rows),
                    "features_completed_in_scope": completed_features,
                    "features_extracted_this_run": newly_extracted,
                    "features_reused_this_run": reused_features,
                    "failed_image_count": len(failures),
                    "missing_feature_count_in_scope": len(rows) - completed_features,
                    "max_num_keypoints": config["superpoint"]["max_num_keypoints"],
                    "descriptor_dimension": 256,
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
                f"SuperPoint checkpoint: {completed_features:,}/{len(rows):,} in scope; "
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
            "model": config["superpoint"]["model_version"],
            "config_signature": signature,
            "expected_feature_count": len(all_rows),
            "features_completed_in_scope": completed_features,
            "features_extracted_this_run": newly_extracted,
            "features_reused_this_run": reused_features,
            "failed_image_count": len(failures),
            "missing_feature_count_in_scope": len(rows) - completed_features,
            "max_num_keypoints": config["superpoint"]["max_num_keypoints"],
            "descriptor_dimension": 256,
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
        f"SuperPoint run finished with status={status}; extracted={newly_extracted:,}, "
        f"reused={reused_features:,}, failed={len(failures):,}, "
        f"elapsed={elapsed / 60:.1f} min, peak_RSS={monitor.peak_rss_bytes / 1024**3:.2f} GiB.",
        flush=True,
    )


if __name__ == "__main__":
    main()
