"""Pydantic request and response models for the API."""

from __future__ import annotations

from pydantic import BaseModel


# Meta
class DataWindow(BaseModel):
    start: str
    end: str


class MetaResponse(BaseModel):
    delivery_days: list[str]
    data_window: DataWindow
    default_cutoff: str
    timezone: str
    decision_month: str
    total_actual_rows: int
    total_forecast_rows: int


# Decision Forecast
class HalfHourForecast(BaseModel):
    startTime: str
    publishTime: str | None = None
    forecast_mw: float | None = None
    actual_mw: float | None = None
    error: float | None = None
    horizon_hours: float | None = None


class DaySummary(BaseModel):
    forecast_mwh: float | None = None
    actual_mwh: float | None = None
    forecast_peak_mw: float | None = None
    forecast_min_mw: float | None = None
    actual_peak_mw: float | None = None
    actual_min_mw: float | None = None
    p90_error: float | None = None
    mae: float | None = None
    bias: float | None = None


class DecisionForecastResponse(BaseModel):
    date: str
    cutoff: str
    summary: DaySummary
    intervals: list[HalfHourForecast]


# Vintages
class ForecastVintage(BaseModel):
    startTime: str
    publishTime: str
    forecast_mw: float
    horizon_hours: float


class VintagesResponse(BaseModel):
    date: str
    count: int
    vintages: list[ForecastVintage]


# Accuracy Summary
class AccuracySummaryResponse(BaseModel):
    from_date: str
    to_date: str
    cutoff: str
    n: int
    mae: float | None = None
    rmse: float | None = None
    bias: float | None = None
    p50: float | None = None
    p90: float | None = None
    p95: float | None = None
    mae_pct_of_mean_actual: float | None = None
    mean_actual: float | None = None


# Accuracy By Horizon
class HorizonBucket(BaseModel):
    bucket: str
    n: int
    mae: float | None = None
    rmse: float | None = None
    bias: float | None = None
    p90: float | None = None


class AccuracyByHorizonResponse(BaseModel):
    from_date: str
    to_date: str
    buckets: list[HorizonBucket]


# Accuracy Breakdowns
class HourOfDayBreakdown(BaseModel):
    hour: int
    n: int
    mae: float | None = None
    rmse: float | None = None
    bias: float | None = None
    p90: float | None = None
    mean_actual: float | None = None


class WindLevelBreakdown(BaseModel):
    level: str
    min_mw: float
    max_mw: float
    n: int
    mae: float | None = None
    rmse: float | None = None
    bias: float | None = None
    p90: float | None = None


class HistogramBin(BaseModel):
    bin_start: float
    bin_end: float
    bin_label: str
    count: int


class AccuracyBreakdownsResponse(BaseModel):
    from_date: str
    to_date: str
    cutoff: str
    by_hour: list[HourOfDayBreakdown]
    by_wind_level: list[WindLevelBreakdown]
    histogram: list[HistogramBin]
