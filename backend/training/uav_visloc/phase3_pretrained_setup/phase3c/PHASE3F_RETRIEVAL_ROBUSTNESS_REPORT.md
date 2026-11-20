# Phase 3F DINOv2 Retrieval Robustness and Satellite Coverage Report

## Scope

This evaluation used the existing completed DINOv2 index and existing geographic validation
data without changing:

- DINOv2 descriptors or satellite index
- SuperPoint shards or checkpoint
- satellite metadata
- model weights or package versions

No training, fine-tuning, package installation, model download, index rebuild, or SuperPoint
extraction occurred.

Audited prior reports:

- `PHASE3D_RETRIEVAL_OPTIMIZATION_REPORT.md`
- `PHASE3E_ALTERNATIVE_RETRIEVAL_REPORT.md`
- `retrieval_validation.csv`
- `satellite_index_manifest.json`
- geographic split and pair files

## Baseline audit

The DINOv2 index remains complete:

- 30,485 DINOv2 descriptors
- 384-D, finite, L2-normalized vectors
- 30,485 unique IDs
- existing 224-pixel satellite preprocessing
- cosine similarity over normalized vectors

The geographic split is:

- Train: Flights 01, 03, 04, 08, 09, 11
- Validation: Flight 05
- Test: Flights 02 and 10
- Uncertain/excluded coverage: Flights 06 and 07

The stored five-representative Top-5 experiment remains limited. It contains one
GPS-containing candidate at K=5, for Flight 10; only Flight 10 has a same-map result in
the existing CSV. The stored historical Top-K extension reported:

| K | Parent-map Recall@K | GPS-center patch Recall@K |
|---:|---:|---:|
| 5 | 20% | 20% |
| 10 | 40% | 20% |
| 20 | 40% | 20% |
| 50 | 60% | 40% |
| 100 | 60% | 40% |

The K=10–100 values were produced as separate reranking experiments and are not stored in
the Top-5 CSV. They are therefore treated as historical observations, not a reproducible
full-split benchmark.

## Full Flight 05 validation benchmark

The validation split contains 946 confirmed rows:

- 473 candidate-positive rows
- 473 candidate-negative rows

The retrieval test used the 473 positive Flight 05 queries. A correct GPS-containing
satellite patch was derived from the retained patch affine transform only after ranking.
It was not used to filter or generate query candidates.

### Original ranking

224-pixel query results for 473 positive validation queries:

| K | Parent-map Recall@K | Exact GPS patch Recall@K | Adjacent-patch Recall@K |
|---:|---:|---:|---:|
| 5 | 56.0% | 8.9% | 27.9% |
| 10 | 67.0% | 15.4% | 39.3% |
| 20 | 76.7% | 21.1% | 47.1% |
| 50 | 87.1% | 30.0% | 59.2% |
| 100 | 92.4% | 37.2% | 66.6% |

280-pixel query results:

| K | Parent-map Recall@K | Exact GPS patch Recall@K | Adjacent-patch Recall@K |
|---:|---:|---:|---:|
| 5 | 67.0% | 11.8% | 34.5% |
| 10 | 73.6% | 18.0% | 42.7% |
| 20 | 79.1% | 24.7% | 51.8% |
| 50 | 89.6% | 33.4% | 64.1% |
| 100 | 95.6% | 40.8% | 70.8% |

The 280-pixel query improves:

- parent recall
- exact GPS-patch recall
- adjacent-patch recall

at every K from 5 through 100 in this validation split.

The improvement is not large enough to make K=5 or K=10 a reliable GPS-patch shortlist.
It is meaningful for candidate generation because it increases the chance that at least
one correct parent/adjacent region remains in the shortlist.

### Representative cross-split flight performance

The five representative queries from earlier reports:

| Flight | Split | 224 historical parent recall at K=50 | 224 fresh parent recall at K=50 | GPS recall at K=50 |
|---|---|---:|---:|---:|
| 01 | train | missed | missed | missed |
| 05 | validation | retrieved | retrieved | exact in fresh run |
| 09 | train | retrieved | retrieved | missed |
| 02 | test | missed | missed | missed |
| 10 | test | retrieved | missed | missed |

The historical and fresh runs differ in ranking, which establishes ranking
non-reproducibility in the limited representative set. It is not evidence of a model
revision or changed index.

At K=50, fresh 224-query results found the correct parent for Flight 05 and Flight 09,
but not Flights 01, 02, or 10. Correct GPS-center patches were found only for Flight 05
at K=50.

280-pixel representative behavior was more variable:

- Flight 05 reached exact GPS recall at K=20 and K=50
- Flight 01 reached correct parent at K=100 rather than K=50
- Flight 09 retained correct parent by K=50
- Flights 02 and 10 remained misses through K=100

This is not enough evidence to claim that 280 preprocessing is robust across all flights.

## Retrieval-failure classification

For Flight 05 positive validation queries:

- correct geographic region absent from satellite coverage: **0**
- exact patch ranking failure despite region coverage:
  - 224 at K=100: 62.8% of 473 queries
  - 280 at K=100: 59.2% of 473 queries
