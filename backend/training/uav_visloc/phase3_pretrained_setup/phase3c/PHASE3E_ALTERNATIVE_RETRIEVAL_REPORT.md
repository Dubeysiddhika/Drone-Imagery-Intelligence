# Phase 3E Alternative Satellite Retrieval Report

## Scope

This investigation used the completed 30,485-tile DINOv2 index and existing representative
drone-image evaluation. It did not rerun DINOv2 extraction, rebuild the index, download
weights or packages, resume SuperPoint extraction, or modify existing SuperPoint shards.

The existing geographic split remains:

- Train: Flights 01, 03, 04, 08, 09, 11
- Validation: Flight 05
- Test: Flights 02, 10
- Excluded from the primary split: uncertain Flights 06 and 07

## Baseline audit and reproducibility

The existing index remains:

- 30,485 descriptors
- 384-D float32 vectors
- finite and L2-normalized
- 30,485 unique IDs
- complete metadata and geospatial validation

The existing historical five-flight report measures:

| K | Parent-map Recall@K | GPS-center patch Recall@K |
|---:|---:|---:|
| 1 | 20% (stored Top-5 rank-1 result: Flight 10) | 20% (stored Top-5: Flight 10) |
| 5 | 20% | 20% |
| 10 | 40% | 20% |
| 20 | 40% | 20% |
| 50 | 60% | 40% |
| 100 | 60% | 40% |

The historical values come from a five-image, 30,485-tile reranking. Parent and GPS
metrics are retrieval proxies, not candidate visual localization or localization accuracy.

A fresh fixed-CPU baseline rerun used:

- same five representative images
- four PyTorch CPU threads
- 224-pixel DINOv2 query preprocessing
- existing 224-pixel satellite descriptors
- cosine similarity
- no geographic filtering

Fresh 224-pixel results:

| K | Parent-map Recall@K | GPS-center patch Recall@K |
|---:|---:|---:|
| 1 | 40% (2/5) | 0% (0/5) |
| 5 | 40% (2/5) | 0% (0/5) |
| 10 | 40% (2/5) | 0% (0/5) |
| 20 | 40% (2/5) | 0% (0/5) |
| 50 | 40% (2/5) | 20% (1/5) |
| 100 | 60% (3/5) | 20% (1/5) |

The fresh result does not reproduce all historical parent-map or GPS rankings. It shows
that a pinned environment and result artifact are required before recall values can be used
as a quality certificate.

Fresh 224-pixel per-flight parent recall:

| Flight | Split | Recall at Top 1/5/10/20/50/100 |
|---|---|---|
| 01 | train | false/false/false/false/false/false |
| 05 | validation | true/true/true/true/true/true |
| 09 | train | true/true/true/true/true/true |
| 02 | test | false/false/false/false/false/false |
| 10 | test | false/false/false/false/false/true at 100 |

Fresh GPS-center patch recall was positive only for Flight 05 at K=50 and K=100.

The historical result remains the current project audit but is not a stable substitute for
the fresh baseline.

## Candidate feasibility

No candidate model was downloaded or installed.

### DINOv2 improved preprocessing

Feasibility:

- pretrained weights already present locally
- CPU-only package is installed
- architecture and descriptor compatibility are known
- no dependency installation is required
- safe to benchmark
- no training or fine-tuning

Preprocessing constraints:

- DINOv2 ViT-S/14 requires input height and width divisible by 14
- 256-pixel square input is invalid for this local implementation
- valid tested sizes: 224, 280, and 392

Satellite descriptors were unchanged at 224-pixel preprocessing. Only query resolution was
changed. This measures a query/satellite preprocessing mismatch, not true multi-scale
satellite indexing.

CPU results:

| Query method | Parent Recall@50 | GPS Recall@50 | GPS Recall@20 | Mean query latency |
|---|---:|---:|---:|---:|
| 224 | 40% | 20% | 0% | 241.9 ms |
| 280 | 40% | 20% | 20% | 358.9 ms |
| 392 | 40% | 20% | 0% | 715.6 ms |

At K=100:

| Query method | Parent Recall@100 | GPS Recall@100 |
|---|---:|---:|
| 224 | 60% | 20% |
| 280 | 60% | 20% |
| 392 | 60% | 20% |

At K=1/5/10/20/50, none of 224, 280, or 392 reached candidate visual localization recall
because candidate patch visual ground truth is unavailable.

A 224+392 query fusion was tested by averaging and renormalizing the two 384-D descriptors.
It produced the same aggregate results as 224 for K=1–100. It requires two query
forward passes and therefore adds roughly 958 ms of DINOv2 query encoding, before cosine
search, on this laptop.

Recommendation:

- 224 remains the baseline only because it is the existing index-compatible method.
- 280 is a modest candidate for a future query-only experiment.
- 392 and 224+392 are not justified by the measured recall gains.
- True multi-scale satellite indexing would require rebuilding or adding satellite
  descriptors and was not performed.

