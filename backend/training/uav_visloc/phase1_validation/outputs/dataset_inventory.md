# UAV-VisLoc Phase 1: Dataset Inventory

## Dataset root
- Root: `E:\Drone-image-intelligence\UAV_VisLoc_dataset`
- Flights: 11
- Drone images: 6774
- Metadata CSV files: 11
- Satellite TIFF files: 14
- Total bytes across all files: 23,962,597,295 bytes

## File extension breakdown
- `.csv`: 12
- `.jpg`: 6774
- `.tif`: 14
- `.txt`: 1

## Flight directory structure
### Flight 01
- Drone images: 817
- Metadata CSV: 01.csv
- Satellite tiles: satellite01.tif
- Drone images sample: 01_0001.JPG, 01_0002.JPG, 01_0003.JPG, 01_0004.JPG, 01_0005.JPG

### Flight 02
- Drone images: 1071
- Metadata CSV: 02.csv
- Satellite tiles: satellite02.tif
- Drone images sample: 02_0001.JPG, 02_0002.JPG, 02_0003.JPG, 02_0004.JPG, 02_0005.JPG

### Flight 03
- Drone images: 768
- Metadata CSV: 03.csv
- Satellite tiles: satellite03.tif
- Drone images sample: 03_0001.JPG, 03_0002.JPG, 03_0003.JPG, 03_0004.JPG, 03_0005.JPG

### Flight 04
- Drone images: 738
- Metadata CSV: 04.csv
- Satellite tiles: satellite04.tif
- Drone images sample: 04_0001.JPG, 04_0002.JPG, 04_0003.JPG, 04_0004.JPG, 04_0005.JPG

### Flight 05
- Drone images: 473
- Metadata CSV: 05.csv
- Satellite tiles: satellite05.tif
- Drone images sample: 05_0001.JPG, 05_0002.JPG, 05_0003.JPG, 05_0004.JPG, 05_0005.JPG

### Flight 06
- Drone images: 344
- Metadata CSV: 06.csv
- Satellite tiles: satellite06.tif
- Drone images sample: 06_0001.JPG, 06_0002.JPG, 06_0003.JPG, 06_0004.JPG, 06_0005.JPG

### Flight 07
- Drone images: 30
- Metadata CSV: 07.csv
- Satellite tiles: satellite07.tif
- Drone images sample: 07_0001.JPG, 07_0002.JPG, 07_0003.JPG, 07_0004.JPG, 07_0005.JPG

### Flight 08
- Drone images: 1033
- Metadata CSV: 08.csv
- Satellite tiles: satellite08.tif
- Drone images sample: 08_0001.JPG, 08_0002.JPG, 08_0003.JPG, 08_0004.JPG, 08_0005.JPG

### Flight 09
- Drone images: 766
- Metadata CSV: 09.csv
- Satellite tiles: satellite09_01-01.tif, satellite09_01-02.tif, satellite09_02-01.tif, satellite09_02-02.tif
- Drone images sample: 09_0001.JPG, 09_0002.JPG, 09_0003.JPG, 09_0004.JPG, 09_0005.JPG

### Flight 10
- Drone images: 144
- Metadata CSV: 10.csv
- Satellite tiles: satellite10.tif
- Drone images sample: 10_0001.JPG, 10_0002.JPG, 10_0003.JPG, 10_0004.JPG, 10_0005.JPG

### Flight 11
- Drone images: 590
- Metadata CSV: 11.csv
- Satellite tiles: satellite11.tif
- Drone images sample: 11_0001.JPG, 11_0002.JPG, 11_0003.JPG, 11_0004.JPG, 11_0005.JPG

## Relationship summary
- Each flight folder is a self-contained capture unit.
- Every flight folder contains a metadata CSV and a `drone/` directory with corresponding JPG images.
- The CSV row count matches the drone image count for every flight in the source dataset, indicating a complete pairing of metadata records to images.
- The flight-level satellite map file(s) are co-located in the same folder and represent the geographic coverage for that flight.
- Flight 09 is the only case with multiple adjacent TIFF tiles in the same folder; they are treated as part of one flyover area.

## Data completeness assessment
- The dataset appears complete at the file-system level, with all expected numbered flight folders present.
- No missing drone metadata records were detected in the source files.
- No duplicate drone-image filenames were found across the dataset.
- All drone images were readable by Pillow and each folder had a consistent image dimension pattern.
