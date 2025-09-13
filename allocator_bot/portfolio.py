import warnings
from datetime import datetime, timedelta

import pandas as pd
from openbb_fmp import FMPEquityHistoricalFetcher
from pypfopt import EfficientFrontier, expected_returns, risk_models  # type: ignore

from .config import config


async def fetch_historical_prices(
    tickers: list[str], start_date: str = "1998-01-01", end_date: str | None = None
) -> pd.DataFrame:
    """Fetch historical prices for a list of tickers."""

    if end_date is None:
        end_date = datetime.today().strftime("%Y-%m-%d")

    price_data = await FMPEquityHistoricalFetcher.fetch_data(
        params={
            "symbol": ",".join(tickers),
            "start_date": start_date,
            "end_date": end_date,
        },
        credentials={"fmp_api_key": config.fmp_api_key or ""},
    )
    return pd.DataFrame(p.model_dump() for p in price_data)  # type: ignore [union-attr]


async def optimize_portfolio(
    prices: pd.DataFrame,
    risk_free_rate: float,
    target_return: float,
    target_volatility: float,
) -> tuple[dict[str, dict[str, float]], dict[str, str]]:
    """Perform portfolio optimization with resilience against infeasible constraints."""
    mu = expected_returns.mean_historical_return(prices)
    S = risk_models.sample_cov(prices)

    results = {}
    failures = {}

    # Always run unconstrained models
    try:
        ef_sharpe = EfficientFrontier(mu, S)
        ef_sharpe.max_sharpe(risk_free_rate=risk_free_rate)
        results["max_sharpe"] = ef_sharpe.clean_weights()
    except Exception as e:
        failures["max_sharpe"] = f"Failed: {str(e)}"

    try:
        ef_volatility = EfficientFrontier(mu, S)
        ef_volatility.min_volatility()
        min_vol_weights = ef_volatility.clean_weights()
        results["min_volatility"] = min_vol_weights
        # Calculate minimum possible volatility for validation
        min_volatility = ef_volatility.portfolio_performance()[1]
    except Exception as e:
        failures["min_volatility"] = f"Failed: {str(e)}"
        min_volatility = None

    # Efficient Risk with validation
    if min_volatility is not None:
        if target_volatility <= min_volatility:
            # Auto-adjust to feasible value
            adjusted_volatility = min_volatility * 1.01  # 1% buffer
            try:
                ef_risk = EfficientFrontier(mu, S)
                ef_risk.efficient_risk(target_volatility=adjusted_volatility)
                results["efficient_risk"] = ef_risk.clean_weights()
                failures["efficient_risk_note"] = (
                    f"Target volatility adjusted from {target_volatility:.3f} to {adjusted_volatility:.3f} (minimum possible)"
                )
            except Exception as e:
                failures["efficient_risk"] = f"Failed even with adjustment: {str(e)}"
        else:
            try:
                ef_risk = EfficientFrontier(mu, S)
                ef_risk.efficient_risk(target_volatility=target_volatility)
                results["efficient_risk"] = ef_risk.clean_weights()
            except Exception as e:
                failures["efficient_risk"] = f"Failed: {str(e)}"
    else:
        failures["efficient_risk"] = (
            "Cannot validate - min volatility calculation failed"
        )

    # Efficient Return with validation
    # Calculate maximum possible return (simplified: max individual asset return)
    max_individual_return = mu.max()
    if target_return >= max_individual_return:
        # Auto-adjust to feasible value
        adjusted_return = max_individual_return * 0.99  # 1% buffer
        try:
            ef_return = EfficientFrontier(mu, S)
            ef_return.efficient_return(target_return=adjusted_return)
            results["efficient_return"] = ef_return.clean_weights()
            failures["efficient_return_note"] = (
                f"Target return adjusted from {target_return:.3f} to {adjusted_return:.3f} (maximum possible)"
            )
        except Exception as e:
            failures["efficient_return"] = f"Failed even with adjustment: {str(e)}"
    else:
        try:
            ef_return = EfficientFrontier(mu, S)
            ef_return.efficient_return(target_return=target_return)
            results["efficient_return"] = ef_return.clean_weights()
        except Exception as e:
            failures["efficient_return"] = f"Failed: {str(e)}"

    return results, failures


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
    Failed models are included as rows with Note column.
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

    # Ensure all price data is numeric
    prices = prices.astype(float)

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
            optimized_weights: dict[str, dict[str, float]]
            failures: dict[str, str]
            optimized_weights, failures = await optimize_portfolio(
                prices, **optimization_kwargs
            )
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
                    "Note": None,
                }
            )

    # Add failure rows
    for model, message in failures.items():
        results.append(
            {
                "Risk Model": model,
                "Ticker": "N/A",
                "Weight": 0.0,
                "Quantity": 0,
                "Note": message,
            }
        )

    return pd.DataFrame(results)
