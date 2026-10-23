"""Accuracy evaluation endpoints: overall summary, by horizon bucket, and breakdowns."""

from __future__ import annotations

import re
import zoneinfo
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from backend.app import config
from backend.app.analytics.decision import decision_forecast, join_actuals
from backend.app.analytics.metrics import (
    error_by_actual_level,
    error_by_horizon,
    error_by_hour_of_day,
    summary_metrics,
)
from backend.app.data_loader import get_actuals, get_delivery_days, get_forecasts
from backend.app.models import (
    AccuracyBreakdownsResponse,
    AccuracyByHorizonResponse,
    AccuracySummaryResponse,
    HistogramBin,
    HorizonBucket,
    HourOfDayBreakdown,
    WindLevelBreakdown,
)
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/accuracy", tags=["accuracy"])

DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CUTOFF_REGEX = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _resolve_date_range(
    from_date_str: str | None,
    to_date_str: str | None,
) -> tuple[str, str]:
    """Validate and resolve date range against available delivery days."""
    available_days = get_delivery_days()
    if not available_days:
        raise HTTPException(status_code=404, detail="No delivery data available.")

    start_date = from_date_str.strip() if from_date_str else available_days[0]
    end_date = to_date_str.strip() if to_date_str else available_days[-1]

    for d_str, param_name in [(start_date, "from"), (end_date, "to")]:
        if not DATE_REGEX.match(d_str):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date format for '{param_name}': '{d_str}'. Expected 'YYYY-MM-DD'.",
            )

    d_start = datetime.strptime(start_date, "%Y-%m-%d").date()
    d_end = datetime.strptime(end_date, "%Y-%m-%d").date()

    if d_start > d_end:
        raise HTTPException(
            status_code=400,
            detail=f"'from' date ({start_date}) cannot be after 'to' date ({end_date}).",
        )

    min_avail = datetime.strptime(available_days[0], "%Y-%m-%d").date()
    max_avail = datetime.strptime(available_days[-1], "%Y-%m-%d").date()

    if d_end < min_avail or d_start > max_avail:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Requested date range {start_date} to {end_date} is entirely outside "
                f"available delivery window ({available_days[0]} to {available_days[-1]})."
            ),
        )

    return start_date, end_date


def _validate_cutoff(cutoff_str: str) -> str:
    """Validate cutoff time format."""
    if not CUTOFF_REGEX.match(cutoff_str.strip()):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid cutoff format '{cutoff_str}'. Expected 'HH:MM' (24-hour clock).",
        )
    return cutoff_str.strip()


def _get_target_half_hours_for_range(start_date: str, end_date: str) -> pd.DatetimeIndex:
    """Generate all 30-min UTC intervals from start_date 00:00 to end_date 23:30."""
    tz = zoneinfo.ZoneInfo(config.TIMEZONE)
    d_start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=tz)
    d_end = (
        datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=tz)
        + timedelta(days=1)
        - timedelta(minutes=30)
    )

    local_range = pd.date_range(start=d_start, end=d_end, freq="30min")
    return local_range.tz_convert(zoneinfo.ZoneInfo("UTC"))


@router.get("/summary", response_model=AccuracySummaryResponse)
def get_accuracy_summary(
    from_date: str | None = Query(
        None, alias="from", description="Start delivery date (YYYY-MM-DD)"
    ),
    to_date: str | None = Query(
        None, alias="to", description="End delivery date (YYYY-MM-DD)"
    ),
    cutoff: str = Query(
        "09:00", description="Day-ahead cutoff time in London local time (HH:MM)"
    ),
) -> AccuracySummaryResponse:
    """Calculate aggregate forecast accuracy metrics across a specified delivery date range."""
    start_d, end_d = _resolve_date_range(from_date, to_date)
    valid_cutoff = _validate_cutoff(cutoff)

    targets_utc = _get_target_half_hours_for_range(start_d, end_d)
    forecasts = get_forecasts()
    actuals = get_actuals()

    df_dec = decision_forecast(
        forecasts, targets_utc, cutoff_time=valid_cutoff, tz=config.TIMEZONE
    )
    df_joined = join_actuals(df_dec, actuals)
    metrics = summary_metrics(df_joined)

    return AccuracySummaryResponse(
        from_date=start_d,
        to_date=end_d,
        cutoff=valid_cutoff,
        n=metrics["n"],
        mae=metrics["mae"],
        rmse=metrics["rmse"],
        bias=metrics["bias"],
        p50=metrics["p50"],
        p90=metrics["p90"],
        p95=metrics["p95"],
        mae_pct_of_mean_actual=metrics["mae_pct_of_mean_actual"],
        mean_actual=metrics["mean_actual"],
    )


