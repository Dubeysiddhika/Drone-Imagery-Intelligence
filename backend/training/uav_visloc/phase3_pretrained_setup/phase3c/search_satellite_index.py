from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from phase3c_common import (
    BASE_DIR,
    configure_cpu,
    dinov2_descriptor,
    load_config,
    load_dinov2,
    metadata_by_tile_id,
)


def search(
    query: np.ndarray, index_ids: np.ndarray, index_vectors: np.ndarray, top_k: int
) -> list[tuple[str, float]]:
    if top_k <= 0:
        raise ValueError("top_k must be a positive integer.")
    if (
        index_vectors.ndim != 2
        or index_vectors.shape[0] == 0
        or index_vectors.shape[0] != len(index_ids)
    ):
        raise ValueError("Index IDs and descriptor matrix must contain the same nonzero row count.")
    vector = np.asarray(query, dtype=np.float32).reshape(-1)
    if vector.shape != (index_vectors.shape[1],):
        raise ValueError(
            f"Query dimension {vector.size} does not match index dimension {index_vectors.shape[1]}"
        )
    norm = float(np.linalg.norm(vector))
    if not np.isfinite(vector).all() or not np.isfinite(norm) or norm <= 0:
        raise ValueError("Query descriptor must contain finite values and have nonzero norm.")
    scores = index_vectors @ (vector / norm)
    if not np.isfinite(scores).all():
        raise ValueError("Cosine similarity computation produced non-finite values.")
    count = min(max(1, top_k), len(scores))
    candidate_indices = np.argpartition(-scores, count - 1)[:count]
    candidate_indices = candidate_indices[np.argsort(-scores[candidate_indices])]
    return [(str(index_ids[i]), float(scores[i])) for i in candidate_indices]


def main() -> None:
    parser = argparse.ArgumentParser(description="Retrieve the top satellite tiles for a drone image.")
    parser.add_argument("--config", type=Path, default=BASE_DIR / "index_config.yaml")
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--image", type=Path, help="Drone image to encode with DINOv2.")
    inputs.add_argument("--descriptor", type=Path, help="Precomputed one-dimensional NumPy descriptor.")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", type=Path, help="Optional JSON result path.")
    args = parser.parse_args()
    config, paths = load_config(args.config)
    manifest_path = paths["index_metadata"] / "satellite_index_manifest.json"
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not manifest["complete"]:
        raise RuntimeError(
            "The cached index is incomplete and cannot be used for exhaustive retrieval: "
            f"{manifest['missing_tile_count']} tiles are missing."
        )
    with np.load(paths["global_features"] / "satellite_index.npz", allow_pickle=False) as index:
        index_ids = index["tile_ids"].astype(str)
        index_vectors = index["descriptors"].astype(np.float32)
    if args.descriptor:
        query = np.load(args.descriptor, allow_pickle=False).astype(np.float32)
    else:
        if not args.image.is_file():
            raise FileNotFoundError(f"Drone image does not exist: {args.image}")
        device = configure_cpu(config)
        model = load_dinov2(config, device)
        query = dinov2_descriptor(model, args.image, config, device)

    hits = search(query, index_ids, index_vectors, args.top_k)
    metadata = metadata_by_tile_id(paths)
    result = {
        "index_complete": bool(manifest["complete"]),
        "interpretation": "Retrieval similarity is not a verified geographic match or localization.",
        "results": [
            {"rank": rank, "tile_id": tile_id, "cosine_similarity": score, **metadata[tile_id]}
            for rank, (tile_id, score) in enumerate(hits, start=1)
        ],
    }
    text = json.dumps(result, indent=2, allow_nan=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
