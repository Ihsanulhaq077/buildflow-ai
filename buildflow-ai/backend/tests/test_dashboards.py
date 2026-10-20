"""Tests for the dashboards module."""
import pytest
from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Authentication headers for test requests."""
    # In a real test, you'd create a test user and organization
    # For now, we'll mock the authentication
    return {"Authorization": "Bearer test-token"}


def test_create_dashboard(client, auth_headers):
    """Test creating a dashboard."""
    dashboard_data = {
        "name": "Test Dashboard",
        "description": "A test dashboard",
        "dashboard_type": "CUSTOM",
        "is_default": False,
        "is_public": False
    }

    # This would require mocking authentication and organization
    # For now we'll test that the route exists
    response = client.post("/dashboards/", json=dashboard_data, headers=auth_headers)
    # Expect 401/403 due to mock auth, not 404
    assert response.status_code != 404


def test_get_dashboards(client, auth_headers):
    """Test listing dashboards."""
    response = client.get("/dashboards/", headers=auth_headers)
    # Expect 401/403 due to mock auth, not 404
    assert response.status_code != 404


def test_dashboard_data_endpoint(client, auth_headers):
    """Test the dashboard data endpoint."""
    # Test with a fake dashboard ID
    dashboard_id = uuid4()
    response = client.get(f"/dashboards/{dashboard_id}/data", headers=auth_headers)
    # Expect 401/403 due to mock auth, not 404
    assert response.status_code != 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])