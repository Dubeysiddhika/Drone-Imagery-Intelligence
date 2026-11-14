# Phase 3A: Pretrained Visual Localization Environment Setup Report

## 1. Objective

This phase evaluated the existing Python environment for a CPU-only pretrained visual localization pipeline that uses:
- DINOv2 for global descriptor extraction and satellite candidate retrieval
- SuperPoint for local feature detection
- LightGlue for local feature matching
- OpenCV for geometric verification
- Rasterio and PyProj for geospatial operations

The goal was to prepare the environment without custom training or fine-tuning.

## 2. Environment inspection results

The environment was inspected without modifying installed packages.

### Current environment baseline
- Python: 3.13.5
- Pip: 25.1.1
- PyTorch: 2.14.1+cpu
- Torchvision: 0.29.1+cpu
- CUDA: unavailable
- CPU: 12th Gen Intel Core i5-1235U
- System RAM: approximately 7.68 GB
- OpenCV: 5.0.0
- Rasterio: 1.5.2
- PyProj: 3.8.0
- Folium: 0.20.0

### Missing packages
- transformers: not installed
- kornia: not installed
- lightglue: not installed
- faiss: not installed

### Summary

The environment already contains the foundational Python, PyTorch, OpenCV, and geospatial libraries. The main gap is missing pretrained inference dependencies.

## 3. Compatibility assessment

The current configuration supports a CPU-only inference stack in principle.

Key compatibility findings:
- PyTorch 2.14.1+cpu is already installed and is compatible with a CPU-only workflow.
- Transformers is needed for DINOv2 model loading and feature extraction.
- LightGlue can be installed from the official source repository and can be used with pretrained SuperPoint weights.
- CUDA is unavailable, which means the workflow must run on CPU only and should be designed for lightweight retrieval-first inference.
- The environment should not be upgraded or replaced unless a concrete compatibility issue appears during real model loading.

## 4. Dependency installation plan

The dependency plan was written and stored in:
- [backend/training/uav_visloc/phase3_pretrained_setup/dependency_plan.md](./dependency_plan.md)

Recommendation summary:
- install transformers
- install LightGlue from the official GitHub source
- optionally install Kornia for image and geometric utilities
- keep the existing PyTorch, OpenCV, Rasterio, and PyProj stack unchanged
- delay FAISS unless descriptor indexing becomes performance-critical

No installation was performed during this planning stage, in compliance with the project restriction that packages should not be installed before the dependency plan is presented.

## 5. Model architecture plan

The architecture plan was documented in:
- [backend/training/uav_visloc/phase3_pretrained_setup/model_architecture_plan.md](./model_architecture_plan.md)

Core design:
- DINOv2 extracts global descriptors for drone images and satellite tiles
- descriptor vectors are compared by cosine similarity
- top-K candidate tiles are retained for local matching
- SuperPoint extracts local features from the shortlist
- LightGlue matches local features
- OpenCV RANSAC verifies the geometry
- Rasterio/PyProj map the match back into geospatial coordinates

This design does not require custom training or fine-tuning.

## 6. CPU performance plan

The CPU plan was documented in:
- [backend/training/uav_visloc/phase3_pretrained_setup/cpu_performance_plan.md](./cpu_performance_plan.md)

Main conclusions:
- The machine has limited RAM and no GPU, so processing should stay lightweight.
- Full exhaustive matching over the complete dataset is not the correct first pass.
- The recommended approach is retrieval-first, shortlist-based matching.
- Descriptor caching is necessary to avoid repeated heavy inference.
- A small candidate set of 3 to 10 tiles per drone image is the sensible first configuration.

## 7. Inference test plan

The inference test plan was documented in:
- [backend/training/uav_visloc/phase3_pretrained_setup/inference_test_plan.md](./inference_test_plan.md)

The eventual validation test will use representative images from Flights 01, 05, 09, 02, and 10. It will:
1. load one drone image
2. load relevant geospatial candidates
3. extract DINOv2 descriptors
4. shortlist top candidate tiles
5. run SuperPoint + LightGlue matching
6. verify geometry by OpenCV RANSAC
7. report the match result

No full inference implementation was executed in this phase.

## 8. Final classification

Classification: READY AFTER DEPENDENCY INSTALLATION

Reasoning:
- the environment is already compatible with a CPU-only pretrained inference approach in principle
- essential packages are missing but not inherently incompatible
- no custom training is required
- the remaining barrier is installation and a lightweight validation run, not a redesign of the pipeline

## 9. Recommendation

The next step is to request approval to install the planned dependency set and then run a minimal representative inference test from the test plan. After that, the project can be reclassified as either:
- READY FOR CPU INFERENCE if the minimal pipeline works cleanly, or
- REQUIRES ENVIRONMENT CHANGES if compatibility issues appear during actual model loading or inference.

At this stage, the environment is ready for dependency installation and lightweight pretrained inference setup, but it is not yet operational for the full DINOv2 + SuperPoint + LightGlue workflow without those missing packages.
