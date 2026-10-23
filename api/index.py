"""Vercel Serverless Function entrypoint for FastAPI backend."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure repository root is on sys.path so 'backend' and 'data' modules are importable
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.api.accuracy import router as accuracy_router  # noqa: E402
from backend.app.api.forecast import router as forecast_router  # noqa: E402
from backend.app.api.health import router as health_router  # noqa: E402
from backend.app.api.meta import router as meta_router  # noqa: E402
from backend.app.main import app as fastapi_app  # noqa: E402

# Mount routers without prefix alongside existing prefix="/api" routes
# so requests routed with or without /api prefix resolve identically.
fastapi_app.include_router(health_router)
fastapi_app.include_router(meta_router)
fastapi_app.include_router(forecast_router)
fastapi_app.include_router(accuracy_router)

# Export 'app' for Vercel's ASGI serverless runner
app = fastapi_app
