# Phase 3D Retrieval Optimization Report

## Scope and artifacts audited

This report audits the existing completed DINOv2 retrieval index without rerunning DINOv2 extraction or rebuilding the index. It also does not modify or resume SuperPoint extraction.

Audited artifacts:

- `extract_dinov2_features.py`
- `build_satellite_index.py`
- `validate_satellite_index.py`
- `phase3c_common.py`
- `satellite_tile_metadata.csv`
- `satellite_index.npz`
- `satellite_index_manifest.json`
- `retrieval_validation.csv`
- `retrieval_validation.json`
- `create_geographic_splits.py`
- `train_pairs.csv`
- `validation_pairs.csv`
- `test_pairs.csv`
- `SUPERPOINT_EXTRACTION_OPTIMIZATION_REPORT.md`

No existing feature shard, DINOv2 index, SuperPoint cache, checkpoint, or metadata file was changed.

## Existing index and ground-truth definitions

The DINOv2 index contains 30,485 unique tile IDs and 30,485 finite, L2-normalized 384-D descriptors. The index manifest confirms complete metadata coverage and no duplicate or unknown IDs.

The existing evaluation uses five representative drone images: first image in Flights 01, 05, 09, 02, and 10. The query preprocessing is the existing DINOv2 pipeline:

- RGB conversion
- aspect-ratio-preserving thumbnail inside a 224-pixel square
- ImageNet mean/std normalization
- pretrained `dinov2_vits14`
- CPU, evaluation mode, `torch.inference_mode()`
- normalized 384-D output

Satellite descriptors use the same 224-pixel preprocessing and L2 normalization. Ranking uses NumPy cosine similarity:

`scores = normalized_index_descriptors @ normalized_query_descriptor`

Three metrics are not interchangeable:

1. **Parent satellite map recall**
   - At least one candidate in the top K has `parent_satellite_map_id` equal to the expected map from `consolidated_drone_metadata.csv`.
   - This is map-region recall, not patch or localization recall.

2. **GPS-center patch recall**
   - At least one top-K candidate is a patch whose affine-transformed bounds contain the drone image's recorded GPS center.
   - This is an exact center-patch proxy.
   - It does not prove that the drone image's full footprint or visual content matches the patch.

3. **Candidate patch retrieval recall**
   - A broader, unresolved definition that requires a verified positive satellite candidate patch or local-match ground truth.
   - The current CSV and metadata do not contain a verified drone-image-to-patch visual ground truth.
   - Therefore candidate patch recall cannot be honestly reported as 20%, 40%, or 60%.
   - GPS-center patch recall is the measured proxy, while candidate patch recall remains unmeasured.

The existing `point_inside_tile()` calculation uses the retained six-coefficient patch affine transform. It does not estimate a footprint and is valid only as a center-in-patch check.

## Confirmation of existing Recall@K values

The stored full-index experiment contains 25 Top-5 rows. It confirms:

| Flight | Split | Top-ranked parent | GPS-center candidate in Top 5 | Parent-map hit in Top 5 |
|---|---|---|---:|---:|
| 01 | train | satellite09 | 0 | 0 |
| 05 | validation | satellite11 | 0 | 0 |
| 09 | train | satellite09 | 0 | 0 |
| 02 | test | satellite08 | 0 | 0 |
| 10 | test | satellite10 | 1 | 4 |

The historical Top-K recalculation recorded in `SUPERPOINT_EXTRACTION_OPTIMIZATION_REPORT.md` is consistent with the stored Top-5 data:

| K | Parent-map Recall@K | GPS-center patch Recall@K |
|---:|---:|---:|
| 5 | 20% (1/5) | 20% (1/5) |
| 10 | 40% (2/5) | 20% (1/5) |
| 20 | 40% (2/5) | 20% (1/5) |
| 50 | 60% (3/5) | 40% (2/5) |
| 100 | 60% (3/5) | 40% (2/5) |