@router.get("/by-horizon", response_model=AccuracyByHorizonResponse)
def get_accuracy_by_horizon(
    from_date: str | None = Query(
        None, alias="from", description="Start delivery date (YYYY-MM-DD)"
    ),
    to_date: str | None = Query(
        None, alias="to", description="End delivery date (YYYY-MM-DD)"
    ),
) -> AccuracyByHorizonResponse:
    """Evaluate forecast accuracy across lead-time horizon buckets using ALL forecast vintages."""
    start_d, end_d = _resolve_date_range(from_date, to_date)
    targets_utc = _get_target_half_hours_for_range(start_d, end_d)

    forecasts = get_forecasts()
    actuals = get_actuals()

    # Filter forecasts and actuals to target range
    fc_filtered = forecasts[forecasts["startTime"].isin(targets_utc)]
    act_filtered = actuals[actuals["startTime"].isin(targets_utc)]

    df_horizon = error_by_horizon(fc_filtered, act_filtered)

    buckets: list[HorizonBucket] = []
    for _, r in df_horizon.iterrows():
        buckets.append(
            HorizonBucket(
                bucket=str(r["bucket"]),
                n=int(r["n"]),
                mae=r["mae"] if pd.notna(r["mae"]) else None,
                rmse=r["rmse"] if pd.notna(r["rmse"]) else None,
                bias=r["bias"] if pd.notna(r["bias"]) else None,
                p90=r["p90"] if pd.notna(r["p90"]) else None,
            )
        )

    return AccuracyByHorizonResponse(
        from_date=start_d,
        to_date=end_d,
        buckets=buckets,
    )


@router.get("/breakdowns", response_model=AccuracyBreakdownsResponse)
def get_accuracy_breakdowns(
    from_date: str | None = Query(
        None, alias="from", description="Start delivery date (YYYY-MM-DD)"
    ),
    to_date: str | None = Query(
        None, alias="to", description="End delivery date (YYYY-MM-DD)"
    ),
    cutoff: str = Query(
        "09:00", description="Day-ahead cutoff time in London local time (HH:MM)"
    ),
) -> AccuracyBreakdownsResponse:
    """Calculate diurnal error patterns, generation-level terciles, and error distribution."""
    start_d, end_d = _resolve_date_range(from_date, to_date)
    valid_cutoff = _validate_cutoff(cutoff)

    targets_utc = _get_target_half_hours_for_range(start_d, end_d)
    forecasts = get_forecasts()
    actuals = get_actuals()

    df_dec = decision_forecast(forecasts, targets_utc, cutoff_time=valid_cutoff, tz=config.TIMEZONE)
    df_joined = join_actuals(df_dec, actuals)

    # 1. Hour of day breakdown
    df_hour = error_by_hour_of_day(df_joined, tz=config.TIMEZONE)
    by_hour: list[HourOfDayBreakdown] = []
    for _, r in df_hour.iterrows():
        by_hour.append(
            HourOfDayBreakdown(
                hour=int(r["hour"]),
                n=int(r["n"]),
                mae=r["mae"] if pd.notna(r["mae"]) else None,
                rmse=r["rmse"] if pd.notna(r["rmse"]) else None,
                bias=r["bias"] if pd.notna(r["bias"]) else None,
                p90=r["p90"] if pd.notna(r["p90"]) else None,
                mean_actual=r["mean_actual"] if pd.notna(r["mean_actual"]) else None,
            )
        )

    # 2. Wind level terciles
    df_level = error_by_actual_level(df_joined, n_terciles=3)
    by_wind_level: list[WindLevelBreakdown] = []
    for _, r in df_level.iterrows():
        by_wind_level.append(
            WindLevelBreakdown(
                level=str(r["level"]),
                min_mw=float(r["min_mw"]),
                max_mw=float(r["max_mw"]),
                n=int(r["n"]),
                mae=r["mae"] if pd.notna(r["mae"]) else None,
                rmse=r["rmse"] if pd.notna(r["rmse"]) else None,
                bias=r["bias"] if pd.notna(r["bias"]) else None,
                p90=r["p90"] if pd.notna(r["p90"]) else None,
            )
        )

    # 3. Error histogram bins
    errors = df_joined["error"].dropna().to_numpy(dtype=float)
    histogram_bins: list[HistogramBin] = []

    if len(errors) > 0:
        counts, edges = np.histogram(errors, bins=12)
        for i in range(len(counts)):
            b_start = round(float(edges[i]), 1)
            b_end = round(float(edges[i + 1]), 1)
            sign_start = "+" if b_start > 0 else ""
            sign_end = "+" if b_end > 0 else ""
            label = f"{sign_start}{int(b_start)} to {sign_end}{int(b_end)} MW"
            histogram_bins.append(
                HistogramBin(
                    bin_start=b_start,
                    bin_end=b_end,
                    bin_label=label,
                    count=int(counts[i]),
                )
            )

    return AccuracyBreakdownsResponse(
        from_date=start_d,
        to_date=end_d,
        cutoff=valid_cutoff,
        by_hour=by_hour,
        by_wind_level=by_wind_level,
        histogram=histogram_bins,
    )
