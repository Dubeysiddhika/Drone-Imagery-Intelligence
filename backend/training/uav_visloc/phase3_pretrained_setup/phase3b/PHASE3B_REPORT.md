# Phase 3B Report

## Objective

This phase installed the minimal official LightGlue dependency set and verified that the pretrained DINOv2 ViT-S/14 and the SuperPoint + LightGlue stack run successfully on CPU in the existing `.venv` environment without custom training or fine-tuning.

## Deployment and installation

The official LightGlue project was cloned into the workspace and installed from source. Its `requirements.txt` declares the required dependencies as:

- `torch>=1.9.1`
- `torchvision>=0.3`
- `numpy`
- `opencv-python`
- `matplotlib`
- `kornia>=0.6.11`

This means `kornia` is a required dependency for the official implementation. The install did not replace or upgrade the existing `torch` or `torchvision` packages.

## Model verification

The following checks passed on a representative Flight 01 image:

- DINOv2 ViT-S/14 loaded successfully via PyTorch Hub.
- Output shape: `(1, 384)`.
- All values finite: `True`.
- SuperPoint loaded pretrained weights successfully.
- LightGlue initialized successfully and matched a representative image pair on CPU.

## CPU benchmark

Measured values:

- DINOv2 model-loading time: 3.583 s
- DINOv2 first inference time: 0.133 s
- DINOv2 second inference time: 0.124 s
- SuperPoint extraction time: 6.378 s
- LightGlue matching time: 0.842 s
- Peak RSS during verification: 1189.1 MB

## Final status

DINOv2: PASS on CPU
SuperPoint: PASS on CPU
LightGlue: PASS on CPU

The minimal pretrained CPU-only inference stack is working in the current environment, and no custom training or fine-tuning was performed.
