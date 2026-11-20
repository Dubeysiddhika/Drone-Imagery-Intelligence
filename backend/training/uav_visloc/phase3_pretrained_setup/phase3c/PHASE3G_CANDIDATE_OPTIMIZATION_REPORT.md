# Phase 3G - Candidate Selection and Spatial Neighborhood Optimization

## Executive summary

Phase 3G evaluated the existing complete 30,485-patch, 384-D DINOv2 index on all
473 positive Flight 05 validation queries. No satellite descriptor was regenerated.
Queries were embedded at 224 and 280 pixels; the satellite index remained at its
original 224-pixel preprocessing.

The recommended GPS-free operating point is:

- 280-pixel query preprocessing, when its measured CPU cost is acceptable
- DINOv2 initial K=50
- one-ring expansion around only the five highest-ranked seeds
- a hard maximum of 75 candidates, with expansion stopping at that budget
- final candidate order by original DINOv2 cosine similarity

For Flight 05, this returned a mean 73 candidates and measured 89.6% parent-map,
45.9% exact GPS-center patch, and 67.0% adjacent-patch recall. Relative to plain
280-pixel Top-50 it added about 23 candidates and improved exact-patch recall by
12.5 percentage points while leaving parent recall unchanged. It did not improve
all metrics over plain Top-75: parent and adjacent recall were lower, so the
recommended point is a candidate-count/patch-recall trade-off, not a universal
winner.

No candidate strategy establishes visual correspondence or localization accuracy.

## Scope and reproducibility

### Inputs and restrictions

- `retrieval_validation.csv`: 946 rows, comprising 473 positive and 473 negative
  Flight 05 pairs. The benchmark uses the same 473 positive images as Phase 3F.
- `validation_pairs.csv`: supplies the held-out positive query list and expected
  parent map.
- `satellite_tile_metadata.csv`: supplies patch affine transforms, source raster,
  offsets, and geographic bounds.
- Existing DINOv2 index: 30,485 descriptors, 384 dimensions, complete and finite.

All 473 positive query paths were checked and found. There are no other flights with
this full positive-query validation coverage; per-flight performance below is
therefore Flight 05 only.

The experiment was CPU-only with the existing locally cached DINOv2 model. It did
not train or fine-tune, download or install packages or weights, rerun DINOv2
extraction, rebuild the index, run SuperPoint extraction, modify SuperPoint shards,
or implement Phase 4.

### Metrics and adjacency

- **Parent-map recall:** at least one selected patch has the expected validation
  parent map.
- **Exact GPS-center patch recall:** at least one selected patch's retained affine
  transform contains the query's recorded GPS center.
- **Adjacent-patch recall:** the exact-containing patches plus their one-ring
  geospatially overlapping neighbors. Adjacency is formed only within the same
  full `source_file`, using patch offsets and positive geographic-bounds
  intersection. This includes final, nonuniform tile starts and excludes
  cross-source/cross-map neighbors.

The uncapped full-neighborhood figures below are offline recall references. The
bounded one-/two-ring selectors add neighbors in seed-rank order and stop adding
when the configured budget is reached. Only the selected candidates are passed on;
unselected candidate IDs are retained in the decision trace.

## Phase 3F baseline reproduction

The original cosine-ranked results were reproduced exactly for parent-map and
exact-patch recall at K=5, 10, 20, 50, and 100. The complete Phase 3G Top-K results
are:

| Query size | K | Parent-map | Exact GPS patch | Adjacent patch |
|---:|---:|---:|---:|---:|
| 224 | 5 | 56.0% | 8.9% | 30.2% |
| 224 | 10 | 67.0% | 15.4% | 41.6% |
| 224 | 20 | 76.7% | 21.1% | 49.3% |
| 224 | 50 | 87.1% | 30.0% | 60.9% |
| 224 | 75 | 89.9% | 33.6% | 65.5% |
| 224 | 100 | 92.4% | 37.2% | 68.1% |
| 224 | 150 | 96.0% | 41.9% | 71.0% |
| 280 | 5 | 67.0% | 11.8% | 37.0% |
| 280 | 10 | 73.6% | 18.0% | 44.6% |
| 280 | 20 | 79.1% | 24.7% | 53.5% |
| 280 | 50 | 89.6% | 33.4% | 65.3% |
| 280 | 75 | 92.8% | 37.8% | 69.6% |
| 280 | 100 | 95.6% | 40.8% | 71.7% |
| 280 | 150 | 98.1% | 46.9% | 75.5% |

