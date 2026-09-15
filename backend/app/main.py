from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .models.database import Base, engine

from .routes import (
    images,
    surveys,
    analysis,
    dashboard
)


# Create database tables
Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Drone Imagery Intelligence API",
    description="Backend API for Drone Imagery Intelligence Platform",
    version="1.0.0"
)


# Allow React frontend to communicate with FastAPI
app.add_middleware(
    CORSMiddleware,

    allow_origins=[
        "http://localhost:5173"
    ],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"]
)


@app.get("/")
def root():
    return {
        "project": "Drone Imagery Intelligence Platform",
        "status": "Backend running"
    }


@app.get("/api/health")
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