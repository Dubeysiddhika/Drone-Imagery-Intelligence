# Phase 3B CPU inference benchmark

## Test configuration

- Model: DINOv2 ViT-S/14 (pretrained via PyTorch Hub)
- Local feature pipeline: SuperPoint + LightGlue
- Device: CPU only
- Representative image: Flight 01, drone image 01_0001.JPG
- DINOv2 input size: 224x224 RGB
- SuperPoint/LightGlue input: representative pair on CPU

## Measured timings

- DINOv2 model-loading time: 3.583 s
- DINOv2 first inference time: 0.133 s
- DINOv2 second inference time: 0.124 s
- SuperPoint inference time: 6.378 s
- LightGlue matching time: 0.842 s
- Peak RSS during verification: 1189.1 MB

## Notes

- CUDA is unavailable; all results are CPU-only.
- No GPU performance is claimed.
- Peak RSS was measured via `psutil` on the Python process and is a proxy for active memory use rather than a full-system memory read.
