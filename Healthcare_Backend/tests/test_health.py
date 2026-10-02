"""
tests/test_health.py

pytest tests for the GET /health endpoint.

Uses FastAPI's built-in TestClient (backed by httpx) — no running
server required. Tests are intentionally kept simple for Phase 1.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestHealthEndpoint:
    """Test suite for GET /health."""

    def test_health_returns_200(self):
        """Health endpoint must respond with HTTP 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_json(self):
        """Response Content-Type must be application/json."""
        response = client.get("/health")
        assert "application/json" in response.headers["content-type"]

    def test_health_status_field(self):
        """Response body must contain status == 'healthy'."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_service_field(self):
        """Response body must contain the correct service name."""
        response = client.get("/health")
        data = response.json()
        assert data["service"] == "Healthcare Monitoring Assistant"

    def test_health_response_shape(self):
        """Response body must contain exactly the expected keys."""
        response = client.get("/health")
        data = response.json()
        assert set(data.keys()) == {"status", "service"}

    def test_health_no_extra_fields(self):
        """Ensure the response is not leaking unexpected fields."""
        response = client.get("/health")
        data = response.json()
        # Only status and service should be present
        for key in data:
            assert key in ("status", "service")
