import warnings
from datetime import datetime, timedelta

import pandas as pd
from openbb import obb  # type: ignore
from pypfopt import EfficientFrontier, expected_returns, risk_models  # type: ignore

from .config import config


async def fetch_historical_prices(
    tickers: list[str], start_date: str = "1998-01-01", end_date: str | None = None
) -> pd.DataFrame:
    """Fetch historical prices for a list of tickers."""
    if obb.user.credentials.fmp_api_key is None:
        obb.user.credentials.fmp_api_key = config.fmp_api_key

    if end_date is None:
        end_date = datetime.today().strftime("%Y-%m-%d")

    price_data = obb.equity.price.historical(  # type: ignore
        symbol=",".join(tickers),
        start_date=start_date,
        end_date=end_date,
        provider="fmp",
    ).to_df()
    return price_data


async def optimize_portfolio(
    prices: pd.DataFrame,
    risk_free_rate: float,
    target_return: float,
    target_volatility: float,
) -> dict[str, dict[str, float]]:
    """Perform portfolio optimization for multiple risk models and return the results."""
    mu = expected_returns.mean_historical_return(prices)
    S = risk_models.sample_cov(prices)

    results = {}

    # Maximize Sharpe Ratio
    ef_sharpe = EfficientFrontier(mu, S)
    ef_sharpe.max_sharpe(risk_free_rate=risk_free_rate)
    results["max_sharpe"] = ef_sharpe.clean_weights()

    # Minimize Volatility
    ef_volatility = EfficientFrontier(mu, S)
    ef_volatility.min_volatility()
    results["min_volatility"] = ef_volatility.clean_weights()

    # Efficient Risk
    ef_risk = EfficientFrontier(mu, S)
    ef_risk.efficient_risk(target_volatility=target_volatility)
    results["efficient_risk"] = ef_risk.clean_weights()

    # Efficient Return
    ef_return = EfficientFrontier(mu, S)
    ef_return.efficient_return(target_return=target_return)
    results["efficient_return"] = ef_return.clean_weights()

    return results


async def calculate_quantities(
    weights: dict[str, float], latest_prices: dict[str, float], total_investment: float
) -> dict[str, int]:
    """Calculate the quantities of shares to allocate based on weights and total investment."""
    quantities = {
        ticker: int((total_investment * weight) // latest_prices[ticker])
        for ticker, weight in weights.items()
    }
    return quantities


async def prepare_allocation(
    asset_symbols: list[str],
    total_investment: float,
    start_date: str | None = None,
    end_date: str | None = None,
    risk_free_rate: float | None = None,
    target_return: float | None = None,
    target_volatility: float | None = None,
) -> pd.DataFrame:
    """
    Main function to fetch data, optimize portfolio, and return a DataFrame with weights and quantities.
    """
    # Define time range for optimization
    start_date = start_date or (datetime.now() - timedelta(days=365)).strftime(
        "%Y-%m-%d"
    )
    end_date = end_date or datetime.now().strftime("%Y-%m-%d")

    # Fetch historical prices
    historical_prices = await fetch_historical_prices(
        asset_symbols, start_date=start_date, end_date=end_date
    )

    # Pivot data to have tickers as columns and dates as rows
    prices = historical_prices.pivot_table(
        values="adj_close", index="date", columns="symbol"
    )

    # Perform portfolio optimization
    optimization_kwargs = {}
    if risk_free_rate is not None:
        optimization_kwargs["risk_free_rate"] = risk_free_rate
    if target_return is not None:
        optimization_kwargs["target_return"] = target_return
    if target_volatility is not None:
        optimization_kwargs["target_volatility"] = target_volatility

    # Capture warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        try:
            optimized_weights = await optimize_portfolio(prices, **optimization_kwargs)
        except Exception as e:
            warning_messages = "\n".join(str(warning.message) for warning in w)
            raise ValueError(
                f"Error optimizing portfolio: {e}\nWarnings: {warning_messages}"
            )

    # Get the latest prices for the tickers
    latest_prices = {symbol: prices[symbol].iloc[-1] for symbol in asset_symbols}

    # Create a DataFrame to store results
    results = []
    for model, weights in optimized_weights.items():
        quantities = await calculate_quantities(
            weights, latest_prices, total_investment
        )
        for symbol, weight in weights.items():
            results.append(
                {
                    "Risk Model": model,
                    "Ticker": symbol,
                    "Weight": weight,
                    "Quantity": quantities[symbol],
                }
            )

    return pd.DataFrame(results)
