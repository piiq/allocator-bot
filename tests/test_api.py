import pytest


@pytest.mark.asyncio
async def test_read_root(async_client):
    response = await async_client.get("/")
    assert response.status_code == 200
    assert response.json() == {"info": "Asset basket allocator"}


@pytest.mark.asyncio
async def test_get_agent_description(async_client):
    response = await async_client.get("/agents.json")
    assert response.status_code == 200
    assert "allocator_bot" in response.json()


@pytest.mark.asyncio
async def test_get_allocation_data_no_id(async_client):
    headers = {"Authorization": "Bearer test_key"}
    response = await async_client.get("/allocation_data", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"error": "Allocation ID is required"}


@pytest.mark.asyncio
async def test_get_allocation_data_with_id(async_client):
    """Test getting allocation data with a valid ID."""
    from unittest.mock import patch

    mock_allocations = {
        "test_id": [
            {
                "Risk Model": "max_sharpe",
                "Ticker": "AAPL",
                "Weight": 0.6,
                "Quantity": 10,
            },
            {
                "Risk Model": "max_sharpe",
                "Ticker": "GOOGL",
                "Weight": 0.4,
                "Quantity": 5,
            },
            {
                "Risk Model": "min_volatility",
                "Ticker": "AAPL",
                "Weight": 0.5,
                "Quantity": 8,
            },
            {
                "Risk Model": "min_volatility",
                "Ticker": "GOOGL",
                "Weight": 0.5,
                "Quantity": 6,
            },
        ]
    }

    headers = {"Authorization": "Bearer test_key"}
    with patch("allocator_bot.api.load_allocations", return_value=mock_allocations):
        response = await async_client.get(
            "/allocation_data?allocation_id=test_id", headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "allocation" in data
        assert len(data["allocation"]) == 4


@pytest.mark.asyncio
async def test_get_allocation_data_with_risk_model_filter(async_client):
    """Test getting allocation data filtered by risk model."""
    from unittest.mock import patch

    mock_allocations = {
        "test_id": [
            {
                "Risk Model": "max_sharpe",
                "Ticker": "AAPL",
                "Weight": 0.6,
                "Quantity": 10,
            },
            {
                "Risk Model": "max_sharpe",
                "Ticker": "GOOGL",
                "Weight": 0.4,
                "Quantity": 5,
            },
            {
                "Risk Model": "min_volatility",
                "Ticker": "AAPL",
                "Weight": 0.5,
                "Quantity": 8,
            },
            {
                "Risk Model": "min_volatility",
                "Ticker": "GOOGL",
                "Weight": 0.5,
                "Quantity": 6,
            },
        ]
    }

    headers = {"Authorization": "Bearer test_key"}
    with patch("allocator_bot.api.load_allocations", return_value=mock_allocations):
        response = await async_client.get(
            "/allocation_data?allocation_id=test_id&risk_model=max_sharpe",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "allocation" in data
        assert len(data["allocation"]) == 2
        for allocation in data["allocation"]:
            assert allocation["Risk Model"] == "max_sharpe"


@pytest.mark.asyncio
async def test_get_allocation_data_quantities_only(async_client):
    """Test getting allocation data with quantities only (no weights)."""
    from unittest.mock import patch

    mock_allocations = {
        "test_id": [
            {
                "Risk Model": "max_sharpe",
                "Ticker": "AAPL",
                "Weight": 0.6,
                "Quantity": 10,
            },
            {
                "Risk Model": "max_sharpe",
                "Ticker": "GOOGL",
                "Weight": 0.4,
                "Quantity": 5,
            },
        ]
    }

    headers = {"Authorization": "Bearer test_key"}
    with patch("allocator_bot.api.load_allocations", return_value=mock_allocations):
        response = await async_client.get(
            "/allocation_data?allocation_id=test_id&weights_or_quantities=quantities",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "allocation" in data
        for allocation in data["allocation"]:
            assert "Weight" not in allocation
            assert "Quantity" in allocation


@pytest.mark.asyncio
async def test_get_allocation_data_weights_only(async_client):
    """Test getting allocation data with weights only (no quantities)."""
    from unittest.mock import patch

    mock_allocations = {
        "test_id": [
            {
                "Risk Model": "max_sharpe",
                "Ticker": "AAPL",
                "Weight": 0.6,
                "Quantity": 10,
            },
            {
                "Risk Model": "max_sharpe",
                "Ticker": "GOOGL",
                "Weight": 0.4,
                "Quantity": 5,
            },
        ]
    }

    headers = {"Authorization": "Bearer test_key"}
    with patch("allocator_bot.api.load_allocations", return_value=mock_allocations):
        response = await async_client.get(
            "/allocation_data?allocation_id=test_id&weights_or_quantities=weights",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "allocation" in data
        for allocation in data["allocation"]:
            assert "Weight" in allocation
            assert "Quantity" not in allocation


@pytest.mark.asyncio
async def test_get_allocation_data_nonexistent_id(async_client):
    """Test getting allocation data with non-existent ID."""
    from unittest.mock import patch

    headers = {"Authorization": "Bearer test_key"}
    with patch("allocator_bot.api.load_allocations", return_value={}):
        response = await async_client.get(
            "/allocation_data?allocation_id=nonexistent", headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "allocation" in data
        # The default allocation only includes Ticker, Quantity is filtered out in weights mode
        assert len(data["allocation"]) == 1
        assert data["allocation"][0]["Ticker"] == "N/A"


@pytest.mark.asyncio
async def test_query_endpoint(async_client):
    """Test the query endpoint (basic structure test)."""
    from unittest.mock import patch

    from openbb_ai import message_chunk  # type: ignore[import-untyped]

    # Mock the execution_loop to return a simple async generator
    async def mock_execution_loop(request):
        yield message_chunk(text="test response")

    headers = {"Authorization": "Bearer test_key"}
    with patch("allocator_bot.api.execution_loop", side_effect=mock_execution_loop):
        # Use proper QueryRequest format
        request_data = {"messages": [{"role": "human", "content": "test query"}]}
        response = await async_client.post(
            "/v1/query", json=request_data, headers=headers
        )
        assert response.status_code == 200
