"""Unit tests for analytics core module using hand-built DataFrames."""

import math

import numpy as np
import pandas as pd
import pytest
from backend.app.analytics.decision import (
    decision_forecast,
    forecast_vintages,
    get_decision_cutoff_utc,
    join_actuals,
)
from backend.app.analytics.metrics import (
    error_by_actual_level,
    error_by_horizon,
    error_by_hour_of_day,
    summary_metrics,
)


def test_decision_cutoff_moves_to_d_minus_1_correctly():
    """Verify that cutoff is calculated at D-1 at cutoff_time in London local time.

    Test across day boundary (e.g. delivery date Jan 2 has cutoff Jan 1 09:00 London).
    """
    # Delivery target: 2026-01-02 14:00:00 UTC (London local date = 2026-01-02)
    target = pd.Timestamp("2026-01-02 14:00:00Z")
    cutoff = get_decision_cutoff_utc(target, cutoff_time="09:00", tz_str="Europe/London")

    # Day D-1 is 2026-01-01 at 09:00:00 UTC
    expected_cutoff = pd.Timestamp("2026-01-01 09:00:00Z")
    assert cutoff == expected_cutoff


def test_decision_forecast_picks_latest_pre_cutoff_never_post_cutoff():
    """Verify decision_forecast chooses the latest forecast <= cutoff and never one after."""
    # Target delivery interval: 2026-01-05 12:00:00 UTC
    target_dt = pd.Timestamp("2026-01-05 12:00:00Z")
    # For Jan 5, London cutoff at 09:00 on Jan 4 is 2026-01-04 09:00:00 UTC

    forecast_data = pd.DataFrame(
        [
            # Published well before cutoff
            {
                "startTime": "2026-01-05 12:00:00Z",
                "publishTime": "2026-01-03 18:00:00Z",
                "generation": 1000,
            },
            # Published just before cutoff (SHOULD BE CHOSEN)
            {
                "startTime": "2026-01-05 12:00:00Z",
                "publishTime": "2026-01-04 08:30:00Z",
                "generation": 1500,
            },
            # Published at cutoff exactly (SHOULD BE ELIGIBLE, latest <= cutoff)
            {
                "startTime": "2026-01-05 12:00:00Z",
                "publishTime": "2026-01-04 09:00:00Z",
                "generation": 2000,
            },
            # Published after cutoff (MUST NEVER BE CHOSEN)
            {
                "startTime": "2026-01-05 12:00:00Z",
                "publishTime": "2026-01-04 09:30:00Z",
                "generation": 9999,
            },
            {
                "startTime": "2026-01-05 12:00:00Z",
                "publishTime": "2026-01-05 06:00:00Z",
                "generation": 8888,
            },
        ]
    )

    targets = [target_dt]
    df_result = decision_forecast(forecast_data, targets, cutoff_time="09:00")

    assert len(df_result) == 1
    row = df_result.iloc[0]
    # Expect row with 2026-01-04 09:00:00Z (latest <= 09:00:00)
    assert row["forecast_mw"] == 2000
    assert row["publishTime"] == pd.Timestamp("2026-01-04 09:00:00Z")
    # Horizon should be (Jan 5 12:00 - Jan 4 09:00) = 27 hours
    assert row["horizon_hours"] == 27.0


def test_missing_forecast_and_actual_propagate_as_nan_not_zero():
    """Verify that targets with no eligible forecast or missing actual propagate as NaN, never 0."""
    target_1 = pd.Timestamp("2026-01-05 10:00:00Z")
    target_2 = pd.Timestamp("2026-01-05 10:30:00Z")  # Has NO forecast

    forecast_data = pd.DataFrame(
        [
            {
                "startTime": "2026-01-05 10:00:00Z",
                "publishTime": "2026-01-04 08:00:00Z",
                "generation": 1200,
            }
        ]
    )

    targets = [target_1, target_2]
    df_decision = decision_forecast(forecast_data, targets, cutoff_time="09:00")

    assert len(df_decision) == 2
    row_1 = df_decision.iloc[0]
    row_2 = df_decision.iloc[1]

    assert row_1["forecast_mw"] == 1200
    assert not pd.isna(row_1["forecast_mw"])

    # Target 2 has no forecast -> must be NaN, NOT 0.0
    assert pd.isna(row_2["forecast_mw"])
    assert pd.isna(row_2["publishTime"])
    assert pd.isna(row_2["horizon_hours"])
    assert row_2["forecast_mw"] != 0.0

    # Test joining with actuals
    actual_data = pd.DataFrame(
        [
            {"startTime": "2026-01-05 10:00:00Z", "generation": 1000},
            # Target 2 missing actual as well
        ]
    )

    merged = join_actuals(df_decision, actual_data)
    assert len(merged) == 2

    # Row 1: 1200 - 1000 = +200 error
    assert merged.iloc[0]["actual_mw"] == 1000
    assert merged.iloc[0]["error"] == 200.0

    # Row 2: NaN - NaN = NaN error (never 0)
    assert pd.isna(merged.iloc[1]["actual_mw"])
    assert pd.isna(merged.iloc[1]["error"])
    assert merged.iloc[1]["error"] != 0.0


