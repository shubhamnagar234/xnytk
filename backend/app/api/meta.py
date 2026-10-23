"""Metadata endpoint."""

from backend.app import config
from backend.app.data_loader import get_actuals, get_delivery_days, get_forecasts
from backend.app.models import DataWindow, MetaResponse
from fastapi import APIRouter

router = APIRouter(tags=["metadata"])


@router.get("/meta", response_model=MetaResponse)
def get_metadata() -> MetaResponse:
    """Return dataset metadata, available delivery days, and default parameters."""
    days = get_delivery_days()
    actuals = get_actuals()
    forecasts = get_forecasts()

    start_str = actuals["startTime"].min().isoformat() if not actuals.empty else ""
    end_str = actuals["startTime"].max().isoformat() if not actuals.empty else ""

    return MetaResponse(
        delivery_days=days,
        data_window=DataWindow(start=start_str, end=end_str),
        default_cutoff=config.DEFAULT_CUTOFF,
        timezone=config.TIMEZONE,
        decision_month=config.DECISION_MONTH,
        total_actual_rows=len(actuals),
        total_forecast_rows=len(forecasts),
    )
