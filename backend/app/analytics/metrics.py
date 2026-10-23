"""Quantitative accuracy metrics and breakdown analyses.

Pure pandas/numpy analytics with zero web framework dependencies.
"""

from __future__ import annotations

import zoneinfo
from typing import Any

import numpy as np
import pandas as pd

DEFAULT_HORIZON_BINS = [-1e-6, 6.0, 12.0, 24.0, 36.0, 48.0]
DEFAULT_HORIZON_LABELS = ["0-6h", "6-12h", "12-24h", "24-36h", "36-48h"]


def summary_metrics(df: pd.DataFrame) -> dict[str, Any]:
    """Calculate key forecast accuracy metrics over a DataFrame containing actuals and errors.

    Metrics computed:
      - n: number of valid evaluated half-hours
      - mae: Mean Absolute Error (MW)
      - rmse: Root Mean Square Error (MW)
      - bias: Mean Bias (MW, forecast - actual). Positive = over-forecast.
      - p50: 50th percentile (median) of absolute error (MW)
      - p90: 90th percentile of absolute error (MW)
      - p95: 95th percentile of absolute error (MW)
      - mae_pct_of_mean_actual: MAE as a percentage of mean actual wind power (%).

    Note: MAPE is deliberately excluded because wind generation actuals can be near zero,
    which causes division instability and distorted percentage errors.
    """
    if df.empty or "error" not in df.columns or "actual_mw" not in df.columns:
        return {
            "n": 0,
            "mae": None,
            "rmse": None,
            "bias": None,
            "p50": None,
            "p90": None,
            "p95": None,
            "mae_pct_of_mean_actual": None,
            "mean_actual": None,
        }

    # Drop rows where error or actual is NaN
    valid = df.dropna(subset=["error", "actual_mw"]).copy()
    n = len(valid)

    if n == 0:
        return {
            "n": 0,
            "mae": None,
            "rmse": None,
            "bias": None,
            "p50": None,
            "p90": None,
            "p95": None,
            "mae_pct_of_mean_actual": None,
            "mean_actual": None,
        }

    errors = valid["error"].to_numpy(dtype=float)
    actuals = valid["actual_mw"].to_numpy(dtype=float)
    abs_errors = np.abs(errors)

    mae = float(np.mean(abs_errors))
    rmse = float(np.sqrt(np.mean(errors**2)))
    bias = float(np.mean(errors))

    # Percentiles using pandas/numpy linear quantile
    abs_series = pd.Series(abs_errors)
    p50 = float(abs_series.quantile(0.50))
    p90 = float(abs_series.quantile(0.90))
    p95 = float(abs_series.quantile(0.95))

    mean_actual = float(np.mean(actuals))
    if mean_actual > 0:
        mae_pct = float((mae / mean_actual) * 100.0)
    else:
        mae_pct = None

    return {
        "n": n,
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "bias": round(bias, 2),
        "p50": round(p50, 2),
        "p90": round(p90, 2),
        "p95": round(p95, 2),
        "mae_pct_of_mean_actual": round(mae_pct, 2) if mae_pct is not None else None,
        "mean_actual": round(mean_actual, 2),
    }


def error_by_horizon(
    forecasts: pd.DataFrame,
    actuals: pd.DataFrame,
    bins: list[float] | None = None,
    labels: list[str] | None = None,
) -> pd.DataFrame:
    """Calculate accuracy metrics grouped by forecast horizon bucket using ALL forecast vintages.

    Default buckets: 0-6h, 6-12h, 12-24h, 24-36h, 36-48h.
    Returns DataFrame with:
        bucket, n, mae, rmse, bias, p90
    """
    if bins is None:
        bins = DEFAULT_HORIZON_BINS
    if labels is None:
        labels = DEFAULT_HORIZON_LABELS

    if forecasts.empty or actuals.empty:
        return pd.DataFrame(columns=["bucket", "n", "mae", "rmse", "bias", "p90"])

    fc_df = forecasts.copy()
    act_df = actuals.copy()

    fc_df["startTime"] = pd.to_datetime(fc_df["startTime"], utc=True)
    fc_df["publishTime"] = pd.to_datetime(fc_df["publishTime"], utc=True)
    act_df["startTime"] = pd.to_datetime(act_df["startTime"], utc=True)

    if "forecast_mw" not in fc_df.columns:
        if "generation" in fc_df.columns:
            fc_df["forecast_mw"] = pd.to_numeric(fc_df["generation"], errors="coerce")
        else:
            raise KeyError("Forecasts must contain 'forecast_mw' or 'generation'.")

    if "actual_mw" not in act_df.columns:
        if "generation" in act_df.columns:
            act_df["actual_mw"] = pd.to_numeric(act_df["generation"], errors="coerce")
        else:
            raise KeyError("Actuals must contain 'actual_mw' or 'generation'.")

    if "horizon_hours" not in fc_df.columns:
        fc_df["horizon_hours"] = (
            fc_df["startTime"] - fc_df["publishTime"]
        ).dt.total_seconds() / 3600.0

    # Inner merge to evaluate error on all vintages that have actuals
    merged = pd.merge(
        fc_df[["startTime", "forecast_mw", "horizon_hours"]],
        act_df[["startTime", "actual_mw"]].drop_duplicates(subset=["startTime"]),
        on="startTime",
        how="inner",
    ).dropna(subset=["forecast_mw", "actual_mw", "horizon_hours"])

    if merged.empty:
        return pd.DataFrame(columns=["bucket", "n", "mae", "rmse", "bias", "p90"])

    merged["error"] = merged["forecast_mw"] - merged["actual_mw"]
    merged["bucket"] = pd.cut(merged["horizon_hours"], bins=bins, labels=labels, right=True)

    results: list[dict[str, Any]] = []
    for label in labels:
        subset = merged[merged["bucket"] == label]
        if subset.empty:
            results.append(
                {
                    "bucket": label,
                    "n": 0,
                    "mae": None,
                    "rmse": None,
                    "bias": None,
                    "p90": None,
                }
            )
            continue

        errs = subset["error"].to_numpy(dtype=float)
        abs_errs = np.abs(errs)
        results.append(
            {
                "bucket": label,
                "n": int(len(errs)),
                "mae": round(float(np.mean(abs_errs)), 2),
                "rmse": round(float(np.sqrt(np.mean(errs**2))), 2),
                "bias": round(float(np.mean(errs)), 2),
                "p90": round(float(pd.Series(abs_errs).quantile(0.90)), 2),
            }
        )

    return pd.DataFrame(results)


