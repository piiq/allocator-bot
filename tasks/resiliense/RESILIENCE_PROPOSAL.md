# Portfolio Optimization Resilience Proposal

## Problem Analysis

The current portfolio optimization algorithm fails when user-specified constraints are unrealistic:

1. **Target Volatility Too Low**: When `target_volatility` ≤ minimum possible portfolio volatility
2. **Target Return Too High**: When `target_return` ≥ maximum possible portfolio return

Current behavior: All four optimization models (Max Sharpe, Min Volatility, Efficient Risk, Efficient Return) are attempted simultaneously. If any model fails due to infeasible constraints, the entire optimization fails and no results are returned.

## Root Cause

The `optimize_portfolio` function in `allocator_bot/portfolio.py` runs all models sequentially without validating constraints against portfolio capabilities. PyPortfolioOpt's `EfficientFrontier` methods raise exceptions when constraints are mathematically infeasible.

## Proposed Solution

### Architecture Changes

1. **Independent Model Execution**: Modify `optimize_portfolio` to run each optimization model independently with individual error handling.

2. **Constraint Validation**: Before running constrained models, calculate portfolio bounds using historical data.

3. **Graceful Degradation**: Return results for successful models while documenting failures for unsuccessful ones.

4. **Automatic Constraint Adjustment**: When constraints are infeasible, automatically adjust them to feasible values rather than failing.

### Implementation Details

#### Modified `optimize_portfolio` Function

```python
async def optimize_portfolio(
    prices: pd.DataFrame,
    risk_free_rate: float,
    target_return: float,
    target_volatility: float,
) -> dict[str, dict[str, float] | str]:
    """Perform portfolio optimization with resilience against infeasible constraints."""
    mu = expected_returns.mean_historical_return(prices)
    S = risk_models.sample_cov(prices)

    results = {}

    # Always run unconstrained models
    try:
        ef_sharpe = EfficientFrontier(mu, S)
        ef_sharpe.max_sharpe(risk_free_rate=risk_free_rate)
        results["max_sharpe"] = ef_sharpe.clean_weights()
    except Exception as e:
        results["max_sharpe"] = f"Failed: {str(e)}"

    try:
        ef_volatility = EfficientFrontier(mu, S)
        ef_volatility.min_volatility()
        min_vol_weights = ef_volatility.clean_weights()
        results["min_volatility"] = min_vol_weights
        # Calculate minimum possible volatility for validation
        min_volatility = ef_volatility.portfolio_performance()[1]
    except Exception as e:
        results["min_volatility"] = f"Failed: {str(e)}"
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
                results["efficient_risk_note"] = f"Target volatility adjusted from {target_volatility:.3f} to {adjusted_volatility:.3f} (minimum possible)"
            except Exception as e:
                results["efficient_risk"] = f"Failed even with adjustment: {str(e)}"
        else:
            try:
                ef_risk = EfficientFrontier(mu, S)
                ef_risk.efficient_risk(target_volatility=target_volatility)
                results["efficient_risk"] = ef_risk.clean_weights()
            except Exception as e:
                results["efficient_risk"] = f"Failed: {str(e)}"
    else:
        results["efficient_risk"] = "Cannot validate - min volatility calculation failed"

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
            results["efficient_return_note"] = f"Target return adjusted from {target_return:.3f} to {adjusted_return:.3f} (maximum possible)"
        except Exception as e:
            results["efficient_return"] = f"Failed even with adjustment: {str(e)}"
    else:
        try:
            ef_return = EfficientFrontier(mu, S)
            ef_return.efficient_return(target_return=target_return)
            results["efficient_return"] = ef_return.clean_weights()
        except Exception as e:
            results["efficient_return"] = f"Failed: {str(e)}"

    return results
```

#### Modified Agent Response Logic

Update the agent in `allocator_bot/agent.py` to handle partial results:

```python
# In execution_loop, after optimization
if allocation is not None:
    # Check for failed models and include in response
    failed_models = []
    successful_models = []
    for model, result in optimized_weights.items():
        if isinstance(result, str) and result.startswith("Failed"):
            failed_models.append(f"{model}: {result}")
        else:
            successful_models.append(model)

    if failed_models:
        yield reasoning_step(
            message="Some optimization models failed due to infeasible constraints:",
            details="\n".join(failed_models),
        )
        yield reasoning_step(
            message="Proceeding with successful models. Consider adjusting constraints for failed models.",
        )
```

#### Updated System Prompt

Modify `SYSTEM_PROMPT` in `allocator_bot/prompts.py`:

```
Behavior:
- If some optimization models fail due to infeasible constraints, provide results for successful models and explain why others failed.
- Suggest constraint adjustments when models fail due to unrealistic targets.
- Always attempt to provide at least Max Sharpe and Min Volatility results.
```

## Benefits

1. **Improved User Experience**: Users get partial results instead of complete failure
2. **Automatic Recovery**: System automatically adjusts infeasible constraints to feasible values
3. **Better Error Communication**: Clear explanations of why specific models failed
4. **Maintained Functionality**: Core unconstrained optimizations always work

## Testing Strategy

1. **Unit Tests**: Add tests for constraint validation and auto-adjustment
2. **Integration Tests**: Test with historical failure scenarios from the provided conversation
3. **Edge Cases**: Test with extreme constraint values, single-asset portfolios, highly correlated assets

## Migration Plan

1. Implement changes in `portfolio.py`
2. Update agent logic in `agent.py`
3. Update prompts in `prompts.py`
4. Add comprehensive tests
5. Deploy and monitor for improved resilience
