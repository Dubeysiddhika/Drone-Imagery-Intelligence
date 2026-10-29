# Drone Imagery Intelligence Platform

FastAPI backend for drone image upload, EXIF/GPS metadata extraction, YOLO object detection, SQLAlchemy persistence, and a React/Vite frontend. PostgreSQL with PostGIS is the intended production database. Development and isolated tests can use SQLite.

## Model & Dataset Strategy

### IMPLEMENTED

- Current baseline model classes: `person`, `vehicle`.
- Baseline dataset: the project-supplied two-class VisDrone-derived dataset under `dataset/` with train/val/test splits.
- Current model: YOLO11n pretrained backbone trained in `runs/drone_person_vehicle/weights/best.pt`.
- Baseline training configuration: `dataset/data.yaml` defines the verified class list and the project keeps the baseline model as `drone_person_vehicle`.
- Optional ten-class mode: select `model_version=visdrone10_yolo11n` to load `runs/visdrone10_yolo11n/weights/best.pt`, which uses the dedicated `dataset_visdrone10_yolo/data.yaml` class order: `pedestrian`, `people`, `bicycle`, `car`, `van`, `truck`, `tricycle`, `awning-tricycle`, `bus`, `motor`. The baseline remains the default and its checkpoint is unchanged.
- The ten-class checkpoint currently present in this workspace records epoch 5 of a 100-epoch run (six epochs in its training log); treat it as an available integration artifact, not as evidence of completed training or validated model quality.
- Set `VISDRONE10_MODEL_PATH` to override the ten-class checkpoint path. Relative values are resolved from the project root; the default is `runs/visdrone10_yolo11n/weights/best.pt`.
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

The existing React/Vite frontend is under `src/`. Install Node dependencies with `npm install`, then run `npm run dev` from the project root. The frontend is unchanged by the database setup work.