def test_summary_metrics_match_hand_computed_4_row_example():
    """Verify all summary metrics match hand-computed values exactly on a 4-row dataset.

    Example setup:
      Row 1: actual = 100, forecast = 120 -> error = +20
      Row 2: actual = 200, forecast = 180 -> error = -20
      Row 3: actual = 150, forecast = 180 -> error = +30
      Row 4: actual =  50, forecast =  40 -> error = -10

    Hand calculations:
      - n = 4
      - Errors = [20, -20, 30, -10]
      - Abs Errors = [20, 20, 30, 10]
      - MAE = (20 + 20 + 30 + 10) / 4 = 80 / 4 = 20.0
      - Squared errors = [400, 400, 900, 100] -> Mean = 1800 / 4 = 450.0
      - RMSE = sqrt(450) = 21.213203... -> 21.21
      - Mean Bias = (20 - 20 + 30 - 10) / 4 = 20 / 4 = 5.0
      - Sorted Abs Errors = [10, 20, 20, 30]
        - P50 (median) = 20.0
        - P90 = 20 + 0.7 * (30 - 20) = 27.0
        - P95 = 20 + 0.85 * (30 - 20) = 28.5
      - Mean Actual = (100 + 200 + 150 + 50) / 4 = 500 / 4 = 125.0
      - MAE % of Mean Actual = (20.0 / 125.0) * 100 = 16.0%
    """
    df = pd.DataFrame(
        {
            "actual_mw": [
                100.0,
                200.0,
                150.0,
                50.0,
                np.nan,
            ],  # includes a NaN row to test robustness
            "forecast_mw": [120.0, 180.0, 180.0, 40.0, 100.0],
        }
    )
    df["error"] = df["forecast_mw"] - df["actual_mw"]

    metrics = summary_metrics(df)

    assert metrics["n"] == 4
    assert metrics["mae"] == 20.0
    assert metrics["bias"] == 5.0
    assert metrics["rmse"] == round(math.sqrt(450.0), 2)  # 21.21
    assert metrics["p50"] == 20.0
    assert metrics["p90"] == 27.0
    assert metrics["p95"] == 28.5
    assert metrics["mean_actual"] == 125.0
    assert metrics["mae_pct_of_mean_actual"] == 16.0


def test_error_by_horizon_buckets():
    """Verify error_by_horizon bins all vintages into the 5 specified buckets."""
    # Build 5 forecasts across different horizon buckets:
    # 0-6h: 4h
    # 6-12h: 8h
    # 12-24h: 18h
    # 24-36h: 30h
    # 36-48h: 42h
    target_base = pd.Timestamp("2026-01-05 12:00:00Z")

    forecasts = pd.DataFrame(
        [
            {
                "startTime": target_base,
                "publishTime": target_base - pd.Timedelta(hours=4),
                "generation": 1100,
            },
            {
                "startTime": target_base,
                "publishTime": target_base - pd.Timedelta(hours=8),
                "generation": 1200,
            },
            {
                "startTime": target_base,
                "publishTime": target_base - pd.Timedelta(hours=18),
                "generation": 1300,
            },
            {
                "startTime": target_base,
                "publishTime": target_base - pd.Timedelta(hours=30),
                "generation": 1400,
            },
            {
                "startTime": target_base,
                "publishTime": target_base - pd.Timedelta(hours=42),
                "generation": 1500,
            },
        ]
    )

    actuals = pd.DataFrame([{"startTime": target_base, "generation": 1000}])

    df_horizons = error_by_horizon(forecasts, actuals)

    assert len(df_horizons) == 5
    assert list(df_horizons["bucket"]) == ["0-6h", "6-12h", "12-24h", "24-36h", "36-48h"]

    # In 0-6h bucket: forecast=1100, actual=1000 -> error=+100
    assert df_horizons.loc[df_horizons["bucket"] == "0-6h", "n"].values[0] == 1
    assert df_horizons.loc[df_horizons["bucket"] == "0-6h", "mae"].values[0] == 100.0

    # In 36-48h bucket: forecast=1500, actual=1000 -> error=+500
    assert df_horizons.loc[df_horizons["bucket"] == "36-48h", "n"].values[0] == 1
    assert df_horizons.loc[df_horizons["bucket"] == "36-48h", "mae"].values[0] == 500.0


