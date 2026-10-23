"""API tests using FastAPI TestClient against real snapshot and mock fixture datasets."""

import pandas as pd
import pytest
from backend.app.data_loader import init_datasets, set_custom_datasets
from backend.app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_api_data():
    """Ensure datasets are initialized for API testing."""
    init_datasets()


def test_api_meta_returns_200_and_expected_metadata():
    """Verify /api/meta returns available delivery days and configuration."""
    response = client.get("/api/meta")
    assert response.status_code == 200
    data = response.json()

    assert "delivery_days" in data
    assert len(data["delivery_days"]) == 31  # 2026-01-02 to 2026-02-01
    assert data["delivery_days"][0] == "2026-01-02"
    assert data["delivery_days"][-1] == "2026-02-01"

    assert data["default_cutoff"] == "09:00"
    assert data["timezone"] == "Europe/London"
    assert data["decision_month"] == "2026-01"
    assert data["total_actual_rows"] == 1488
    assert data["total_forecast_rows"] == 11777


def test_api_forecast_decision_returns_valid_day_structure():
    """Verify /api/forecast/decision returns 48 intervals and day summaries."""
    response = client.get("/api/forecast/decision?date=2026-01-15&cutoff=09:00")
    assert response.status_code == 200
    data = response.json()

    assert data["date"] == "2026-01-15"
    assert data["cutoff"] == "09:00"
    assert "summary" in data
    assert "intervals" in data
    assert len(data["intervals"]) == 48

    # Verify summary fields
    summary = data["summary"]
    assert summary["forecast_mwh"] is not None
    assert summary["actual_mwh"] is not None
    assert summary["forecast_peak_mw"] is not None
    assert summary["actual_peak_mw"] is not None
    assert summary["mae"] is not None

    # Spot check target interval 14:00 UTC (matches Phase 3 spot check: 9619 MW, 30.5h horizon)
    target_14h = next(i for i in data["intervals"] if "14:00:00" in i["startTime"])
    assert target_14h["forecast_mw"] == 9619.0
    assert target_14h["horizon_hours"] == 30.5
    assert target_14h["publishTime"] == "2026-01-14T07:30:00+00:00"
    assert target_14h["actual_mw"] is not None
    assert target_14h["error"] is not None


def test_api_forecast_decision_validation_errors():
    """Verify 400 on malformed date/cutoff and 404 on out-of-range date."""
    # Bad date format -> 400
    r_bad_date = client.get("/api/forecast/decision?date=15-01-2026")
    assert r_bad_date.status_code == 400
    assert "Invalid date format" in r_bad_date.json()["detail"]

    # Out of range date -> 404
    r_out_of_range = client.get("/api/forecast/decision?date=2026-03-01")
    assert r_out_of_range.status_code == 404
    assert "outside the available delivery window" in r_out_of_range.json()["detail"]

    # Bad cutoff format -> 400
    r_bad_cutoff = client.get("/api/forecast/decision?date=2026-01-15&cutoff=9:00")
    assert r_bad_cutoff.status_code == 400
    assert "Invalid cutoff format" in r_bad_cutoff.json()["detail"]


def test_api_forecast_vintages_returns_all_revisions():
    """Verify /api/forecast/vintages returns revisions for a delivery day."""
    response = client.get("/api/forecast/vintages?date=2026-01-15")
    assert response.status_code == 200
    data = response.json()

    assert data["date"] == "2026-01-15"
    assert data["count"] > 0
    assert len(data["vintages"]) == data["count"]

    first_vintage = data["vintages"][0]
    assert "startTime" in first_vintage
    assert "publishTime" in first_vintage
    assert "forecast_mw" in first_vintage
    assert "horizon_hours" in first_vintage


