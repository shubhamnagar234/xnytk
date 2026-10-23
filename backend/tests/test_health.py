"""Trivial test for health check endpoint."""

from backend.app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_check_returns_200_and_ok():
    """Verify that /api/health responds with 200 and status == 'ok'."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "wind-forecast-dashboard"
    assert "timestamp" in data


def test_root_endpoint_returns_200():
    """Verify that root endpoint responds with 200."""
    response = client.get("/")
    assert response.status_code == 200
    assert "docs" in response.json()
