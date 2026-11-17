# Complete Satellite Index Validation

## Status: COMPLETE AND VALIDATED

- Satellite patches with metadata: 30,485
- Unique indexed tile IDs: 30,485
- Missing features: 0
- Unknown feature IDs: 0
- Duplicate feature IDs: 0
- Descriptor dimensions: 384
- All descriptors finite and L2-normalized: yes
- Parent/patch geospatial transforms and geographic bounds: validated
- Index file: `E:\Drone-image-intelligence\backend\training\uav_visloc\phase3_pretrained_setup\phase3c\global_features\satellite_index.npz`

The five-flight full-index experiment queried one representative image each from Flights 01, 05, 09, 02, and 10. The CSV contains 25 top-five rows and marks every row `index_complete=True`.

| Flight | Expected parent | Top-ranked parent (score) | Parent-map hits in top 5 | GPS center inside a candidate | Retrieval latency |
|---|---|---|---:|---:|---:|
| 01 | satellite01 | satellite09 (0.8077) | 0 | 0 | 435.0 ms |
| 05 | satellite05 | satellite11 (0.7896) | 0 | 0 | 271.9 ms |
| 09 | satellite09 | satellite03 (0.8565) | 0 | 0 | 300.9 ms |
| 02 | satellite02 | satellite08 (0.8528) | 0 | 0 | 319.5 ms |
| 10 | satellite10 | satellite10 (0.6725) | 4 | 1 | 278.8 ms |

Mean retrieval latency was 321.2 ms. The CSV also records per-result RSS and candidate metadata. These are retrieval rankings and comparisons against available parent-map/GPS metadata, **not localization accuracy**; cosine similarity alone does not establish a geographic match.
