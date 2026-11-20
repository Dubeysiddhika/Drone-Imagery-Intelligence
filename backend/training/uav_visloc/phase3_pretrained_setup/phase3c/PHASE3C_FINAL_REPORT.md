# Phase 3C Final Report

## Final classification: INCOMPLETE

The complete DINOv2 satellite retrieval index is built and validated. Overall Phase 3C remains **incomplete** because the SuperPoint cache contains 12,421 of 30,485 patches at the latest verified checkpoint, with 18,064 patches missing after a memory-safe stop. Do not treat the five-flight retrieval experiment as localization accuracy.

## Completed and preserved

- 30,485 satellite patches were generated and validated, with unique IDs and preserved parent and patch georeferencing.
- The original 14 source TIFFs and prior Phase 1/2A outputs were not modified.
- DINOv2 ViT-S/14 CPU extraction completed all 30,485 descriptors, reusing existing features and recording zero failures.
- A shard-by-shard audit found no missing/duplicate/unknown tile IDs, non-finite or non-normalized descriptors, or inconsistent dimensions.
- The complete NumPy cosine index contains all 30,485 normalized 384-D descriptors. Its manifest verifies complete metadata coverage and geospatial transform validation.
- The required five-flight experiment ran against the complete index and wrote 25 top-five rows to `retrieval_validation.csv`, all marked `index_complete=True`.
- SuperPoint extraction began only after DINOv2 finished and resumed from the existing checkpoint. The latest audited state is 12,421 completed patches: 2,908 newly extracted in the latest run and 9,513 reused existing features, with zero failed images.
- The original DINOv2 and SuperPoint pilot caches were preserved separately.

## Not completed

- Full SuperPoint coverage at the latest verified checkpoint: 12,421 / 30,485; 18,064 features remain.
- Full local-feature cache and matching validation are not complete.
- The retrieval experiment is a small initial retrieval study, not a measure of localization accuracy.

See [dinov2_extraction_report.md](./dinov2_extraction_report.md), [superpoint_extraction_report.md](./superpoint_extraction_report.md), and [complete_index_validation.md](./complete_index_validation.md) for counts and validation details.

## Resource summary

- DINOv2 elapsed time across attempts: 29,557.25 seconds; average inference time: 0.9666 seconds per extracted feature.
- DINOv2 peak process RSS: 502,206,464 bytes; minimum available system RAM observed: 252,567,552 bytes.
- SuperPoint elapsed time across runs: 22,691.422 seconds; 1.7601797245 seconds average inference time per newly extracted patch in the latest checkpoint; peak process RSS: 742,932,480 bytes.
- Satellite patch cache: 2,949,697,322 bytes.
- DINOv2 complete-run feature cache: 44,055,293 bytes.
- SuperPoint complete-run feature cache at the latest verified checkpoint: 5,417,872,951 bytes across 195 shards.
- No existing caches were deleted.

## Resume conditions

The latest SuperPoint resume stopped gracefully with `status=stopped_for_memory` after saving shard 195. The complete post-run audit found 0 duplicate, unknown, unreadable, invalid, or failed patches; 5,666,244 finite keypoints and 256-D descriptors are cached. Finish and validate SuperPoint before treating the full Phase 3C feature suite as complete. Do not interpret the five-flight rankings or cosine similarity as a verified geographic match.

No training, fine-tuning, CUDA, or FAISS was used. No YOLO, API route, database schema, frontend, or source dataset changes were made.
