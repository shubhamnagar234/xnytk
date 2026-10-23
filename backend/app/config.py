"""Application configuration and constants."""

import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))

ACTUALS_CSV_GZ = DATA_DIR / "actuals.csv.gz"
FORECASTS_CSV_GZ = DATA_DIR / "forecasts.csv.gz"

# Decision-making context
DECISION_MONTH = "2026-01"
DEFAULT_CUTOFF = "09:00"
TIMEZONE = "Europe/London"

DELIVERY_START_DATE = "2026-01-02"
DELIVERY_END_DATE = "2026-02-01"

# CORS
DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"
)
