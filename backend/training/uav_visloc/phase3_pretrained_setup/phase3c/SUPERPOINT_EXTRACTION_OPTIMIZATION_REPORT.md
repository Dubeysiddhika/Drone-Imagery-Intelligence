# SuperPoint Extraction Optimization Report

## Scope and data state

The optimization study used the existing, unchanged Phase 3C artifacts:

- 30,485 satellite patch metadata rows
- Complete DINOv2 index: 30,485/30,485 descriptors, 384-D, L2-normalized
- SuperPoint complete cache: 13,852 unique extracted IDs
- Remaining SuperPoint patches: 16,633
- Existing SuperPoint shards: 217
- Existing checkpoint:
  `metadata/superpoint_full_extraction.json`
- SuperPoint failure log: zero failed images
- CPU-only environment: Intel Core i5-1235U, approximately 8 GB RAM
- Configured RAM safety floor: 0.5 GiB

No exhaustive SuperPoint process was started by this study. No DINOv2 descriptor, DINOv2 index, SuperPoint shard, metadata row, or checkpoint was modified or deleted.

## Existing implementation findings

### Feature formats

DINOv2:

- 384-D float32 descriptors
- L2-normalized
- stored by tile ID in 64-tile compressed NumPy shards
- complete `satellite_index.npz` matrix has the same 30,485 ordered IDs

SuperPoint:

- `tile_ids`: one string ID per patch
- `row_indices`: metadata-relative row index
- `offsets`: keypoint offsets for each patch
- `image_sizes`: patch width and height
- `keypoints`: float32 `(x_px, y_px, score)`
- `descriptors`: float32 256-D normalized-style feature descriptors
- `config_signature`: model/config signature
- configured maximum: 512 keypoints
- configured input limit: 512 pixels on the longest side

The existing extractor and cache loader validate:

- exact configuration signature
- unique tile IDs
- correct offsets and array lengths
- keypoint shape `(N, 3)`
- descriptor shape `(N, 256)`
- finite keypoints and descriptors
- no more than 512 keypoints per patch

The 217 existing shards were audited and all 13,852 cached rows loaded with valid structure.

### Exhaustive-extraction bottleneck

The exhaustive script processes satellite metadata in 64-patch shards and loads one satellite image at a time for SuperPoint. It already:

- reuses valid completed shards
- avoids duplicate tile IDs
- writes shards atomically
- checkpoints after each shard
- watches available RAM and stops below the configured 0.5 GiB floor

The bottleneck is the remaining 16,633 sequential patch inferences, not the NumPy cache size or metadata. The existing 217-shard cache itself is reusable and does not require rebuilding.

## DINOv2 top-K retrieval evaluation

The complete DINOv2 index was searched for the existing representative first image in Flights 01, 05, 09, 02, and 10. Each result was compared with its recorded parent satellite map and GPS-center-containing patch. These metrics are retrieval coverage only, not localization accuracy.

| K | Parent-map Recall@K | GPS-center patch Recall@K | Mean DINOv2 latency | Mean cosine-search latency |
|---:|---:|---:|---:|---:|
| 5 | 20% (1/5) | 20% (1/5) | 450.6 ms | 5.2 ms |
| 10 | 40% (2/5) | 20% (1/5) | 450.6 ms | 3.4 ms |
| 20 | 40% (2/5) | 20% (1/5) | 450.6 ms | 3.5 ms |
| 50 | 60% (3/5) | 40% (2/5) | 450.6 ms | 3.7 ms |
| 100 | 60% (3/5) | 40% (2/5) | 450.6 ms | 3.7 ms |

Per-image DINOv2 latency ranged from approximately 284 to 700 ms, with a 525.1 MiB mean process RSS after model loading. Cosine search itself remained about 3–5 ms across K values. Raising K from 5 to 100 produced negligible search latency change but did not materially improve the 5-image GPS-center recall beyond 40%.

Important examples:

