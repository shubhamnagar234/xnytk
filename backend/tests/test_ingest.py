"""Unit tests for Elexon data ingestion and parsers (offline fixtures only)."""

import json
from pathlib import Path

import pandas as pd
import pytest
from backend.ingest.fetch_elexon import (
    HORIZON_MAX_HOURS,
    HORIZON_MIN_HOURS,
    calculate_missing_half_hours,
    parse_fuelhh_records,
    parse_windfor_records,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fuelhh_fixture() -> list[dict]:
    with open(FIXTURES_DIR / "fuelhh_sample.json") as f:
        return json.load(f)


@pytest.fixture
def windfor_fixture() -> list[dict]:
    with open(FIXTURES_DIR / "windfor_sample.json") as f:
        return json.load(f)


def test_parse_fuelhh_records_structure_and_types(fuelhh_fixture):
    """Test FUELHH parser on real saved sample."""
    df = parse_fuelhh_records(fuelhh_fixture)

    assert not df.empty
    assert list(df.columns) == ["startTime", "generation"]
    assert pd.api.types.is_datetime64_any_dtype(df["startTime"])
    assert str(df["startTime"].dt.tz) == "UTC"
    assert pd.api.types.is_numeric_dtype(df["generation"])

    # Verify no duplicates
    assert df["startTime"].is_monotonic_increasing
    assert len(df) == df["startTime"].nunique()


def test_parse_fuelhh_schema_mismatch_raises_error():
    """Verify parser fails loudly if required keys are missing."""
    invalid_records = [
        {"dataset": "FUELHH", "startTime": "2026-01-02T00:00:00Z"}  # missing fuelType, generation
    ]
    with pytest.raises(ValueError, match="FUELHH schema mismatch"):
        parse_fuelhh_records(invalid_records)


def test_parse_fuelhh_filters_non_wind():
    """Verify non-wind fuelTypes are discarded."""
    mixed_records = [
        {
            "dataset": "FUELHH",
            "startTime": "2026-01-02T00:00:00Z",
            "fuelType": "BIOMASS",
            "generation": 1000,
        },
        {
            "dataset": "FUELHH",
            "startTime": "2026-01-02T00:00:00Z",
            "fuelType": "WIND",
            "generation": 5000,
        },
    ]
    df = parse_fuelhh_records(mixed_records)
    assert len(df) == 1
    assert df.iloc[0]["generation"] == 5000


def test_parse_windfor_records_structure_and_horizon(windfor_fixture):
    """Test WINDFOR parser computes horizon and filters to 0-48h window."""
    df = parse_windfor_records(windfor_fixture)

    assert not df.empty
    assert list(df.columns) == ["startTime", "publishTime", "generation", "horizon_hours"]
    assert pd.api.types.is_datetime64_any_dtype(df["startTime"])
    assert pd.api.types.is_datetime64_any_dtype(df["publishTime"])
    assert str(df["startTime"].dt.tz) == "UTC"
    assert str(df["publishTime"].dt.tz) == "UTC"

    # Verify horizon constraints
    assert (df["horizon_hours"] >= HORIZON_MIN_HOURS).all()
    assert (df["horizon_hours"] <= HORIZON_MAX_HOURS).all()

    # Verify calculation: horizon_hours = (startTime - publishTime) in hours
    expected_horizon = (df["startTime"] - df["publishTime"]).dt.total_seconds() / 3600.0
    pd.testing.assert_series_equal(
        df["horizon_hours"].round(4),
        expected_horizon.round(4),
        check_names=False,
    )


def test_parse_windfor_schema_mismatch_raises_error():
    """Verify parser fails loudly if WINDFOR expected fields are absent."""
    invalid_records = [
        {
            "dataset": "WINDFOR",
            "publishTime": "2026-01-01T00:00:00Z",
        }  # missing startTime, generation
    ]
    with pytest.raises(ValueError, match="WINDFOR schema mismatch"):
        parse_windfor_records(invalid_records)


def test_parse_windfor_filters_out_of_range_horizons():
    """Verify negative horizons and horizons > 48h are dropped."""
    records = [
        # Horizon = -2h (publishTime after startTime)
        {
            "dataset": "WINDFOR",
            "startTime": "2026-01-02T10:00:00Z",
            "publishTime": "2026-01-02T12:00:00Z",
            "generation": 3000,
        },
        # Horizon = 24h (valid)
        {
            "dataset": "WINDFOR",
            "startTime": "2026-01-02T10:00:00Z",
            "publishTime": "2026-01-01T10:00:00Z",
            "generation": 4000,
        },
        # Horizon = 52h (exceeds 48h limit)
        {
            "dataset": "WINDFOR",
            "startTime": "2026-01-04T10:00:00Z",
            "publishTime": "2026-01-02T06:00:00Z",
            "generation": 5000,
        },
    ]
    df = parse_windfor_records(records)
    assert len(df) == 1
    assert df.iloc[0]["generation"] == 4000
    assert df.iloc[0]["horizon_hours"] == 24.0


def test_calculate_missing_half_hours():
    """Verify accurate counting of missing periods."""
    full_range = pd.date_range(
        start="2026-01-02T00:00:00Z", end="2026-01-02T02:00:00Z", freq="30min"
    )
    assert (
        calculate_missing_half_hours(full_range, "2026-01-02T00:00:00Z", "2026-01-02T02:00:00Z")
        == 0
    )

    # Drop one timestamp
    partial_range = full_range.drop(full_range[1])
    assert (
        calculate_missing_half_hours(partial_range, "2026-01-02T00:00:00Z", "2026-01-02T02:00:00Z")
        == 1
    )
