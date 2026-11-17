# Phase 3A Dependency Installation Plan

## Status

This plan reflects the current environment state after inspection only. No packages were installed, upgraded, or removed during the inspection step.

## Environment baseline

Current virtual environment:
- Python: 3.13.5
- Pip: 25.1.1
- PyTorch: 2.14.1+cpu
- Torchvision: 0.29.1+cpu
- CUDA: unavailable
- OpenCV: 5.0.0
- Rasterio: 1.5.2
- PyProj: 3.8.0
- Folium: 0.20.0
- transformers: not installed
- kornia: not installed
- lightglue: not installed
- faiss: not installed

## Dependency recommendations

### 1) transformers
- Proposed package: transformers
- Proposed version: latest stable compatible release, typically 4.46.x or newer, with a conservative pin such as "transformers>=4.46.0,<5.0.0"
- Purpose: DINOv2 model loading and feature extraction utilities, along with model hub access for pretrained checkpoints.
- Compatibility considerations: Official transformers metadata confirms support for Python 3.11+, and the project is using PyTorch 2.14 CPU. This is compatible with the current environment without altering the base PyTorch stack.
- Dependency impact: adds model-download and inference utilities; does not require modifying the existing PyTorch installation.

### 2) torchvision
- Proposed package: torchvision
- Proposed version: keep the existing installed version, 0.29.1+cpu, unless a future requirement specifically forces a bump; no change recommended at this stage.
- Purpose: image preprocessing and shared vision utilities that work with the existing PyTorch CPU environment.
- Compatibility considerations: already installed and compatible with the current CPU-only PyTorch build.
- Dependency impact: no new dependency change needed.

### 3) kornia
- Proposed package: kornia
- Proposed version: latest compatible release for PyTorch 2.14 / Python 3.13; a conservative target is "kornia>=0.8.0,<0.9.0"
- Purpose: optional image preprocessing, geometric utilities, and robust image-to-image operations; useful for local feature and homography workflows.
- Compatibility considerations: PyPI metadata lists support for Python 3.11-3.13 and PyTorch integration. Compatible with the current environment and CPU-only operation.
- Dependency impact: new dependency; no PyTorch replacement required.

### 4) lightglue
- Proposed package: LightGlue from the official source repository
- Proposed version: install from GitHub source, not from an unverified binary build
- Command pattern: git clone https://github.com/cvg/LightGlue.git && pip install -e .
- Purpose: local feature matching backbone used with SuperPoint or alternative local feature extractors.
- Compatibility considerations: the official LightGlue README states that it can be installed from source with pip install -e ., and that it ships with pretrained weights for SuperPoint and related features. The project is CPU-compatible, but the runtime will be slower than GPU-only performance.
- Dependency impact: new dependency; does not require a PyTorch downgrade or upgrade. It is a standard source install and is the official path recommended by the project authors.

### 5) opencv-python
- Proposed package: opencv-python
- Proposed version: keep the current installed version 5.0.0 if it remains stable; no change needed unless a specific feature is missing.
- Purpose: geometric verification through RANSAC, homography estimation, and image manipulation.
- Compatibility considerations: OpenCV wheels explicitly support Python 3.10-3.14 and are widely compatible with the current Windows CPU environment.
- Dependency impact: no new install required for current checks.

### 6) faiss-cpu
- Proposed package: faiss-cpu
- Proposed version: optional; only if large-scale descriptor indexing becomes necessary
- Purpose: high-speed nearest-neighbor search for DINOv2 descriptor retrieval if the satellite index grows beyond a lightweight NumPy-based top-K search.
- Compatibility considerations: optional and not required for the initial CPU-only prototype. For a small satellite index, a simple NumPy cosine-similarity search is lighter and less brittle than introducing a heavy FAISS dependency.
- Dependency impact: optional, only if retrieval performance demands a larger index.

## Recommended install set for the initial phase

1. transformers
2. lightglue from official GitHub source
3. kornia (optional but helpful for geometric preprocessing and compatibility with local matching workflows)
4. Keep the existing PyTorch, Torchvision, OpenCV, Rasterio, PyProj, and Folium installations unchanged
5. Delay FAISS until the initial retrieval prototype is benchmarked and the index size requires it

## Compatibility note

The LightGlue project explicitly states that its pretrained weights are released for SuperPoint and other local feature methods and are accessible via the official model hub. This means the project can use the pretrained matcher without custom training or fine-tuning.

## Decision

The current environment is suitable for dependency installation without replacing the existing PyTorch stack. The recommended path is to install only the missing inference libraries and not to touch the base runtime beyond that.
