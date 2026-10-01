# Drone Imagery Intelligence Platform

FastAPI backend for drone image upload, EXIF/GPS metadata extraction, YOLO object detection, SQLAlchemy persistence, and a React/Vite frontend. PostgreSQL with PostGIS is the intended production database. Development and isolated tests can use SQLite.

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
