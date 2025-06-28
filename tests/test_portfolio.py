import os
import pandas as pd
from unittest.mock import patch, MagicMock
from allocator_bot.portfolio import (
    fetch_historical_prices,
    optimize_portfolio,
    calculate_quantities,
    prepare_allocation,
    save_allocation,
)


def test_fetch_historical_prices():
    mock_df = pd.DataFrame(
        {
            "symbol": ["AAPL", "GOOG"],
            "date": ["2023-01-01", "2023-01-01"],
            "adj_close": [150.0, 2800.0],
        }
    )
    mock_obb = MagicMock()
    mock_obb.equity.price.historical.return_value.to_df.return_value = mock_df

    with patch("allocator_bot.portfolio.obb", mock_obb):
        prices = fetch_historical_prices(["AAPL", "GOOG"])
        assert not prices.empty
        assert list(prices.columns) == ["symbol", "date", "adj_close"]
        assert len(prices) == 2


def test_optimize_portfolio():
    data = {
        "date": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]),
        "AAPL": [150, 152, 151],
        "GOOG": [2800, 2810, 2805],
    }
    prices = pd.DataFrame(data).set_index("date")
    results = optimize_portfolio(prices, 0.02, 0.1, 0.2)
    assert "max_sharpe" in results
    assert "min_volatility" in results
    assert "efficient_risk" in results
    assert "efficient_return" in results


def test_calculate_quantities():
    weights = {"AAPL": 0.5, "GOOG": 0.5}
    latest_prices = {"AAPL": 150.0, "GOOG": 2800.0}
    total_investment = 100000
    quantities = calculate_quantities(weights, latest_prices, total_investment)
    assert quantities["AAPL"] == 333
    assert quantities["GOOG"] == 17


@patch("allocator_bot.portfolio.fetch_historical_prices")
def test_prepare_allocation(mock_fetch_historical_prices):
    mock_df = pd.DataFrame(
        {
            "symbol": ["AAPL", "GOOG"],
            "date": ["2023-01-01", "2023-01-02"],
            "adj_close": [150.0, 2800.0],
        }
    )
    mock_fetch_historical_prices.return_value = mock_df

    # Create a dummy DataFrame for prices, as the mocked fetch_historical_prices is not returning a pivotable DataFrame
    prices_data = {
        "date": pd.to_datetime(pd.date_range("2023-01-01", periods=100)),
        "AAPL": [150 + i + (i * 0.01) for i in range(100)],
        "GOOG": [2800 + i - (i * 0.02) for i in range(100)],
    }
    prices = pd.DataFrame(prices_data).set_index("date")

    # Mock the pivot_table call
    mock_df.pivot_table = MagicMock(return_value=prices)

    allocation = prepare_allocation(
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


@patch("allocator_bot.portfolio.save_allocations_to_s3")
@patch("allocator_bot.portfolio.load_allocations_from_s3")
@patch("allocator_bot.portfolio.config")
def test_save_allocation_s3(mock_config, mock_load_s3, mock_save_s3):
    mock_config.s3_enabled = True
    mock_load_s3.return_value = {}
    allocation_id = "test_id"
    allocation_data = [{"Ticker": "AAPL", "Weight": 1.0}]
    result = save_allocation(allocation_id, allocation_data)
    assert result == allocation_id
    mock_save_s3.assert_called_once()


@patch("builtins.open", new_callable=MagicMock)
@patch("json.dump")
@patch("json.load")
@patch("os.getenv")
@patch("allocator_bot.portfolio.config")
def test_save_allocation_local(
    mock_config, mock_getenv, mock_json_load, mock_json_dump, mock_open
):
    mock_config.s3_enabled = False
    mock_getenv.return_value = "/fake/path"
    mock_json_load.return_value = {}
    allocation_id = "test_id"
    allocation_data = [{"Ticker": "AAPL", "Weight": 1.0}]
    result = save_allocation(allocation_id, allocation_data)
    assert result == allocation_id
    mock_open.assert_called()
    mock_json_dump.assert_called()
