from __future__ import annotations

import argparse
import bisect
import copy
import csv
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from phase3c_common import (
    BASE_DIR,
    ResourceMonitor,
    configure_cpu,
    dinov2_descriptor,
    load_config,
    load_dinov2,
    read_csv,
)

BUDGETS = (20, 50, 75, 100, 150)
BASELINE_KS = (5, 10)
EXPANSION_ANCHORS = (5, 10, 20)
REFERENCE_KS = (5, 10, 20, 50, 100)


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


def build_adjacency(
    tile_rows: list[dict[str, str]]
) -> list[set[int]]:
    grids: dict[str, dict[int, dict[int, int]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    row_offsets: dict[str, list[int]] = {}
    col_offsets: dict[tuple[str, int], list[int]] = {}
    max_width: dict[str, int] = defaultdict(int)
    max_height: dict[str, int] = defaultdict(int)
    for index, row in enumerate(tile_rows):
        source = row["source_file"]
        width = int(row["tile_width_px"])
        height = int(row["tile_height_px"])
        row_offset = int(row["tile_row_offset_px"])
        col_offset = int(row["tile_col_offset_px"])
        row_grid = grids[source][row_offset]
        if col_offset in row_grid:
            raise ValueError(f"Duplicate tile grid position: {(source, row_offset, col_offset)}")
        row_grid[col_offset] = index
        max_width[source] = max(max_width[source], width)
        max_height[source] = max(max_height[source], height)

    for source, rows in grids.items():
        row_offsets[source] = sorted(rows)
        for row_offset, cols in rows.items():
            col_offsets[(source, row_offset)] = sorted(cols)
    adjacency = [set() for _ in tile_rows]
    for index, row in enumerate(tile_rows):
        source = row["source_file"]
        row_offset = int(row["tile_row_offset_px"])
        col_offset = int(row["tile_col_offset_px"])
        possible_rows = row_offsets[source]
        first_row = bisect.bisect_left(
            possible_rows, row_offset - max_height[source] + 1
        )
        last_row = bisect.bisect_right(
            possible_rows, row_offset + int(row["tile_height_px"]) - 1
        )
        for neighbor_row in possible_rows[first_row:last_row]:
            possible_cols = col_offsets[(source, neighbor_row)]
            first_col = bisect.bisect_left(
                possible_cols, col_offset - max_width[source] + 1
            )
            last_col = bisect.bisect_right(
                possible_cols, col_offset + int(row["tile_width_px"]) - 1
            )
            for neighbor_col in possible_cols[first_col:last_col]:
                neighbor = grids[source][neighbor_row][neighbor_col]
                if neighbor == index:
                    continue
                other = tile_rows[neighbor]
                lon_overlap = min(float(row["max_lon"]), float(other["max_lon"])) - max(
                    float(row["min_lon"]), float(other["min_lon"])
                )
                lat_overlap = min(float(row["max_lat"]), float(other["max_lat"])) - max(
                    float(row["min_lat"]), float(other["min_lat"])
                )
                if lon_overlap > 0 and lat_overlap > 0:
                    if (
                        row["parent_satellite_map_id"]
                        != other["parent_satellite_map_id"]
                    ):
                        raise ValueError(
                            "Adjacent source patches have inconsistent parent maps: "
                            f"{row['tile_id']} and {other['tile_id']}"
                        )
                    adjacency[index].add(neighbor)
                    adjacency[neighbor].add(index)
    return adjacency


def neighborhood(indices: set[int], adjacency: list[set[int]], rings: int) -> set[int]:
    reached = set(indices)
    frontier = set(indices)
    for _ in range(rings):
        frontier = {
            neighbor
            for index in frontier
            for neighbor in adjacency[index]
            if neighbor not in reached
        }
        reached.update(frontier)
    return reached


def adaptive_expansion(
    seeds: list[int],
    adjacency: list[set[int]],
    scores: np.ndarray,
    anchor_count: int,
    budget: int,
    rings: int,
) -> list[int]:
    selected = set(seeds[:budget])
    if len(selected) < budget:
        for anchor in seeds[:anchor_count]:
            neighbors = sorted(
                neighborhood({anchor}, adjacency, rings) - {anchor},
                key=lambda index: (-float(scores[index]), index),
            )
            for neighbor in neighbors:
                if neighbor in selected:
                    continue
                selected.add(neighbor)
                if len(selected) >= budget:
                    break
            if len(selected) >= budget:
                break
    return sorted(selected, key=lambda index: (-float(scores[index]), index))


def query_records() -> list[dict[str, Any]]:
    phase2_dir = BASE_DIR.parent.parent / "phase2_pair_preparation"
    phase1_metadata_path = (
        BASE_DIR.parent.parent
        / "phase1_validation"
        / "outputs"
        / "consolidated_drone_metadata.csv"
    )
    positives = [
        row
        for row in read_csv(phase2_dir / "validation_pairs.csv")
        if row["pair_type"] == "candidate_positive"
    ]
    metadata = read_csv(phase1_metadata_path)
    by_image = {
        (row["flight_number"], row["image_filename"]): row for row in metadata
    }
    queries: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for pair in positives:
        key = (pair["flight_number"], pair["drone_image_filename"])
        if key in seen:
            raise ValueError(f"Duplicate positive validation query: {key}")
        seen.add(key)
        drone = by_image.get(key)
        if drone is None:
            raise ValueError(f"No Phase 1 metadata for validation query {key}")
        image_path = Path(drone["image_path"])
        if not image_path.is_file():
            raise FileNotFoundError(f"Missing validation query image: {image_path}")
        queries.append(
            {
                "flight": pair["flight_number"],
                "filename": pair["drone_image_filename"],
                "image_path": image_path,
                "expected_parent": pair["satellite_map_id"],
                "latitude": float(pair["drone_latitude"]),
                "longitude": float(pair["drone_longitude"]),
            }
        )
    if not queries:
        raise ValueError("No positive validation queries were found.")
    return queries


def get_metrics(
    candidate_indices: list[int] | set[int],
    tile_rows: list[dict[str, str]],
    exact_targets: set[int],
    adjacent_targets: set[int],
    expected_parent: str,
) -> dict[str, bool]:
    selected = set(candidate_indices)
    return {
        "parent_hit": any(
            tile_rows[index]["parent_satellite_map_id"] == expected_parent
            for index in selected
        ),
        "exact_hit": bool(selected & exact_targets),
        "adjacent_hit": bool(selected & adjacent_targets),
    }


def recall(metrics: list[dict[str, bool]], key: str) -> float:
    if not metrics:
        raise ValueError("Cannot calculate recall without queries.")
    return sum(result[key] for result in metrics) / len(metrics)


def make_summary_row(
    *,
    resolution: int,
    query: dict[str, Any],
    strategy: str,
    parameters: str,
    budget: int,
    seeds_count: int,
    pool_order: list[int],
    selected_order: list[int],
    all_rank_order: list[int],
    tile_rows: list[dict[str, str]],
    exact_targets: set[int],
    adjacent_targets: set[int],
    parent_indices: set[int],
    selection_ms: float,
    expanded_count: int | None = None,
) -> dict[str, Any]:
    pool_metrics = get_metrics(
        pool_order, tile_rows, exact_targets, adjacent_targets, query["expected_parent"]
    )
    selected_metrics = get_metrics(
        selected_order,
        tile_rows,
        exact_targets,
        adjacent_targets,
        query["expected_parent"],
    )
    return {
        "resolution": resolution,
        "flight": query["flight"],
        "query": query["filename"],
        "strategy": strategy,
        "parameters": parameters,
        "budget": budget,
        "seed_count": seeds_count,
        "candidate_count_before_expansion": seeds_count,
        "candidate_count_after_expansion": (
            len(pool_order) if expanded_count is None else expanded_count
        ),
        "candidate_count_before_budget": len(pool_order),
        "candidate_count_after_budget": len(selected_order),
        "discarded_candidate_count": len(pool_order) - len(selected_order),
        "gps_parent_candidate_count": len(parent_indices),
        "all_rank_top150_recall": get_metrics(
            all_rank_order[:150],
            tile_rows,
            exact_targets,
            adjacent_targets,
            query["expected_parent"],
        ),
        "pool_recall": pool_metrics,
        "selected_recall": selected_metrics,
        "selection_ms": selection_ms,
    }


def evaluate_resolution(
    resolution: int,
    config: dict[str, Any],
    model: Any,
    index_ids: np.ndarray,
    index_vectors: np.ndarray,
    tile_rows: list[dict[str, str]],
    adjacency: list[set[int]],
    queries: list[dict[str, Any]],
    device: Any,
    output_records: list[dict[str, Any]],
    timings: dict[int, list[float]],
    decision_log: list[dict[str, Any]],
) -> None:
    query_config = copy.deepcopy(config)
    query_config["dinov2"]["input_size_px"] = resolution
    by_parent: dict[str, set[int]] = defaultdict(set)
    parent_bounds: dict[str, tuple[float, float, float, float]] = {}
    for index, row in enumerate(tile_rows):
        by_parent[row["parent_satellite_map_id"]].add(index)
        parent = row["parent_satellite_map_id"]
        bounds = (
            float(row["parent_min_lon"]),
            float(row["parent_min_lat"]),
            float(row["parent_max_lon"]),
            float(row["parent_max_lat"]),
        )
        if parent in parent_bounds:
            previous = parent_bounds[parent]
            parent_bounds[parent] = (
                min(previous[0], bounds[0]),
                min(previous[1], bounds[1]),
                max(previous[2], bounds[2]),
                max(previous[3], bounds[3]),
            )
        else:
            parent_bounds[parent] = bounds

    for query in queries:
        started = time.perf_counter()
        descriptor = dinov2_descriptor(
            model, query["image_path"], query_config, device
        )
        encode_ms = (time.perf_counter() - started) * 1000
        search_started = time.perf_counter()
        scores = index_vectors @ descriptor
        if not np.isfinite(scores).all():
            raise ValueError(f"Non-finite cosine scores for {query['filename']}")
        top_count = min(max(BUDGETS), len(scores))
        top_indices = np.argpartition(-scores, top_count - 1)[:top_count]
        top_indices = top_indices[np.argsort(-scores[top_indices], kind="stable")]
        rank_order = top_indices.tolist()
        search_ms = (time.perf_counter() - search_started) * 1000
        timings[resolution].append(encode_ms + search_ms)
        ranks = {index: rank for rank, index in enumerate(rank_order)}

        expected_parent_indices = by_parent.get(query["expected_parent"], set())
        if not expected_parent_indices:
            raise ValueError(f"Unknown GPS parent map {query['expected_parent']}")
        gps_parents = {
            parent
            for parent, (min_lon, min_lat, max_lon, max_lat) in parent_bounds.items()
            if (
                min_lon <= query["longitude"] <= max_lon
                and min_lat <= query["latitude"] <= max_lat
            )
        }
        if not gps_parents:
            raise ValueError(f"GPS point is not inside a parent-map footprint for {query['filename']}")
        if query["expected_parent"] not in gps_parents:
            raise ValueError(
                f"GPS parent containment disagrees with validation metadata for {query['filename']}"
            )
        gps_candidate_indices = {
            index
            for parent in gps_parents
            for index in by_parent[parent]
        }
        exact_targets = {
            index
            for index in gps_candidate_indices
            if point_inside_tile(
                tile_rows[index], query["longitude"], query["latitude"]
            )
        }
        if not exact_targets:
            raise ValueError(f"No GPS-containing tile for {query['filename']}")
        adjacent_targets = neighborhood(exact_targets, adjacency, 1)

        def append_record(
            strategy: str,
            parameters: str,
            budget: int,
            seeds_count: int,
            pool_order: list[int],
            selected_order: list[int],
            started_selection: float,
            trace_decisions: bool = False,
            expanded_count: int | None = None,
            adaptive_stop: bool = False,
        ) -> None:
            selection_ms = (time.perf_counter() - started_selection) * 1000
            output_records.append(
                make_summary_row(
                    resolution=resolution,
                    query=query,
                    strategy=strategy,
                    parameters=parameters,
                    budget=budget,
                    seeds_count=seeds_count,
                    pool_order=pool_order,
                    selected_order=selected_order,
                    all_rank_order=rank_order,
                    tile_rows=tile_rows,
                    exact_targets=exact_targets,
                    adjacent_targets=adjacent_targets,
                    parent_indices=gps_candidate_indices,
                    selection_ms=selection_ms,
                    expanded_count=expanded_count,
                )
            )
            if trace_decisions:
                decision_log.append(
                    {
                        "resolution": resolution,
                        "flight": query["flight"],
                        "query": query["filename"],
                        "strategy": strategy,
                        "parameters": parameters,
                        "budget": budget,
                        "seed_count": seeds_count,
                        "candidate_count_before_expansion": seeds_count,
                        "candidate_count_after_expansion": (
                            len(pool_order)
                            if expanded_count is None
                            else expanded_count
                        ),
                        "candidate_count_before_budget": len(pool_order),
                        "candidate_count_after_budget": len(selected_order),
                        "selected_candidate_ids": [
                            tile_rows[index]["tile_id"] for index in selected_order
                        ],
                        "discarded_candidate_ids": [
                            tile_rows[index]["tile_id"]
                            for index in pool_order
                            if index not in set(selected_order)
                        ],
                        "expansion_stop_reason": (
                            "budget_reached"
                            if adaptive_stop and len(selected_order) >= budget
                            else "anchor_limit_exhausted"
                            if adaptive_stop
                            else "not_applicable"
                        ),
                    }
                )

        # A: Original DINOv2 ranking, with the candidate budget as K.
        for budget in (*BASELINE_KS, *BUDGETS):
            started_selection = time.perf_counter()
            pool = rank_order[:budget]
            append_record(
                "visual_topk",
                "initial_k=budget",
                budget,
                budget,
                pool,
                pool,
                started_selection,
            )

        # B: Expand only the first few visual hits; preserve DINOv2 order within the union.
        base_k = 50
        base = rank_order[:base_k]
        for anchor_count in EXPANSION_ANCHORS:
            # The full union is only for uncapped recall measurement; adaptive selection below
            # stops adding neighbors as soon as its output budget is reached.
            expanded = set(base)
            expanded.update(neighborhood(set(base[:anchor_count]), adjacency, 1))
            pool = sorted(expanded, key=lambda index: (-float(scores[index]), index))
            for budget in BUDGETS:
                started_selection = time.perf_counter()
                selected = adaptive_expansion(
                    base, adjacency, scores, anchor_count, budget, rings=1
                )
                append_record(
                    "limited_one_ring",
                    f"initial_k={base_k};anchors={anchor_count};rings=1",
                    budget,
                    base_k,
                    pool,
                    selected,
                    started_selection,
                    trace_decisions=True,
                    expanded_count=len(selected),
                    adaptive_stop=True,
                )

        # Also compare a smaller anchor set expanded two adjacency rings.
        # Keep the uncapped two-ring set only as an offline recall reference.
        expanded_two = set(base)
        expanded_two.update(neighborhood(set(base[:5]), adjacency, 2))
        pool_two = sorted(
            expanded_two, key=lambda index: (-float(scores[index]), index)
        )
        for budget in BUDGETS:
            started_selection = time.perf_counter()
            selected = adaptive_expansion(
                base, adjacency, scores, anchor_count=5, budget=budget, rings=2
            )
            append_record(
                "limited_two_ring",
                f"initial_k={base_k};anchors=5;rings=2",
                budget,
                base_k,
                pool_two,
                selected,
                started_selection,
                expanded_count=len(selected),
            )

        # Reproduce the full-neighborhood reference sweep from Phase 3F.
        for k in REFERENCE_KS:
            generation_started = time.perf_counter()
            started_selection = time.perf_counter()
            expanded = set(rank_order[:k])
            expanded.update(neighborhood(set(rank_order[:k]), adjacency, 1))
            pool = sorted(expanded, key=lambda index: (-float(scores[index]), index))
            generation_ms = (time.perf_counter() - generation_started) * 1000
            append_record(
                "all_topk_one_ring_reference",
                f"initial_k={k};anchors=all;rings=1;uncapped",
                0,
                k,
                pool,
                pool,
                started_selection,
            )
            output_records[-1]["selection_ms"] += generation_ms

        # C: Soft spatial diversity; adjacent candidates are penalized, never excluded.
        for penalty in (0.005, 0.02):
            started_selection = time.perf_counter()
            candidates = rank_order[:150]
            remaining = set(candidates)
            selected: list[int] = []
            adjacent_selected_count = {index: 0 for index in candidates}
            while remaining:
                def diversity_score(index: int) -> tuple[float, int, int]:
                    return (
                        float(scores[index]) - penalty * adjacent_selected_count[index],
                        -ranks[index],
                        -index,
                    )

                choice = max(remaining, key=diversity_score)
                selected.append(choice)
                remaining.remove(choice)
                for neighbor in adjacency[choice]:
                    if neighbor in remaining:
                        adjacent_selected_count[neighbor] += 1
            ordering_ms = (time.perf_counter() - started_selection) * 1000
            pool = candidates
            for budget in BUDGETS:
                selection_started = time.perf_counter()
                append_record(
                    "soft_spatial_diversity",
                    f"pool_k=150;adjacent_penalty={penalty}",
                    budget,
                    150,
                    pool,
                    selected[:budget],
                    selection_started,
                )
                output_records[-1]["selection_ms"] += ordering_ms

        # D: Blend each candidate's score with its best adjacent-patch visual support.
        started_selection = time.perf_counter()
        candidates = rank_order[:150]
        combined_scores: dict[int, float] = {}
        for index in candidates:
            neighbor_scores = [float(scores[n]) for n in adjacency[index]]
            if neighbor_scores:
                neighbor_scores.sort(reverse=True)
                local_support = float(np.mean(neighbor_scores[:4]))
                combined_scores[index] = 0.9 * float(scores[index]) + 0.1 * local_support
            else:
                combined_scores[index] = float(scores[index])
        combined_order = sorted(
            candidates,
            key=lambda index: (-combined_scores[index], ranks[index], index),
        )
        ordering_ms = (time.perf_counter() - started_selection) * 1000
        for budget in BUDGETS:
            selection_started = time.perf_counter()
            append_record(
                "similarity_spatial_consistency",
                "pool_k=150;score=0.9*cosine+0.1*mean_top4_adjacent_cosine",
                budget,
                150,
                candidates,
                combined_order[:budget],
                selection_started,
            )
            output_records[-1]["selection_ms"] += ordering_ms

        # GPS-assisted diagnostic, explicitly separate from the GPS-free selectors.
        generation_started = time.perf_counter()
        gps_pool = sorted(
            gps_candidate_indices, key=lambda index: (-float(scores[index]), index)
        )
        generation_ms = (time.perf_counter() - generation_started) * 1000
        for budget in BUDGETS:
            started_selection = time.perf_counter()
            append_record(
                "gps_parent_filter",
                "select_containing_parent_from_gps_then_rank_by_cosine",
                budget,
                len(gps_candidate_indices),
                gps_pool,
                gps_pool[:budget],
                started_selection,
            )
            output_records[-1]["selection_ms"] += generation_ms


def aggregate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        key = (
            row["resolution"],
            row["strategy"],
            row["parameters"],
            row["budget"],
        )
        grouped[key].append(row)
    summary: list[dict[str, Any]] = []
    for (resolution, strategy, parameters, budget), rows in sorted(grouped.items()):
        summary.append(
            {
                "resolution": resolution,
                "strategy": strategy,
                "parameters": parameters,
                "budget": budget,
                "query_count": len(rows),
                "mean_candidates_before_budget": float(
                    np.mean([row["candidate_count_before_budget"] for row in rows])
                ),
                "mean_candidates_before_expansion": float(
                    np.mean([row["candidate_count_before_expansion"] for row in rows])
                ),
                "mean_candidates_after_expansion": float(
                    np.mean([row["candidate_count_after_expansion"] for row in rows])
                ),
                "mean_candidates_after_budget": float(
                    np.mean([row["candidate_count_after_budget"] for row in rows])
                ),
                "mean_discarded_candidate_count": float(
                    np.mean([row["discarded_candidate_count"] for row in rows])
                ),
                "mean_selection_ms": float(np.mean([row["selection_ms"] for row in rows])),
                "mean_pool_parent_recall": recall(
                    [row["pool_recall"] for row in rows], "parent_hit"
                ),
                "mean_pool_exact_recall": recall(
                    [row["pool_recall"] for row in rows], "exact_hit"
                ),
                "mean_pool_adjacent_recall": recall(
                    [row["pool_recall"] for row in rows], "adjacent_hit"
                ),
                "parent_recall": recall(
                    [row["selected_recall"] for row in rows], "parent_hit"
                ),
                "exact_recall": recall(
                    [row["selected_recall"] for row in rows], "exact_hit"
                ),
                "adjacent_recall": recall(
                    [row["selected_recall"] for row in rows], "adjacent_hit"
                ),
                "mean_candidate_count_in_gps_parent": float(
                    np.mean([row["gps_parent_candidate_count"] for row in rows])
                ),
            }
        )
    return summary


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, allow_nan=False)
        handle.write("\n")


def write_decisions(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value, separators=(",", ":"))
                    if key.endswith("_candidate_ids")
                    else value
                    for key, value in row.items()
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate GPS-free and GPS-assisted candidate selection on Phase 3C assets."
    )
    parser.add_argument("--config", type=Path, default=BASE_DIR / "index_config.yaml")
    parser.add_argument("--output", type=Path, required=True, help="Summary JSON output path.")
    parser.add_argument(
        "--decisions",
        type=Path,
        required=True,
        help="CSV containing selected and budget-discarded tile IDs for one-ring trials.",
    )
    args = parser.parse_args()
    config, paths = load_config(args.config)
    memory = ResourceMonitor(float(config["inference"]["minimum_available_ram_gb"]))
    memory.start()
    manifest_path = paths["index_metadata"] / "satellite_index_manifest.json"
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not manifest.get("complete"):
        raise RuntimeError("Candidate evaluation requires the complete existing DINOv2 index.")
    with np.load(paths["global_features"] / "satellite_index.npz", allow_pickle=False) as index:
        index_ids = index["tile_ids"].astype(str)
        index_vectors = index["descriptors"].astype(np.float32)
    if (
        index_vectors.shape != (len(index_ids), int(config["dinov2"]["descriptor_dim"]))
        or len(index_ids) != int(manifest["descriptor_count"])
    ):
        raise ValueError("The loaded DINOv2 index does not match its complete-index manifest.")
    if not np.isfinite(index_vectors).all():
        raise ValueError("The existing DINOv2 index contains non-finite descriptors.")

    tile_rows = read_csv(paths["tile_metadata"])
    if len(tile_rows) != len(index_ids):
        raise ValueError("Satellite metadata and the complete DINOv2 index differ in size.")
    tile_ids = [row["tile_id"] for row in tile_rows]
    if len(set(tile_ids)) != len(tile_ids) or set(tile_ids) != set(index_ids):
        raise ValueError("Satellite metadata IDs do not exactly match the DINOv2 index.")
    id_to_row = {tile_id: row for tile_id, row in zip(tile_ids, tile_rows)}
    tile_rows = [id_to_row[str(tile_id)] for tile_id in index_ids]
    adjacency = build_adjacency(tile_rows)
    queries = query_records()

    device = configure_cpu(config)
    model = load_dinov2(config, device)
    output_records: list[dict[str, Any]] = []
    decision_log: list[dict[str, Any]] = []
    timings: dict[int, list[float]] = defaultdict(list)
    for resolution in (224, 280):
        evaluate_resolution(
            resolution,
            config,
            model,
            index_ids,
            index_vectors,
            tile_rows,
            adjacency,
            queries,
            device,
            output_records,
            timings,
            decision_log,
        )
    memory.close()

    payload = {
        "experiment": "Phase 3G candidate selection",
        "index_descriptor_count": len(index_ids),
        "index_modified": False,
        "query_count": len(queries),
        "query_flights": sorted({query["flight"] for query in queries}),
        "candidate_budgets": list(BUDGETS),
        "limited_expansion_stops_at_budget": True,
        "resolutions": {
            str(resolution): {
                "mean_query_encode_and_dense_search_ms": float(np.mean(values)),
                "median_query_encode_and_dense_search_ms": float(np.median(values)),
                "query_count": len(values),
            }
            for resolution, values in timings.items()
        },
        "peak_process_rss_bytes": memory.peak_rss_bytes,
        "peak_process_rss_mib": memory.peak_rss_bytes / (1024**2),
        "selection_summary": aggregate(output_records),
    }
    write_json(args.output, payload)
    write_decisions(args.decisions, decision_log)
    print(
        f"Evaluated {len(queries)} queries at 224 and 280 px; "
        f"peak RSS {payload['peak_process_rss_mib']:.1f} MiB."
    )
    print(f"Wrote {args.output} and {args.decisions}")


if __name__ == "__main__":
    main()