def error_by_hour_of_day(
    df: pd.DataFrame,
    tz: str = "Europe/London",
) -> pd.DataFrame:
    """Calculate forecast error metrics grouped by hour of the day (0 to 23 in London local time).

    Returns DataFrame with:
        hour, n, mae, rmse, bias, p90, mean_actual
    """
    if df.empty or "startTime" not in df.columns or "error" not in df.columns:
        return pd.DataFrame(columns=["hour", "n", "mae", "rmse", "bias", "p90", "mean_actual"])

    tz_obj = zoneinfo.ZoneInfo(tz)
    valid = df.dropna(subset=["startTime", "error"]).copy()
    valid["startTime"] = pd.to_datetime(valid["startTime"], utc=True)

    # Convert to local London hour
    valid["hour"] = valid["startTime"].dt.tz_convert(tz_obj).dt.hour

    results: list[dict[str, Any]] = []
    for h in range(24):
        subset = valid[valid["hour"] == h]
        if subset.empty:
            results.append(
                {
                    "hour": h,
                    "n": 0,
                    "mae": None,
                    "rmse": None,
                    "bias": None,
                    "p90": None,
                    "mean_actual": None,
                }
            )
            continue

        errs = subset["error"].to_numpy(dtype=float)
        abs_errs = np.abs(errs)
        act_vals = (
            subset["actual_mw"].dropna().to_numpy(dtype=float)
            if "actual_mw" in subset.columns
            else np.array([])
        )

        results.append(
            {
                "hour": h,
                "n": int(len(errs)),
                "mae": round(float(np.mean(abs_errs)), 2),
                "rmse": round(float(np.sqrt(np.mean(errs**2))), 2),
                "bias": round(float(np.mean(errs)), 2),
                "p90": round(float(pd.Series(abs_errs).quantile(0.90)), 2),
                "mean_actual": round(float(np.mean(act_vals)), 2) if len(act_vals) > 0 else None,
            }
        )

    return pd.DataFrame(results)


def error_by_actual_level(
    df: pd.DataFrame,
    n_terciles: int = 3,
) -> pd.DataFrame:
    """Calculate error metrics stratified across actual wind output levels (terciles).

    Returns DataFrame with:
        level, min_mw, max_mw, n, mae, rmse, bias, p90
    """
    labels = ["Low", "Medium", "High"]
    cols = ["level", "min_mw", "max_mw", "n", "mae", "rmse", "bias", "p90"]

    if df.empty or "actual_mw" not in df.columns or "error" not in df.columns:
        return pd.DataFrame(columns=cols)

    valid = df.dropna(subset=["actual_mw", "error"]).copy()
    if len(valid) < n_terciles:
        return pd.DataFrame(columns=cols)

    try:
        valid["tercile"] = pd.qcut(
            valid["actual_mw"], q=n_terciles, labels=labels, duplicates="drop"
        )
    except Exception:
        return pd.DataFrame(columns=cols)

    results: list[dict[str, Any]] = []
    for lbl in labels:
        subset = valid[valid["tercile"] == lbl]
        if subset.empty:
            continue

        errs = subset["error"].to_numpy(dtype=float)
        abs_errs = np.abs(errs)
        actuals = subset["actual_mw"].to_numpy(dtype=float)

        results.append(
            {
                "level": lbl,
                "min_mw": round(float(np.min(actuals)), 1),
                "max_mw": round(float(np.max(actuals)), 1),
                "n": int(len(errs)),
                "mae": round(float(np.mean(abs_errs)), 2),
                "rmse": round(float(np.sqrt(np.mean(errs**2))), 2),
                "bias": round(float(np.mean(errs)), 2),
                "p90": round(float(pd.Series(abs_errs).quantile(0.90)), 2),
            }
        )

    return pd.DataFrame(results)
