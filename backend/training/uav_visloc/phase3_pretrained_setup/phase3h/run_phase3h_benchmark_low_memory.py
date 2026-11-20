from __future__ import annotations

import argparse
import csv
import gc
import json
import os
import time
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
import psutil
import torch
from PIL import Image
from lightglue import LightGlue, SuperPoint


def read_rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def find_image(root: Path, stem_or_name: str) -> Path | None:
    direct = root / stem_or_name
    if direct.is_file():
        return direct
    matches = list(root.rglob(stem_or_name))
    if matches:
        return matches[0]
    stem = Path(stem_or_name).stem
    for ext in (".jpg", ".JPG", ".jpeg", ".JPEG", ".png", ".tif", ".tiff"):
        matches = list(root.rglob(stem + ext))
        if matches:
            return matches[0]
    return None


def available_ram_gb() -> float:
    return psutil.virtual_memory().available / (1024 ** 3)


def release_memory(*objects):
    for obj in objects:
        try:
            del obj
        except UnboundLocalError:
            pass
    gc.collect()
    if hasattr(torch, "set_num_threads"):
        # Keep CPU thread pools small on low-memory systems.
        torch.set_num_threads(1)


def image_tensor(path: Path, max_side: int) -> torch.Tensor:
    # Decode, resize and copy one image at a time; never retain full-resolution pairs.
    with Image.open(path) as im:
        im = im.convert("RGB")
        scale = min(1.0, max_side / max(im.size))
        if scale < 1.0:
            im = im.resize(
                (max(1, round(im.width * scale)), max(1, round(im.height * scale))),
                Image.Resampling.BILINEAR,
            )
        arr = np.asarray(im, dtype=np.uint8).copy()
    tensor = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0).float()
    tensor.div_(255.0)
    del arr
    return tensor


def extract_features(extractor, path: Path, max_side: int):
    tensor = image_tensor(path, max_side)
    with torch.inference_mode():
        features = extractor.extract(tensor)
    del tensor
    return features


def match_pair(extractor, matcher, query_path: Path, tile_path: Path,
               max_side: int, min_pair_ram_gb: float):
    start = time.perf_counter()
    f0 = f1 = out = pairs = p0 = p1 = None

    try:
        f0 = extract_features(extractor, query_path, max_side)
        gc.collect()
        if available_ram_gb() < min_pair_ram_gb:
            return {
                "query_image": query_path.name,
                "satellite_tile": tile_path.stem,
                "tentative_matches": 0,
                "ransac_inliers": 0,
                "inlier_ratio": 0.0,
                "homography_estimated": False,
                "pair_seconds": round(time.perf_counter() - start, 4),
                "status": "stopped_after_query_features_low_ram",
            }

        f1 = extract_features(extractor, tile_path, max_side)
        with torch.inference_mode():
            out = matcher({"image0": f0, "image1": f1})

        pairs = out["matches"][0].detach().cpu().numpy()
        if pairs.ndim != 2 or pairs.shape[1] != 2:
            pairs = np.empty((0, 2), dtype=np.int64)

        inliers = 0
        inlier_ratio = 0.0
        homography_ok = False
        if len(pairs) >= 4:
            p0 = f0["keypoints"][0].detach().cpu().numpy()[pairs[:, 0]]
            p1 = f1["keypoints"][0].detach().cpu().numpy()[pairs[:, 1]]
            try:
                H, mask = cv2.findHomography(
                    p0.astype(np.float32), p1.astype(np.float32),
                    cv2.RANSAC, 4.0, maxIters=1000, confidence=0.99
                )
                if H is not None and mask is not None:
                    inliers = int(mask.ravel().sum())
                    inlier_ratio = float(inliers / len(pairs))
                    homography_ok = inliers >= 4
            except cv2.error:
                pass

        return {
            "query_image": query_path.name,
            "satellite_tile": tile_path.stem,
            "tentative_matches": int(len(pairs)),
            "ransac_inliers": inliers,
            "inlier_ratio": round(inlier_ratio, 5),
            "homography_estimated": homography_ok,
            "pair_seconds": round(time.perf_counter() - start, 4),
            "status": "completed",
        }
    finally:
        # Drop all per-image tensors/features before the next pair.
        del f0, f1, out, pairs, p0, p1
        gc.collect()


