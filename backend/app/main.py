"""FastAPI Application entrypoint."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from backend.app.api.accuracy import router as accuracy_router
from backend.app.api.forecast import router as forecast_router
from backend.app.api.health import router as health_router
from backend.app.api.meta import router as meta_router
from backend.app.data_loader import init_datasets
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load data snapshot once into memory on application startup."""
    try:
        init_datasets()
        logger.info("Snapshots successfully loaded into memory at startup.")
    except Exception as exc:
        logger.warning("Could not load snapshot datasets at startup: %s", exc)
    yield


app = FastAPI(
    title="UK Wind Forecast Dashboard API",
    description=(
        "API for day-ahead wind power purchase decision support and forecast accuracy evaluation"
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration for dev
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

# Include all routers under /api
app.include_router(health_router, prefix="/api")
app.include_router(meta_router, prefix="/api")
app.include_router(forecast_router, prefix="/api")
app.include_router(accuracy_router, prefix="/api")


@app.get("/")
def root():
    return {
        "message": "UK Wind Forecast Dashboard API is operational.",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "health": "/api/health",
        "meta": "/api/meta",
    }