- adjacent patch ranking failure despite region coverage:
  - 224 at K=100: 33.4% of 473 queries
  - 280 at K=100: 29.2% of 473 queries

All 473 positive Flight 05 queries are assigned a satellite-covering GPS point. Therefore
an exact/adjacent miss in this split is a ranking failure or ground-truth granularity
issue, not a demonstrated coverage hole.

Failure causes supported by evidence:

1. **Ranking failure**
   - global cosine descriptors do not consistently place the exact patch or nearby patch at
     low K
   - parent recall is much stronger than exact-patch recall

2. **Patch granularity / overlap**
   - exact GPS-center patch recall penalizes a valid nearby patch
   - adjacent-patch recall is substantially higher than exact-patch recall
   - 512-pixel patches have 20% overlap

3. **Global appearance mismatch**
   - the model ranks visually similar or globally similar regions; one 384-D vector
     is not patch-aligned to a drone image

Failure causes not established:

- missing satellite coverage
- incorrect metadata for positive Flight 05
- cross-model training/domain adaptation improvement
- verified local appearance mismatch

No evidence justifies attributing misses in general to any of the following:

- camera calibration
- footprint mismatch
- terrain height
- seasonal appearance
- different flight orientations

Those remain hypotheses until visual or geometric validation exists.

## Patch neighborhood expansion

Neighborhood expansion means adding one-row/one-column patches and nearby patches around
each retrieved candidate. It was tested against the exact and adjacent target neighborhoods
derived from ground-truth metadata after ranking.

For GPS-free operation, no ground-truth GPS was used to build the expanded candidate set.
GPS was used only to measure whether the expanded set contained the exact or adjacent
target patches.

### 224-pixel original and expanded ranking

| K | Original exact recall | Expanded exact recall | Original adjacent recall | Expanded adjacent recall |
|---:|---:|---:|---:|---:|
| 5 | 8.9% | 30.2% | 27.9% | 40.4% |
| 10 | 15.4% | 41.6% | 39.3% | 52.9% |
| 20 | 21.1% | 49.3% | 47.1% | 59.8% |
| 50 | 30.0% | 60.9% | 59.2% | 69.8% |
| 100 | 37.2% | 68.1% | 66.6% | 77.0% |

Mean expanded candidate counts:

| K | Mean candidates after one-neighbor expansion |
|---:|---:|
| 5 | 46.7 |
| 10 | 90.9 |
| 20 | 178.1 |
| 50 | 437.4 |
| 100 | 862.8 |

Expansion therefore provides a large coverage gain but also roughly multiplies candidate
count.

### 280-pixel original and expanded ranking

| K | Original exact recall | Expanded exact recall | Original adjacent recall | Expanded adjacent recall |
|---:|---:|---:|---:|---:|
| 5 | 11.8% | 37.0% | 34.5% | 47.8% |
| 10 | 18.0% | 44.6% | 42.7% | 57.1% |
| 20 | 24.7% | 53.5% | 51.8% | 63.6% |
| 50 | 33.4% | 65.3% | 64.1% | 74.0% |
| 100 | 40.8% | 71.7% | 70.8% | 81.4% |

The 280-pixel/K=100 adjacent values are retained as separate exploratory outputs. The
direct full-validation run measured 70.8% original adjacent recall; the separate
neighborhood sweep measured 70.825% before expansion and 81.395% after expansion.

Mean expanded candidate counts for 280:

| K | Mean candidates after one-neighbor expansion |
|---:|---:|
| 5 | 44.5 |
| 10 | 87.9 |
| 20 | 172.8 |
| 50 | 428.0 |
| 100 | 841.7 |

## Spatially consistent reranking

Two GPS-free reranking heuristics were tested:

1. **Parent/parent-group grouping**
   - rank parent-map groups from the Top-100 pool
   - then rank patches inside groups

2. **Spatial group density**
   - prefer candidates with many nearby retrieved candidates
   - tie-break with cosine score

### Parent grouping

This heuristic did not improve exact or adjacent recall:

224-pixel:

| K | Original exact | Grouped exact | Original adjacent | Grouped adjacent |
|---:|---:|---:|---:|---:|
| 5 | 8.9% | 3.2% | 27.9% | 11.8% |
| 20 | 21.1% | 8.2% | 47.1% | 18.6% |
| 50 | 30.0% | 16.7% | 59.2% | 26.8% |
| 100 | 37.2% | 37.2% | 66.6% | 66.6% |

280-pixel:

| K | Original exact | Grouped exact | Original adjacent | Grouped adjacent |
|---:|---:|---:|---:|---:|
| 5 | 11.8% | 2.7% | 34.5% | 11.4% |
| 20 | 24.7% | 8.5% | 51.8% | 17.5% |
| 50 | 33.4% | 17.3% | 64.1% | 29.8% |
| 100 | 40.8% | 40.8% | 70.8% | 70.8% |

At K=100, grouping is the same candidate set as original, because all 100 candidates remain.
It does not improve the set, only order. At lower K, restricting by inferred parent groups
reduces recall.

### Spatial density reranking

