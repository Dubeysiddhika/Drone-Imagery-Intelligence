# SuperPoint Extraction Report

## Status: INCOMPLETE — RESUMABLE

Full SuperPoint extraction began only after DINOv2 completed. It ran separately on CPU with pretrained weights, evaluation mode, `torch.inference_mode()`, and at most 512 keypoints per patch. It safely stopped at the configured memory threshold and preserved completed shards.

| Measure | Result |
|---|---:|
| Generated satellite patches | 30,485 |
| Completed full-run features at the latest checkpoint | 7,232 / 30,485 (23.72%) |
| Missing features at the latest checkpoint | 23,253 |
| Newly extracted during the full run | 7,224 |
| Reused pilot features | 8 |
| Failed images | 0 |
| Keypoints and 256-D descriptors cached | 2,207,794 each |
| Maximum keypoints per patch | 512 |
| Device / inference settings | CPU / pretrained / eval / `torch.inference_mode()` |
| Elapsed time across resumed runs | 13,396.72 seconds or more |
| Average inference time per newly extracted patch | 1.790 seconds (checkpoint snapshot) |
| Peak process RSS | 742,932,480 bytes (about 708.4 MiB) |
| Minimum available system RAM observed | 312,188,928 bytes (about 297.7 MiB) |
| Complete-run shard cache size | 3,211,309,583 bytes |

The checkpoint is at `metadata/superpoint_full_extraction.json`; the extraction process is continuing with `status=in_progress` at this report's latest snapshot. Memory-triggered stops and resumes preserve completed shards. The failure log reports zero failed images. A shard audit at 4,736 features found no duplicate or unknown tile IDs, invalid feature shapes, non-finite keypoints/descriptors, or patches exceeding the keypoint limit. The 8-patch pilot cache remains preserved separately.
