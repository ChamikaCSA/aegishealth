"""Smoke tests for health endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_health_returns_200(client: TestClient) -> None:
    """Health endpoint returns 200 OK."""
    response = client.get("/api/health")
    assert response.status_code == 200


def test_health_returns_json(client: TestClient) -> None:
    """Health endpoint returns valid JSON with expected fields."""
    response = client.get("/api/health")
    data = response.json()
    assert "status" in data
    assert "service" in data
    assert data["service"] == "aegishealth-orchestrator"
    assert data["status"] in ("healthy", "degraded")
    assert "orchestrator_ready" in data
    assert "supabase_connected" in data