The definition and arithmetic are reproducible from the Top-5 CSV only through K=5; K=10–100 are not saved in `retrieval_validation.csv` or the existing JSON report. They come from a separate reranking of the 30,485-vector index. The report should therefore treat K=10–100 as previously measured extension values, not as a stored artifact.

### Candidate patch recall

No candidate patch visual ground truth is available in the existing validation artifacts. The existing result:

- verifies parent-map agreement
- verifies whether the GPS center lies in a candidate patch
- does not verify visual overlap, homography, pose, or localization

Therefore:

- Candidate patch Recall@5/10/20/50/100: **not measured**
- GPS-center patch Recall@5/10/20/50/100: 20/20/20/40/40
- Parent-map Recall@5/10/20/50/100: 20/40/40/60/60

## Retrieval limitations

### DINOv2 and satellite preprocessing

The existing global embedding pipeline is internally consistent:

- same RGB conversion
- same 224-pixel letterbox/canvas behavior
- same mean/std normalization
- same L2 normalization
- same cosine operator

The main limitation is that one global descriptor is compared against 30,485 visually varied overlapping patches. It does not encode which part of a drone image corresponds to a satellite patch.

### Patch size and overlap

The satellite library uses 512-pixel patches with nominal 20% overlap. Neighboring patches share geographic imagery and are not independent candidates. A GPS center can fall in one exact patch, but a nearby patch may contain substantially overlapping content.

The overlap makes parent-map recall weakly informative and makes exact GPS-center patch recall sensitive to center position and patch boundaries.

### Flight-specific performance

The stored Top-5 result is:

| Flight | Split | GPS-center in Top 5 | Parent hits in Top 5 |
|---|---|---:|---:|
| 01 | train | 0 | 0 |
| 05 | validation | 0 | 0 |
| 09 | train | 0 | 0 |
| 02 | test | 0 | 0 |
| 10 | test | 1 | 4 |

Per-flight geographic misses are concentrated in Flights 01, 05, 09, and 02. This is a severe weakness for the five-image representative set. It is not enough to claim broad flight coverage.

### Geographic distribution

The misses span geographically distinct regions:

- Flight 01: satellite01
- Flight 05: satellite05
- Flight 09: satellite09
- Flight 02: satellite02

Flight 10 is the only representative with strong Top-5 same-map coverage. There is no evidence of one isolated coastline, altitude, or longitude failure from five samples. A larger evaluation is required.

## Geographical splits and leakage

The split is flight-based:

- Train: Flights 01, 03, 04, 08, 09, 11
- Validation: Flight 05
- Test: Flights 02, 10
- Excluded from primary split: uncertain Flights 06 and 07

The five representative images do not form a model-training set. DINOv2 is pretrained and was not trained or fine-tuned. Therefore no model-weight leakage is introduced. However, geographic split boundaries must still govern any tuning:

- Train representatives 01 and 09
- Validation representative 05
- Test representatives 02 and 10

No representative in the current subset should be used to tune a final parameter without being excluded from test reporting.

## Retrieval improvement experiments

### 1. Existing cosine ranking

Result:

- no model or index rewrite
- weak parent and GPS recall in the five-image set
- cheap: approximately 3–5 ms cosine search after DINOv2 query encoding
- mean DINOv2 query latency was approximately 450.6 ms in the historical Top-K extension

This is the safest baseline because it has no retraining or fabricated ground truth.

### 2. Parent-map-aware candidate grouping

A GPS-bearing query can filter candidates to its known map, but that is not available for operational images without GPS. It would reduce work and remove candidates from unrelated parents.

Typical valid-filter counts:

| Parent | Satellite patch count |
|---|---:|
| satellite01 | 1,584 |
| satellite02 | 2,352 |
| satellite03 | 5,160 |
| satellite04 | 4,136 |
| satellite05 | 345 |
| satellite09 | 9,020 |
| satellite10 | 208 |

This count depends on the GPS location's known parent. It is safe to filter only when parent/map association is independently established. It is unsafe to infer or hard-filter an unknown parent.

