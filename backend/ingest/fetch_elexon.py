"""Elexon BMRS API Ingestion CLI for UK Wind Actuals and Forecasts.

Pulls:
- Actuals from FUELHH stream (fuelType == 'WIND')
- Forecasts from WINDFOR stream (horizon between 0 and 48 hours)
Outputs compressed CSV snapshots into data/actuals.csv.gz and data/forecasts.csv.gz.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("elexon_ingest")

# Constants
BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"
FUELHH_ENDPOINT = f"{BASE_URL}/datasets/FUELHH/stream"
WINDFOR_ENDPOINT = f"{BASE_URL}/datasets/WINDFOR/stream"

DECISION_MONTH = "2026-01"
DELIVERY_START_DATE = "2026-01-02"
DELIVERY_END_DATE = "2026-02-01"

DELIVERY_START_UTC = "2026-01-02T00:00:00Z"
DELIVERY_END_UTC = "2026-02-01T23:30:00Z"

FORECAST_PUBLISH_START_UTC = "2025-12-31T00:00:00Z"
FORECAST_PUBLISH_END_UTC = "2026-02-01T00:00:00Z"

HORIZON_MIN_HOURS = 0.0
HORIZON_MAX_HOURS = 48.0

REQUEST_CHUNK_DAYS = 5
MAX_RETRIES = 4
BACKOFF_FACTOR = 1.5


def fetch_with_retry(
    client: httpx.Client,
    url: str,
    params: dict[str, Any],
    max_retries: int = MAX_RETRIES,
) -> list[dict[str, Any]]:
    """Fetch JSON records from an Elexon endpoint with exponential backoff."""
    for attempt in range(1, max_retries + 1):
        try:
            response = client.get(url, params=params, timeout=45.0)
            if response.status_code == 200:
                data = response.json()
                if not isinstance(data, list):
                    raise ValueError(
                        f"Expected JSON array response from {url}, got {type(data).__name__}"
                    )
                return data
            logger.warning(
                "Attempt %d/%d failed with HTTP %d for %s (params=%s): %s",
                attempt,
                max_retries,
                response.status_code,
                url,
                params,
                response.text[:200],
            )
        except (httpx.RequestError, httpx.TimeoutException) as exc:
            logger.warning("Attempt %d/%d network error: %s", attempt, max_retries, exc)

        if attempt < max_retries:
            sleep_sec = BACKOFF_FACTOR**attempt
            time.sleep(sleep_sec)

    raise RuntimeError(f"Failed to fetch from {url} after {max_retries} attempts with {params}")


def parse_fuelhh_records(records: list[dict[str, Any]]) -> pd.DataFrame:
    """Validate and parse raw FUELHH JSON records into a cleaned actuals DataFrame.

    Fails loudly if expected fields are missing.
    Filters fuelType == 'WIND', parses timestamps as UTC, and drops duplicates.
    """
    if not records:
        return pd.DataFrame(columns=["startTime", "generation"])

    required_keys = {"startTime", "fuelType", "generation"}
    first_record = records[0]
    missing_keys = required_keys - set(first_record.keys())
    if missing_keys:
        raise ValueError(
            f"FUELHH schema mismatch! Missing required keys: {missing_keys}. "
            f"Available keys: {list(first_record.keys())}"
        )

    # Filter to WIND fuelType
    wind_records = [
        {"startTime": r["startTime"], "generation": r["generation"]}
        for r in records
        if r.get("fuelType") == "WIND"
    ]

    if not wind_records:
        return pd.DataFrame(columns=["startTime", "generation"])

    df = pd.DataFrame(wind_records)

    # Parse timestamps as UTC ISO string and validate
    df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
    df["generation"] = pd.to_numeric(df["generation"], errors="coerce")

    # Drop duplicate start times
    df = df.drop_duplicates(subset=["startTime"])
    df = df.sort_values(by="startTime").reset_index(drop=True)

    return df[["startTime", "generation"]]


def parse_windfor_records(
    records: list[dict[str, Any]],
    min_horizon: float = HORIZON_MIN_HOURS,
    max_horizon: float = HORIZON_MAX_HOURS,
) -> pd.DataFrame:
    """Validate and parse raw WINDFOR JSON records into a cleaned forecasts DataFrame.

    Fails loudly if expected fields are missing.
    Computes horizon_hours = (startTime - publishTime) in hours.
    Filters to horizon between min_horizon and max_horizon.
    Drops duplicate rows.
    """
    if not records:
        return pd.DataFrame(columns=["startTime", "publishTime", "generation", "horizon_hours"])

    required_keys = {"startTime", "publishTime", "generation"}
    first_record = records[0]
    missing_keys = required_keys - set(first_record.keys())
    if missing_keys:
        raise ValueError(
            f"WINDFOR schema mismatch! Missing required keys: {missing_keys}. "
            f"Available keys: {list(first_record.keys())}"
        )

    df = pd.DataFrame(records)

    # Convert timestamps to UTC
    df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
    df["publishTime"] = pd.to_datetime(df["publishTime"], utc=True)
    df["generation"] = pd.to_numeric(df["generation"], errors="coerce")

    # Compute horizon_hours = (startTime - publishTime) in hours
    df["horizon_hours"] = (df["startTime"] - df["publishTime"]).dt.total_seconds() / 3600.0

    # Filter horizon between 0 and 48 hours
    df = df[(df["horizon_hours"] >= min_horizon) & (df["horizon_hours"] <= max_horizon)]

    # Deduplicate on (startTime, publishTime)
    df = df.drop_duplicates(subset=["startTime", "publishTime"])
    df = df.sort_values(by=["startTime", "publishTime"]).reset_index(drop=True)

    return df[["startTime", "publishTime", "generation", "horizon_hours"]]


def fetch_all_actuals(
    client: httpx.Client,
    start_date: str = DELIVERY_START_DATE,
    end_date: str = DELIVERY_END_DATE,
) -> pd.DataFrame:
    """Fetch wind actuals from FUELHH stream chunked by settlementDate."""
    start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    all_records: list[dict[str, Any]] = []
    curr = start_dt
    logger.info("Fetching FUELHH actuals from %s to %s...", start_date, end_date)

    while curr <= end_dt:
        chunk_end = min(curr + timedelta(days=REQUEST_CHUNK_DAYS - 1), end_dt)
        s_from = curr.strftime("%Y-%m-%d")
        s_to = chunk_end.strftime("%Y-%m-%d")

        params = {
            "settlementDateFrom": s_from,
            "settlementDateTo": s_to,
            "fuelType": "WIND",
        }
        records = fetch_with_retry(client, FUELHH_ENDPOINT, params)
        all_records.extend(records)
        logger.info("  FUELHH [%s -> %s]: received %d records", s_from, s_to, len(records))

        curr = chunk_end + timedelta(days=1)

    df = parse_fuelhh_records(all_records)

    # Filter strictly to delivery window
    window_start = pd.to_datetime(DELIVERY_START_UTC)
    window_end = pd.to_datetime(DELIVERY_END_UTC)
    df = df[(df["startTime"] >= window_start) & (df["startTime"] <= window_end)].reset_index(
        drop=True
    )
    return df


def fetch_all_forecasts(
    client: httpx.Client,
    publish_start_utc: str = FORECAST_PUBLISH_START_UTC,
    publish_end_utc: str = FORECAST_PUBLISH_END_UTC,
) -> pd.DataFrame:
    """Fetch wind forecasts from WINDFOR stream chunked by publishDateTime."""
    start_dt = datetime.fromisoformat(publish_start_utc.replace("Z", "+00:00"))
    end_dt = datetime.fromisoformat(publish_end_utc.replace("Z", "+00:00"))

    all_records: list[dict[str, Any]] = []
    curr = start_dt
    logger.info(
        "Fetching WINDFOR forecasts published from %s to %s...",
        publish_start_utc,
        publish_end_utc,
    )

    while curr < end_dt:
        chunk_end = min(curr + timedelta(days=REQUEST_CHUNK_DAYS), end_dt)
        p_from = curr.strftime("%Y-%m-%dT%H:%M:%SZ")
        p_to = chunk_end.strftime("%Y-%m-%dT%H:%M:%SZ")

        params = {
            "publishDateTimeFrom": p_from,
            "publishDateTimeTo": p_to,
        }
        records = fetch_with_retry(client, WINDFOR_ENDPOINT, params)
        all_records.extend(records)
        logger.info("  WINDFOR [%s -> %s]: received %d records", p_from, p_to, len(records))

        curr = chunk_end

    df = parse_windfor_records(all_records)

    # Watch for & filter out forecasts for startTime outside the target delivery window
    window_start = pd.to_datetime(DELIVERY_START_UTC)
    window_end = pd.to_datetime(DELIVERY_END_UTC)
    df = df[(df["startTime"] >= window_start) & (df["startTime"] <= window_end)].reset_index(
        drop=True
    )
    return df


def calculate_missing_half_hours(
    actual_start_times: pd.Series,
    window_start_utc: str = DELIVERY_START_UTC,
    window_end_utc: str = DELIVERY_END_UTC,
) -> int:
    """Calculate the count of missing half-hour intervals in the expected delivery window."""
    expected_index = pd.date_range(
        start=window_start_utc,
        end=window_end_utc,
        freq="30min",
    )
    present_set = set(actual_start_times)
    missing = [ts for ts in expected_index if ts not in present_set]
    return len(missing)


def print_summary(
    df_actuals: pd.DataFrame,
    df_forecasts: pd.DataFrame,
    actuals_path: Path,
    forecasts_path: Path,
) -> None:
    """Print a clean verification summary for both actuals and forecasts datasets."""
    missing_actuals = calculate_missing_half_hours(df_actuals["startTime"])

    expected_total_half_hours = len(
        pd.date_range(start=DELIVERY_START_UTC, end=DELIVERY_END_UTC, freq="30min")
    )
    forecast_target_half_hours = df_forecasts["startTime"].nunique()
    missing_forecast_targets = expected_total_half_hours - forecast_target_half_hours

    actuals_size_kb = actuals_path.stat().st_size / 1024 if actuals_path.exists() else 0
    forecasts_size_kb = forecasts_path.stat().st_size / 1024 if forecasts_path.exists() else 0
    total_size_mb = (actuals_size_kb + forecasts_size_kb) / 1024

    print("\n" + "=" * 65)
    print("           ELEXON INGESTION SUMMARY: JAN 2026 SCOPE")
    print("=" * 65)
    print(f"Target Delivery Window : {DELIVERY_START_UTC} to {DELIVERY_END_UTC}")
    print(f"Expected Half-Hours    : {expected_total_half_hours} (31 delivery days * 48)")
    print("-" * 65)
    print("1. ACTUALS (FUELHH -> fuelType: WIND):")
    print(f"   - Total Rows        : {len(df_actuals)}")
    print(f"   - Min Start Time    : {df_actuals['startTime'].min()}")
    print(f"   - Max Start Time    : {df_actuals['startTime'].max()}")
    print(f"   - Missing Periods   : {missing_actuals} half-hours")
    print(f"   - File & Size       : {actuals_path.name} ({actuals_size_kb:.1f} KB)")
    print("-" * 65)
    print("2. FORECASTS (WINDFOR -> horizon 0-48h):")
    print(f"   - Total Rows        : {len(df_forecasts)}")
    print(f"   - Min Publish Time  : {df_forecasts['publishTime'].min()}")
    print(f"   - Max Publish Time  : {df_forecasts['publishTime'].max()}")
    print(f"   - Min Start Time    : {df_forecasts['startTime'].min()}")
    print(f"   - Max Start Time    : {df_forecasts['startTime'].max()}")
    print(f"   - Min Horizon Hours : {df_forecasts['horizon_hours'].min():.1f} h")
    print(f"   - Max Horizon Hours : {df_forecasts['horizon_hours'].max():.1f} h")
    print(
        f"   - Target Coverage   : {forecast_target_half_hours}/{expected_total_half_hours} "
        "half-hours covered"
    )
    print(f"   - Missing Targets   : {missing_forecast_targets} half-hours without forecasts")
    print(f"   - File & Size       : {forecasts_path.name} ({forecasts_size_kb:.1f} KB)")
    print("-" * 65)
    print(f"Combined Snapshot Size : {total_size_mb:.2f} MB (< 20 MB budget limit)")
    print("=" * 65 + "\n")


def save_snapshot(df: pd.DataFrame, file_path: Path) -> None:
    """Save a DataFrame as a compressed gzipped CSV."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(file_path, index=False, compression="gzip")
    logger.info("Saved %d rows to %s", len(df), file_path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest UK Wind actuals and forecasts from Elexon BMRS."
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data"),
        help="Directory to save the gzipped CSV snapshots (default: data/)",
    )
    args = parser.parse_args()

    out_dir: Path = args.out_dir
    actuals_path = out_dir / "actuals.csv.gz"
    forecasts_path = out_dir / "forecasts.csv.gz"

    start_time = time.time()
    with httpx.Client(timeout=45.0) as client:
        # 1. Actuals
        df_actuals = fetch_all_actuals(client)
        save_snapshot(df_actuals, actuals_path)

        # 2. Forecasts
        df_forecasts = fetch_all_forecasts(client)
        save_snapshot(df_forecasts, forecasts_path)

    print_summary(df_actuals, df_forecasts, actuals_path, forecasts_path)
    logger.info("Ingestion complete in %.1f seconds.", time.time() - start_time)
    return 0


if __name__ == "__main__":
    sys.exit(main())