The Phase 3F report's historical adjacent-recall values are 0.9-2.5 percentage
points lower across K=5-100. The Phase 3F artifacts do not preserve per-query
adjacency targets or enough detail to reproduce that target construction exactly.
This report therefore gives the explicit, validated source-file/bounds definition
above rather than adjusting results to match the historical percentages. Parent and
exact-patch reproduction is unaffected.

The Phase 3F uncapped full one-ring exact-patch recall is reproduced at each
reported K. Adjacent-patch recall differs by at most 1.1 points under the
documented adjacency definition. Unique candidate counts are lower than the
Phase 3F report's counts; the prior per-query expanded ID sets were not retained,
so the historical count difference cannot be attributed more specifically. At
K=50, this run returned 345.8/341.3 candidates (224/280), versus the Phase 3F
reported 437.4/428.0; at K=100, it returned 661.2/653.9 versus 862.8/841.7.

## Candidate selection experiments

### Original ranking and full-expansion reference

Top-K selects exactly K candidates. Uncapped expansion around every Top-K patch
provides a high-recall reference, but is too large for efficient local processing:

| Initial K | 224 mean expanded candidates | 224 exact / adjacent | 280 mean expanded candidates | 280 exact / adjacent |
|---:|---:|---:|---:|---:|
| 5 | 39.6 | 30.2% / 40.4% | 39.0 | 37.0% / 48.6% |
| 10 | 75.7 | 41.6% / 53.3% | 74.4 | 44.6% / 58.1% |
| 20 | 145.7 | 49.3% / 60.5% | 142.9 | 53.5% / 64.3% |
| 50 | 345.8 | 60.9% / 70.6% | 341.3 | 65.3% / 74.4% |
| 100 | 661.2 | 68.1% / 78.0% | 653.9 | 71.7% / 82.5% |

Parent-map recall is unchanged by expansion: neighbors are from the same source
map, so expansion cannot recover a parent absent from the initial DINOv2 candidates.

### Adaptive one-ring expansion

The operational selector starts with Top-50. It expands one ring around at most
the first 5, 10, or 20 seeds, processing seeds in DINOv2 rank order and neighbors
in cosine order. It stops adding candidates at the budget. The uncapped pool is
measured separately only to calculate recall lost to the cap.

For the five-seed variant, the full diagnostic pool averages 80.0 candidates at
224 pixels and 79.0 at 280 pixels. The table shows actual mean candidates
submitted after the cap:

| Budget | 224 submitted / discarded | 224 parent / exact / adjacent | 280 submitted / discarded | 280 parent / exact / adjacent |
|---:|---:|---:|---:|---:|
| 20 | 20.0 / 60.0 | 76.7% / 21.1% / 49.3% | 20.0 / 59.0 | 79.1% / 24.7% / 53.5% |
| 50 | 50.0 / 30.0 | 87.1% / 30.0% / 60.9% | 50.0 / 29.0 | 89.6% / 33.4% / 65.3% |
| 75 | 73.4 / 6.6 | 87.1% / 40.8% / 62.6% | 73.0 / 6.1 | 89.6% / 45.9% / 67.0% |
| 100 | 80.0 / 0.0 | 87.1% / 41.9% / 62.8% | 79.0 / 0.0 | 89.6% / 46.7% / 67.7% |
| 150 | 80.0 / 0.0 | 87.1% / 41.9% / 62.8% | 79.0 / 0.0 | 89.6% / 46.7% / 67.7% |

At budget 75, the selector retains 97.4% of the 224-pixel pool's exact recall and
99.7% of its adjacent recall; at 280 pixels it retains 98.3% and 99.0%,
respectively. The cap is effective because the five-seed pool is already small.
Budgets 20 and 50 are filled by the visual seeds, so no neighborhood expansion is
performed at those budgets.

Increasing the number of expanded seeds raises uncapped recall and candidate
volume:

