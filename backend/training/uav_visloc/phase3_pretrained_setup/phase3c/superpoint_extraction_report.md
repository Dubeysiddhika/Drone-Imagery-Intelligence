# SuperPoint Extraction Report

## Status: INCOMPLETE — RESUMABLE

Full SuperPoint extraction began only after DINOv2 completed. It ran separately on CPU with pretrained weights, evaluation mode, `torch.inference_mode()`, and at most 512 keypoints per patch. It safely stopped at the configured memory threshold and preserved completed shards.

| Measure | Result |
|---|---:|
| Generated satellite patches | 30,485 |
| Completed full-run features at the latest checkpoint | 12,421 / 30,485 (40.74%) |
| Missing features at the latest checkpoint | 18,064 |
| Newly extracted in the latest resume run | 2,908 |
| Reused existing features in the latest resume run | 9,513 |
| Failed images | 0 |
| Keypoints and 256-D descriptors cached | 5,666,244 each |
| Maximum keypoints per patch | 512 |
| Device / inference settings | CPU / pretrained / eval / `torch.inference_mode()` |
| Elapsed time across resumed runs | 22,691.422 seconds |
| Average inference time per newly extracted patch | 1.7601797245 seconds |
| Peak process RSS | 742,932,480 bytes (about 708.4 MiB) |
| Minimum available system RAM observed | 312,188,928 bytes (about 297.7 MiB) |
| Complete-run shard cache size | 5,417,872,951 bytes |

The checkpoint is at `metadata/superpoint_full_extraction.json` with `status=stopped_for_memory`. The latest resume stopped safely after saving shard 195 and did not delete or rebuild existing shards. A complete post-run audit found 12,421 unique extracted IDs, 18,064 missing IDs, 0 duplicate IDs, 0 unknown IDs, 0 unreadable shards, and 0 invalid shards. Keypoints are `(x, y, score)` with 3 columns, descriptors are 256-D, all keypoints/descriptors are finite, and no patch exceeds 512 keypoints. The 195 complete-run shards match the recorded configuration signature. The failure log reports zero failed images. The 8-patch pilot cache remains preserved separately.
