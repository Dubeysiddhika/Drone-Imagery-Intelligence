# Drone Imagery Intelligence Platform

FastAPI backend for drone image upload, EXIF/GPS metadata extraction, YOLO object detection, SQLAlchemy persistence, and a React/Vite frontend. PostgreSQL with PostGIS is the intended production database. Development and isolated tests can use SQLite.

For cross-platform setup on Windows, macOS and Linux, environment configuration,
model/data asset requirements, startup, tests and deployment guidance, see
[LOCAL_SETUP.md](LOCAL_SETUP.md). Run `python scripts/check_environment.py` after
installing dependencies to check the local environment and optional research assets.

**Important:** a fresh clone does not contain every local artifact. The two-class
baseline checkpoint, UAV-VisLoc source dataset, generated satellite index, local
SQLite database and uploaded images may need to be supplied separately. The setup
guide identifies which features depend on each asset.

## Model & Dataset Strategy

### IMPLEMENTED

- Current baseline model classes: `person`, `vehicle`.
- Baseline dataset: the project-supplied two-class VisDrone-derived dataset under `dataset/` with train/val/test splits.
- Current model: YOLO11n pretrained backbone trained in `runs/drone_person_vehicle/weights/best.pt`.
- Baseline training configuration: `dataset/data.yaml` defines the verified class list and the project keeps the baseline model as `drone_person_vehicle`.
- Optional ten-class mode: select `model_version=visdrone10_yolo11n` to load `backend/app/models/weights/visdrone10_yolo11n_best.pt`. Its class order is `pedestrian`, `people`, `bicycle`, `car`, `van`, `truck`, `tricycle`, `awning-tricycle`, `bus`, `motor`; the upload workbench defaults to this model while the direct detection API retains the baseline default. The supplied `last.pt` is retained as `visdrone10_yolo11n_last.pt`.
- Training metadata from the supplied model is retained under `backend/app/models/visdrone10_training/`. Its `final_metrics.json` records precision `0.459`, recall `0.33`, mAP50 `0.329`, and mAP50-95 `0.183`; these are the artifact's reported metrics, not independently reproduced validation results.
- Set `VISDRONE10_MODEL_PATH` to override the ten-class checkpoint path. Relative values are resolved from the project root; the default is `backend/app/models/weights/visdrone10_yolo11n_best.pt`.
- The supplied `visdrone10_best_model.pkl` statically identifies an Ultralytics `DetectionModel` pickle, but it is not loaded or enabled. Pickle deserialization can execute code, and its trusted provenance, environment/version, class metadata, and preprocessing/inference contract are not established. Obtain these details or a documented inference checkpoint from its source before enabling it.
- Current recorded metrics: the baseline run in `runs/drone_person_vehicle/results.csv` reports precision `0.63156`, recall `0.44119`, mAP50 `0.48010`, and mAP50-95 `0.25045` for the available two-class setup.
- The backend stores image GPS/time metadata and keeps every detection traceable to its source image and model version.
- The API supports confidence-threshold filtering on retrieval without deleting the stored detections.

### PLANNED

- Extend the training pipeline to support additional object classes via a dataset YAML-driven class registry.
- Prepare a modular conversion architecture for additional aerial datasets while preserving the original VisDrone dataset and avoiding dataset mixing.
- Add evaluation reporting for per-class metrics, confusion matrices, and test-split summaries.

### REQUIRES ADDITIONAL DATA

- The baseline remains limited to `person` and `vehicle`. The separate ten-class VisDrone model uses its own labels and is not interchangeable with the two-class baseline.
- Future aerial-domain classes such as building, barrier, temporary structure, or equipment require a separate dataset with documented annotations, licensing, and conversion to the project YOLO format.
- Any expanded taxonomy must be explicitly mapped and evaluated on a held-out test set before being treated as a production model.

### GPS and Geolocation Limitations

- The current system stores image-level GPS and capture time when EXIF contains them.
- No object-level geographic coordinates are inferred from a bounding box.
- The database supports future geospatial queries by image location, but bounding boxes remain pixel-based and are not treated as exact ground-truth coordinates.

### Model Limitations

- The default detector remains a baseline object detector for `person` and `vehicle`.
- The optional ten-class VisDrone detector has different class definitions; it does not change the baseline taxonomy or make the two models' metrics directly comparable.
- The ten-class checkpoint currently available in the workspace is not from a completed training run; complete training and evaluate on the documented validation split before relying on its predictions.
- Future model changes must preserve the baseline as a reference and compare metrics against it before claiming improvement.

