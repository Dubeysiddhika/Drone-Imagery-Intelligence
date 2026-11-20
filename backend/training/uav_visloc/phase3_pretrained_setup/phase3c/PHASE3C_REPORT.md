# Phase 3C — Satellite Tile Generation and Pretrained Feature Indexing

## Executive summary

The Phase 3C pipeline and georeferenced satellite patch set were created without modifying the source dataset or earlier phase outputs. All 14 source TIFFs were opened with Rasterio, and their CRS, dimensions, affine transforms, and bounds were carried into patch metadata. Flight 09's four originals were verified as adjoining cells in a gap-free 2×2 EPSG:4326 arrangement.

The 512-pixel, 20%-overlap tiler produced **30,485** JPEG patches and a tracked metadata CSV. DINOv2 CPU extraction is complete for all 30,485 patches; the complete normalized NumPy index passed descriptor and geospatial-metadata validation. SuperPoint extraction was started only after DINOv2 completed and resumed from its existing checkpoint; verified progress is 12,421/30,485 patches after the latest memory-safe stop. Both feature pipelines are resumable.

**Final assessment: Phase 3C is INCOMPLETE.** The DINOv2 retrieval index is complete and validated, and the full-index five-flight retrieval experiment is recorded in [retrieval_validation.csv](./retrieval_validation.csv). Full SuperPoint extraction remains incomplete (18,064 patches missing at the latest verified checkpoint); allow its resumable worker to continue before declaring the full Phase 3C feature suite complete. Retrieval rankings are not localization accuracy. See [PHASE3C_FINAL_REPORT.md](./PHASE3C_FINAL_REPORT.md) for the current status.

## Previous phases and input reuse

- Reviewed Phase 1, Phase 2A, Phase 2B, Phase 3A, and Phase 3B reports.
- Reused Phase 2A's `satellite_tile_metadata.csv` as the source inventory; no Phase 1 or Phase 2A outputs were regenerated or changed.
- The Phase 2A file contains 14 source records, including four distinct Flight 09 TIFFs. Its recorded flight associations and parent map IDs are retained for each derived patch.
- The Phase 1 outside-coverage cases and Phase 2A uncertain pairs remain unchanged. No drone image footprint is inferred from its center GPS.
- No model training, fine-tuning, CUDA execution, FAISS, package installation, YOLO, API, database, or frontend changes were made.

## Source TIFF inspection and geospatial preservation

All 14 TIFFs were inspected individually with Rasterio. They are three-band `uint8` images with embedded `EPSG:4326` georeferencing. Affine transforms were checked for finite coefficients and invertibility. Each generated patch records:

- unique patch ID, parent map ID, original Phase 2A tile ID, TIFF filename, source path, and flight;
- source and patch pixel dimensions and patch pixel offsets;
- the parent TIFF affine transform and bounds, plus each patch's CRS, six affine coefficients, and explicit pixel-to-geographic mapping formula;
- all four transformed geographic corners and the derived geographic bounds;
- its relative patch-image path and the parent adjacency metadata.

Patch transforms were checked against Rasterio `window_transform` results for representative interior, edge, Flight 07, Flight 09, and Flight 11 patches. Bounds recomputed from each patch's affine transform matched the metadata. No geospatial transform could not be preserved.

### Flight 09

The four originals form a gap-free 2×2 grid with shared edges at longitude **120.0984191895** and latitude **30.9313201904**. They remain four separate parent TIFFs; no mosaic or cross-parent patch was manufactured.

| Parent TIFF | Dimensions (px) | Generated patches |
|---|---:|---:|
| `satellite09_01-01.tif` | 25,600 × 25,600 | 3,969 |
| `satellite09_01-02.tif` | 19,200 × 25,600 | 2,961 |
| `satellite09_02-01.tif` | 25,600 × 7,680 | 1,197 |
| `satellite09_02-02.tif` | 19,200 × 7,680 | 893 |

## Satellite patch generation

- Patch size: 512 × 512 pixels, with an 80%-of-tile stride (nominal 20% overlap).
- Edge patches retain their natural, smaller dimensions; source imagery is not stretched or padded during patch creation.
- JPEG quality 95 is used to keep the approximately 30,000 patch files manageable. Geospatial transforms are stored in the CSV rather than relying on image-file geotags.
- TIFFs are processed one at a time and read by window; no complete source raster is loaded into memory.
- Empty/nodata-only or all-zero patches are skipped. This run skipped **0** patches.

