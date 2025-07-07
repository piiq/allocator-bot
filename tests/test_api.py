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
async def test_get_task_data_empty(async_client):
    """Test getting task data when no tasks exist."""
    from unittest.mock import patch

    headers = {"Authorization": "Bearer test_key"}
    with patch("allocator_bot.api.load_tasks", return_value={}):
        response = await async_client.get("/task_data", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert data["tasks"] == []


@pytest.mark.asyncio
async def test_get_task_data_basic(async_client):
    """Test getting basic task data without filters."""
    from unittest.mock import patch

    mock_tasks = {
        "task_1": {
            "timestamp": "2024-01-15T10:30:00",
            "asset_symbols": ["AAPL", "GOOGL"],
            "total_investment": 100000,
            "start_date": "2023-01-01",
            "end_date": "2024-01-01",
            "risk_free_rate": 0.05,
            "target_return": 0.15,
            "target_volatility": 0.20,
        },
        "task_2": {
            "timestamp": "2024-01-10T14:20:00",
            "asset_symbols": ["MSFT", "TSLA"],
            "total_investment": 50000,
            "start_date": "2023-06-01",
            "end_date": "2024-06-01",
            "risk_free_rate": 0.04,
            "target_return": 0.12,
            "target_volatility": 0.18,
        },
    }

    headers = {"Authorization": "Bearer test_key"}
    with patch("allocator_bot.api.load_tasks", return_value=mock_tasks):
        response = await async_client.get("/task_data", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert len(data["tasks"]) == 2

        # Check data formatting
        task = data["tasks"][0]  # Should be sorted by timestamp desc (newest first)
        assert "Task ID" in task
        assert "Timestamp" in task
        assert "Assets" in task
        assert "Investment" in task
        assert task["Investment"] == 100000
        assert task["Assets"] == "AAPL, GOOGL"
        assert task["Risk Free Rate"] == 0.05


@pytest.mark.asyncio
async def test_get_task_data_date_filter(async_client):
    """Test getting task data with date filters."""
    from unittest.mock import patch

    mock_tasks = {
        "task_1": {
            "timestamp": "2024-01-15T10:30:00",
            "asset_symbols": ["AAPL"],
            "total_investment": 100000,
            "start_date": "2023-01-01",
            "end_date": "2024-01-01",
            "risk_free_rate": 0.05,
            "target_return": 0.15,
            "target_volatility": 0.20,
        },
        "task_2": {
            "timestamp": "2024-01-10T14:20:00",
            "asset_symbols": ["MSFT"],
            "total_investment": 50000,
            "start_date": "2023-06-01",
            "end_date": "2024-06-01",
            "risk_free_rate": 0.04,
            "target_return": 0.12,
            "target_volatility": 0.18,
        },
        "task_3": {
            "timestamp": "2024-01-20T09:15:00",
            "asset_symbols": ["GOOGL"],
            "total_investment": 75000,
            "start_date": "2023-01-01",
            "end_date": "2024-01-01",
            "risk_free_rate": 0.05,
            "target_return": 0.15,
            "target_volatility": 0.20,
        },
    }

    headers = {"Authorization": "Bearer test_key"}
    with patch("allocator_bot.api.load_tasks", return_value=mock_tasks):
        # Test start_date filter
        response = await async_client.get(
            "/task_data?start_date=2024-01-12", headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["tasks"]) == 2  # task_1 and task_3

        # Test end_date filter
        response = await async_client.get(
            "/task_data?end_date=2024-01-12", headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["tasks"]) == 1  # only task_2

        # Test date range filter
        response = await async_client.get(
            "/task_data?start_date=2024-01-12&end_date=2024-01-18", headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["tasks"]) == 1  # only task_1


@pytest.mark.asyncio
async def test_get_task_data_symbol_filter(async_client):
    """Test getting task data with symbol search filter."""
    from unittest.mock import patch

    mock_tasks = {
        "task_1": {
            "timestamp": "2024-01-15T10:30:00",
            "asset_symbols": ["AAPL", "GOOGL"],
            "total_investment": 100000,
            "start_date": "2023-01-01",
            "end_date": "2024-01-01",
            "risk_free_rate": 0.05,
            "target_return": 0.15,
            "target_volatility": 0.20,
        },
        "task_2": {
            "timestamp": "2024-01-10T14:20:00",
            "asset_symbols": ["MSFT", "TSLA"],
            "total_investment": 50000,
            "start_date": "2023-06-01",
            "end_date": "2024-06-01",
            "risk_free_rate": 0.04,
            "target_return": 0.12,
            "target_volatility": 0.18,
        },
    }

    headers = {"Authorization": "Bearer test_key"}
    with patch("allocator_bot.api.load_tasks", return_value=mock_tasks):
        # Test partial symbol match (case insensitive)
        response = await async_client.get(
            "/task_data?symbol_search=aapl", headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["tasks"]) == 1
        assert "AAPL" in data["tasks"][0]["Assets"]

        # Test another symbol
        response = await async_client.get(
            "/task_data?symbol_search=MSFT", headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["tasks"]) == 1
        assert "MSFT" in data["tasks"][0]["Assets"]

        # Test partial match
        response = await async_client.get(
            "/task_data?symbol_search=GOO", headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["tasks"]) == 1
        assert "GOOGL" in data["tasks"][0]["Assets"]


@pytest.mark.asyncio
async def test_get_task_data_combined_filters(async_client):
    """Test getting task data with combined filters."""
    from unittest.mock import patch

    mock_tasks = {
        "task_1": {
            "timestamp": "2024-01-15T10:30:00",
            "asset_symbols": ["AAPL", "GOOGL"],
            "total_investment": 100000,
            "start_date": "2023-01-01",
            "end_date": "2024-01-01",
            "risk_free_rate": 0.05,
            "target_return": 0.15,
            "target_volatility": 0.20,
        },
        "task_2": {
            "timestamp": "2024-01-10T14:20:00",
            "asset_symbols": ["AAPL", "MSFT"],
            "total_investment": 50000,
            "start_date": "2023-06-01",
            "end_date": "2024-06-01",
            "risk_free_rate": 0.04,
            "target_return": 0.12,
            "target_volatility": 0.18,
        },
    }

    headers = {"Authorization": "Bearer test_key"}
    with patch("allocator_bot.api.load_tasks", return_value=mock_tasks):
        # Test date and symbol filters combined
        response = await async_client.get(
            "/task_data?start_date=2024-01-12&symbol_search=AAPL", headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["tasks"]) == 1  # Only task_1 matches both filters
        assert "AAPL" in data["tasks"][0]["Assets"]


@pytest.mark.asyncio
async def test_get_task_data_missing_fields(async_client):
    """Test getting task data with missing or None fields."""
    from unittest.mock import patch

    mock_tasks = {
        "task_1": {
            "timestamp": "2024-01-15T10:30:00",
            "asset_symbols": ["AAPL"],
            "total_investment": 100000,
            # Missing some fields
        },
        "task_2": {
            "timestamp": "2024-01-10T14:20:00",
            # Missing asset_symbols
            "total_investment": 50000,
            "start_date": "2023-06-01",
            "end_date": None,  # Explicitly None
            "risk_free_rate": 0.04,
            "target_return": 0.12,
            "target_volatility": 0.18,
        },
    }

    headers = {"Authorization": "Bearer test_key"}
    with patch("allocator_bot.api.load_tasks", return_value=mock_tasks):
        response = await async_client.get("/task_data", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["tasks"]) == 2

        # Check handling of missing fields
        for task in data["tasks"]:
            assert "Task ID" in task
            assert "Timestamp" in task
            assert "Assets" in task
            assert "Investment" in task


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