## UAV-VisLoc Visual Localization

The UAV-VisLoc page lets a user select an uploaded image or upload a new one,
then explicitly choose GPS-free or GPS-assisted retrieval.
`POST /api/uav-visloc/localize/{image_id}?mode=gps_free` uses the existing
DINOv2 satellite index and the evaluated retrieval settings:
280-pixel query preprocessing, top 50 retrieval, one-ring expansion around
the top five seeds, a 75-candidate budget, and final ordering by the original
DINOv2 cosine score. The satellite index is not rebuilt. The service then
attempts live SuperPoint/LightGlue matching with RANSAC verification on at most
the first five ranked candidates. To opt into GPS assistance, use
`POST /api/uav-visloc/localize/{image_id}?mode=gps_assisted`; the selected image
must have valid stored EXIF latitude and longitude. This mode restricts the
retrieval pool to satellite parent-map footprints containing that point, then
ranks the eligible patches visually. It fails clearly if the coordinate is
missing or outside all indexed footprints and never falls back to GPS-free
search. Satellite previews are available from
`GET /api/uav-visloc/candidates/{tile_id}/preview`.

Candidate coordinates are satellite patch centers transformed from each
patch's raster CRS to WGS84. They identify candidate patches only; retrieval
similarity is a ranking score, and geometric verification is evidence of
image consistency. Neither is a calibrated confidence nor a precise query
location. Candidate footprints are returned in WGS84 GeoJSON. Detected objects
are not assigned candidate coordinates. GPS-free mode never reads image GPS
for candidate ranking; GPS-assisted mode is visibly labeled in results and
processing history. Accepted runs are persisted in `processing_runs` with
mode, status, timing, candidate count, and verification count. Only one
CPU/RAM-heavy localization run can execute at a time. Runtime memory checks
may skip local verification on constrained machines, and matching is limited
to five candidates.

The bounded integration check used one existing UAV-VisLoc query image. It
returned 75 ranked patches and served the satellite preview successfully in
76.8 seconds. Its top candidate had 17 tentative matches and 5 RANSAC inliers,
but its parent satellite area did not match the query's known area. This is a
successful pipeline integration check, not evidence of localization accuracy.

## Complete Image Intelligence Workflow

Image uploads are matched against all 11 source flight CSV files under
`UAV_VisLoc_dataset/` and the consolidated metadata inventory. Exact filenames
are accepted only when the uploaded bytes also match the referenced dataset
image by SHA-256. For renamed or recompressed images, the registry builds a
cached perceptual-hash shortlist and accepts a result only after exact hash or
ORB/RANSAC verification; ambiguous matches remain unassigned. The first such
fallback can read the dataset images once to build `.uav_visloc_fingerprints.json`
in the project root. Set `UAV_VISLOC_DATASET_DIR` if the dataset is elsewhere.
CSV fields from the flight source and consolidated inventory are retained
separately with the match record.

The Upload/Analysis workbench automatically runs the selected detector (the
VisDrone10 YOLO11n weights by default) and, for a verified UAV-VisLoc image,
starts GPS-free localization unless that option is unchecked. Ground-truth
coordinates are never passed to GPS-free retrieval. EXIF coordinates,
UAV-VisLoc ground truth, and satellite candidate patch coordinates are shown
with separate provenance. This localization implementation does not produce
a calibrated UAV coordinate, so distance-error accuracy is intentionally
reported as unavailable; the report may include the rank of the matching
ground-truth satellite region and patch-center offsets labeled as candidate
offsets, not prediction errors.

The complete persisted result is available at
`GET /api/intelligence/images/{image_id}`. Run detection and eligible
GPS-free localization together with
`POST /api/intelligence/images/{image_id}/process?model_version=visdrone10_yolo11n&run_localization=true`.
Download `.../export.json`, `.../export.csv`, or `.../report.pdf` for the same
image ID. Existing individual Images, Analysis, and UAV-VisLoc endpoints remain
available. YOLO boxes are source-image pixel coordinates and are never treated
as individual-object ground positions.

The bounded end-to-end model check processed one image from each of the 11
flights sequentially. Dataset identity matched for all 11. Each query returned
64–75 ranked satellite patches; 0–5 candidates per query passed the current
RANSAC consistency check. The ground-truth map appeared in the retrieved
candidate set for flights 01, 03, 04, 05, 06, 08, and 10; candidate retrieval
did not include the expected map for flights 02, 07, and 11. These are
retrieval-coverage observations on the bounded sample, not UAV localization
accuracy measurements. Flight 09 references multiple satellite TIFFs and is
ranked against all listed maps.

