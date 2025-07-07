import os
import pytest
from httpx import AsyncClient

# Set required environment variables for testing
os.environ["DATA_FOLDER_PATH"] = "/tmp/test"
os.environ["FMP_API_KEY"] = "test_key"
os.environ["OPENROUTER_API_KEY"] = "test_key"
os.environ["AGENT_HOST_URL"] = "http://localhost:8000"
os.environ["APP_API_KEY"] = "test_key"


@pytest.fixture
async def async_client():
    """Provide an async HTTP client for testing FastAPI endpoints."""
    from allocator_bot.__main__ import get_app
    from httpx import ASGITransport

    app = get_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
