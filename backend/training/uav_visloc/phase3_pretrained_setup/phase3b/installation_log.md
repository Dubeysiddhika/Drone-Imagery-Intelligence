# Phase 3B dependency installation log

## Dependency check before install

The official LightGlue repository declares the following runtime requirements in its `requirements.txt`:

- `torch>=1.9.1`
- `torchvision>=0.3`
- `numpy`
- `opencv-python`
- `matplotlib`
- `kornia>=0.6.11`

The dry-run installation also showed the following package changes would occur without changing the base torch/torchvision stack:

- `lightglue-0.0` would be installed
- `kornia-0.9.1` would be installed
- `kornia-rs-0.2.0` would be installed
- no replacement or upgrade of the current `torch==2.14.1+cpu` or `torchvision==0.29.1+cpu` was proposed

## Actual install command

```bash
E:\Drone-image-intelligence\.venv\Scripts\python.exe -m pip install -v -e E:\Drone-image-intelligence\backend\training\uav_visloc\third_party\LightGlue
```

## Actual package changes

The installation succeeded and added the following packages to the current environment:

- `lightglue-0.0`
- `kornia-0.9.1`
- `kornia-rs-0.2.0`

The existing CPU PyTorch stack remained unchanged.
