# Phase 3H — Low-Memory Local Matching Smoke Test

- Status: **completed**
- Method: SuperPoint + LightGlue + OpenCV RANSAC
- Device: CPU
- Completed pairs: 1/1
- Input max side: 512px
- SuperPoint keypoint cap: 256
- Model load time: 0.29s
- Mean tentative matches: 13.0
- Mean RANSAC inliers: 4.0
- Mean inlier ratio: 0.30769
- Peak process RSS: 450.3 MiB

## Limitations

This is a deliberately small engineering smoke test. It uses only the first selected retrieval-validation candidate(s), reduced image size, and a reduced keypoint cap. It is not a full benchmark and must not be reported as a localization-accuracy result. RANSAC consistency alone does not prove geographic correctness; camera calibration and independent ground truth would be needed for that claim.

The script does not retrain models, rebuild the DINOv2 index, load the multi-gigabyte SuperPoint cache, or resume exhaustive feature extraction.
