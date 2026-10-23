"""Decision-time forecast selection and actuals alignment.

Pure pandas analytics with zero web or API framework dependencies.
"""

from __future__ import annotations

import zoneinfo
from datetime import date, datetime, timedelta
from typing import Sequence

import numpy as np
import pandas as pd

LONDON_TZ = "Europe/London"


def _parse_cutoff_time(cutoff_time: str) -> tuple[int, int]:
    """Parse HH:MM string into (hour, minute)."""
    try:
        parts = cutoff_time.strip().split(":")
        if len(parts) != 2:
            raise ValueError
        hour, minute = int(parts[0]), int(parts[1])
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
        return hour, minute
    except Exception as exc:
        raise ValueError(
            f"Invalid cutoff_time format '{cutoff_time}'. Expected 'HH:MM' (24-hour clock)."
        ) from exc


def get_decision_cutoff_utc(
    target_dt_utc: pd.Timestamp,
    cutoff_time: str = "09:00",
    tz_str: str = LONDON_TZ,
) -> pd.Timestamp:
    """Calculate the decision cutoff timestamp in UTC for a target delivery timestamp.

    The cutoff occurs on day D-1 at cutoff_time in London local time, then converted to UTC.
    Day D is the local calendar date of the target delivery interval in tz_str.
    """
    tz = zoneinfo.ZoneInfo(tz_str)
    hour, minute = _parse_cutoff_time(cutoff_time)

    # Convert target delivery timestamp to local London time to determine delivery day D
    target_local = target_dt_utc.astimezone(tz)
    local_date_d = target_local.date()

    # Cutoff is on day D-1
    cutoff_date = local_date_d - timedelta(days=1)
    cutoff_local = datetime(
        cutoff_date.year,
        cutoff_date.month,
        cutoff_date.day,
        hour,
        minute,
        tzinfo=tz,
    )

    # Convert to UTC Timestamp
    return pd.Timestamp(cutoff_local).tz_convert(zoneinfo.ZoneInfo("UTC"))


def decision_forecast(
    forecasts: pd.DataFrame,
    actuals_index: pd.DatetimeIndex | pd.Series | Sequence[pd.Timestamp],
    cutoff_time: str = "09:00",
    tz: str = LONDON_TZ,
) -> pd.DataFrame:
    """Select the decision-time forecast for each target half-hour.

    For each target half-hour with London-local date D, select the forecast row with the
    latest publishTime <= (D-1 at cutoff_time, London local, converted to UTC).

    Targets with no eligible forecast are returned as NaN, never filled silently.

    Returns DataFrame with columns:
        startTime, forecast_mw, publishTime, horizon_hours
    """
    # Standardize target index
    if isinstance(actuals_index, (pd.DatetimeIndex, pd.Series)):
        targets_utc = pd.to_datetime(actuals_index, utc=True)
        if isinstance(targets_utc, pd.DatetimeIndex):
            targets_series = targets_utc.to_series()
        else:
            targets_series = targets_utc
    else:
        targets_series = pd.to_datetime(pd.Series(list(actuals_index)), utc=True)

    targets_series = targets_series.drop_duplicates().sort_values().reset_index(drop=True)
    out_base = pd.DataFrame({"startTime": targets_series})

    if forecasts.empty or targets_series.empty:
        out_base["forecast_mw"] = np.nan
        out_base["publishTime"] = pd.NaT
        out_base["horizon_hours"] = np.nan
        return out_base

    fc_df = forecasts.copy()
    fc_df["startTime"] = pd.to_datetime(fc_df["startTime"], utc=True)
    fc_df["publishTime"] = pd.to_datetime(fc_df["publishTime"], utc=True)

    # Standardize column naming
    if "forecast_mw" not in fc_df.columns:
        if "generation" in fc_df.columns:
            fc_df["forecast_mw"] = pd.to_numeric(fc_df["generation"], errors="coerce")
        else:
            raise KeyError("Forecasts DataFrame must contain 'forecast_mw' or 'generation' column.")

    # Compute cutoff map per unique local delivery date D
    tz_obj = zoneinfo.ZoneInfo(tz)
    cutoff_hour, cutoff_min = _parse_cutoff_time(cutoff_time)

    # Precalculate cutoffs for unique delivery dates to optimize performance
    unique_start_times = pd.Series(targets_series.unique())
    local_dates = unique_start_times.dt.tz_convert(tz_obj).dt.date
    unique_local_dates = local_dates.unique()

    cutoff_lookup: dict[date, pd.Timestamp] = {}
    for d in unique_local_dates:
        prev_d = d - timedelta(days=1)
        dt_local = datetime(
            prev_d.year, prev_d.month, prev_d.day, cutoff_hour, cutoff_min, tzinfo=tz_obj
        )
        cutoff_lookup[d] = pd.Timestamp(dt_local).tz_convert(zoneinfo.ZoneInfo("UTC"))

    # Map each target start time to its respective cutoff
    date_to_cutoff_map = dict(zip(unique_start_times, [cutoff_lookup[ld] for ld in local_dates]))

    # Filter forecasts that match target startTimes
    fc_matching = fc_df[fc_df["startTime"].isin(date_to_cutoff_map.keys())].copy()
    if fc_matching.empty:
        out_base["forecast_mw"] = np.nan
        out_base["publishTime"] = pd.NaT
        out_base["horizon_hours"] = np.nan
        return out_base

    fc_matching["cutoff_utc"] = fc_matching["startTime"].map(date_to_cutoff_map)

    # Filter: publishTime <= cutoff_utc
    eligible = fc_matching[fc_matching["publishTime"] <= fc_matching["cutoff_utc"]].copy()

    if eligible.empty:
        out_base["forecast_mw"] = np.nan
        out_base["publishTime"] = pd.NaT
        out_base["horizon_hours"] = np.nan
        return out_base

    # Compute horizon_hours if not already present
    if "horizon_hours" not in eligible.columns:
        eligible["horizon_hours"] = (
            eligible["startTime"] - eligible["publishTime"]
        ).dt.total_seconds() / 3600.0

    # For each startTime, pick the row with latest publishTime
    # Sort by publishTime ascending and take last row per startTime
    eligible_sorted = eligible.sort_values(by=["startTime", "publishTime"])
    latest_per_target = eligible_sorted.groupby("startTime", as_index=False).last()

    selected_cols = ["startTime", "forecast_mw", "publishTime", "horizon_hours"]
    latest_per_target = latest_per_target[selected_cols]

    # Left merge with out_base to ensure missing forecasts propagate as NaN, never filled
    result = pd.merge(out_base, latest_per_target, on="startTime", how="left")
    return result[selected_cols]


