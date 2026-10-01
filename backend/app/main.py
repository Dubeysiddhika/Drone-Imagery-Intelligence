from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .models.database import (
    Base,
    engine,
    ensure_detection_columns,
    ensure_image_location_column,
    verify_postgis,
)
from .routes import images, surveys, analysis, dashboard


# Create database tables
if engine.dialect.name == "postgresql":
    verify_postgis(engine)
Base.metadata.create_all(bind=engine)
ensure_detection_columns(engine)
ensure_image_location_column(engine)

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
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


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
    tags=["Images"]
)


app.include_router(
    surveys.router,
    prefix="/api/surveys",
    tags=["Surveys"]
)


app.include_router(
    analysis.router,
    prefix="/api/analysis",
    tags=["AI Analysis"]
)


app.include_router(
    dashboard.router,
    prefix="/api/dashboard",
    tags=["Dashboard"]
)