## Project Paths and Dataset Tools

Project scripts derive the project root from their own file locations, so their default dataset, checkpoint, report, database, and upload paths do not depend on the shell's current directory. Relative path arguments to `training/prepare_dataset.py` and `training/evaluate.py` are interpreted from the project root; absolute arguments are also accepted.

The VisDrone converter expects the extracted source under `dataset/raw/` by default, with the train and validation directories in the archive's original layout. It writes the converted dataset under `dataset/`; the YAML split paths are relative to the YAML file, so they stay valid if the project is moved. Do not run the converter unless you intend to create or replace converted dataset outputs. `training/check_dataset.py`, `training/train.py`, and `training/evaluate.py` use the project dataset and model locations regardless of the directory from which they are launched. The training and evaluation scripts resolve the YAML dataset root before passing the configuration to Ultralytics.

The FastAPI service stores uploads in `backend/uploads/`. Its default development SQLite database is the project-root `drone.db`; a relative SQLite `DATABASE_URL` is also resolved from the project root. PostgreSQL URLs in `.env` or the process environment continue to refer to the configured external database service.

## Database Setup

Install PostgreSQL and a PostGIS package matching that PostgreSQL version. On Windows, PostGIS can be installed through the PostgreSQL Stack Builder or an approved PostGIS installer. No PostgreSQL server or PostGIS installation was detected on the development machine during Phase 5; neither was installed automatically.

Create a database and enable PostGIS as a database administrator:

```sql
CREATE DATABASE drone_intelligence;
\c drone_intelligence
CREATE EXTENSION IF NOT EXISTS postgis;
SELECT PostGIS_Full_Version();
```

Copy `.env.example` to `.env`, then replace the placeholder connection values with your local database credentials. Never commit `.env` or put real credentials in source control.

The production URL format is:

```text
postgresql+psycopg://postgres:<password>@localhost:5432/drone_intelligence
```

When `APP_ENV=production`, the application requires `DATABASE_URL`. If the URL selects PostgreSQL, startup checks `PostGIS_Full_Version()` and exits with a setup error if PostGIS is not enabled. The app does not create the extension automatically because that requires database privileges.

For development, if `DATABASE_URL` is not set, SQLite falls back to the project-root file `drone.db`, resolved from this source tree rather than the current working directory. Set `DATABASE_URL` explicitly to select another database. The existing root and backend SQLite files are not deleted or automatically copied. No SQLite-to-PostgreSQL data migration is performed. Before moving real data, take backups and use a reviewed, repeatable migration (preferably Alembic) with validation; do not treat test records as production data.

## Database Model

- `Survey` contains `DroneImage` rows.
- `DroneImage` contains nullable latitude, longitude, altitude, capture time, and a nullable `location` point.
- `Detection` belongs to a `DroneImage` by `image_id`. It does not store calculated object coordinates.

On PostgreSQL, `location` is `geometry(POINT,4326)` and is populated only when both latitude and longitude are present and in range. Its coordinate order is `POINT(longitude latitude)`. The SQLite development fallback stores an EWKT string for model tests; this is not a spatial database and does not provide PostGIS queries. No coordinates are generated from detection boxes.

Startup creates missing tables and adds the Phase 3 detection columns and image location column additively. Existing SQLite rows are not copied or deleted. For a new PostgreSQL database, enable PostGIS before starting the app. For an existing PostgreSQL schema, startup adds the nullable columns but does not backfill geometry or invent locations.

Future spatial queries can use the image location column with PostGIS functions such as `ST_Within`; detections inherit their geographic context by joining `Detection.image_id` to `DroneImage.id`.

The dashboard aggregates surveys, uploaded images, persisted detections, EXIF GPS
availability, and class/confidence distributions directly from these records.
Detection and UAV-VisLoc attempts are also recorded in the additive
`processing_runs` table, including completion status, elapsed time, and result
counts. Existing image records remain unchanged; a stored detection or a
completed run marks an image as processed. An older image with no detections
and no run history is reported as pending because the database cannot establish
whether a historical zero-result inference occurred. Date filters apply to
image upload dates, and survey filters scope the associated images and their
processing history.

## Python Environment