def join_actuals(
    decision_df: pd.DataFrame,
    actuals: pd.DataFrame,
) -> pd.DataFrame:
    """Join decision-time forecasts with actual generation and calculate error.

    Error is defined as: error = forecast - actual.
    Positive error means over-forecast (promised more power than delivered),
    representing an under-buying risk for the day-ahead desk.
    """
    df_dec = decision_df.copy()
    df_act = actuals.copy()

    df_dec["startTime"] = pd.to_datetime(df_dec["startTime"], utc=True)
    df_act["startTime"] = pd.to_datetime(df_act["startTime"], utc=True)

    if "actual_mw" not in df_act.columns:
        if "generation" in df_act.columns:
            df_act["actual_mw"] = pd.to_numeric(df_act["generation"], errors="coerce")
        else:
            raise KeyError("Actuals DataFrame must contain 'actual_mw' or 'generation' column.")

    act_subset = df_act[["startTime", "actual_mw"]].drop_duplicates(subset=["startTime"])

    merged = pd.merge(df_dec, act_subset, on="startTime", how="left")
    merged["error"] = merged["forecast_mw"] - merged["actual_mw"]

    return merged


def forecast_vintages(
    forecasts: pd.DataFrame,
    target_date: str | date,
    tz: str = LONDON_TZ,
) -> pd.DataFrame:
    """Return all forecast revisions for a given delivery day in London local time.

    Sorted by target startTime and publishTime.
    """
    if isinstance(target_date, str):
        target_d = datetime.strptime(target_date.strip(), "%Y-%m-%d").date()
    else:
        target_d = target_date

    tz_obj = zoneinfo.ZoneInfo(tz)
    df = forecasts.copy()
    df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
    df["publishTime"] = pd.to_datetime(df["publishTime"], utc=True)

    # Filter to rows where startTime local date equals target_d
    local_start_dates = df["startTime"].dt.tz_convert(tz_obj).dt.date
    vintages = df[local_start_dates == target_d].copy()

    if "forecast_mw" not in vintages.columns:
        if "generation" in vintages.columns:
            vintages["forecast_mw"] = pd.to_numeric(vintages["generation"], errors="coerce")
        else:
            raise KeyError("Forecasts must contain 'forecast_mw' or 'generation' column.")

    if "horizon_hours" not in vintages.columns:
        vintages["horizon_hours"] = (
            vintages["startTime"] - vintages["publishTime"]
        ).dt.total_seconds() / 3600.0

    vintages = vintages.sort_values(by=["startTime", "publishTime"]).reset_index(drop=True)
    return vintages[["startTime", "publishTime", "forecast_mw", "horizon_hours"]]
