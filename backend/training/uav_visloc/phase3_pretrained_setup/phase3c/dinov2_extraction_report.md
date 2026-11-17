# DINOv2 Extraction Report

## Status: COMPLETE

Pretrained DINOv2 ViT-S/14 was run on CPU in evaluation mode under `torch.inference_mode()`. Extraction resumed from its existing shards; cached descriptors were reused rather than recomputed. Memory-triggered stops preserved the completed shards, and extraction ultimately finished with all metadata tile IDs covered.

| Measure | Result |
|---|---:|
| Generated, validated satellite patches | 30,485 |
| Complete-run descriptors | 30,485 / 30,485 |
| Features extracted by DINOv2 inference | 30,472 |
| Features reused from the pilot cache | 13 |
| Missing descriptors | 0 |
| Failed images | 0 |
| Descriptor dimension | 384 |
| Descriptor validation | Finite and L2-normalized |
| Device / inference settings | CPU / eval / `torch.inference_mode()` |
| Total extraction time across runs | 29,557.25 seconds |
| Inference time | 29,453.29 seconds |
| Average inference time per extracted descriptor | 0.9666 seconds |
| Peak process RSS | 502,206,464 bytes (about 478.9 MiB) |
| Minimum available system RAM observed | 252,567,552 bytes (about 240.9 MiB) |
| Complete-run feature shard cache size | 44,055,293 bytes |

The configured 0.5 GiB available-RAM threshold caused safe stops and resumptions; the completed checkpoint reports `status=complete`, zero missing descriptors, and zero failures. The full cache is under `global_features/dinov2_complete_shards/`; the original pilot cache remains preserved separately.