def test_error_by_hour_of_day():
    """Verify grouping by London local hour of day (0..23)."""
    df = pd.DataFrame(
        [
            {
                "startTime": pd.Timestamp("2026-01-05 08:00:00Z"),
                "actual_mw": 1000.0,
                "forecast_mw": 1200.0,
                "error": 200.0,
            },
            {
                "startTime": pd.Timestamp("2026-01-05 08:30:00Z"),
                "actual_mw": 1000.0,
                "forecast_mw": 900.0,
                "error": -100.0,
            },
        ]
    )
    df_hours = error_by_hour_of_day(df)
    assert len(df_hours) == 24

    hour_8 = df_hours[df_hours["hour"] == 8].iloc[0]
    assert hour_8["n"] == 2
    assert hour_8["mae"] == 150.0  # (|200| + |-100|) / 2 = 150.0
    assert hour_8["bias"] == 50.0  # (200 + (-100)) / 2 = 50.0


def test_error_by_actual_level_terciles():
    """Verify error breakdown across actual generation terciles (Low, Medium, High)."""
    df = pd.DataFrame(
        {
            "actual_mw": [10.0, 20.0, 50.0, 60.0, 90.0, 100.0],
            "error": [2.0, 4.0, 5.0, 6.0, 10.0, 12.0],
        }
    )
    df_terciles = error_by_actual_level(df, n_terciles=3)

    assert len(df_terciles) == 3
    assert list(df_terciles["level"]) == ["Low", "Medium", "High"]
    assert (df_terciles["n"] == 2).all()


def test_forecast_vintages_for_delivery_day():
    """Verify all revisions for a single target delivery day are returned in order."""
    forecasts = pd.DataFrame(
        [
            # Target day Jan 5
            {
                "startTime": "2026-01-05 00:00:00Z",
                "publishTime": "2026-01-04 06:00:00Z",
                "generation": 1000,
            },
            {
                "startTime": "2026-01-05 00:00:00Z",
                "publishTime": "2026-01-04 12:00:00Z",
                "generation": 1100,
            },
            {
                "startTime": "2026-01-05 01:00:00Z",
                "publishTime": "2026-01-04 12:00:00Z",
                "generation": 1200,
            },
            # Different delivery day Jan 6 (should NOT be included)
            {
                "startTime": "2026-01-06 00:00:00Z",
                "publishTime": "2026-01-05 12:00:00Z",
                "generation": 1300,
            },
        ]
    )

    vintages = forecast_vintages(forecasts, target_date="2026-01-05")
    assert len(vintages) == 3
    assert list(vintages.columns) == ["startTime", "publishTime", "forecast_mw", "horizon_hours"]
    assert (vintages["startTime"].dt.date == pd.to_datetime("2026-01-05").date()).all()


def test_real_snapshot_spot_check_matches_manual_filter():
    """Spot check against the real January 2026 snapshot on delivery day 2026-01-15 14:00."""
    from pathlib import Path

    snapshot_path = Path("data/forecasts.csv.gz")
    if not snapshot_path.exists():
        pytest.skip("data/forecasts.csv.gz not present")

    forecasts = pd.read_csv(snapshot_path)
    target_hh = pd.Timestamp("2026-01-15 14:00:00Z")
    cutoff = pd.Timestamp("2026-01-14 09:00:00Z")

    # Manual direct filter
    matching = forecasts[pd.to_datetime(forecasts["startTime"], utc=True) == target_hh].sort_values(
        "publishTime"
    )
    eligible = matching[pd.to_datetime(matching["publishTime"], utc=True) <= cutoff]
    manual_latest = eligible.iloc[-1]

    # Function call
    df_dec = decision_forecast(forecasts, [target_hh], cutoff_time="09:00")
    func_row = df_dec.iloc[0]

    assert func_row["forecast_mw"] == manual_latest["generation"]
    assert func_row["publishTime"] == pd.Timestamp(manual_latest["publishTime"])
    assert func_row["horizon_hours"] == manual_latest["horizon_hours"]