def main():
    parser = argparse.ArgumentParser(
        description="Low-memory CPU SuperPoint + LightGlue + RANSAC smoke benchmark."
    )
    parser.add_argument("--phase3c", type=Path, required=True)
    parser.add_argument("--phase3h", type=Path, required=True)
    parser.add_argument("--queries", type=int, default=1)
    parser.add_argument("--candidates-per-query", type=int, default=1)
    parser.add_argument("--max-side", type=int, default=512)
    parser.add_argument("--max-keypoints", type=int, default=256)
    parser.add_argument("--min-free-ram-gb", type=float, default=0.45)
    parser.add_argument("--min-pair-ram-gb", type=float, default=0.30)
    parser.add_argument("--max-pairs", type=int, default=1)
    args = parser.parse_args()

    phase3c = args.phase3c.resolve()
    phase3h = args.phase3h.resolve()
    phase3h.mkdir(parents=True, exist_ok=True)
    for folder in ("outputs", "reports", "logs"):
        (phase3h / folder).mkdir(exist_ok=True)

    retrieval_csv = phase3c / "retrieval_validation.csv"
    config_path = phase3c / "index_config.yaml"
    if not retrieval_csv.is_file() or not config_path.is_file():
        raise FileNotFoundError(
            f"Missing retrieval_validation.csv or index_config.yaml in {phase3c}"
        )

    import yaml
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    dataset_root = (phase3c / config["dataset_root"]).resolve()
    tile_root = (phase3c / config["satellite_tiles"]).resolve()

    rows = read_rows(retrieval_csv)
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["flight_number"], row["image_filename"])].append(row)

    selected = list(grouped.items())[:max(1, args.queries)]
    jobs = []
    missing = []
    for (flight, filename), group in selected:
        query_path = find_image(dataset_root, filename)
        if query_path is None:
            missing.append(f"drone image {filename}")
            continue
        group = sorted(group, key=lambda r: int(r.get("rank", "999999")))
        for row in group[:max(1, args.candidates_per_query)]:
            tile_path = find_image(tile_root, row["tile_id"])
            if tile_path is None:
                missing.append(f"satellite tile {row['tile_id']}")
                continue
            jobs.append((query_path, tile_path, flight, row))

    if missing:
        raise FileNotFoundError(
            "Could not resolve required image files:\n" + "\n".join(missing[:15])
        )
    jobs = jobs[:max(1, args.max_pairs)]
    if not jobs:
        raise RuntimeError("No image pairs could be constructed.")

    # Check after imports and path resolution, immediately before loading models.
    free_before = available_ram_gb()
    print(f"Available RAM before model load: {free_before:.2f} GB")
    print(f"Low-memory settings: max_side={args.max_side}, "
          f"max_keypoints={args.max_keypoints}, max_pairs={len(jobs)}")
    if free_before < args.min_free_ram_gb:
        raise SystemExit(
            f"STOP safely: {free_before:.2f} GB available; "
            f"minimum is {args.min_free_ram_gb:.2f} GB. "
            "Close memory-heavy apps or restart Windows; do not bypass this check."
        )

    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    device = torch.device("cpu")
    extractor = matcher = None
    results = []
    process = psutil.Process(os.getpid())
    peak_rss = process.memory_info().rss
    model_load_seconds = 0.0

    try:
        print("Loading compact SuperPoint and LightGlue models on CPU...")
        load_start = time.perf_counter()
        extractor = SuperPoint(max_num_keypoints=args.max_keypoints).eval().to(device)
        matcher = LightGlue(features="superpoint").eval().to(device)
        model_load_seconds = time.perf_counter() - load_start
        gc.collect()

        free_after_load = available_ram_gb()
        print(f"Model load: {model_load_seconds:.2f}s; "
              f"available RAM after load: {free_after_load:.2f} GB")
        if free_after_load < args.min_pair_ram_gb:
            raise SystemExit(
                "STOP safely after model load: remaining RAM is below "
                f"{args.min_pair_ram_gb:.2f} GB. No image pair was processed."
            )

        for i, (query_path, tile_path, flight, row) in enumerate(jobs, start=1):
            available = available_ram_gb()
            if available < args.min_pair_ram_gb:
                print(f"Stopping safely before pair {i}: RAM {available:.2f} GB")
                break

            print(f"[{i}/{len(jobs)}] {query_path.name} <-> {tile_path.name}")
            result = match_pair(
                extractor, matcher, query_path, tile_path,
                args.max_side, args.min_pair_ram_gb
            )
            result.update({
                "flight_number": flight,
                "retrieval_rank": int(row.get("rank", 0) or 0),
                "retrieval_cosine_similarity": float(
                    row.get("cosine_similarity", "nan") or "nan"
                ),
                "expected_parent_map": row.get("expected_satellite_map", ""),
                "retrieved_parent_map": row.get("parent_satellite_map_id", ""),
            })
            results.append(result)
            peak_rss = max(peak_rss, process.memory_info().rss)
            print(
                f"  status={result['status']} "
                f"matches={result['tentative_matches']} "
                f"inliers={result['ransac_inliers']} "
                f"ratio={result['inlier_ratio']:.3f} "
                f"time={result['pair_seconds']:.2f}s "
                f"RAM={available_ram_gb():.2f} GB"
            )
            gc.collect()

            if result["status"] != "completed":
                break

    finally:
        # Release model weights at the end of this tiny smoke test.
        del extractor, matcher
        gc.collect()

    output_csv = phase3h / "outputs" / "phase3h_matching_results.csv"
    if results:
        with output_csv.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            writer.writeheader()
            writer.writerows(results)

    completed = sum(1 for r in results if r["status"] == "completed")
    summary = {
        "phase": "3H",
        "status": "completed" if completed == len(jobs) else "stopped_safely",
        "method": "SuperPoint + LightGlue + OpenCV RANSAC",
        "device": "cpu",
        "low_memory_mode": True,
        "max_side_px": args.max_side,
        "max_keypoints": args.max_keypoints,
        "requested_pairs": len(jobs),
        "completed_pairs": completed,
        "model_load_seconds": round(model_load_seconds, 3),
        "mean_tentative_matches": round(
            float(np.mean([r["tentative_matches"] for r in results])), 3
        ) if results else 0,
        "mean_ransac_inliers": round(
            float(np.mean([r["ransac_inliers"] for r in results])), 3
        ) if results else 0,
        "mean_inlier_ratio": round(
            float(np.mean([r["inlier_ratio"] for r in results])), 5
        ) if results else 0,
        "peak_process_rss_bytes": int(peak_rss),
        "ram_available_after_run_gb": round(available_ram_gb(), 3),
        "results_csv": str(output_csv),
        "interpretation": (
            "This is a bounded local-feature smoke test, not a full accuracy "
            "evaluation. RANSAC inliers do not establish geographic localization."
        ),
    }
    summary_path = phase3h / "outputs" / "phase3h_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    report = [
        "# Phase 3H — Low-Memory Local Matching Smoke Test",
        "",
        f"- Status: **{summary['status']}**",
        "- Method: SuperPoint + LightGlue + OpenCV RANSAC",
        "- Device: CPU",
        f"- Completed pairs: {completed}/{len(jobs)}",
        f"- Input max side: {args.max_side}px",
        f"- SuperPoint keypoint cap: {args.max_keypoints}",
        f"- Model load time: {model_load_seconds:.2f}s",
        f"- Mean tentative matches: {summary['mean_tentative_matches']}",
        f"- Mean RANSAC inliers: {summary['mean_ransac_inliers']}",
        f"- Mean inlier ratio: {summary['mean_inlier_ratio']}",
        f"- Peak process RSS: {peak_rss / (1024 ** 2):.1f} MiB",
        "",
        "## Limitations",
        "",
        "This is a deliberately small engineering smoke test. It uses only the "
        "first selected retrieval-validation candidate(s), reduced image size, "
        "and a reduced keypoint cap. It is not a full benchmark and must not be "
        "reported as a localization-accuracy result. RANSAC consistency alone "
        "does not prove geographic correctness; camera calibration and independent "
        "ground truth would be needed for that claim.",
        "",
        "The script does not retrain models, rebuild the DINOv2 index, load the "
        "multi-gigabyte SuperPoint cache, or resume exhaustive feature extraction.",
    ]
    (phase3h / "reports" / "PHASE3H_LOCAL_MATCHING_REPORT.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )

    print("\nSaved:")
    print(output_csv)
    print(summary_path)
    print(phase3h / "reports" / "PHASE3H_LOCAL_MATCHING_REPORT.md")
    print("Phase 3H smoke test finished. Continue to YOLO/FastAPI integration.")


if __name__ == "__main__":
    main()
