"""FastAPI Application entrypoint."""

import os

from backend.app.api.health import router as health_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="UK Wind Forecast Dashboard API",
    description=(
        "API for day-ahead wind power purchase decision support and "
        "forecast accuracy evaluation"
    ),
    version="0.1.0",
)

# CORS configuration
allowed_origins_env = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173",
)
origins = [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes under /api
app.include_router(health_router, prefix="/api")


@app.get("/")
def root():
    return {
        "message": "UK Wind Forecast Dashboard API is running.",
        "docs": "/docs",
        "health": "/api/health",
    }
