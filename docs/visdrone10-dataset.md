# Preparing the original VisDrone2019-DET source

Obtain the **VisDrone2019 object detection (VisDrone-DET)** data from the
official [VisDrone dataset repository](https://github.com/VisDrone/VisDrone-Dataset),
following its VisDrone-DET download links and dataset terms. Use the
`VisDrone2019-DET-train` and `VisDrone2019-DET-val` archives. The optional
`VisDrone2019-DET-test-dev` split may also be included; its image/annotation
availability depends on the official release. Do not substitute the project's
existing two-class YOLO labels: they cannot establish the original ten
categories.

Extract the archives without changing their original `images/` and
`annotations/` contents under `dataset_visdrone10_source/`. Both common archive
layouts below are accepted:

```text
dataset_visdrone10_source/
├── VisDrone2019-DET-train/
│   ├── images/
│   └── annotations/
└── VisDrone2019-DET-val/
    ├── images/
    └── annotations/
```

Some archives add a repeated directory level:

```text
dataset_visdrone10_source/
└── VisDrone2019-DET-train/
    └── VisDrone2019-DET-train/
        ├── images/
        └── annotations/
```

Point the verifier at the directory containing the split folders (or point it
directly at a split folder). For example, from the project root in PowerShell:

```powershell
& 'E:\Drone-image-intelligence\.venv-1\Scripts\python.exe' `
  .\scripts\verify_visdrone_source.py `
  --source .\dataset_visdrone10_source
```

Run the synthetic tests from the project root with the interpreter that has
Pillow and PyYAML installed (`.venv-2` in the current workspace):

```powershell
& 'E:\Drone-image-intelligence\.venv-2\Scripts\python.exe' `
  -m unittest discover -s tests -p 'test_*visdrone*.py' -v
```

The verifier is read-only. It reports image and annotation-file counts, rows,
malformed rows, zero-area boxes, unmatched image/annotation filenames,
observed category IDs, and categories missing from the original annotation
rows. Category ID 0 (ignored regions) and category ID 11 (`others`) are valid
original annotation categories but are not detector classes in this ten-class
task. An unannotated optional test-dev split is inventoried but is not required.

## Staging and annotation repair

Never edit the downloaded source tree. The staging script copies the required
split directories to a new `dataset_visdrone10/` directory and refuses to run
if that output directory already exists. It only repairs the specific known
train annotation file `9999974_00000_d_0000053.txt`: each trailing empty field
is removed in the staged copy only when the remaining eight integer fields
constitute a supported VisDrone annotation row with positive box dimensions.
Each changed file and row is recorded in `repair_report.json`.
The full report is written to `dataset_visdrone10/repair_report.json` and also
includes every remaining zero-area annotation's file and line.

VisDrone rows follow
`bbox_left,bbox_top,bbox_width,bbox_height,score,category,truncation,occlusion`.
Three known train rows have zero-height boxes. They are syntactically
eight-integer VisDrone rows, not malformed CSV, but their box geometry has zero
area. The source and staged annotation rows are preserved unchanged. The
training-label conversion policy is to **exclude any row with zero width or
zero height from generated YOLO labels**, recording the excluded source
filename and line; do not invent or alter coordinates. The verifier reports
these separately from malformed rows and keeps `ready_for_ten_class_conversion`
false while such rows remain, so this policy must be implemented and checked by
the eventual converter before training labels are considered ready.

Run staging from the project root only after confirming that
`dataset_visdrone10/` does not exist:

```powershell
& 'E:\Drone-image-intelligence\.venv-1\Scripts\python.exe' `
  .\scripts\stage_visdrone_source.py `
  --source .\dataset_visdrone10_source `
  --output .\dataset_visdrone10
```

Validate the staged tree independently:

```powershell
& 'E:\Drone-image-intelligence\.venv-1\Scripts\python.exe' `
  .\scripts\verify_visdrone_source.py `
  --source .\dataset_visdrone10
```

The source verifier continues to report non-zero status for the staged tree
because it preserves and flags the original zero-area rows. The converter below
handles this separately through the explicit training-label exclusion policy.

Run both synthetic test suites without requiring the real dataset:

```powershell
& 'E:\Drone-image-intelligence\.venv-1\Scripts\python.exe' -m pytest `
  .\tests\test_verify_visdrone_source.py `
  .\tests\test_stage_visdrone_source.py -v
```

Expected VisDrone detection annotation rows have eight comma-separated integer
fields:

```text
bbox_left,bbox_top,bbox_width,bbox_height,score,category,truncation,occlusion
```

| VisDrone category ID | YOLO class ID | Category |
|---:|---:|---|
| 1 | 0 | pedestrian |
| 2 | 1 | people |
| 3 | 2 | bicycle |
| 4 | 3 | car |
| 5 | 4 | van |
| 6 | 5 | truck |
| 7 | 6 | tricycle |
| 8 | 7 | awning-tricycle |
| 9 | 8 | bus |
| 10 | 9 | motor |

VisDrone category IDs 0 (ignored regions) and 11 (`others`) are not mapped to
YOLO detector classes. This verification and staging workflow does not convert
labels or start training.

## Ten-class YOLO conversion

The separate converter reads the staged VisDrone annotations and writes images,
labels, a ten-name YAML, and a conversion report under
`dataset_visdrone10_yolo/`. It refuses any existing output folder and never
modifies `dataset/`, the original source, the staging source, or the
two-class run. Use the environment with Pillow/PyYAML available (and
Ultralytics 8.4.155 is installed in `.venv-2`):

```powershell
& 'E:\Drone-image-intelligence\.venv-2\Scripts\python.exe' `
  .\scripts\convert_visdrone10_yolo.py `
  --source .\dataset_visdrone10 `
  --output .\dataset_visdrone10_yolo
```

The converter validates the source annotations and image dimensions, rejects
malformed rows, negative sizes, invalid target coordinates and boxes outside
image bounds, and checks the generated image/label pairs, class IDs, normalized
boxes, and YAML class order before committing the output directory. Target
categories map as follows:

| VisDrone category ID | YOLO class ID | Category |
|---:|---:|---|
| 1 | 0 | pedestrian |
| 2 | 1 | people |
| 3 | 2 | bicycle |
| 4 | 3 | car |
| 5 | 4 | van |
| 6 | 5 | truck |
| 7 | 6 | tricycle |
| 8 | 7 | awning-tricycle |
| 9 | 8 | bus |
| 10 | 9 | motor |

Category 0 (ignored regions) and category 11 (`others`) are counted and omitted
from detector labels. Zero-width or zero-height boxes are not modified; each is
recorded with split, annotation filename, row number, category and reason, and
excluded from generated labels. The three known zero-height training rows must
appear in the conversion report. After conversion, validate without modifying
the generated dataset:

```powershell
& 'E:\Drone-image-intelligence\.venv-2\Scripts\python.exe' `
  .\scripts\convert_visdrone10_yolo.py `
  --validate-only `
  --output .\dataset_visdrone10_yolo
```

Training has not been started as part of conversion. Review the generated
`conversion_report.json` and the validation output before choosing training
settings.

### Verified conversion output

The generated dataset passed the converter's independent validation and the
`--validate-only` command:

| Split | Images | Label files | Generated target boxes |
|---|---:|---:|---:|
| Train | 6,471 | 6,471 | 343,204 |
| Validation | 548 | 548 | 38,759 |

All ten class names are present in the prescribed order. Generated boxes per
class (train + validation) are: pedestrian 88,181; people 32,184; bicycle
11,767; car 158,930; van 26,931; truck 13,625; tricycle 5,857;
awning-tricycle 3,778; bus 6,177; motor 34,533.

The report records 10,191 category-0 ignored-region rows, 1,564 category-11
`others` rows, and all 3 zero-height rows. The zero-height rows are excluded
from labels; source and staged annotation contents remain unchanged. The
staging repair report records 34 trailing-comma field normalizations. There is
no separate test split in this conversion; evaluation on the validation split
is possible, but a test-set metric is not available. No training or model
evaluation was run as part of conversion.

## Git handling

The project already ignores `dataset/images/`, `dataset/labels/`, and `runs/`
(including generated run weights), as well as `training/*.pt` (including the
local pretrained checkpoint). The root `.gitignore` now also leaves the
`dataset_visdrone10_source/` placeholder trackable while excluding downloaded
source files. Keep additional large archives and generated weights out of Git;
if weights are stored outside `runs/` or `training/`, add a narrowly scoped
ignore rule for that artifact directory rather than ignoring all model files
globally.