- Flight 10 reached correct parent and GPS-containing patch at K=5.
- Flight 05 reached correct parent at K=10 and GPS-containing patch at K=50.
- Flight 01 reached correct parent only at K=50, rank 47.
- Flights 09 and 02 did not retrieve the correct parent within K=100 in this representative set.

These results show that global DINOv2 retrieval is useful for narrowing work but is not a reliable sole localization mechanism. Candidate recall should be combined with geospatial constraints and local geometric verification.

## SuperPoint CPU benchmarks

### Existing preprocessing

A 512-pixel satellite patch was extracted with pretrained CPU SuperPoint using the existing preprocessing path.

| CPU threads | Input resize | Max keypoints | Warm-up | Mean 3-run latency | Median | Mean output keypoints |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 512 | 512 | 1662.9 ms | 1367.8 ms | 1366.6 ms | 512 |
| 2 | 512 | 512 | 1029.7 ms | 1038.9 ms | 1040.3 ms | 512 |
| 4 | 512 | 512 | 1157.4 ms | 1174.9 ms | 1168.4 ms | 512 |
| 4 | 256 | 512 | 315.3 ms | 308.4 ms | 309.3 ms | 206 |
| 4 | 256 | 256 | 322.4 ms | 333.5 ms | 333.1 ms | 206 |
| 4 | 512 | 256 | 1178.2 ms | 1226.0 ms | 1229.4 ms | 256 |
| 4 | 512 | unlimited | 1226.6 ms | 1246.7 ms | 1248.8 ms | 845 |

Model-load time was 42.5 ms after the weights were cached. Process RSS was approximately 321–463 MiB across configurations.

Results:

- 2 threads were faster than 4 threads for 512-pixel/512-keypoint extraction.
- The existing 512-pixel/512-keypoint setting averaged about 1.04 seconds per patch with 2 threads.
- Resizing to 256 pixels reduced mean latency to about 308 ms per patch.
- Reducing maximum keypoints to 256 at 512 pixels did not improve speed significantly.
- Unlimited keypoints violated the existing compatibility limit and must not replace the 512-keypoint cache format.
- Sequential one-image calls are the correct batching strategy. `Extractor.extract()` asserts a batch size of one.

The 256-pixel benchmark is not directly interchangeable with existing 512-pixel cached features. It is useful only as a separate cache variant with a separate configuration signature.

### Compatibility with existing shards and LightGlue

The existing cache was tested without extracting or rewriting it:

- 217 shard files
- 13,852 cached patch rows
- 256-D descriptors
- first shard ID: `01_satellite01_r000000_c000000`
- 512 keypoints in the tested cached patch
- LightGlue accepted the cached keypoints and descriptors
- one 512-keypoint cached-patch/representative-drone pairing completed in 211.1 ms
- output: 9 matched candidates

This verifies cache-format compatibility, not the correctness or accuracy of a localization match.

## Recommended on-demand architecture

The exhaustive full-dataset pass should be paused for review. Add a separate on-demand path while preserving the exhaustive checkpoint and existing shards.

1. Load the completed DINOv2 index and metadata.
2. Extract one DINOv2 descriptor for the query image.
3. Apply geospatial constraints when they are available.
4. Retrieve an initial top-K candidate set, with K=20 as the default candidate-review size.
5. Consider K=50 for weak or ambiguous retrieval if the geospatial constraints do not narrow the set.
6. Before SuperPoint extraction, load all existing 217 shards and build an in-memory tile-ID lookup.
7. For each shortlisted tile:
   - reuse an existing valid 512-pixel/512-keypoint feature record
   - otherwise extract exactly that tile once
8. Write each new tile atomically to a separate on-demand cache file using the existing array format:
   `tile_ids`, `row_indices`, `offsets`, `image_sizes`, `keypoints`,
   `descriptors`, and `config_signature`.
9. Maintain a small cache manifest mapping `tile_id` to cache path and completion state.
10. Reuse the same cached tile in future queries.
11. Run drone SuperPoint extraction once, then run LightGlue only on the cached shortlisted candidates.
12. Apply RANSAC/affine geometric verification and ambiguity rejection after matching.

