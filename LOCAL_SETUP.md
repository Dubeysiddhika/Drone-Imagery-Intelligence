# Cross-platform setup and deployment

AeroVision has a React/Vite frontend at the repository root and a FastAPI backend
under \`backend/\`. The application is designed to run on Windows, macOS and Linux.
Machine-specific paths, API origins, database URLs and research-data locations
should be configured in the root \`.env\`, not hard-coded into source files.

## 1. Requirements

- Git (with Git LFS installed if you intend to fetch LFS-managed training files)
- Python 3.12 or 3.13 recommended
- Node.js 22 LTS and npm
- 8 GB RAM minimum for the web app and CPU detector; more RAM is recommended
  for image processing and localization
- Internet access for package installation and map tiles

CPU inference is supported. GPU inference requires a PyTorch build that matches
the host's CUDA/ROCm hardware and drivers; do not copy a machine-specific GPU
environment to another computer.

## 2. Clone the repository

\`\`\`bash
git clone https://github.com/Dubeysiddhika/Drone-Imagery-Intelligence.git
cd Drone-Imagery-Intelligence
\`\`\`

Use the branch that contains the version you intend to run. The latest themed
UI and portable setup changes are currently in the
\`chore/cross-platform-readiness\` branch until its pull request is merged.

If you need the training checkpoints or data tracked through Git LFS:

\`\`\`bash
git lfs install
git lfs pull
\`\`\`

## 3. Create a Python environment

### Windows PowerShell

\`\`\`powershell
py -3.12 -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
\`\`\`

If PowerShell blocks activation, run this in the current terminal only, then
activate again:

\`\`\`powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\\.venv\\Scripts\\Activate.ps1
\`\`\`

### macOS / Linux

\`\`\`bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
\`\`\`

Install the backend dependencies from the repository root:

\`\`\`bash
python -m pip install -r backend/requirements.txt
python -m pip check
\`\`\`

The backend manifest includes the API, SQL/database, image, YOLO, geospatial,
and test packages imported by the current application. If you require NVIDIA
GPU inference, first install the matching PyTorch and TorchVision builds using
the official PyTorch installation selector for that system, then validate
with \`python -m pip check\`.

Install the frontend dependencies:

\`\`\`bash
npm ci
\`\`\`

## 4. Configure the environment

Copy the example environment file:

**Windows PowerShell**

\`\`\`powershell
Copy-Item .env.example .env
\`\`\`

**macOS / Linux**

\`\`\`bash
cp .env.example .env
\`\`\`

The defaults are for local development. Relative file paths are resolved from
the repository root, not from the current terminal directory. Edit \`.env\`
when paths, ports, database services or browser origins differ on another
machine. Do not commit \`.env\` or place passwords/secrets in source code.

### Database

- Local development uses \`drone.db\` (SQLite) in the repository root if
  \`DATABASE_URL\` is unset.
- A fresh clone creates its own empty local database; your existing SQLite
  records are not contained in Git.
- For shared or production data, configure PostgreSQL with PostGIS and set
  \`DATABASE_URL\` to a \`postgresql+psycopg://...\` URL. Production startup
  verifies that the PostGIS extension is enabled.
- Do not point multiple production instances at a local SQLite file.

### Browser/API addresses

- In local development, Vite proxies \`/api\` to
  \`VITE_API_PROXY_TARGET\` (default \`http://127.0.0.1:8000\`). The browser
  calls the frontend origin, which also keeps cookie authentication same-origin.
- If the frontend and API are hosted separately, set
  \`VITE_API_BASE_URL\` at frontend build time to the API origin, and set
  \`CORS_ORIGINS\` on the backend to the exact frontend origin(s), including
  scheme and port. Credentialed CORS must not use a wildcard.
- Set \`FRONTEND_BASE_URL\` to the public frontend URL if password-reset emails
  are enabled.
- For production, set \`APP_ENV=production\`, configure a unique
  \`JWT_SECRET_KEY\` of at least 32 characters, and use HTTPS.

## 5. Model and research assets

The repository and the local developer machine do not necessarily contain
all model/data assets. These are the current expectations:

| Asset | Needed for | How to configure |
|---|---|---|
| \`backend/app/models/weights/visdrone10_yolo11n_best.pt\` | Ten-class VisDrone detector | Default \`VISDRONE10_MODEL_PATH\` in \`.env.example\` |
| Baseline \`best.pt\` under \`runs/drone_person_vehicle/weights/\` | Two-class baseline detector | Obtain the checkpoint from the project owner/model artifact store and set \`BASELINE_MODEL_PATH\` |
| \`UAV_VisLoc_dataset/\` with flight folders and source CSV files | Matching uploaded images to UAV-VisLoc metadata | Obtain the licensed dataset separately and set \`UAV_VISLOC_DATASET_DIR\` |
| UAV-VisLoc Phase 3C/3H artifacts, including the satellite index | GPS-free/GPS-assisted visual localization | Obtain the generated research artifacts separately and set \`UAV_VISLOC_PHASE3C_DIR\` and \`UAV_VISLOC_PHASE3H_DIR\` |

Do not assume that a Git clone includes ignored datasets, generated satellite
indices, local uploads, or a developer's SQLite database. The UAV-VisLoc
matching/localization features report unavailable when their required assets
are missing; the core upload, metadata and object-detection workflow can still
be used when a valid detector checkpoint is installed.

The ten-class checkpoint path in the example file points to the checkpoint
stored under \`backend/app/models/weights/\`. If you use a different copy, set
\`VISDRONE10_MODEL_PATH\` to its absolute path or a path relative to the
repository root. Verify that model classes match the configured ten-class
registry before using it. The baseline is a separate two-class model and is
not interchangeable with the ten-class checkpoint.

### Import all UAV-VisLoc metadata records

The consolidated metadata CSV can be imported even when the large source image
folders are stored outside the repository. The import is idempotent: rerunning
it updates existing records by flight-relative image path rather than creating
duplicates. It does not move or copy the dataset images.

From the repository root, first run a dry run:

\`\`\`powershell
python training/import_uav_visloc.py
\`\`\`

This validates every CSV row and writes a complete JSON export to
\`backend/training/uav_visloc/phase1_validation/outputs/uav_visloc_metadata_export.json\`.
After reviewing the row counts and export, import the records into the
application database:

\`\`\`powershell
python training/import_uav_visloc.py --commit
\`\`\`

The source CSV defaults to
\`backend/training/uav_visloc/phase1_validation/outputs/consolidated_drone_metadata.csv\`.
When it is stored elsewhere, set \`UAV_VISLOC_CONSOLIDATED_CSV\` in the root
\`.env\`. The optional \`UAV_VISLOC_DATASET_DIR\` points to the original flight
folders and drone images; it is used for exact-image and visual matching, not
as a prerequisite for importing the metadata table.

After import, the UAV-VisLoc Dataset page displays all imported records with
pagination and record details. The importer also retries matching for prior
uploaded images that were previously marked not matched. Matches are only
saved after exact-content or visual verification. Coordinates shown on the
dataset page are dataset ground truth, not EXIF values extracted from the
uploaded JPEG.

## 6. Start the application

Use two terminals from the repository root.

### Backend terminal (all platforms)

\`\`\`bash
# Activate .venv first, then:
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
\`\`\`

To make the backend reachable from another device on the same trusted network,
bind to \`0.0.0.0\` and configure firewall rules and \`CORS_ORIGINS\` carefully.
Do not expose the development server directly to the public internet.

### Frontend terminal (all platforms)

\`\`\`bash
# From the repository root:
npm run dev
\`\`\`

Open the URL printed by Vite. It normally starts at
\`http://localhost:5173\`; if that port is busy Vite may choose another one.
The same-origin API proxy continues to work when Vite selects a different
development port. FastAPI Swagger is available at
\`http://127.0.0.1:8000/docs\`.

## 7. Preflight, tests and production frontend build

From the repository root, with the Python environment activated:

\`\`\`bash
python scripts/check_environment.py
cd backend
python -m unittest discover -s tests -v
cd ..
npm test
npm run type-check
npm run build
npm run lint
\`\`\`

For a production frontend build, set \`VITE_API_BASE_URL\` to the deployed API
origin before running \`npm run build\`. Deploy the generated \`dist/\` directory
to a static web host and run FastAPI separately. Configure the backend CORS
allow-list and \`FRONTEND_BASE_URL\` for the deployed frontend.

The PostGIS integration test is skipped unless
\`TEST_POSTGIS_DATABASE_URL\` points to a dedicated test database. Never point
tests at a database containing user or production data.

## 8. Data persistence and backup

The following are machine-local unless you configure shared persistent storage:

- \`drone.db\` (SQLite database)
- \`backend/uploads/\` (uploaded images and generated previews)
- local model checkpoints not tracked by Git
- ignored research datasets and localization indices

Back up the database and uploaded files together. In a multi-user deployment,
use managed PostgreSQL/PostGIS and persistent object/file storage rather than
ephemeral container disks.

## 9. Common portability issues

- **Model weights not found:** check the configured \`BASELINE_MODEL_PATH\` or
  \`VISDRONE10_MODEL_PATH\`; run \`git lfs pull\` if the checkpoint is LFS-managed.
- **UAV-VisLoc matching returns no match:** verify that
  \`UAV_VISLOC_DATASET_DIR\` points to the folder containing the flight
  subfolders and source CSV files.
- **Localization index unavailable:** the Phase 3C/3H research artifacts are
  separate from the code checkout. Configure their paths and verify the
  satellite index manifest and descriptor file exist.
- **CORS error with a separately hosted frontend:** add the exact frontend
  origin (for example \`https://aerovision.example.com\`) to \`CORS_ORIGINS\`,
  including the scheme and port, then restart the backend.
- **API connection error in local Vite:** check that the backend is running on
  port 8000 or set \`VITE_API_PROXY_TARGET\` to its actual address, then restart
  Vite.
- **PostGIS startup error:** verify the PostgreSQL URL, database credentials,
  network access and \`CREATE EXTENSION postgis\` on that database.
- **Map tiles do not appear:** the map uses online OpenStreetMap tile services
  and needs network access.
