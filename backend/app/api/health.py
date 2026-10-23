"""Health check API endpoint."""

from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def get_health() -> dict[str, str]:
    """Health check endpoint to verify service availability."""
    return {
        "status": "ok",
        "service": "wind-forecast-dashboard",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
