# UAV-VisLoc Phase 2A Report: Geographic Pair Preparation

## 1. Scope and constraints

This stage prepared a conservative drone-to-satellite pair-generation pipeline without training any model. The work respected the Phase 1 geospatial validation and avoided inventing camera parameters or silently accepting uncertain matches.

Key restrictions followed from Phase 1:

- Keep the original dataset immutable.
- Preserve source metadata and validation logs.
- Keep uncertain pairs out of the confirmed training set.
- Avoid mosaics unless transforms are demonstrably consistent.
- Do not estimate photogrammetric footprint without calibration data that is not present in the dataset.

## 2. Stage 1: Review of Phase 1 outputs

The Phase 1 review confirmed the dataset inventory:

- Flights: 11
- Drone images: 6,774
- Metadata CSVs: 11
- Satellite TIFFs: 14
- Valid latitude/longitude rows: 6,774
- Missing/invalid coordinate rows: 0
- GPS points inside coverage: 6,766
- GPS points outside coverage: 8

The 8 outside-coverage rows are all in Flights 06 and 07 and were explicitly preserved as uncertain cases. Flight 09 contains four adjacent, non-overlapping TIFF tiles that were confirmed as safe for a tiling pipeline and not for an invalid mosaic without a consistent grid transform.

## 3. Stage 2: Footprint estimation feasibility

Image center coordinates are present, and the dataset includes drone altitude and orientation angles (Omega, Kappa, Phi1, Phi2), but no documented camera intrinsics or calibration metadata. Specifically, there is no documented:

- focal length
- sensor width or height
- image sensor model
- calibration parameters
- explicit terrain/elevation reference model

Because the required calibration information is absent, the footprint estimate is not reliably computable from the available files. The project therefore does not estimate full image footprint overlap or use center GPS as a proxy for image extent.

Status: footprint estimation is not feasible from the current dataset without explicit assumptions and calibration metadata.

## 4. Stage 3: Satellite tile preparation

The reusable tile-preparation pipeline reads the preserved TIFFs with Rasterio, preserves CRS and geographic bounds, and records per-tile metadata, including:

- flight number
- satellite parent map ID
- tile ID
- source file path
- CRS and bounds
- width/height and pixel resolution
- affine transform
- adjacency group status

The pipeline produced 14 tile records, including all four Flight 09 tiles under a shared adjacency group. This preserves the geospatial relationship of the Flight 09 2x2 tile set without manufacturing a mosaic transform.

## 5. Stage 4: Candidate pair generation

Candidate pairs were created using geographic validity and map-bounds checks, with a conservative distance rule for negatives.

Generated counts:

- Positive candidate pairs: 6,766
- Negative candidate pairs: 6,766
- Uncertain pairs requiring manual verification: 8

The uncertain pairs correspond to the eight outside-coverage drone images and were intentionally excluded from the confirmed training set.

## 6. Stage 5: Validation and filtering

Validation logic enforces the required distinction between confirmed and uncertain examples:

- candidate positive pairs are kept only when a drone image center lies inside a valid satellite tile coverage area
- candidate negative pairs are kept only when the sample is geographically distant from the relevant map region
- uncertain pairs remain separate and are flagged for manual inspection

The final validation summary was:

- confirmed positive pairs: 6,766
- confirmed negative pairs: 6,766
- uncertain pairs: 8
- total confirmed pairs: 13,532

This means the confirmed pair set is conservative and excludes the 8 manual-review cases.

## 7. Stage 6: Geographic splits

Final split design follows flight-based geographic grouping instead of random sampling.

- Train flights: 01, 03, 04, 08, 09, 11
- Validation flight: 05
- Test flights: 02, 10

Rationale:

- Flights 02 and 10 are geographically distinct and are a sensible held-out test set.
- Flight 05 is a single, large region with a good sample size and is a better validation candidate than Flights 05/06 combined.
- Flight 06 was intentionally excluded from validation because it contains six outside-coverage examples and would reduce the reliability of a normal validation split.
- Excluding Flights 06 and 07 from the primary split avoids mixing coverage holes and low-sample flights into the main train/validation/test cycle.

Split outputs:

- train_pairs.csv: 9,424 rows
- validation_pairs.csv: 946 rows
- test_pairs.csv: 2,430 rows

## 8. Final assessment

Dataset readiness for model training:

- Ready for conservative pair preparation: Yes
- Ready for model training: Not yet

The dataset is geospatially valid enough for pair-generation work, but it is not yet safe for standard image-pair training because:

1. the footprint overlap cannot be verified without explicit camera calibration information;
2. the eight outside-coverage examples are not accepted as positives; and
3. the pair-generation logic is intentionally conservative and excludes uncertain geometry.

Therefore, this Phase 2A output should be treated as a prepared and validated dataset pipeline for future model training after calibration, footprint estimation, or manual verification is completed.