This improved exact recall slightly at low K but did not improve adjacent recall:

224-pixel at K=50:

- original exact: 30.0%
- spatial exact: 33.8%
- original adjacent: 59.2%
- spatial adjacent: 56.2%

280-pixel at K=50:

- original exact: 33.4%
- spatial exact: 37.2%
- original adjacent: 64.1%
- spatial adjacent: 62.4%

Spatial density reranking is not a strong enough method to justify deployment. It provides
small exact-patch gain while losing some adjacent coverage.

## Query preprocessing comparison

Existing 224-pixel query:

- mean full-validation latency: 238.6 ms
- median: 232.5 ms
- peak RSS: 536.6 MiB

280-pixel query:

- mean full-validation latency: 337.6 ms
- median: 333.3 ms
- peak RSS: 483.9 MiB

The 280-pixel mean was 99 ms slower (+41.5%), but it improved Flight 05:

| Metric | 224 | 280 | Change |
|---|---:|---:|---:|
| Parent Recall@50 | 87.1% | 89.6% | +2.5 points |
| Exact patch Recall@50 | 30.0% | 33.4% | +3.4 points |
| Adjacent Recall@50 | 59.2% | 64.1% | +4.9 points |
| Parent Recall@100 | 92.4% | 95.6% | +3.2 points |
| Exact patch Recall@100 | 37.2% | 40.8% | +3.6 points |
| Adjacent Recall@100 | 66.6% | 70.8% | +4.2 points |

The 280-pixel query should be considered for the candidate-generation prototype, but it
must remain optional and measured together with the existing 224-pixel satellite index.
The 224-pixel and 280-pixel query embeddings are both 384-D and compatible for cosine
search. No index rebuild is needed.

No 392-pixel result is repeated in this report as a general recommendation because the
prior Phase 3E result showed higher latency and no aggregate recall improvement.

## Satellite coverage analysis

The 473 positive Flight 05 queries cover satellite05 and have no missing GPS containment.
Coverage counts in the complete metadata:

| Parent | Patch count |
|---|---:|
| satellite05 | 345 |
| satellite01 | 1,584 |
| satellite02 | 2,352 |
| satellite03 | 5,160 |
| satellite04 | 4,136 |
| satellite08 | 4,240 |
| satellite09 | 9,020 |
| satellite10 | 208 |
| satellite11 | 2,952 |

Patch coverage itself does not explain the 473 Flight 05 misses:

- all positive validation centers lie inside satellite05 coverage
- the exact patch exists in metadata
- adjacent overlapping patches exist
- ranking, appearance, and patch granularity are the demonstrated issues

For the five representative queries, misses outside Flight 05 cannot be classified as
coverage absence without a larger full-flight ground-truth result. The retained metadata
proves parent-map and patch bounds only; it does not prove visual candidate validity.

## K recommendation

For candidate generation, K=50 is reasonable as a conservative first-stage shortlisting
value:

- 224: 87.1% Flight 05 parent recall, 59.2% adjacent recall
- 280: 89.6% Flight 05 parent recall, 64.1% adjacent recall

K=20 is not enough:

- 224 exact recall: 21.1%
- 280 exact recall: 24.7%
- adjacent recall remains below 52% for 280

K=100 improves Flight 05 recall further but without a demonstrated global five-flight gain:

- exact recall remains below 41%
- K=50 and K=100 both need geometric verification before localization claims

The correct role for K=50 or K=100 is candidate recall, not localization.

## Recommendation

The existing DINOv2 pipeline can support a useful candidate-generation stage, but it is
not reliable as a standalone GPS-free locator.

Recommended:

1. Preserve the existing 224-pixel DINOv2 index unchanged.
2. Retain 224-pixel query preprocessing as the compatibility baseline.
3. Retain 280-pixel query preprocessing as an optional, benchmarked query variant.
4. Prefer 280 when only query encoding changes and the existing satellite descriptors
   remain acceptable; do not rebuild or reindex satellites.
5. Use K=50 as the default exploratory candidate count, not as a localization threshold.
6. For GPS-bearing candidates, only use a containing parent/patch neighborhood as an
   optional geographic constraint after DINOv2 ranking.
7. For GPS-free candidates, do not use GPS to build expanded neighborhoods.
8. Add adjacent patches to a retrieved candidate set if disk/compute permits. It raised
   Flight 05 exact/adjacent recall but expanded candidate count to roughly 428 patches
   at K=50.
9. Do not use parent-group reranking. It materially reduces low-K coverage.
10. Do not use spatial-density reranking as a primary improvement. Gains are small and
    adjacent recall can decrease.
11. Do not adopt alternative pretrained models without a larger pinned benchmark.

Nearest supported interpretation:

- DINOv2 is useful for reducing 30,485 candidates to several dozen or hundreds.
- It is not supported as exact GPS-patch recovery.
- Adjacent expansion is the strongest demonstrated no-training improvement.
- 280-pixel query preprocessing is a useful moderate-cost option.
- SuperPoint, local matching, RANSAC, and verified visual ground truth are still required
  before localization readiness.