Oracle parent reranking was investigated only by assigning the known ground-truth parent after ranking. This does not represent an operational filter and cannot create a correct parent that is absent from the original Top-100 candidate set.

It did not materially change the historical result: the five-image parent recall remained 60% at K=100 because adding known parent ordering cannot recover the two misses.

### 3. Adjacent satellite patch expansion

Expanding around top DINO candidates can add nearby patches from the same parent map and exploit 20% overlap. This is an inference-time neighborhood expansion, not model training.

Cost grows much faster than K:

- a candidate neighborhood is map-dependent
- it may add multiple overlapping rows/columns
- 100 cosine-ranked candidates can expand to hundreds or thousands of duplicate-region candidates
- raw overlap count is not visual-match confidence

No verified local-match or candidate-ground-truth data exists to measure whether expansion improves candidate patch localization.

### 4. Geographic neighborhood expansion with GPS

For queries with valid GPS:

- determine whether the GPS center is inside any parent satellite map
- use the containing patch
- optionally add adjacent rows/columns and overlapping patches

This is operationally safer than global cosine ranking only if GPS is valid and the map/patch affine metadata is trusted.

Typical approximate K-independent candidate sets are much smaller if GPS identifies one parent and containing patch. But the project already prohibits treating center GPS as a footprint. The containing patch is only a center candidate.

It is unsafe to use this method for images without GPS.

### 5. Multi-candidate retrieval

Returning a union of cosine candidates and GPS/geographic neighbors can reduce omission risk, but at a cost:

- repeated patches
- on-demand cache churn
- more SuperPoint/LightGlue pairs
- ambiguous matches
- no guaranteed visual verification

Multi-candidate retrieval is appropriate only after local matching and RANSAC, not as a claimed retrieval improvement.

### 6. Alternative reranking

No demonstrated alternative reranking method can claim improvement on this sample. Any reranking based on parent grouping, adjacent expansion, or score fusion:

- must be tested on held-out flights
- must preserve map and split boundaries
- must have candidate patch or matching ground truth
- must not use query GPS for GPS-free evaluation

No trained reranker was used.

## Reproducibility audit

A fresh rerun of the complete index and representative images produced candidate rankings that did not match every stored historical Top-5 row. Parent-map and GPS-center values should therefore not be claimed as a stable, independently verified result until rerun determinism is resolved.

For example:

- Stored Flight 01 Top-5: satellite09 at ranks 1–3
- Fresh rerun: satellite04/satellite03 candidates
- Stored Flight 05: no satellite05 in Top-5
- Fresh rerun: satellite05 in Top-5

Possible causes include model-loading/runtime differences and nondeterministic or stale local PyTorch Hub state. The index artifact itself was not changed, and no model retraining occurred.

Before relying on recall gains, rerun the same five images with a pinned environment, fixed thread count, fixed DINOv2 model revision, and record exact image hash, model cache revision, torch version, and result. The measured historical values remain valid audit records but are not enough to certify repeatability.

## GPS-bearing and GPS-free evaluation

### A. Images with GPS metadata

GPS is valid for evaluation and filtering only after the DINOv2 query is computed. The historical five-image results are GPS-bearing:

- DINOv2 ranking: no GPS used
- parent scoring: GPS/parent map used only after ranking
- center-patch scoring: GPS used only after ranking
- possible geospatial filter: GPS parent and containing patch

Safe GPS-bearing uses:

- separate candidate list by independent map containment
- expand adjacent patches only around the containing parent
- measure correct candidates lost by filtering

### B. Images without GPS metadata

The consolidated dataset has no missing-GPS representative in this evaluation. All 6,774 Phase 1 records are listed with latitude/longitude values.

For GPS-free operational evaluation:

- do not use coordinates to choose, filter, rerank, or score the result
- use only image-derived DINOv2 and, later, SuperPoint/LightGlue evidence
- measure parent recall, GPS-independent candidate recall, and local geometric acceptance
- do not claim a localization result based only on cosine ranking