| Query size | Expanded seeds | Uncapped candidates | Pool exact recall | Pool adjacent recall |
|---:|---:|---:|---:|---:|
| 224 | 5 | 80.0 | 41.9% | 62.8% |
| 224 | 10 | 109.8 | 48.2% | 65.5% |
| 224 | 20 | 169.3 | 52.0% | 67.0% |
| 280 | 5 | 79.0 | 46.7% | 67.7% |
| 280 | 10 | 108.1 | 50.5% | 70.0% |
| 280 | 20 | 166.3 | 56.0% | 70.8% |

At a budget of 75, expanding 10 or 20 seeds produced no adjacent-recall gain over
five seeds. At 280 pixels, it raised exact recall by only 0.6 points (to 46.5%)
while using essentially all 75 candidates. Five-seed expansion is therefore the
more efficient setting at this budget.

### Two-ring expansion

Two-ring expansion was tested around the first five seeds with the same early
budget stop. At 280 pixels, budget 100 returned 98.5 candidates with 51.2% exact
and 67.4% adjacent recall; budget 150 returned 132.0 candidates with 54.3% exact
and 68.9% adjacent recall. At the 100-candidate setting, this is more exact recall
than one-ring/five-seed expansion (46.7%), but it requires about 20 additional
candidates and does not improve adjacent recall. The extra ring is not recommended
for the default budget.

### Diversity and similarity-plus-spatial consistency

Diversity-aware ordering used a soft penalty for each already-selected adjacent
patch; no patch was hard-rejected for geographic proximity. At 280 pixels and
budget 50:

| Ordering | Parent | Exact | Adjacent | Selector time |
|---|---:|---:|---:|---:|
| Original cosine Top-50 | 89.6% | 33.4% | 65.3% | <0.01 ms |
| Soft diversity, penalty 0.005 | 90.5% | 29.8% | 64.7% | 7.5 ms |
| Soft diversity, penalty 0.02 | 91.3% | 24.3% | 64.3% | 7.4 ms |
| 0.9 cosine + 0.1 mean top-4 neighbor cosine | 89.0% | 34.7% | 66.0% | 3.0 ms |

At budget 100, the spatial-consistency score reached 43.6% exact and 71.7%
adjacent recall at 280 pixels, versus cosine Top-100's 40.8% and 71.7%; parent
recall fell from 95.6% to 94.1%. Soft diversity raised parent recall slightly but
reduced exact recall. The measured changes are not strong or consistent enough to
replace cosine ordering. In particular, spatial support is treated as a visual
similarity signal, not proof that neighboring patches are correct.

## GPS-enabled and GPS-free results

### GPS-free candidate selection

The visual Top-K, adaptive expansion, diversity, and spatial-consistency selectors
receive only the query descriptor, DINOv2 scores, and validated satellite
adjacency. Query GPS is used only after selection to calculate recall. Thus the
selection results above are valid GPS-free simulations.

All 473 positive validation queries do have GPS. There is no separate set of
genuinely GPS-unavailable queries, so this is not an independent operational
GPS-free test set.

### GPS-assisted diagnostic

For GPS-enabled operation only, the GPS point identifies the containing parent
map(s), and candidates are then ranked by DINOv2 cosine within those maps. The
Flight 05 containing parent has 345 patches:

| Query size | Budget | Parent | Exact | Adjacent |
|---:|---:|---:|---:|---:|
| 224 | 50 | 100.0% | 68.5% | 96.2% |
| 224 | 75 | 100.0% | 76.7% | 97.9% |
| 224 | 100 | 100.0% | 82.7% | 98.7% |
| 280 | 50 | 100.0% | 68.1% | 96.0% |
| 280 | 75 | 100.0% | 75.9% | 97.9% |
| 280 | 100 | 100.0% | 81.8% | 98.9% |

This is an oracle-available GPS diagnostic and is not comparable to the GPS-free
selectors. It must not be used when GPS is absent or invalid.

## Query preprocessing, latency, and memory

Only query preprocessing changed; the 224-pixel satellite descriptors were reused
for both resolutions.

| Query size | Mean encode + search | Median encode + search | Flight 05 Top-50 parent / exact / adjacent |
|---:|---:|---:|---:|
| 224 | 255.7 ms | 246.7 ms | 87.1% / 30.0% / 60.9% |
| 280 | 383.2 ms | 362.1 ms | 89.6% / 33.4% / 65.3% |