| Flight | Patch count |
|---|---:|
| 01 | 1,584 |
| 02 | 2,352 |
| 03 | 5,160 |
| 04 | 4,136 |
| 05 | 345 |
| 06 | 480 |
| 07 | 8 |
| 08 | 4,240 |
| 09 | 9,020 |
| 10 | 208 |
| 11 | 2,952 |
| **Total** | **30,485** |

The generated JPEG cache occupies approximately **2.95 GB** locally. The required [satellite_tile_metadata.csv](./satellite_tile_metadata.csv) has 30,485 unique patch records. Generated image and feature caches are excluded from Git by the Phase 3C-specific `.gitignore` entries.

## Pretrained features and index

### DINOv2

- Model: pretrained DINOv2 ViT-S/14 (`dinov2_vits14`), loaded from the local PyTorch Hub cache.
- Device/mode: CPU, evaluation mode, `torch.inference_mode()`.
- Input: RGB, aspect-ratio-preserving letterbox to 224 × 224, ImageNet normalization.
- Descriptor: finite 384-D vector, L2-normalized before cosine similarity.
- Cache: compressed NumPy shards of 64 tiles; each completed shard is atomically written and verified against its tile IDs and configuration signature before reuse.
- Full cache: **30,485 / 30,485** finite, normalized 384-D descriptors; zero failures. See [dinov2_extraction_report.md](./dinov2_extraction_report.md).

### SuperPoint

- Pretrained LightGlue SuperPoint weights; CPU, evaluation mode, `torch.inference_mode()`.
- Tile input capped at 512 pixels on the long side; up to 512 keypoints per patch.
- Compressed NumPy shards store tile IDs, image dimensions, per-tile offsets, `(x, y, score)` keypoints, and 256-D descriptors.
- Full extraction was started after DINOv2 and resumed from the existing checkpoint. It has reached **12,421 / 30,485** patches with 18,064 missing, 0 duplicate, 0 unknown, 0 unreadable/invalid shards, and zero failures. The latest run added 2,908 patches and reused 9,513 existing patches. See [superpoint_extraction_report.md](./superpoint_extraction_report.md).
- Shards are atomic and resumable. Model/config signatures prevent reuse of shards generated with different preprocessing or settings.

### Index behavior

The NumPy cosine-similarity index stores normalized DINOv2 descriptors and tile IDs. Search returns the top five with their metadata and scores. The index builder refuses incomplete feature sets by default; search also refuses an incomplete manifest. An explicit `--allow-incomplete` build is available only for smoke testing, and the validation script's `--allow-partial` flag marks its results as non-exhaustive.

The complete manifest reports **30,485 / 30,485** descriptors, zero missing tiles, and validated geospatial metadata. The previous pilot index was preserved as `global_features/satellite_index_partial_pilot.npz`.

## Historical five-flight pilot retrieval experiment

One first-listed drone image was used per flight. The 13-tile pilot candidate set deliberately included tiles containing the five images' Phase 1 GPS centers plus a small set of distant-map controls. It is therefore a **selected, partial candidate set**, not an exhaustive search. Ground-truth fields report parent-map agreement and whether the known GPS center falls inside the candidate patch; neither is a verified visual localization.

Latency covers query descriptor extraction plus NumPy retrieval with the model already loaded. RSS is resident process memory after each query, not a sampled peak.

| Flight / image | Top-five parent maps (cosine scores, descending) | Correct parent-map candidate in top 5 | Latency | RSS after query |
|---|---|---:|---:|---:|
| 01 / `01_0001.JPG` | 01 (.7418), 09 (.6600), 06 (.6574), 05 (.6548), 05 (.5485) | Yes; rank 1 | 378.5 ms | 464.3 MiB |
| 05 / `05_0001.JPG` | 05 (.7594), 05 (.7208), 06 (.6333), 04 (.6252), 09 (.5248) | Yes; ranks 1–2 | 194.8 ms | 465.6 MiB |
| 09 / `09_0001.JPG` | 09 (.7499), 01 (.7410), 05 (.6748), 06 (.6681), 04 (.5945) | Yes; rank 1 | 260.9 ms | 465.6 MiB |
| 02 / `02_0001.JPG` | 05 (.7631), 05 (.7537), 04 (.7431), 06 (.7056), 09 (.6205) | No | 252.8 ms | 465.6 MiB |
| 10 / `10_0001.JPG` | 10 (.6725), 02 (.5061), 10 (.5011), 03 (.4858), 02 (.3722) | Yes; ranks 1 and 3 | 211.3 ms | 466.1 MiB |

