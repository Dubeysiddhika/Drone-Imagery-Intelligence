# Phase 2B Verification Report

## 1. Goal

Phase 2B evaluated whether the project is ready for Phase 3: a pretrained DINOv2 retrieval stage plus SuperPoint/LightGlue matching without custom training.

## 2. Audit of previous phases

The previous Phase 1 and Phase 2A outputs were reviewed and found to be mutually consistent:

- 6,774 valid metadata rows
- 14 georeferenced TIFFs
- 8 out-of-coverage drone points preserved as uncertain
- 6,766 positive candidate pairs and 6,766 negative candidate pairs
- no fabricated footprint estimate

The earlier decisions remain valid: uncertain pairs are excluded from the confirmed training set, and no image-footprint claim was made without calibration.

## 3. Camera and calibration review

The dataset does not provide the calibration information needed for photogrammetric footprint estimation.

No evidence was found for:

- focal length
- sensor size
- camera model
- calibration file
- intrinsic matrix
- distortion coefficients

Representative EXIF metadata checks found empty metadata blocks. The dataset supplies center coordinates and orientation angles, but not the required camera geometry.

## 4. Footprint feasibility

The footprint estimate is not feasible without external calibration and terrain assumptions. The project therefore continues to avoid treating GPS center coordinates as if they were the full image extent. This remains a hard limitation, not a modeling shortcut.

## 5. Visual suitability review

Representative drone-satellite comparisons were generated for Flights 01, 05, 09, 02, and 10. These visual audits show visually plausible local scene matches and confirm that the georeferenced tiles preserve their geographic context and basic visual structure. The tiles appear suitable for pretrained local feature matching.

## 6. Uncertain cases

The eight uncertain cases from Flights 06 and 07 were reviewed and kept separate from the confirmed set. They remain outside validated coverage and belong in a manual-review bucket, not in the positive training pool.

## 7. Negative-pair review

The negative pairs are overwhelmingly distant. The minimum negative distance observed was 1,112 km, with a median near 1,909 km. This makes false negatives from the same local scene highly unlikely.

## 8. Environment and model readiness

The current environment was checked:

- Python 3.13.5
- PyTorch 2.14.1+cpu
- CUDA: unavailable
- GPU: not detected
- transformers, lightglue, kornia, superpoint: not installed

This means the unrestricted Phase 3 workflow is not ready in the current workspace. The concept is viable, but the execution environment is not yet prepared for pretrained DINOv2 and SuperPoint/LightGlue matching without additional package approval and likely a GPU-enabled setup.

## 9. Final readiness assessment

Overall readiness for Phase 3 is:

- geospatial pipeline: ready for conservative pair review
- visual tile suitability: acceptable for local feature matching
- camera calibration and footprint rigor: not ready without external metadata
- pretrained model execution environment: not yet ready

Conclusion: the project is not yet fully ready for Phase 3 in the current environment, but it is conceptually ready for a pretrained-matching workflow once the environment is approved and the required dependencies are available.
