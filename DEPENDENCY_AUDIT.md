# Dependency and local-environment audit

## Initial findings

- The backend entry point and requirements are under `backend/`; the
  React/Vite frontend and `package.json` are in the repository root, not in a
  `frontend/` directory.
- The specified `E:\Drone-image-intelligence\.venv-1` exists and runs Python
  3.14.3. FastAPI, Uvicorn, Ultralytics, PyTorch, Pillow, SQLAlchemy, NumPy,
  OpenCV, dotenv, PyYAML, and HTTPX were available. `GeoAlchemy2` and Psycopg,
  both required by the backend model/database layer, were missing. The initial
  `pip check` was clean, illustrating that it does not detect missing
  application imports.
- The backend test suite also needs HTTPX for `fastapi.testclient`. Ultralytics
  attempted to install `pi-heif` during its first real inference; it is now an
  explicit backend dependency to avoid runtime auto-installation.
- No `.env` or process-level `DATABASE_URL` was configured. The application
  defaults to the existing project-root `drone.db` SQLite database.
- No PostgreSQL service or `psql` executable was detected. PostgreSQL/PostGIS
  connectivity is therefore unverified; the PostGIS integration test is
  skipped unless a dedicated test database is configured.
- The frontend dependencies are locked by the root `package-lock.json`. The
  repository had no ESLint configuration even though `npm run lint` is defined.
- The supplied PKL file was not deserialized. Its provenance and inference
  contract remain unverified.

## Changes and verified environment

- Installed the declared backend requirements into `.venv-1` only:
  `GeoAlchemy2 0.21.0`, `psycopg 3.3.8` with its binary extra, and the
  compatible packages already present. Added HTTPX and `pi-heif` to
  `backend/requirements.txt`; recorded the Windows Python 3.14 CPU direct
  dependency pins in `backend/requirements-py314-win-cpu.lock.txt`.
- `python -m pip check` reports no broken requirements. Imports succeed under
  Python 3.14.3, and CPU-only PyTorch 2.14.1 / Torchvision 0.29.1 are installed.
  No Python 3.12 environment was needed: both checkpoints loaded and ran real
  inference successfully.
- Ran `npm ci` from the root. Added `.eslintrc.cjs`. A compatible
  `npm audit fix` removed the production dependency advisories; the production
  audit reports zero vulnerabilities. The full audit still reports 9
  development-dependency advisories (1 moderate, 6 high, 2 critical) whose
  suggested complete fix requires a breaking Vitest major upgrade; no forced
  major upgrade was applied.
- Added `vite.config.ts` with bounded explicit dependency optimization and
  changed `src/main.tsx` to use the documented named React root APIs. The
  browser-rendered frontend and backend-backed dashboard/image analysis were
  verified without JavaScript errors.
- `.env.example` now defaults to development/SQLite and leaves the optional
  PostgreSQL URL commented out, so copying it does not force an unavailable
  database.

## Runtime verification

- Both the `baseline` and `visdrone10_yolo11n` checkpoints were loaded and run
  against `backend/tests/fixtures/0000007_04999_d_0000036.jpg` (1360 × 765).
  The baseline returned four detections; VisDrone10 returned one `car`.
  Class order, confidence ranges, and bounding boxes within source-image pixel
  bounds were checked.
- Uvicorn started on `127.0.0.1:8000` using the default protocol. `/`, both
  health routes, analysis, model metadata, images, dashboard, surveys,
  UAV-VisLoc stats/records, `/docs`, and `/openapi.json` returned HTTP 200.
- A real HTTP upload and VisDrone10 inference were run against an isolated
  temporary SQLite database. Saved detections were retrieved, a repeated
  inference replaced rather than duplicated the rows, dashboard counts
  matched, and frontend-origin CORS succeeded. Smoke-test image/database
  artifacts were removed afterward; the existing project database was not
  used for these writes.
- Backend tests: 35 passed, 1 PostGIS test skipped. Frontend tests: 16 passed.
  TypeScript/production build and ESLint passed.

## Remaining limitations

- Actual PostgreSQL/PostGIS connectivity still requires a locally installed
  PostgreSQL/PostGIS service and credentials. Do not set production mode
  without a valid `DATABASE_URL`.
- The PKL artifact remains intentionally unused pending trusted provenance,
  package/version information, model metadata, and the source's preprocessing
  and inference procedure.
- The full npm audit's remaining advisories are in development dependencies;
  addressing all of them would require a major Vitest upgrade and subsequent
  compatibility review.
