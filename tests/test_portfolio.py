from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd

from allocator_bot.portfolio import (
    calculate_quantities,
    fetch_historical_prices,
    optimize_portfolio,
    prepare_allocation,
)
from allocator_bot.storage import save_allocation


async def test_fetch_historical_prices():
    # Mock data that FMPEquityHistoricalFetcher would return
    mock_price_obj_1 = MagicMock()
    mock_price_obj_1.model_dump.return_value = {
        "symbol": "AAPL",
        "date": "2023-01-01",
        "adj_close": 150.0,
    }
    mock_price_obj_2 = MagicMock()
    mock_price_obj_2.model_dump.return_value = {
        "symbol": "GOOG",
        "date": "2023-01-01",
        "adj_close": 2800.0,
    }
    mock_price_data = [mock_price_obj_1, mock_price_obj_2]

    with patch(
        "allocator_bot.portfolio.FMPEquityHistoricalFetcher.fetch_data",
        return_value=mock_price_data,
    ):
        prices = await fetch_historical_prices(["AAPL", "GOOG"])
        assert not prices.empty
        assert list(prices.columns) == ["symbol", "date", "adj_close"]
        assert len(prices) == 2


async def test_optimize_portfolio():
    data = {
        "date": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]),
        "AAPL": [150, 152, 151],
        "GOOG": [2800, 2810, 2805],
    }
    prices = pd.DataFrame(data).set_index("date")
    results, failures = await optimize_portfolio(prices, 0.02, 0.1, 0.2)
    assert "max_sharpe" in results
    assert "min_volatility" in results
    assert "efficient_risk" in results
    assert "efficient_return" in results


async def test_optimize_portfolio_resilience():
    """Test that optimize_portfolio handles infeasible constraints gracefully."""
    data = {
        "date": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]),
        "AAPL": [150, 152, 151],
        "GOOG": [2800, 2810, 2805],
    }
    prices = pd.DataFrame(data).set_index("date")

    # Test with infeasible constraints
    results, failures = await optimize_portfolio(
        prices, 0.02, 5.0, 5.0
    )  # Very high target return and volatility

    # Should still return results dict
    assert isinstance(results, dict)
    assert "max_sharpe" in results
    assert "min_volatility" in results

    # Some models may fail and return strings, others may succeed or auto-adjust
    successful_models = [k for k, v in results.items() if isinstance(v, dict)]
    string_results = [k for k, v in results.items() if isinstance(v, str)]

    # At least some models should succeed
    assert (
        len(successful_models) >= 2
    )  # max_sharpe and min_volatility should always work

    # String results should be either failure messages or adjustment notes
    for model in string_results:
        result = results[model]
        assert (
            result.startswith("Failed")
            or "adjusted" in result
            or "Cannot validate" in result
        )


async def test_calculate_quantities():
    weights = {"AAPL": 0.5, "GOOG": 0.5}
    latest_prices = {"AAPL": 150.0, "GOOG": 2800.0}
    total_investment = 100000
    quantities = await calculate_quantities(weights, latest_prices, total_investment)
    assert quantities["AAPL"] == 333
    assert quantities["GOOG"] == 17


@patch("allocator_bot.portfolio.fetch_historical_prices")
async def test_prepare_allocation(mock_fetch_historical_prices):
    mock_df = pd.DataFrame(
        {
            "symbol": ["AAPL", "GOOG"],
            "date": ["2023-01-01", "2023-01-02"],
            "adj_close": [150.0, 2800.0],
        }
    )
    mock_fetch_historical_prices.return_value = mock_df

    # Create a dummy DataFrame for prices, as the mocked fetch_historical_prices is not
    # returning a pivotable DataFrame
    prices_data = {
        "date": pd.to_datetime(pd.date_range("2023-01-01", periods=100)),
        "AAPL": [150 + i + (i * 0.01) for i in range(100)],
        "GOOG": [2800 + i - (i * 0.02) for i in range(100)],
    }
    prices = pd.DataFrame(prices_data).set_index("date")

    # Mock the pivot_table call
    mock_df.pivot_table = MagicMock(return_value=prices)

    allocation = await prepare_allocation(
        asset_symbols=["AAPL", "GOOG"],
        total_investment=100000,
        risk_free_rate=0.02,
        target_return=0.1,
        target_volatility=0.2,
    )
    assert not allocation.empty
    assert "Risk Model" in allocation.columns
    assert "Ticker" in allocation.columns
    assert "Weight" in allocation.columns
    assert "Quantity" in allocation.columns
    assert "Note" in allocation.columns


@patch("allocator_bot.storage.get_storage")
async def test_save_allocation_s3(mock_get_storage):
    mock_storage = AsyncMock()
    mock_storage.load_allocations.return_value = {}
    mock_get_storage.return_value = mock_storage

    allocation_id = "test_id"
    allocation_data = [{"Ticker": "AAPL", "Weight": 1.0}]
    result = await save_allocation(allocation_id, allocation_data)
    assert result == allocation_id
    mock_storage.save_allocations.assert_called_once_with(
        {allocation_id: allocation_data}
    )


@patch("allocator_bot.storage.get_storage")
async def test_save_allocation_local(mock_get_storage):
    mock_storage = AsyncMock()
    mock_storage.load_allocations.return_value = {}
    mock_get_storage.return_value = mock_storage

    allocation_id = "test_id"
    allocation_data = [{"Ticker": "AAPL", "Weight": 1.0}]
    result = await save_allocation(allocation_id, allocation_data)
    assert result == allocation_id
    mock_storage.save_allocations.assert_called_once_with(
        {allocation_id: allocation_data}
    )
