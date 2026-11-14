# Satellite TIFF Inspection

## Summary
- Total satellite TIFFs: 14
- TIFFs with embedded CRS: 14
- TIFFs requiring external georeferencing: 0

## Flight 09 tile investigation
- satellite09_01-01.tif: 25600 x 25600, bounds=120.02975463867188,30.931320190429688 to 120.09841918945312,30.999984741210938, CRS=EPSG:4326
- satellite09_01-02.tif: 19200 x 25600, bounds=120.09841918945312,30.931320190429688 to 120.14991760253906,30.999984741210938, CRS=EPSG:4326
- satellite09_02-01.tif: 25600 x 7680, bounds=120.02975463867188,30.910720825195312 to 120.09841918945312,30.931320190429688, CRS=EPSG:4326
- satellite09_02-02.tif: 19200 x 7680, bounds=120.09841918945312,30.910720825195312 to 120.14991760253906,30.931320190429688, CRS=EPSG:4326
- Tile order: satellite09_01-01.tif, satellite09_01-02.tif, satellite09_02-01.tif, satellite09_02-02.tif
- Spatial arrangement: 2x2 grid with shared boundaries along the vertical and horizontal midlines.
- Overlap check: no tile overlaps with another tile; the edges touch exactly at shared coordinates.
- Mosaic verdict: safe to combine into a single mosaic if the intended output is a 2x2 satellite composite.

## General TIFF findings
- satellite01.tif: width=9774, height=26762, bands=3, dtype=uint8, CRS=EPSG:4326, bounds=(115.970635, 29.702283) to (115.996851, 29.774065)
- satellite02.tif: width=11482, height=34291, bands=3, dtype=uint8, CRS=EPSG:4326, bounds=(116.033769, 29.725402) to (116.064566, 29.817376)
- satellite03.tif: width=35092, height=24308, bands=3, dtype=uint8, CRS=EPSG:4326, bounds=(119.805926, 32.29029) to (119.900052, 32.355491)
- satellite04.tif: width=18093, height=38408, bands=3, dtype=uint8, CRS=EPSG:4326, bounds=(119.90598, 32.151018) to (119.954509, 32.254036)
- satellite05.tif: width=9394, height=6144, bands=3, dtype=uint8, CRS=EPSG:4326, bounds=(102.340055, 24.650422) to (102.365252, 24.666899)
- satellite06.tif: width=8082, height=9780, bands=3, dtype=uint8, CRS=EPSG:4326, bounds=(109.63516, 32.346944) to (109.656837, 32.373177)
- satellite07.tif: width=3000, height=170, bands=3, dtype=uint8, CRS=EPSG:4326, bounds=(115.791182, 40.339604) to (115.79923, 40.340058)
- satellite08.tif: width=43421, height=16294, bands=3, dtype=uint8, CRS=EPSG:4326, bounds=(120.136489, 30.903521) to (120.252951, 30.947227)
- satellite09_01-01.tif: width=25600, height=25600, bands=3, dtype=uint8, CRS=EPSG:4326, bounds=(120.02975463867188, 30.931320190429688) to (120.09841918945312, 30.999984741210938)
- satellite09_01-02.tif: width=19200, height=25600, bands=3, dtype=uint8, CRS=EPSG:4326, bounds=(120.09841918945312, 30.931320190429688) to (120.14991760253906, 30.999984741210938)
- satellite09_02-01.tif: width=25600, height=7680, bands=3, dtype=uint8, CRS=EPSG:4326, bounds=(120.02975463867188, 30.910720825195312) to (120.09841918945312, 30.931320190429688)
- satellite09_02-02.tif: width=19200, height=7680, bands=3, dtype=uint8, CRS=EPSG:4326, bounds=(120.09841918945312, 30.910720825195312) to (120.14991760253906, 30.931320190429688)
- satellite10.tif: width=6593, height=5077, bands=3, dtype=uint8, CRS=EPSG:4326, bounds=(115.776356, 40.341475) to (115.794041, 40.355093)
- satellite11.tif: width=29592, height=16582, bands=3, dtype=uint8, CRS=EPSG:4326, bounds=(101.013109, 38.807825) to (101.092483, 38.852301)