### DINOv2 parent-map-aware ranking

Feasibility:

- no model change
- no extra pretrained weight or package
- GPS-bearing queries can restrict or rerank candidates by independently established
  satellite map containment
- GPS-free queries cannot perform this filtering safely
- low search cost compared with DINOv2 encoding
- compatible with existing 384-D descriptors

Safe behavior:

- GPS is applied only after DINOv2 ranking
- the containing parent and adjacent parent maps are not inferred from the cosine score
- candidates outside an independently valid GPS/parent constraint are filtered
- GPS-free images use the original cosine ranking

Measured result:

- no measured improvement was demonstrated from parent-map reranking in the five-image
  experiments
- historical K=100 parent recall remained 60%
- parent reranking cannot create a correct parent absent from the DINO candidate set
- no GPS-free parent reranking signal exists

Technical concern:

- filtering to a parent can remove correct overlapping candidates at map boundaries
- no footprint is inferred from center GPS
- filtering is a candidate constraint, not localization proof

### CLIP / OpenCLIP

Feasibility:

- `transformers`, `open_clip`, and `clip` are not installed
- no Hugging Face or OpenCLIP weight cache is present
- no large model was downloaded
- `torchvision` exists, but no confirmed compatible CLIP weight package is local

CPU requirements:

- ViT-B CLIP image encoders are several hundred MB and may exceed a comfortable 8 GB
  laptop process budget with search matrices and runtime caching
- exact memory depends on implementation and image size
- no measured run exists in this environment

Preprocessing:

- required RGB resize/crop and CLIP-specific mean/std
- separate image and satellite embedding bank
- text-text or text-image embeddings are not relevant without a text prompt

Suitability:

- CLIP is a useful zero-shot image encoder but is primarily trained for broad
  image-text correspondence
- no evidence supports superior drone-to-overhead satellite patch retrieval
- it would require a new 30,485-descriptor satellite bank
- that is intentionally not created under this task

Verdict: feasible only after an explicit package/weight approval, dependency compatibility
check, and fair 30,485-patch experiment. It is not currently a measured candidate.

### NetVLAD

Feasibility:

- no NetVLAD package or pretrained local implementation is present
- no PyTorch Hub/torchvision NetVLAD weights are confirmed
- no standard pretrained CPU weight bundle is available locally

CPU/RAM:

- unknown until a specific implementation and pretrained weights are approved
- place-recognition networks commonly require substantial model and descriptor banks
- descriptor dimension and residual/cluster count vary by implementation
- compatibility with drone/satellite cross-domain retrieval is unverified

Use-case suitability:

- NetVLAD is normally designed for place and visual geo-localization
- pretrained weights are commonly trained on street-level or landmark datasets
- drone-to-satellite appearance/domain transfer is not established
- a NetVLAD encoder would require rebuilding the satellite index
- VLAD dimensions and descriptor normalization must be matched for a fair cosine or
  distance ranking

Verdict: unsuitable for immediate investigation because no verified compatible pretrained
weights or implementation are local. No download or installation was made.

### CosPlace or other place-recognition models

Feasibility:

- no local package, implementation, or weights
- no existing dependency or model cache
- a large-model download would require explicit approval

Suitability:

- place-recognition models may transfer better than broad CLIP encoders
- however, pretrained models often target street scenes or urban-level recognition
- cross-domain drone-to-satellite matching requires held-out evidence
- descriptor banks and CPU benchmarks must be measured before deployment

Verdict: defer until compatible pretrained weights and a dependency plan are reviewed.

## Fair comparison summary

The following table compares only fresh, actually measured DINOv2 query methods.
The existing historical DINOv2 values are shown separately.

| Method | Parent Recall@50 | GPS Recall@50 | GPS Recall@20 | Mean CPU latency | Mean RSS |
|---|---:|---:|---:|---:|---:|
| Historical DINOv2 baseline | 60% | 40% | 20% | 321.2 ms stored Top-5/script | about 525–528 MiB |
| Fresh DINOv2 224 | 40% | 20% | 0% | 241.9 ms | 541.2 MiB |
| Fresh DINOv2 280 | 40% | 20% | 20% | 358.9 ms | 544.0 MiB |
| Fresh DINOv2 392 | 40% | 20% | 0% | 715.6 ms | 543.7 MiB |
| Fresh DINOv2 224+392 | 40% | 20% | 0% | 958+ ms estimated | 543.7 MiB |

The 224+392 estimate includes two query encodings and is not a measured combined inference
latency. It was 2.7 ms for cosine search after descriptors were already generated.

Per-flight fresh 224 baseline:

