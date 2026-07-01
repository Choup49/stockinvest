"""Tests unitaires pour backtest/engine.py et backtest/metrics.py."""

import numpy as np
import pandas as pd
import pytest

from backtest.engine import BacktestEngine
from backtest.metrics import PerformanceMetrics
from core.enums import RebalanceFrequency
from core.exceptions import BacktestError


def _make_equity_curve(n: int = 252, drift: float = 0.0005) -> pd.Series:
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    values = 100_000 * np.cumprod(1 + np.random.normal(drift, 0.01, n))
    return pd.Series(values, index=dates)


def test_metrics_cagr_positive_for_growing_curve():
    curve = pd.Series([100, 110, 121, 133.1], index=pd.date_range("2023-01-01", periods=4, freq="YE"))
    cagr = PerformanceMetrics.cagr(curve)
    assert cagr > 0


def test_metrics_max_drawdown_is_negative_or_zero():
    curve = _make_equity_curve()
    mdd = PerformanceMetrics.max_drawdown(curve)
    assert mdd <= 0


def test_metrics_sharpe_ratio_is_finite():
    curve = _make_equity_curve()
    sharpe = PerformanceMetrics.sharpe_ratio(curve)
    assert np.isfinite(sharpe)


def test_backtest_engine_raises_on_empty_scores():
    engine = BacktestEngine()
    with pytest.raises(BacktestError):
        engine.run(price_data={}, score_history=pd.DataFrame(), benchmark_prices=pd.Series(dtype=float))


def test_backtest_engine_runs_end_to_end():
    dates = pd.date_range("2023-01-01", periods=100, freq="B")
    tickers = [f"T{i}" for i in range(5)]

    price_data = {}
    for t in tickers:
        close = 100 + np.cumsum(np.random.normal(0.02, 1, len(dates)))
        price_data[t] = pd.DataFrame(
            {"Adj Close": close, "Volume": 1_000_000}, index=dates
        )

    score_history = pd.DataFrame(
        np.random.uniform(0, 100, size=(len(dates), len(tickers))),
        index=dates,
        columns=tickers,
    )

    benchmark = pd.Series(100 + np.cumsum(np.random.normal(0.01, 0.8, len(dates))), index=dates)

    engine = BacktestEngine(top_n=3, rebalance_frequency=RebalanceFrequency.MONTHLY)
    result = engine.run(price_data, score_history, benchmark, strategy_name="Test Strategy")

    assert result.strategy_name == "Test Strategy"
    assert len(result.equity_curve) == len(dates)
    assert np.isfinite(result.cagr)
    assert np.isfinite(result.sharpe_ratio)
