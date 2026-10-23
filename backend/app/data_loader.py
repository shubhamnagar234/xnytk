"""In-memory dataset loader and caching for actuals and forecasts."""

from __future__ import annotations

import logging
import zoneinfo
from pathlib import Path

import pandas as pd
from backend.app.config import ACTUALS_CSV_GZ, FORECASTS_CSV_GZ, TIMEZONE

logger = logging.getLogger("data_loader")

_cached_actuals: pd.DataFrame | None = None
_cached_forecasts: pd.DataFrame | None = None
_cached_delivery_days: list[str] | None = None


def load_actuals(path: Path = ACTUALS_CSV_GZ) -> pd.DataFrame:
    """Load and prepare actual generation DataFrame."""
    if not path.exists():
        raise FileNotFoundError(f"Actuals snapshot file not found at: {path}")

    df = pd.read_csv(path, compression="gzip")
    df["startTime"] = pd.to_datetime(df["startTime"], utc=True)

    if "actual_mw" not in df.columns:
        if "generation" in df.columns:
            df["actual_mw"] = pd.to_numeric(df["generation"], errors="coerce")
        else:
            raise KeyError("Actuals data must contain 'generation' or 'actual_mw' column.")

    df = df.sort_values(by="startTime").reset_index(drop=True)
    return df[["startTime", "actual_mw"]]


def load_forecasts(path: Path = FORECASTS_CSV_GZ) -> pd.DataFrame:
    """Load and prepare forecast DataFrame."""
    if not path.exists():
        raise FileNotFoundError(f"Forecasts snapshot file not found at: {path}")

    df = pd.read_csv(path, compression="gzip")
    df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
    df["publishTime"] = pd.to_datetime(df["publishTime"], utc=True)

    if "forecast_mw" not in df.columns:
        if "generation" in df.columns:
            df["forecast_mw"] = pd.to_numeric(df["generation"], errors="coerce")
        else:
            raise KeyError("Forecasts data must contain 'generation' or 'forecast_mw' column.")

    if "horizon_hours" not in df.columns:
        df["horizon_hours"] = (df["startTime"] - df["publishTime"]).dt.total_seconds() / 3600.0
    else:
        df["horizon_hours"] = pd.to_numeric(df["horizon_hours"], errors="coerce")

    df = df.sort_values(by=["startTime", "publishTime"]).reset_index(drop=True)
    return df[["startTime", "publishTime", "forecast_mw", "horizon_hours"]]


def init_datasets(
    actuals_path: Path = ACTUALS_CSV_GZ,
    forecasts_path: Path = FORECASTS_CSV_GZ,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load both datasets once into memory cache."""
    global _cached_actuals, _cached_forecasts, _cached_delivery_days
    logger.info("Loading actuals from %s...", actuals_path)
    _cached_actuals = load_actuals(actuals_path)

    logger.info("Loading forecasts from %s...", forecasts_path)
    _cached_forecasts = load_forecasts(forecasts_path)

    # Compute available delivery days in London local time
    tz = zoneinfo.ZoneInfo(TIMEZONE)
    local_dates = _cached_actuals["startTime"].dt.tz_convert(tz).dt.strftime("%Y-%m-%d")
    _cached_delivery_days = sorted(local_dates.unique().tolist())

    logger.info(
        "Datasets loaded: %d actuals rows, %d forecasts rows, %d delivery days.",
        len(_cached_actuals),
        len(_cached_forecasts),
        len(_cached_delivery_days),
    )
    return _cached_actuals, _cached_forecasts


def get_actuals() -> pd.DataFrame:
    """Get the cached actuals DataFrame, loading if not already cached."""
    global _cached_actuals
    if _cached_actuals is None:
        init_datasets()
    assert _cached_actuals is not None
    return _cached_actuals


def get_forecasts() -> pd.DataFrame:
    """Get the cached forecasts DataFrame, loading if not already cached."""
    global _cached_forecasts
    if _cached_forecasts is None:
        init_datasets()
    assert _cached_forecasts is not None
    return _cached_forecasts


def get_delivery_days() -> list[str]:
    """Get sorted list of available delivery dates (YYYY-MM-DD)."""
    global _cached_delivery_days
    if _cached_delivery_days is None:
        init_datasets()
    assert _cached_delivery_days is not None
    return _cached_delivery_days


def set_custom_datasets(actuals_df: pd.DataFrame, forecasts_df: pd.DataFrame) -> None:
    """Explicitly set custom in-memory DataFrames (used for isolated unit testing)."""
    global _cached_actuals, _cached_forecasts, _cached_delivery_days
    _cached_actuals = actuals_df.copy()
    _cached_forecasts = forecasts_df.copy()

    tz = zoneinfo.ZoneInfo(TIMEZONE)
    local_dates = _cached_actuals["startTime"].dt.tz_convert(tz).dt.strftime("%Y-%m-%d")
    _cached_delivery_days = sorted(local_dates.unique().tolist())


def clear_cache() -> None:
    """Clear cached datasets."""
    global _cached_actuals, _cached_forecasts, _cached_delivery_days
    _cached_actuals = None
    _cached_forecasts = None
    _cached_delivery_days = None