| Flight | Split | GPS recall at K=50 | Parent recall at K=50 |
|---|---|---:|---:|
| 01 | train | 0% | 0% |
| 05 | validation | 100% | 100% |
| 09 | train | 0% | 100% |
| 02 | test | 0% | 0% |
| 10 | test | 0% | 0% |

280-pixel query behavior improved only Flight 05 GPS-center recall to K=20. No 224/280/392
method achieved GPS recall for Flights 01, 09, 02, or 10 at K=50 except Flight 05.

No method has a measured candidate-patch Recall@K. Candidate patch recall remains
unavailable until verified visual positive-patch ground truth and local matching/RANSAC
results exist.

## GPS-enabled and GPS-free separation

### GPS-enabled

The following inputs are permitted for evaluation:

- parent map and containing patch metadata
- adjacent map/patch expansion
- GPS-center post-ranking ground truth

Ground-truth GPS must not be added to the DINO query. It may only filter or score
candidates after retrieval.

The 280-pixel query is modestly stronger at K=20 for GPS-bearing Flight 05. It does not
improve the full five-flight GPS aggregate above 20% at K=50 compared with 224.

### GPS-free

GPS-free queries must use:

- drone image only
- DINO/CLIP/place-recognition descriptor only
- no parent filter
- no containing-patch filter
- no GPS-derived rerank
- no neighbor expansion derived from ground-truth coordinates

The fresh 224 baseline is the valid GPS-free result for this report. No alternative method
is measured for GPS-free drone/satellite retrieval.

## Geospatial limitations

Satellite coverage counts:

| Parent | Patch count |
|---|---:|
| satellite01 | 1,584 |
| satellite02 | 2,352 |
| satellite03 | 5,160 |
| satellite04 | 4,136 |
| satellite05 | 345 |
| satellite06 | 480 |
| satellite07 | 8 |
| satellite08 | 4,240 |
| satellite09 | 9,020 |
| satellite10 | 208 |
| satellite11 | 2,952 |

Coverage gaps and patch adjacency:

- parent maps have uneven patch density
- satellite09 consists of four adjoining TIFF cells and is preserved as separate patches
- satellite06 and satellite07 are low-sample or excluded uncertain regions
- 20% patch overlap means adjacent patches contain shared scene content
- exact GPS-center patch recall is sensitive to 512-pixel boundaries
- center GPS does not prove image footprint or visual coverage

Misses should not be attributed to DINOv2 alone:

- four of five representative maps have weak or inconsistent top-K recall
- parent-map and patch ground truth are incomplete proxies
- satellite content and drone appearance differ substantially
- repeated seasonal, viewpoint, terrain, and altitude appearance changes are possible
- the GPS center can lie outside the exact visual crop that matches a satellite patch
- candidate patch visual overlap has not been manually or geometrically verified

## CPU and memory considerations

Baseline and tested DINOv2 query preprocessing:

- 224: approximately 242 ms mean query, ~541 MiB peak process RSS
- 280: approximately 359 ms mean query, ~544 MiB peak process RSS
- 392: approximately 716 ms mean query, ~544 MiB peak process RSS
- cosine search remained only a few milliseconds for K=100

The historical result's 321.2 ms includes the validation script's DINOv2/search path and
had RSS around 525–528 MiB. The fresh process had a slightly higher steady process RSS
because the model and environment were measured as a standalone benchmark.

RAM is not the primary DINOv2 retrieval bottleneck at K=100. CPU query encoding dominates.

External CLIP, NetVLAD, and CosPlace models are unknown-cost estimates only because no
compatible package or weights were present.

## Final recommendation

The best measured approach remains DINOv2, but not a higher-resolution or multi-scale
query as a general default.

Recommended:

1. Keep the existing 224-pixel 384-D DINOv2 index unchanged.
2. Keep cosine ranking as the GPS-free fallback.
3. Use 280-pixel DINOv2 query preprocessing only as an optional query variant if further
   held-out testing demonstrates improvement.
4. Do not adopt 392-pixel or 224+392 query fusion on this laptop; no measured aggregate
   recall improvement justified their 1.5–4x additional query cost.
5. Use K=50 for GPS-bearing exploratory candidates, but do not claim that it is sufficient
   for localization.
6. Do not use K=100 as the default when K=50 shows no demonstrated gain.
7. Use parent-map filtering only when GPS containment is independently valid.
8. Keep GPS-free retrieval fully independent of coordinates.
9. Do not proceed to on-demand SuperPoint until a larger held-out candidate-patch
   benchmark and fixed result replay exist.
10. Do not install or download CLIP, NetVLAD, or CosPlace weights at this stage.

CLIP could become a future candidate only after a dependency and weight feasibility review
and creation of a separate 30,485-patch descriptor bank. NetVLAD/CosPlace should remain
deferred because no verified pretrained implementation or compatible weights are local.

No custom training, fine-tuning, SuperPoint resume, DINOv2 extraction, index rebuild,
data deletion, or Phase 4 work occurred.
