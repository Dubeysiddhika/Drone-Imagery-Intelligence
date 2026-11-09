# Local setup (Windows PowerShell)

The backend and frontend are in the repository root layout: the FastAPI
application is in `backend/`, while the React/Vite app and `package.json` are
at the repository root. There is no `frontend/` subdirectory.

## Requirements

- Windows 10/11
- Python 3.14.3 (verified in `.venv-1`; both YOLO checkpoints ran successfully)
- Node.js 22.x and npm 10.x (verified)
- PostgreSQL with PostGIS only if using PostgreSQL; local development can use
  the existing project-root `drone.db` SQLite database.

The supplied `.pkl` artifact is not loaded by the application. Do not deserialize
it without trusted provenance and the source's supported inference instructions.

## Install

From the project root:

```powershell
Set-Location E:\Drone-image-intelligence
.\.venv-1\Scripts\Activate.ps1
python --version
python -m pip install -r backend\requirements-py314-win-cpu.lock.txt
python -m pip check
npm ci
```

The backend requirements include FastAPI, Uvicorn, multipart upload support,
Ultralytics/PyTorch, SQLAlchemy, GeoAlchemy2, Psycopg, Pillow, PyYAML, dotenv,
and HTTPX for API tests. The test suite uses Python's built-in `unittest`.
The pinned file records the versions verified on Windows with Python 3.14.3
and CPU-only PyTorch. For a different operating system or Python version,
install from `backend\requirements.txt` and validate its resolved packages.
`requirements-visdrone10.txt` is a separate training environment specification;
do not install it over the verified inference environment without a deliberate
PyTorch/Ultralytics compatibility check.

To copy the safe local defaults:

```powershell
Copy-Item .env.example .env
```

The default configuration is development mode and uses the project-root
`drone.db` SQLite file. The application preserves existing database records;
do not delete or replace this file. You may also omit `.env` and use the same
development SQLite fallback. The frontend reads `VITE_API_BASE_URL` from the
root `.env`; its default is `http://127.0.0.1:8000`.

### Optional PostgreSQL/PostGIS

No PostgreSQL service or `psql` executable was detected during verification,
so PostgreSQL/PostGIS connectivity could not be tested. Install PostgreSQL and
a matching PostGIS package, create a database, then enable the extension as a
database administrator:

```sql
CREATE DATABASE drone_intelligence;
\c drone_intelligence
CREATE EXTENSION IF NOT EXISTS postgis;
SELECT PostGIS_Full_Version();
```

Set `DATABASE_URL` in `.env` to a valid local URL, for example:

```text
postgresql+psycopg://postgres:<your-password>@localhost:5432/drone_intelligence
```

Use your own local credentials; do not commit them. When `APP_ENV=production`,
`DATABASE_URL` is mandatory and PostgreSQL startup verifies PostGIS. The
optional `TEST_POSTGIS_DATABASE_URL` must point to a dedicated test database;
the integration test creates and removes a uniquely named temporary schema.

## Start the application

Use two PowerShell terminals.

**Backend terminal:**

```powershell
Set-Location E:\Drone-image-intelligence
.\.venv-1\Scripts\Activate.ps1
Set-Location backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

If the default Uvicorn HTTP or WebSocket protocol backend fails to initialize
in your environment, use the verified pure-Python HTTP protocol with WebSockets
disabled:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --http h11 --ws none
```

**Frontend terminal:**

```powershell
Set-Location E:\Drone-image-intelligence
npm run dev
```

Open the frontend URL printed by Vite (normally
`http://localhost:5173`). FastAPI Swagger is at
`http://127.0.0.1:8000/docs`.
After a fresh install or optimizer configuration change, allow Vite's first
dependency prebundle to finish before opening the page.

## Models and API

Both project checkpoints are used in their existing roles:

- `runs/drone_person_vehicle/weights/best.pt` is the default two-class baseline.
- `backend/app/models/weights/visdrone10_yolo11n_best.pt` is selected with
  `model_version=visdrone10_yolo11n`; its classes are listed in
  `backend/app/models/classes.json`.

The VisDrone10 path can be overridden with `VISDRONE10_MODEL_PATH`. A relative
path is resolved from the repository root. The model-information endpoint
is `GET /api/analysis/models`. Upload images through the frontend or
`POST /api/images/upload`; run inference with
`POST /api/analysis/detect/{image_id}?model_version=visdrone10_yolo11n`.
Omit `model_version` or use `baseline` for the existing default model.
Saved results can be retrieved with `GET /api/analysis/detections/{image_id}`.
Bounding boxes are source-image pixel coordinates in `xyxy` order, not GPS
coordinates.

## Test and build

From the repository root:

```powershell
Set-Location E:\Drone-image-intelligence
.\.venv-1\Scripts\Activate.ps1
Set-Location backend
python -m unittest discover -s tests -v
Set-Location ..
npm test
npm run type-check
npm run build
npm run lint
```

The PostGIS integration test is skipped unless
`TEST_POSTGIS_DATABASE_URL` is set. SQLite-backed tests use isolated temporary
databases and do not replace the project's `drone.db`.

## Common Windows issues

- **`No module named app`:** run Uvicorn with the current directory set to
  `backend`, and use `app.main:app` as its import target.
- **Wrong/stale virtual environment:** verify
  `python -c "import sys; print(sys.executable)"` points to
  `E:\Drone-image-intelligence\.venv-1\Scripts\python.exe`.
- **PowerShell blocks activation:** for the current terminal only, run
  `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then activate
  the environment again. Alternatively invoke the environment's
  `python.exe` directly.
- **Missing Python packages:** activate `.venv-1`, install
  `backend\requirements-py314-win-cpu.lock.txt`, and run `python -m pip check`.
- **Port 8000 is occupied:** stop the application already using it or choose
  another backend port and update `VITE_API_BASE_URL` in `.env`.
- **Map tiles do not appear:** the map uses OpenStreetMap tiles and needs
  network access.
- **PostGIS startup error:** use development SQLite locally, or verify that the
  configured database is reachable and has the PostGIS extension enabled.
