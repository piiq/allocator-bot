import pytest
from fastapi.testclient import TestClient
from allocator_bot.api import app

client = TestClient(app)


def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"info": "Asset basket allocator"}


def test_get_agent_description():
    response = client.get("/agents.json")
    assert response.status_code == 200
    assert "vanilla_agent_raw_context" in response.json()


def test_get_allocation_data_no_id():
    response = client.get("/allocation_data")
    assert response.status_code == 200
    assert response.json() == {"error": "Allocation ID is required"}


# More tests would be needed here to cover S3 and local file cases
# but this requires more extensive mocking of the environment