From the project root in PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
```

To use PostgreSQL, set `APP_ENV=production` and configure `DATABASE_URL` in `.env` or the process environment. For local SQLite development, leave `DATABASE_URL` unset or point it explicitly at a SQLite URL.

## Start the Backend

Run from `backend` so the existing package entry point resolves:

```powershell
Set-Location backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --http h11 --ws none
```

`--http h11 --ws none` avoids optional `httptools` and WebSocket protocol modules that were incompatible in the verified local Python environment. The API does not currently define WebSocket routes.

Health checks:

```text
GET http://127.0.0.1:8000/health
GET http://127.0.0.1:8000/api/health
```

## API Endpoints

- `POST /api/images/upload` uploads an image and extracts available metadata.
- `GET /api/images/` lists image records.
- `GET /api/images/{image_id}` returns image metadata.
- `GET /api/analysis/models` lists supported model IDs, framework, class count, and weight availability without exposing filesystem paths.
- `POST /api/analysis/detect/{image_id}` runs YOLO and replaces that image's stored detections.
- `GET /api/analysis/detections/{image_id}` returns persisted detections without rerunning YOLO.
- `GET /api/surveys/` and survey routes manage surveys.
- `GET /api/dashboard/` exposes dashboard data.

Interactive API documentation is available at `/docs` while the backend is running.

The detection route defaults to the existing baseline. Select the ten-class model
with a query parameter:

```text
POST /api/analysis/detect/123?model_version=visdrone10_yolo11n
```

Check available models with `GET /api/analysis/models`. The detection endpoint
defaults to `baseline`; select the received ten-class weights with the query
parameter shown above.

The response includes the selected class list and detections with `class_id`,
`class_name`, `confidence`, and `bbox` (`x1`, `y1`, `x2`, `y2`). Coordinates are
floating-point pixel coordinates in the original image, in top-left-origin
`pixel_xyxy` order (`x1`, `y1` are the upper-left corner; `x2`, `y2` the
lower-right). Selecting a model reruns detection and replaces that image's
previously persisted detections, matching the existing baseline endpoint
behavior. Image uploads accept JPG/JPEG, PNG, and TIFF with matching decoded
content; unsupported or corrupt images are rejected with HTTP 400.

Example response:

```json
{
  "image_id": 123,
  "model_name": "YOLO11n VisDrone10",
  "model_version": "visdrone10_yolo11n",
  "classes": [
    "pedestrian", "people", "bicycle", "car", "van",
    "truck", "tricycle", "awning-tricycle", "bus", "motor"
  ],
  "coordinate_system": "pixel_xyxy",
  "detections": [
    {
      "id": 8,
      "class_id": 3,
      "class_name": "car",
      "confidence": 0.91,
      "model_name": "YOLO11n VisDrone10",
      "model_version": "visdrone10_yolo11n",
      "bbox": {"x1": 102.5, "y1": 60.0, "x2": 244.0, "y2": 173.5}
    }
  ],
  "detection_count": 1
}
```

## Tests

Run the isolated SQLite-backed tests from the backend directory:

```powershell
Set-Location backend
python -m unittest discover -s tests -v
```

These tests cover metadata, model persistence, repeated detection, and the real YOLO weights without writing to the project databases. They do not claim to test PostGIS.

To run the PostGIS integration test, configure `TEST_POSTGIS_DATABASE_URL` to a dedicated disposable PostgreSQL database with PostGIS enabled, then run the same unittest command. The test creates and drops only its uniquely named temporary schema in that explicitly configured database. Without this variable, PostGIS integration is skipped.

## Frontend

The existing React/Vite frontend is under `src/`. Install Node dependencies with `npm install`, then run `npm run dev` from the project root. The UAV-VisLoc page supports selecting an uploaded image or uploading a new query, choosing GPS-free or explicitly GPS-assisted retrieval, and reviewing ranked candidates and verification evidence.

## Direct Detection Upload API

The interactive `/docs` page also exposes `POST /api/detection/predict`. Send a
multipart field named `file` with a JPG, JPEG, PNG, BMP, TIF, or TIFF image. The
response includes class names, confidence scores, pixel bounding boxes,
detection count, and an `annotated_image_url`. Fetch that URL from the same
backend to view the generated JPEG. Annotated results are written to
`backend/uploads/annotated/` and are separate from uploaded source imagery.

The direct endpoint uses the existing CPU YOLO detector. The VisDrone10 model
path defaults to `runs/visdrone10_yolo11n/weights/best.pt`; set
`VISDRONE10_MODEL_PATH` to override it. The existing image upload and persisted
analysis endpoints remain available.

## Image EXIF and GPS Metadata

`POST /api/images/upload` extracts image dimensions and available EXIF values
before creating the image record. JPG/JPEG are the primary EXIF formats; PNG
and TIFF uploads remain supported, with fields reported only when the decoder
can read them. The response and `GET /api/images/{image_id}` include nullable
latitude, longitude, altitude, capture time, camera make/model, dimensions,
EXIF orientation (1-8), focal length in millimeters, and `gps_available`.
GPS is available only when both coordinates and valid hemisphere references
are present. Missing or malformed GPS values remain null; the service never
supplies fallback coordinates.

To associate an upload with an existing survey, send its ID as the multipart
`survey_id` field alongside `file`. Unknown survey IDs are rejected and the
uploaded file is removed. Existing image rows are preserved when the app adds
nullable metadata columns at startup.

## Geospatial Image Map

`GET /api/images/geospatial` returns valid image capture points in
`located_images` (also available through the legacy `images` field) and images
without valid coordinates in `unlocated_images`. Both collections include
survey details, capture time, altitude, detection totals, per-class counts,
original and annotated image preview URLs, and an explicit GPS availability
flag. Optional `survey_id`, `image_id`, `class_name`, `date_from`, and `date_to`
query parameters filter by survey, image, stored class, and upload date. Images
without valid GPS are never plotted. The Leaflet map refreshes on focus and
periodically so newly GPS-tagged uploads appear without a page redesign.
Detection boxes are pixel-space only; this API does not project them onto the
ground or report object locations. The map handles display projection from
EPSG:4326, and its clusters represent nearby image capture points only.

`GET /api/images/{image_id}/annotated` renders the image with its saved YOLO
boxes for map popups. It does not assign GPS positions to individual objects.
# Phase 5: Geometrically verified image-center estimation

UAV-VisLoc now attempts a query-to-satellite homography for the five shortlisted candidates. It estimates the query image center in the satellite patch, transforms that pixel through the patch affine transform and CRS to EPSG:4326, and reports a coordinate only when the configurable geometric checks pass. Candidate patch centers remain separate from the estimated query center.

The default checks require at least eight tentative matches and RANSAC inliers, a 0.25 inlier ratio, spatially distributed support in both images, median reprojection error at most 3 pixels, and an image-center projection inside the satellite patch. Several accepted candidate estimates must agree within 25 metres; conflicting groups are rejected. A single accepted candidate is labeled as such and flagged as lower-support. A homography assumes a locally planar scene and does not model all oblique-camera perspective or terrain relief, so the result is an estimate rather than a calibrated uncertainty.

Quality settings can be overridden with `UAV_VISLOC_MIN_MATCHES`, `UAV_VISLOC_MIN_INLIERS`, `UAV_VISLOC_MIN_INLIER_RATIO`, `UAV_VISLOC_MIN_HULL_FRACTION`, `UAV_VISLOC_MIN_SPAN_FRACTION`, `UAV_VISLOC_MAX_REPROJECTION_ERROR_PX`, `UAV_VISLOC_CONSENSUS_DISTANCE_M`, and `UAV_VISLOC_MAX_KEYPOINTS`. Values outside safe bounds fall back to the defaults. Ground-truth coordinates are attached only after GPS-free estimation for persisted evaluation; they are never passed into retrieval or projection.

The intelligence API, JSON/CSV/PDF exports, dashboard aggregates, workbench, UAV-VisLoc page, and map expose the estimate separately from EXIF GPS, dataset ground truth, and satellite patch centers. Evaluation includes per-image haversine error and dashboard mean/median/threshold summaries, including flight-level summaries, calculated only when matched ground truth is available.

Initial bounded estimator validation used `01_0065.JPG`, `03_0001.JPG`, and `06_0001.JPG` on CPU (512 SuperPoint keypoints; top five candidates only). All three remained retrieval-only: the strongest shortlisted candidates had 4–6 RANSAC inliers, below the eight-inlier gate. No image-center coordinates were emitted, so per-image coordinate errors, threshold percentages, and aggregate error metrics are unavailable for this sample. Recorded processing times were 54.3 s, 51.1 s, and 49.3 s; process RSS snapshots after inference were 245 MB, 214 MB, and 338 MB. These are bounded-run observations, not peak RAM measurements or benchmark claims.