def test_api_accuracy_summary_full_range():
    """Verify /api/accuracy/summary computes valid metrics over the month."""
    response = client.get("/api/accuracy/summary?from=2026-01-02&to=2026-02-01&cutoff=09:00")
    assert response.status_code == 200
    data = response.json()

    assert data["from_date"] == "2026-01-02"
    assert data["to_date"] == "2026-02-01"
    assert data["cutoff"] == "09:00"
    assert data["n"] > 0
    assert data["mae"] > 0
    assert data["rmse"] > data["mae"]
    assert data["p90"] is not None
    assert data["mean_actual"] is not None
    assert data["mae_pct_of_mean_actual"] is not None


def test_api_accuracy_summary_date_validation():
    """Verify 400 when from_date is after to_date."""
    response = client.get("/api/accuracy/summary?from=2026-01-20&to=2026-01-10")
    assert response.status_code == 400
    assert "cannot be after" in response.json()["detail"]


def test_api_accuracy_by_horizon():
    """Verify /api/accuracy/by-horizon returns 5 buckets across all vintages."""
    response = client.get("/api/accuracy/by-horizon?from=2026-01-02&to=2026-02-01")
    assert response.status_code == 200
    data = response.json()

    assert "buckets" in data
    assert len(data["buckets"]) == 5
    bucket_labels = [b["bucket"] for b in data["buckets"]]
    assert bucket_labels == ["0-6h", "6-12h", "12-24h", "24-36h", "36-48h"]

    for b in data["buckets"]:
        assert b["n"] > 0
        assert b["mae"] is not None
        assert b["rmse"] is not None
        assert b["bias"] is not None
        assert b["p90"] is not None


def test_api_accuracy_breakdowns():
    """Verify /api/accuracy/breakdowns returns hour-of-day, terciles, and histogram."""
    response = client.get("/api/accuracy/breakdowns?from=2026-01-02&to=2026-02-01&cutoff=09:00")
    assert response.status_code == 200
    data = response.json()

    assert "by_hour" in data
    assert len(data["by_hour"]) == 24
    assert data["by_hour"][0]["hour"] == 0
    assert data["by_hour"][23]["hour"] == 23

    assert "by_wind_level" in data
    assert len(data["by_wind_level"]) == 3
    levels = [lvl["level"] for lvl in data["by_wind_level"]]
    assert levels == ["Low", "Medium", "High"]

    assert "histogram" in data
    assert len(data["histogram"]) > 0
    for h_bin in data["histogram"]:
        assert "bin_start" in h_bin
        assert "bin_end" in h_bin
        assert "bin_label" in h_bin
        assert "count" in h_bin


def test_api_with_tiny_custom_mock_fixture():
    """Verify API works cleanly when isolated with a tiny custom mock fixture dataset."""
    mock_actuals = pd.DataFrame(
        [
            {"startTime": pd.Timestamp("2026-01-10 12:00:00Z"), "actual_mw": 1500.0},
            {"startTime": pd.Timestamp("2026-01-10 12:30:00Z"), "actual_mw": 1600.0},
        ]
    )
    mock_forecasts = pd.DataFrame(
        [
            {
                "startTime": pd.Timestamp("2026-01-10 12:00:00Z"),
                "publishTime": pd.Timestamp("2026-01-09 08:00:00Z"),
                "forecast_mw": 1400.0,
                "horizon_hours": 28.0,
            }
        ]
    )

    try:
        set_custom_datasets(mock_actuals, mock_forecasts)
        res = client.get("/api/meta")
        assert res.status_code == 200
        assert res.json()["delivery_days"] == ["2026-01-10"]

        res_fc = client.get("/api/forecast/decision?date=2026-01-10&cutoff=09:00")
        assert res_fc.status_code == 200
        intervals = res_fc.json()["intervals"]
        # Interval 12:00 has forecast 1400, actual 1500 -> error = -100
        i_12h = next(i for i in intervals if "12:00:00" in i["startTime"])
        assert i_12h["forecast_mw"] == 1400.0
        assert i_12h["actual_mw"] == 1500.0
        assert i_12h["error"] == -100.0
    finally:
        # Restore real datasets
        init_datasets()
