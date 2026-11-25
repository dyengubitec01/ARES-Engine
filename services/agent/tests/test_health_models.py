"""Tests for Story 1.7: Health Check and Model List API."""

from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for GET /health endpoint (AC 1.7.1)."""

    def test_health_returns_200(self, client: TestClient) -> None:
        """Test health endpoint returns 200 status code."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_format(self, client: TestClient) -> None:
        """Test health endpoint returns CommonResponse format."""
        response = client.get("/health")
        data = response.json()

        assert data["code"] == "AGT0000"
        assert data["msg"] == "요청이 성공하였습니다."
        assert "data" in data

    def test_health_data_contains_status(self, client: TestClient) -> None:
        """Test health data contains status field."""
        response = client.get("/health")
        data = response.json()

        assert data["data"]["status"] == "ok"

    def test_health_data_contains_version(self, client: TestClient) -> None:
        """Test health data contains version field."""
        response = client.get("/health")
        data = response.json()

        assert "version" in data["data"]
        assert isinstance(data["data"]["version"], str)

    def test_health_data_contains_timestamp(self, client: TestClient) -> None:
        """Test health data contains timestamp field in ISO format."""
        response = client.get("/health")
        data = response.json()

        assert "timestamp" in data["data"]
        # Verify timestamp is valid ISO format
        timestamp = data["data"]["timestamp"]
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


class TestDeepHealthEndpoint:
    """Tests for GET /health?deep=true endpoint (AC 1.7.2)."""

    def test_deep_health_returns_200(self, client: TestClient) -> None:
        """Test deep health endpoint returns 200."""
        with patch("app.api.v1.health.check_llm_server_health") as mock_check:
            mock_check.return_value = {
                "primary": {"status": "connected", "latency_ms": 45},
                "fallback": {"status": "connected", "latency_ms": 52},
            }
            response = client.get("/health?deep=true")
            assert response.status_code == 200

    def test_deep_health_contains_llm_servers(self, client: TestClient) -> None:
        """Test deep health response contains llm_servers."""
        with patch("app.api.v1.health.check_llm_server_health") as mock_check:
            mock_check.return_value = {
                "primary": {"status": "connected", "latency_ms": 45},
                "fallback": {"status": "connected", "latency_ms": 52},
            }
            response = client.get("/health?deep=true")
            data = response.json()

            assert "llm_servers" in data["data"]

    def test_deep_health_server_status_format(self, client: TestClient) -> None:
        """Test deep health server status format."""
        with patch("app.api.v1.health.check_llm_server_health") as mock_check:
            mock_check.return_value = {
                "primary": {"status": "connected", "latency_ms": 45},
                "fallback": {"status": "connected", "latency_ms": 52},
            }
            response = client.get("/health?deep=true")
            data = response.json()

            llm_servers = data["data"]["llm_servers"]
            assert "primary" in llm_servers
            assert "status" in llm_servers["primary"]
            assert "latency_ms" in llm_servers["primary"]

    def test_deep_health_disconnected_server(self, client: TestClient) -> None:
        """Test deep health with disconnected server."""
        with patch("app.api.v1.health.check_llm_server_health") as mock_check:
            mock_check.return_value = {
                "primary": {"status": "disconnected", "latency_ms": None},
                "fallback": {"status": "connected", "latency_ms": 52},
            }
            response = client.get("/health?deep=true")
            data = response.json()

            assert data["data"]["llm_servers"]["primary"]["status"] == "disconnected"


class TestModelsEndpoint:
    """Tests for GET /v1/models endpoint (AC 1.7.3)."""

    def test_models_returns_200(self, client: TestClient) -> None:
        """Test models endpoint returns 200."""
        response = client.get("/v1/models")
        assert response.status_code == 200

    def test_models_response_format(self, client: TestClient) -> None:
        """Test models endpoint returns CommonResponse format."""
        response = client.get("/v1/models")
        data = response.json()

        assert data["code"] == "AGT0000"
        assert data["msg"] == "요청이 성공하였습니다."
        assert "data" in data

    def test_models_contains_roles_list(self, client: TestClient) -> None:
        """Test models response contains roles list."""
        response = client.get("/v1/models")
        data = response.json()

        assert "roles" in data["data"]
        assert isinstance(data["data"]["roles"], list)

    def test_models_role_format(self, client: TestClient) -> None:
        """Test each role has required fields."""
        response = client.get("/v1/models")
        data = response.json()

        roles = data["data"]["roles"]
        assert len(roles) > 0

        for role in roles:
            assert "role" in role
            assert "model" in role
            assert "server" in role

    def test_models_contains_primary_role(self, client: TestClient) -> None:
        """Test models contains primary role."""
        response = client.get("/v1/models")
        data = response.json()

        roles = data["data"]["roles"]
        role_names = [r["role"] for r in roles]
        assert "primary" in role_names