In this run, 280 pixels cost about 127 ms (50%) more mean query time than 224.
The prior Phase 3F run measured 238.6 ms and 337.6 ms, respectively; CPU timing
varied between complete runs, so these numbers should be treated as local
benchmarks rather than hardware guarantees.

Peak process RSS during the complete Phase 3G run was **595.8 MiB**, shared across
both query sizes and all candidate methods. It includes the loaded model, index,
adjacency graph, and decision-trace collection. Separate per-strategy peak RAM was
not isolated. Candidate-selection overhead in this run was about 0.03-0.12 ms for
five-seed adaptive one-ring expansion, 0.02-0.24 ms for the adaptive two-ring
variants, 7.2-7.5 ms for soft diversity ordering, and 2.6-3.0 ms for the
spatial-consistency reranker. DINOv2 encoding remains the dominant measured cost.

## Per-flight result

The full candidate-selection evaluation is available only for Flight 05:

| Flight | Queries | Configuration | Parent | Exact | Adjacent | Mean candidates submitted |
|---|---:|---|---:|---:|---:|---:|
| 05 | 473 | 224 Top-50 | 87.1% | 30.0% | 60.9% | 50 |
| 05 | 473 | 280 Top-50 | 89.6% | 33.4% | 65.3% | 50 |
| 05 | 473 | 280 Top-50 + five-seed one-ring, budget 75 | 89.6% | 45.9% | 67.0% | 73 |
| 05 | 473 | GPS parent filter, 280, budget 50 | 100.0% | 68.1% | 96.0% | 50 |

The GPS-filtered row is a separate GPS-enabled diagnostic.

## Recommended operating configuration

For GPS-free candidate generation, use:

1. **280-pixel query preprocessing** if the added CPU time is acceptable; keep 224
   as the faster fallback.
2. **Initial DINOv2 K=50.**
3. **Expand one ring around only the top five seeds**, using adjacency validated
   from the same source TIFF and geographic overlap.
4. **Maximum candidate budget 75.** Stop adding neighbors as soon as the budget is
   reached. If the seed set already fills the budget, do not expand.
5. **Order the selected union by original DINOv2 cosine score** for downstream
   matching. Avoid parent grouping and do not hard-discard a patch only because it
   is geographically close.

This setting returns about 73 patches/query on this validation set. Compared with
plain 280-pixel Top-50, it improves exact recall from 33.4% to 45.9% and adjacent
recall from 65.3% to 67.0%, with parent recall unchanged at 89.6%. If preserving
broader parent-map recall is more important than exact-patch recall, plain Top-75
is a valid alternative (92.8% parent, 37.8% exact, 69.6% adjacent).

For GPS-bearing inputs, a containing-parent filter can be offered as a separate
mode, but only when the GPS/map association is independently valid. It must never
be a fallback for GPS-free queries.

## Limitations

- All full-split metrics are from one flight, Flight 05; they do not establish
  cross-flight generalization.
- Exact GPS-center patch and adjacent-patch recall are geospatial proxies, not
  verified visual-positive or local-match recall.
- The adjacent-recall target construction in the stored Phase 3F report is not
  fully specified; the measured difference is documented rather than hidden.
- 280-pixel query vectors are compared against the unchanged 224-pixel satellite
  index. A multi-scale satellite index was not built.
- SuperPoint, LightGlue, RANSAC, and localization latency/quality were not tested.
- The GPS-assisted diagnostic uses available GPS and cannot be generalized to
  GPS-free operation.

## Reproducibility artifacts

The benchmark implementation is [evaluate_candidate_selection.py](./evaluate_candidate_selection.py).
Run it from the repository root with the existing `.venv` and provide output paths:

```powershell
.venv\Scripts\python.exe backend\training\uav_visloc\phase3_pretrained_setup\phase3c\evaluate_candidate_selection.py `
  --output <summary.json> `
  --decisions <candidate-decisions.csv>
```

The Phase 3G decision log contains 14,190 per-query configuration rows with
selected IDs, discarded IDs, candidate counts, and budget stop reasons for the
one-ring trials. The DINOv2 index and existing SuperPoint data were not modified.
