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


def image_tensor(path: Path, max_side: int = 1024) -> torch.Tensor:
    with Image.open(path) as im:
        im = im.convert("RGB")
        scale = min(1.0, max_side / max(im.size))
        if scale < 1.0:
            im = im.resize((max(1, round(im.width * scale)),
                            max(1, round(im.height * scale))))
        arr = np.asarray(im, dtype=np.uint8).copy()
    return torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0).float() / 255.0


def extract_features(extractor, path: Path, device):
    tensor = image_tensor(path).to(device)
    with torch.inference_mode():
        feats = extractor.extract(tensor)
    del tensor
    return feats


def match_pair(extractor, matcher, query_path: Path, tile_path: Path, device):
    start = time.perf_counter()
    f0 = extract_features(extractor, query_path, device)
    f1 = extract_features(extractor, tile_path, device)

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
                p0.astype(np.float32),
                p1.astype(np.float32),
                cv2.RANSAC,
                4.0,
                maxIters=2000,
                confidence=0.995,
            )
            if H is not None and mask is not None:
                inliers = int(mask.ravel().sum())
                inlier_ratio = float(inliers / len(pairs))
                homography_ok = inliers >= 4
        except cv2.error:
            pass

    elapsed = time.perf_counter() - start
    result = {
        "query_image": query_path.name,
        "satellite_tile": tile_path.stem,
        "tentative_matches": int(len(pairs)),
        "ransac_inliers": inliers,
        "inlier_ratio": round(inlier_ratio, 5),
        "homography_estimated": homography_ok,
        "pair_seconds": round(elapsed, 4),
    }
    del f0, f1, out, pairs
    gc.collect()
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Small CPU-only SuperPoint + LightGlue + RANSAC benchmark."
    )
    parser.add_argument("--phase3c", type=Path, required=True)
    parser.add_argument("--phase3h", type=Path, required=True)
    parser.add_argument("--queries", type=int, default=5)
    parser.add_argument("--candidates-per-query", type=int, default=5)
    parser.add_argument("--max-side", type=int, default=1024)
    parser.add_argument("--min-free-ram-gb", type=float, default=1.0)
    args = parser.parse_args()

    phase3c = args.phase3c.resolve()
    phase3h = args.phase3h.resolve()
    phase3h.mkdir(parents=True, exist_ok=True)
    (phase3h / "outputs").mkdir(exist_ok=True)
    (phase3h / "reports").mkdir(exist_ok=True)
    (phase3h / "logs").mkdir(exist_ok=True)

    free_gb = psutil.virtual_memory().available / (1024 ** 3)
    if free_gb < args.min_free_ram_gb:
        raise SystemExit(
            f"STOP: only {free_gb:.2f} GB RAM available; "
            f"need at least {args.min_free_ram_gb:.2f} GB. "
            "Close applications and rerun."
        )

    retrieval_csv = phase3c / "retrieval_validation.csv"
    config_path = phase3c / "index_config.yaml"
    if not retrieval_csv.is_file() or not config_path.is_file():
        raise FileNotFoundError("Missing retrieval_validation.csv or index_config.yaml.")

    import yaml
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    dataset_root = (phase3c / config["dataset_root"]).resolve()
    tile_root = (phase3c / config["satellite_tiles"]).resolve()

    rows = read_rows(retrieval_csv)
    grouped = defaultdict(list)
    for row in rows:
        key = (row["flight_number"], row["image_filename"])
        grouped[key].append(row)

    selected = list(grouped.items())[:args.queries]
    if not selected:
        raise RuntimeError("No query rows found in retrieval_validation.csv.")

    # Find all required image paths before loading neural models.
    jobs = []
    missing = []
    for (flight, filename), group in selected:
        query_path = find_image(dataset_root, filename)
        if query_path is None:
            missing.append(f"drone image {filename}")
            continue
        group = sorted(group, key=lambda r: int(r.get("rank", "999999")))
        for row in group[:args.candidates_per_query]:
            tile_id = row["tile_id"]
            tile_path = find_image(tile_root, tile_id)
            if tile_path is None:
                missing.append(f"satellite tile {tile_id}")
                continue
            jobs.append((query_path, tile_path, flight, row))
    if missing:
        raise FileNotFoundError(
            "Could not resolve required image files:\n" + "\n".join(missing[:20])
            + "\nCheck the dataset and satellite_tiles paths in index_config.yaml."
        )
    if not jobs:
        raise RuntimeError("No image pairs could be constructed.")

    torch.set_num_threads(2)
    device = torch.device("cpu")
    print(f"Queries: {len(selected)} | image pairs: {len(jobs)}")
    print(f"Drone dataset: {dataset_root}")
    print(f"Satellite tiles: {tile_root}")
    print(f"RAM available before model load: {free_gb:.2f} GB")
    print("Loading pretrained SuperPoint and LightGlue on CPU...")

    extractor = SuperPoint(max_num_keypoints=512).eval().to(device)
    matcher = LightGlue(features="superpoint").eval().to(device)

    results = []
    process = psutil.Process(os.getpid())
    peak_rss = process.memory_info().rss
    for i, (query_path, tile_path, flight, row) in enumerate(jobs, start=1):
        available = psutil.virtual_memory().available / (1024 ** 3)
        if available < 0.65:
            print(f"Stopping safely before pair {i}: available RAM {available:.2f} GB")
            break
        print(f"[{i}/{len(jobs)}] {query_path.name}  <->  {tile_path.name}")
        result = match_pair(extractor, matcher, query_path, tile_path, device)
        result.update({
            "flight_number": flight,
            "retrieval_rank": int(row.get("rank", 0) or 0),
            "retrieval_cosine_similarity": float(row.get("cosine_similarity", "nan")),
            "expected_parent_map": row.get("expected_satellite_map", ""),
            "retrieved_parent_map": row.get("parent_satellite_map_id", ""),
        })
        results.append(result)
        peak_rss = max(peak_rss, process.memory_info().rss)
        print(
            f"  matches={result['tentative_matches']} "
            f"inliers={result['ransac_inliers']} "
            f"ratio={result['inlier_ratio']:.3f} "
            f"time={result['pair_seconds']:.2f}s"
        )

    output_csv = phase3h / "outputs" / "phase3h_matching_results.csv"
    if results:
        with output_csv.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            writer.writeheader()
            writer.writerows(results)

    summary = {
        "phase": "3H",
        "status": "completed" if len(results) == len(jobs) else "stopped_safely",
        "method": "SuperPoint + LightGlue + OpenCV RANSAC",
        "device": "cpu",
        "requested_queries": len(selected),
        "requested_pairs": len(jobs),
        "completed_pairs": len(results),
        "mean_tentative_matches": (
            round(float(np.mean([r["tentative_matches"] for r in results])), 3)
            if results else 0
        ),
        "mean_ransac_inliers": (
            round(float(np.mean([r["ransac_inliers"] for r in results])), 3)
            if results else 0
        ),
        "mean_inlier_ratio": (
            round(float(np.mean([r["inlier_ratio"] for r in results])), 5)
            if results else 0
        ),
        "mean_pair_seconds": (
            round(float(np.mean([r["pair_seconds"] for r in results])), 4)
            if results else 0
        ),
        "peak_process_rss_bytes": int(peak_rss),
        "ram_available_after_run_gb": round(
            psutil.virtual_memory().available / (1024 ** 3), 3
        ),
        "results_csv": str(output_csv),
        "interpretation": (
            "Geometric match counts are a visual-consistency diagnostic only. "
            "A homography or RANSAC inlier set does not establish geographic "
            "localization accuracy, especially without camera calibration."
        ),
    }
    summary_path = phase3h / "outputs" / "phase3h_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    report = [
        "# Phase 3H — Local Feature Matching Benchmark",
        "",
        f"- Status: **{summary['status']}**",
        "- Method: SuperPoint + LightGlue + OpenCV RANSAC",
        "- Device: CPU",
        f"- Completed image pairs: {len(results)} / {len(jobs)}",
        f"- Mean tentative matches: {summary['mean_tentative_matches']}",
        f"- Mean RANSAC inliers: {summary['mean_ransac_inliers']}",
        f"- Mean inlier ratio: {summary['mean_inlier_ratio']}",
        f"- Mean pair time: {summary['mean_pair_seconds']} seconds",
        f"- Peak process RSS: {peak_rss / (1024 ** 2):.1f} MiB",
        "",
        "## Interpretation and limitations",
        "",
        "This benchmark tests local visual correspondence and robust geometric "
        "consistency on a small set of retrieved drone/satellite image pairs. "
        "It does not prove geographic localization accuracy. Camera calibration, "
        "image orientation, scale, terrain relief, and independent ground truth "
        "are not available for a metric localization claim.",
        "",
        "The benchmark uses the existing retrieval_validation.csv candidate rows. "
        "It does not retrain models, rebuild the DINOv2 index, or resume exhaustive "
        "SuperPoint cache extraction.",
    ]
    (phase3h / "reports" / "PHASE3H_LOCAL_MATCHING_REPORT.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )
    print("\nSaved:")
    print(output_csv)
    print(summary_path)
    print(phase3h / "reports" / "PHASE3H_LOCAL_MATCHING_REPORT.md")
    print("\nIMPORTANT: RANSAC verification is not a geographic localization guarantee.")


if __name__ == "__main__":
    main()