The average measured query latency was **259.7 ms**. Flight 02 did not retrieve a same-parent tile in this selected top five. This historical experiment used a selected, partial pilot index; its rows are not the current root CSV. It does not establish retrieval accuracy or localization performance.

## Full-index five-flight retrieval experiment

The required root [retrieval_validation.csv](./retrieval_validation.csv) now contains 25 top-five rows from the complete 30,485-tile index; all rows are marked `index_complete=True`. Average retrieval latency was **321.2 ms**.

| Flight | Expected parent | Top-ranked parent (score) | Parent-map hits in top 5 | GPS center inside a candidate |
|---|---|---|---:|---:|
| 01 | satellite01 | satellite09 (0.8077) | 0 | 0 |
| 05 | satellite05 | satellite11 (0.7896) | 0 | 0 |
| 09 | satellite09 | satellite03 (0.8565) | 0 | 0 |
| 02 | satellite02 | satellite08 (0.8528) | 0 | 0 |
| 10 | satellite10 | satellite10 (0.6725) | 4 | 1 |

This is a small retrieval experiment with GPS/parent-map comparisons, **not localization accuracy**. Cosine similarity and candidate ranking do not establish that a geographic match is correct.

## Files and resuming full processing

Tracked entry points:

- `generate_satellite_tiles.py`
- `extract_dinov2_features.py`
- `extract_superpoint_features.py`
- `build_satellite_index.py`
- `search_satellite_index.py`
- `validate_satellite_index.py`
- `phase3c_common.py`
- `index_config.yaml`
- `satellite_tile_metadata.csv`

From the repository root in PowerShell, run the full extraction in order:

```powershell
& .\.venv\Scripts\python.exe .\backend\training\uav_visloc\phase3_pretrained_setup\phase3c\generate_satellite_tiles.py
& .\.venv\Scripts\python.exe .\backend\training\uav_visloc\phase3_pretrained_setup\phase3c\extract_dinov2_features.py
& .\.venv\Scripts\python.exe .\backend\training\uav_visloc\phase3_pretrained_setup\phase3c\extract_superpoint_features.py
& .\.venv\Scripts\python.exe .\backend\training\uav_visloc\phase3_pretrained_setup\phase3c\build_satellite_index.py
& .\.venv\Scripts\python.exe .\backend\training\uav_visloc\phase3_pretrained_setup\phase3c\validate_satellite_index.py
```

Rerunning an extractor skips valid, matching completed shards and recomputes an invalid or partial shard. DINOv2 is complete; resume SuperPoint from `metadata/superpoint_full_extraction.json` when memory is adequate. The existing 0.5 GiB safety threshold stopped the last SuperPoint run. Do not pass `--allow-incomplete` or `--allow-partial` for final index/validation. The complete index and five-flight experiment have already been generated. Query an image with:

```powershell
& .\.venv\Scripts\python.exe .\backend\training\uav_visloc\phase3_pretrained_setup\phase3c\search_satellite_index.py --image <drone-image-path>
```

## Validation and final readiness

Passed: all 14 TIFF inspections; Flight 09 adjacency check; generated count and unique IDs; representative affine/bounds checks; full DINOv2 feature count, dimension, finiteness, normalization, and unique metadata coverage; full-index build and geospatial validation; full-index top-five retrieval for all five flights; complete audit of 12,421 SuperPoint patches for unique IDs, 3-column keypoint shape, 256-D descriptor shape, and finite values.

**Phase 4 localization readiness: No.** The DINOv2 retrieval index is complete and validated, but the SuperPoint cache is incomplete and the five-flight retrieval rankings are not localization accuracy. Resume SuperPoint and perform the downstream matching/geometric validation before declaring the full Phase 3C feature set complete or relying on it for localization.