The historical rankings can be reused as GPS-free DINOv2 rankings, but the parent/patch recall values are calculated only for audit.

## Performance

Historical complete-index retrieval:

- mean Top-5 retrieval latency: approximately 321.2 ms including DINOv2 query and search in the existing validation script
- historical per-flight values: 435.0, 271.9, 300.9, 319.5, and 278.8 ms
- process RSS around 525–528 MiB after DINOv2 loading

Cosine search alone was measured at roughly 3–5 ms for K=5–100. The main latency cost is DINOv2 query encoding and model loading, not Top-K matrix ranking.

Geographic filtering can reduce the candidate count dramatically, but the exact filtered count and lost-candidate rate cannot be claimed without a larger GPS-bearing benchmark.

## Candidate count and filtering risk

Using a GPS-derived parent filter is large and flight-dependent:

| Expected representative parent | Patch count |
|---|---:|
| satellite01 | 1,584 |
| satellite02 | 2,352 |
| satellite05 | 345 |
| satellite09 | 9,020 |

Filtering to a parent does not preserve the 30,485-index ranking. It only removes unrelated parents and therefore cannot repair a miss if the correct parent patch is absent in DINOv2's top candidates.

In the stored Top-100 extension:

- 3 of 5 correct parents were recovered: 60%.
- 2 of 5 correct GPS-center patches were recovered: 40%.

No count of correct candidates lost can be derived for candidate-patch visual recall because that ground truth is absent.

## Recommendation

### Is K=20 sufficient?

No.

In the historical five-image expansion:

- parent recall at K=20: 40%
- GPS-center patch recall at K=20: 20%
- candidate patch recall: unmeasured

K=20 does not provide a reliable retrieval shortlist.

### Is K=50 preferable?

For a GPS-bearing image with a valid, independently known map region, K=50 is a reasonable fallback rather than a claim of superior localization.

For global GPS-free retrieval:

- historical parent recall rises from 40% to 60%
- GPS-center patch recall rises from 20% to 40%
- candidate patch recall remains unmeasured

K=50 is therefore preferable to K=20 as a conservative exploratory shortlist, not as a reliable threshold.

### Is K=100 necessary?

No clear gain over K=50 is demonstrated:

- parent recall remains 60%
- GPS-center recall remains 40%

K=100 adds roughly 50 extra local-matching candidates and can increase cache and compute demand without a measured retrieval gain.

### Is geospatial filtering safe?

Only conditionally:

- safe with independently valid GPS, map bounds, and affine metadata
- unsafe to infer parent or location for GPS-free operation
- unsafe to estimate image footprint from center GPS
- containing-patch and adjacent-patch expansion do not prove visual overlap

The filter must remain an optional candidate constraint, not a hard rejection of all cosine candidates.

### Can on-demand SuperPoint proceed reliably?

Not as a localization implementation yet.

On-demand extraction is technically compatible with the existing shards, but the current retrieval evidence is insufficient to justify treating the shortlist as a reliable candidate set:

- no verified candidate-patch recall
- no local matching/RANSAC result
- no larger held-out validation
- a fresh ranking rerun disagreed with stored five-image rankings

The safe short-term recommendation is:

1. Preserve the existing 217 SuperPoint shards and 13,852-patch checkpoint.
2. Do not resume exhaustive SuperPoint extraction.
3. Do not rebuild DINOv2 or modify the existing index.
4. Do not implement local matching as Phase 4 yet.
5. Add a read-only, on-demand prototype only after a pinned, held-out retrieval benchmark is available.
6. Use K=50 as the conservative default for GPS-bearing exploratory shortlisting.
7. Keep all GPS-free work without geographic filtering.
8. Require SuperPoint/LightGlue plus RANSAC/geometric verification before any localization claim.

The measured evidence supports further candidate retrieval evaluation, but it does not support declaring K=20 reliable or K=50/100 sufficient for localization.
