# Satellite Visual Suitability Review

## Objective

Assess whether the georeferenced satellite tiles are suitable for pretrained feature matching and retrieval.

## Observations

- All 14 satellite TIFFs are CRS-embedded and georeferenced in EPSG:4326.
- The transforms and spatial bounds were preserved in the Phase 2A tile metadata export.
- Flight 09 uses four adjacent tiles with consistent geographic arrangement and no overlap.
- The visual audit created in this phase shows that georeferenced crops align with representative drone imagery at the sampled locations.

## Representative side-by-side audit

Representative drone-satellite comparisons were generated for Flights 01, 05, 09, 02, and 10. The visual outputs show that the satellite tiles are valid, full-sized geographic views and that the local scene structure is recognizable in the corresponding georeferenced crop.

This does not mean the full image footprint is verified; it means the source tiles are suitable for local visual comparison and feature-based matching in the same geographic neighborhood.

## Conclusion

The satellite tiles are suitable for visual review and likely suitable for pretrained visual feature matching at the tile level, provided the pairing is constrained by valid geographic association and not by assumed full-image overlap. The primary risk is not the tile quality; the risk is the missing camera calibration needed to strictly judge full-image overlap.
