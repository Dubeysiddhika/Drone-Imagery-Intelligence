# Previous Phase Audit

## Scope

This document audits the Phase 1 and Phase 2A outputs without regenerating or altering them.

## Confirmed Phase 1 findings

- 11 flight folders were identified.
- 6,774 drone images were present and matched to metadata rows.
- 11 metadata CSV files were produced and validated.
- 14 satellite TIFFs were inspected and georeferenced.
- 6,774 latitude/longitude rows were valid.
- 8 drone image centers were outside the validated satellite coverage in Flights 06 and 07.
- All TIFFs had embedded EPSG:4326 georeferencing.
- Flight 09 consists of four adjacent, non-overlapping tiles.

## Confirmed Phase 2A findings

- A conservative pair-generation pipeline produced 6,766 candidate positive pairs and 6,766 candidate negative pairs.
- 8 uncertain cases were retained separately for manual investigation.
- The confirmed set excludes uncertain cases from training.
- Flights 02 and 10 were considered suitable as a held-out test split; Flight 05 was selected as validation; the remaining flights were used for training.
- No photogrammetric footprint estimate was fabricated because calibration metadata is absent.

## Audit conclusion

The previous outputs are internally consistent. No contradictions were found between the inventory, the validation CSV, and the final Phase 2A report. The main unresolved issue remains the absence of supplier or dataset camera calibration metadata, and the requirement to keep uncertain cases out of the confirmed training set.
