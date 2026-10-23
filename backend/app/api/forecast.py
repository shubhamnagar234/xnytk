"""Forecast endpoints: decision-time forecast and historical forecast vintages."""

from __future__ import annotations

import re
import zoneinfo
from datetime import datetime

import pandas as pd
from backend.app import config
from backend.app.analytics.decision import decision_forecast, forecast_vintages, join_actuals
from backend.app.analytics.metrics import summary_metrics
from backend.app.data_loader import get_actuals, get_delivery_days, get_forecasts
from backend.app.models import (
    DaySummary,
    DecisionForecastResponse,
    ForecastVintage,
    HalfHourForecast,
    VintagesResponse,
)
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/forecast", tags=["forecast"])

DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CUTOFF_REGEX = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _validate_date(date_str: str) -> str:
    """Validate date format and presence in available delivery window."""
    if not DATE_REGEX.match(date_str.strip()):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date format '{date_str}'. Expected 'YYYY-MM-DD'.",
        )
    date_clean = date_str.strip()
    available_days = get_delivery_days()
    if available_days and date_clean not in available_days:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Date '{date_clean}' is outside the available delivery window "
                f"({available_days[0]} to {available_days[-1]})."
            ),
        )
    return date_clean


def _validate_cutoff(cutoff_str: str) -> str:
    """Validate cutoff time format."""
    if not CUTOFF_REGEX.match(cutoff_str.strip()):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid cutoff format '{cutoff_str}'. Expected 'HH:MM' (24-hour clock).",
        )
    return cutoff_str.strip()


@router.get("/decision", response_model=DecisionForecastResponse)
def get_decision_forecast(
    date: str = Query(..., description="Target delivery date (YYYY-MM-DD)"),
    cutoff: str = Query(
        "09:00", description="Day-ahead cutoff time in London local time (HH:MM)"
    ),
) -> DecisionForecastResponse:
    """Return the decision-time wind forecast available at cutoff for each half-hour.

    Includes actuals, forecast errors, horizon lead times, and day-level summary statistics.
    """
    valid_date = _validate_date(date)
    valid_cutoff = _validate_cutoff(cutoff)

    # Generate 48 target half-hours for the delivery day in London local time
    tz = zoneinfo.ZoneInfo(config.TIMEZONE)
    local_start = datetime.strptime(valid_date, "%Y-%m-%d").replace(tzinfo=tz)

    local_range = pd.date_range(
        start=local_start,
        periods=48,
        freq="30min",
    )
    targets_utc = local_range.tz_convert(zoneinfo.ZoneInfo("UTC"))

    forecasts = get_forecasts()
    actuals = get_actuals()

    # Calculate decision forecast
    df_decision = decision_forecast(
        forecasts=forecasts,
        actuals_index=targets_utc,
        cutoff_time=valid_cutoff,
        tz=config.TIMEZONE,
    )

    # Join actuals
    df_joined = join_actuals(df_decision, actuals)

    # Day totals and metrics
    fc_non_null = df_joined["forecast_mw"].dropna()
    act_non_null = df_joined["actual_mw"].dropna()

    # Half-hourly generation (MW) to energy (MWh) conversion: MW * 0.5 hours
    forecast_mwh = round(float(fc_non_null.sum() * 0.5), 1) if not fc_non_null.empty else None
    actual_mwh = round(float(act_non_null.sum() * 0.5), 1) if not act_non_null.empty else None

    forecast_peak = round(float(fc_non_null.max()), 1) if not fc_non_null.empty else None
    forecast_min = round(float(fc_non_null.min()), 1) if not fc_non_null.empty else None
    actual_peak = round(float(act_non_null.max()), 1) if not act_non_null.empty else None
    actual_min = round(float(act_non_null.min()), 1) if not act_non_null.empty else None

    metrics = summary_metrics(df_joined)

    day_summary = DaySummary(
        forecast_mwh=forecast_mwh,
        actual_mwh=actual_mwh,
        forecast_peak_mw=forecast_peak,
        forecast_min_mw=forecast_min,
        actual_peak_mw=actual_peak,
        actual_min_mw=actual_min,
        p90_error=metrics.get("p90"),
        mae=metrics.get("mae"),
        bias=metrics.get("bias"),
    )

    # Format intervals
    intervals: list[HalfHourForecast] = []
    for _, row in df_joined.iterrows():
        st = row["startTime"].isoformat()
        pt = row["publishTime"].isoformat() if pd.notna(row["publishTime"]) else None
        fmw = round(float(row["forecast_mw"]), 1) if pd.notna(row["forecast_mw"]) else None
        amw = round(float(row["actual_mw"]), 1) if pd.notna(row["actual_mw"]) else None
        err = round(float(row["error"]), 1) if pd.notna(row["error"]) else None
        h = round(float(row["horizon_hours"]), 1) if pd.notna(row["horizon_hours"]) else None

        intervals.append(
            HalfHourForecast(
                startTime=st,
                publishTime=pt,
                forecast_mw=fmw,
                actual_mw=amw,
                error=err,
                horizon_hours=h,
            )
        )

    return DecisionForecastResponse(
        date=valid_date,
        cutoff=valid_cutoff,
        summary=day_summary,
        intervals=intervals,
    )


@router.get("/vintages", response_model=VintagesResponse)
def get_forecast_vintages(
    date: str = Query(..., description="Target delivery date (YYYY-MM-DD)"),
) -> VintagesResponse:
    """Return all historical forecast revisions published for a given delivery date."""
    valid_date = _validate_date(date)
    forecasts = get_forecasts()

    df_vintages = forecast_vintages(forecasts, target_date=valid_date, tz=config.TIMEZONE)

    records: list[ForecastVintage] = []
    for _, r in df_vintages.iterrows():
        records.append(
            ForecastVintage(
                startTime=r["startTime"].isoformat(),
                publishTime=r["publishTime"].isoformat(),
                forecast_mw=round(float(r["forecast_mw"]), 1),
                horizon_hours=round(float(r["horizon_hours"]), 1),
            )
        )

    return VintagesResponse(
        date=valid_date,
        count=len(records),
        vintages=records,
    )
