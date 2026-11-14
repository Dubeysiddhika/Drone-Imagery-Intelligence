# UAV-VisLoc Phase 1 Report

## 1. Dataset summary

- Flights identified: 11
- Drone images: 6774
- Metadata CSV files: 11
- Satellite TIFF files: 14
- Valid latitude/longitude rows: 6774
- Missing coordinates: 0
- Invalid coordinates: 0
- Duplicate image filenames: 0
- GPS points inside satellite coverage: 6766
- GPS points outside satellite coverage: 8

## 2. Directory structure and file inventory

The dataset root contains 11 numbered flight folders plus the dataset README and one satellite-boundary CSV. Each flight folder is paired with a `drone/` image directory, a flight metadata CSV, and one or more TIFF tiles. Flight 09 is a 2x2 tile mosaic and therefore contains four separate TIFF files instead of one.

## 3. Metadata extraction

The CSV files follow the documented UAV-VisLoc schema: `num, filename, date, lat, lon, height, Omega, Kappa, Phi1, Phi2` for most flights. The metadata values are consistent across the dataset, with all 6,774 image records present and correctly paired to the corresponding drone images.

The raw metadata was preserved exactly in the consolidated export, including flight association, source CSV path, source row number, and original coordinate strings. All latitude and longitude values were kept in separate columns and were not reversed.

## 4. Satellite TIFF inspection

The TIFF files are already georeferenced in EPSG:4326, and the transformation matrices establish valid geographic bounds without requiring external recalculation. Each file exposes width, height, number of bands, dtype, CRS, affine transform, and geographic bounds. Flight 09 comprises four adjacent tiles that share exact boundaries without overlap, which makes them safe to combine into a single mosaic once the intended composite is required.

## 5. Geographic coverage validation

A total of 6,774 drone coordinates were checked against the available flight satellite boundaries. All coordinates were valid geodetic values. A small number of coordinates (8 total) fall outside the provided satellite map coverage and are explicitly flagged in the validation export; these are not silently overwritten. These outside-coverage points were found in flight 06 and flight 07.

## 6. Dataset limitations

- Raw date strings from some flights are compact and may require additional parsing logic if pipeline code expects ISO-8601 timestamps.
- The dataset includes a coarse map-corner CSV, but the per-flight TIFF bounds remain the stronger source for actual geographic coverage checks.
- A center coordinate inside a map is not a guarantee that the full drone image footprint is covered; this was kept conceptually separate in the validation report.

## 7. Integration recommendations

The current project already exposes a UAV-VisLoc metadata API and a React dataset page. The most compatible next step is to keep the source dataset immutable and store only the extracted ground-truth metadata and validation results in application data models, while leaving model-predicted localization outputs separate. That means:

- Keep metadata rows in a table keyed by flight and image filename.
- Link each image record to a flight and an optional satellite map or map tile group.
- Keep satellite coverage polygons in separate geospatial fields, not as replacements for the ground-truth GPS values.
- Present flight-wise markers and satellite boundary overlays in the dashboard without overwriting original coordinates.
- Store model prediction results in a distinct table with a foreign key to the original drone image record.

## 8. Classification

This dataset is classified as READY WITH CONDITIONS for the next phase of drone-to-satellite visual localization development. The metadata is complete and geospatially rich, but the outside-coverage points and raw date formatting in a few entries should be audited before model development proceeds.
