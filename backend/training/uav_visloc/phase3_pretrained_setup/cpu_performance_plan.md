# Phase 3A CPU Performance Plan

## Scope

This plan covers the expected runtime behavior of a CPU-only, pretrained DINOv2 + SuperPoint + LightGlue inference pipeline for the UAV-VisLoc project. It is a planning document only; no model benchmarking was run in this phase.

## Observed environment constraints

Current machine and environment facts:
- Python: 3.13.5
- PyTorch: 2.14.1+cpu
- CUDA: unavailable
- CPU: 12th Gen Intel Core i5-1235U
- System RAM: approximately 7.68 GB
- No GPU acceleration is available

This is a modest-capability workstation for CPU-only inference. The design should therefore avoid heavy, end-to-end full-dataset processing in one pass.

## Memory considerations

### 1) DINOv2 backbone

A DINOv2 ViT model is large enough that it should be treated as a single-image-at-a-time or small-batch inference workload on CPU.

Approximate planning guidance without benchmarking:
- model weights and runtime memory: typically a few hundred MB to around 1 GB depending on the model variant and library implementation
- activation memory for a single resized image: manageable, but not trivial on a low-memory machine
- the main risk is not final model size, but repeated inference over all satellite tiles or all drone images in a single loop

### 2) Descriptor cache

The safest design is to cache per-tile descriptor vectors, not raw image arrays.

This keeps memory lower because:
- tile embeddings are compact vectors
- raw TIFF data does not need to remain loaded for every tile
- repeated comparisons can use a lightweight matrix or NumPy array

For a small satellite set (14 georeferenced TIFFs with tile metadata), a descriptor bank should fit comfortably in memory if the descriptor vectors are kept compact and the image tiles are processed in a limited shortlist.

### 3) Local feature matching

SuperPoint + LightGlue on a short candidate list is feasible on CPU, but the images must remain reasonably sized to avoid excessive memory churn.

The practical rule is:
- run SuperPoint on the drone image and a small set of candidate tiles only
- avoid matching against every tile in the dataset at once
- use a shortlist of 3 to 10 tiles after DINOv2 retrieval

## CPU inference constraints

The environment is CPU-only and small-memory, so the plan should prefer:
- single-image or very small-batch processing
- DINOv2 retrieval on a shortlist only
- local matching only on high-confidence candidates
- lightweight descriptor caching
- no full exhaustive matching over the entire dataset in a single command

This is especially important because:
- LightGlue is substantially slower on CPU than on GPU
- large satellite tiles can create heavy local feature density
- repeated resizing and full-tile processing can multiply the runtime cost

## Satellite tile resizing strategy

A lightweight approach is to resize raster tiles for feature matching, but do so conservatively.

Recommended practice:
- keep the original georeferenced tile intact for geospatial metadata and CRS preservation
- load a resized or cropped version only for feature extraction when necessary
- maintain aspect ratio during resizing
- avoid upsampling unnecessarily beyond the resolution required for feature match quality

For the initial pipeline, the best practice is to keep candidate tiles at a moderate resolution and use top-K shortlist filtering before local matching.

## Feature caching

Feature caching should happen at two levels:

1. Global descriptors
- DINOv2 descriptor vectors for each satellite tile
- computed once and saved to disk

2. Optional local feature descriptors
- SuperPoint keypoints and descriptors for high-value candidate tiles
- cache only when repeated inference or validation is expected

This gives a strong reduction in CPU load and keeps the repeated inference loop efficient.

## Batch-size guidance

Because of the low-memory CPU environment, the initial configuration should use:
- DINOv2 batch size: 1 for the drone image and one candidate tile at a time, or very small batches if the memory footprint remains safe
- candidate shortlist: 3 to 10 tiles
- local matching: one drone image against one tile at a time

This is deliberately conservative and appropriate for a CPU-only prototype.

## Image preprocessing guidance

The pipeline should normalize images consistently before the DINOv2 and SuperPoint stages.

Recommended preprocessing rules:
- use the same resize and normalization pipeline for all drone and satellite images in the same stage
- keep RGB or multispectral channel conventions consistent with the pretrained model expectations
- avoid arbitrary interpolation or resampling beyond what is needed for feature extraction
- maintain the original dataset image content for geospatial metadata and auditing

## Can the full satellite dataset be indexed?

On this machine, the full satellite dataset is likely still manageable for a lightweight prototype, but only if it is handled conservatively.

The safest answer is:
- yes, the georeferenced satellite library is small enough to handle in a restricted descriptor cache
- no, the full dataset should not be processed exhaustively with full-size local matching on CPU in the first pass

The initial design should index the tile descriptor bank and use DINOv2 retrieval to choose a small candidate set before any expensive local matching.

## Recommended lightweight configuration

Recommended first-pass CPU configuration:
- DINOv2 global retrieval only on a compact descriptor bank
- top-K candidate retrieval with K = 3 to 10
- no exhaustive local matching across all tiles
- local matching only on candidate tiles
- OpenCV RANSAC after SuperPoint + LightGlue matching
- cache satellite descriptors on disk for reuse
- maintain all geospatial metadata and tile IDs

This is the safest initial configuration for the available workstation and aligns with the project’s requirement to avoid custom training and avoid full-dataset heavy inference.

## Final assessment

The available machine is sufficient for a modest, inference-only prototype, but not for a broad, unfiltered, end-to-end local-matching workload across all images and tiles. The correct strategy is a lightweight retrieval-first pipeline with short candidate lists and cached descriptors.
