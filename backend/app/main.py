from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import auth, images, surveys, analysis, dashboard, uav_visloc, detection, intelligence
from .services.security import get_current_user

from .models.database import (
    Base,
    engine,
    ensure_detection_columns,
    ensure_image_location_column,
    ensure_image_metadata_columns,
    ensure_processing_run_columns,
    verify_postgis,
)



# Create database tables
if engine.dialect.name == "postgresql":
    verify_postgis(engine)
Base.metadata.create_all(bind=engine)
ensure_detection_columns(engine)
ensure_image_location_column(engine)
ensure_image_metadata_columns(engine)
ensure_processing_run_columns(engine)

app = FastAPI(
    title="Drone Imagery Intelligence API",
    description="Backend API for Drone Imagery Intelligence Platform",
    version="1.0.0"
)


# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])


# Root endpoint
@app.get("/")
def root():
    return {
        "project": "Drone Imagery Intelligence Platform",
        "status": "Backend running"
    }


# Health check
@app.get("/api/health")
@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


app.include_router(
    images.router,
    prefix="/api/images",
    tags=["Images"],
    dependencies=[Depends(get_current_user)],
)



app.include_router(
    surveys.router,
    prefix="/api/surveys",
    tags=["Surveys"],
    dependencies=[Depends(get_current_user)],
)


app.include_router(
    analysis.router,
    prefix="/api/analysis",
    tags=["AI Analysis"],
    dependencies=[Depends(get_current_user)],
)


app.include_router(
    dashboard.router,
    prefix="/api/dashboard",
    tags=["Dashboard"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    uav_visloc.router,
    prefix="/api/uav-visloc",
    tags=["UAV-VisLoc Dataset"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(detection.router, prefix="/api/detection", tags=["Detection"], dependencies=[Depends(get_current_user)])
app.include_router(intelligence.router, prefix="/api/intelligence", tags=["Image Intelligence"], dependencies=[Depends(get_current_user)])