### Cache layout recommendation

Keep the existing exhaustive cache unchanged and add:

`local_features/superpoint_on_demand_cache/<tile_id>.npz`

Use an atomic temporary file followed by rename/replacement only after validation. Reuse a completed file only when:

- tile ID equals the requested ID
- descriptor dimension is 256
- keypoint shape is `(N, 3)`
- descriptor count equals keypoint count
- all values are finite
- keypoint count is at most 512
- configuration signature matches the existing 512-pixel/512-keypoint signature

A manifest or lock should prevent concurrent or repeated extraction of the same tile. One process may hold the tile lock briefly and mark the cache complete only after the atomic write succeeds.

Do not merge on-demand files into the existing 217-shard files. Separate storage preserves the checkpoint and avoids renumbering or invalidating verified exhaustive progress.

### RAM safety

The existing `ResourceMonitor` and 0.5 GiB available-RAM floor must remain unchanged. The on-demand worker should:

- remain sequential
- sample memory at 0.25-second intervals
- stop before opening/extracting another tile if memory pressure is set
- write each tile atomically before continuing
- keep one active patch and model in memory rather than loading a K-sized batch

### Model and compatibility constraints

Preserve:

- pretrained SuperPoint v1 weights
- CPU/evaluation mode
- `torch.inference_mode()`
- 256-D descriptors
- 512-pixel input limit
- 512 maximum keypoints
- existing LightGlue feature and keypoint conventions

Do not treat a 256-pixel cache as compatible with an existing 512-pixel cache because it changes feature coverage and configuration signature. It may be tested as a separate cache variant only.

## RAM and latency comparison

Approximate exhaustive remaining cost:

- 16,633 patches
- 512-pixel/512-keypoint, 2-thread sequential benchmark: about 1.039 seconds per patch
- estimated remaining inference time: about 4.8 hours
- excluding process startup, shard rewrites, cache compression, image decode, and scheduling overhead

Approximate on-demand cost for K=20 with no cache hits:

- 20 satellite patches: about 20.8 seconds at 512-pixel/512-keypoint 2-thread speed
- representative DINOv2 retrieval: about 450.6 ms
- representative drone SuperPoint extraction: about 1.04 seconds
- representative first 512-pixel LightGlue pair: 211.1 ms
- all 20 pairs are not required to run at once; one candidate pair should be processed sequentially

The on-demand cost is much lower for a small workload, but repeated cache misses are cumulative. A future query remains costly only until its shortlisted tiles are cached.

## Risks and trade-offs

1. DINOv2 recall is only 20–60% on this five-image representative set.
2. GPS-center recall is only 20–40% for K values from 5–100 in this set.
3. Parent-map recall does not prove the correct patch or localization result.
4. A DINO-only shortlist can omit the visually correct candidate.
5. A large K increases CPU, disk, and LightGlue work without guaranteed recall gains.
6. A small K risks omitting the correct candidate.
7. The existing cache may contain partially discontinuous coverage, but all 217 existing shards are valid.
8. On-demand cache growth can increase disk usage without limits unless a cache policy is added.
9. Repeated coordinate/layout differences from alternate resolutions must remain isolated by signature.
10. LightGlue and RANSAC need separate validation before production use.

## Exhaustive extraction recommendation

Exhaustive extraction should not continue automatically until the on-demand evaluation is reviewed.

The evidence supports:

- keep the existing 13,852-patch cache and 217 shards
- keep the 16,633-patch checkpoint
- do not rebuild DINOv2 or rerun DINOv2 extraction
- implement or evaluate on-demand extraction behind a separate opt-in cache
- use DINOv2 plus geospatial constraints for shortlisting
- benchmark K=20 and K=50 in real local-matching/RANSAC validation
- resume exhaustive extraction only if broad precomputed local matching is later required

The existing exhaustive extractor is already safe and resumable. The on-demand design avoids an additional four-hour estimated pass when only a small candidate set is needed, and makes cache growth proportional to queries rather than the entire satellite dataset.

