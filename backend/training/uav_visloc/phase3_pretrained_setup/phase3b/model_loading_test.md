# Phase 3B model loading test

## Environment recheck

- torch: 2.14.1+cpu
- torchvision: 0.29.1+cpu
- cv2: 5.0.0
- rasterio: 1.5.2
- pyproj: 3.8.0
- numpy: 2.5.3
- PIL: 12.3.0
- CUDA available: False

## DINOv2 verification

- Load time: 3.583 s
- First inference time: 0.133 s
- Second inference time: 0.124 s
- Output shape: (1, 384)
- All finite: True

## SuperPoint and LightGlue verification

- SuperPoint extraction time: 6.378 s
- LightGlue match time: 0.842 s
- Keypoints from image 0: 1
- Keypoints from image 1: 1
- Match keys: ['matches', 'matches0', 'matches1', 'matching_scores0', 'matching_scores1', 'prune0', 'prune1', 'scores', 'stop']

The pretrained DINOv2 ViT-S/14 model successfully loads via PyTorch Hub on CPU, and the pretrained SuperPoint + LightGlue stack executes successfully on a representative Flight 01 input with no custom training.
