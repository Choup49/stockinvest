"""Tests unitaires pour data/features.py et quant/factors.py."""

import numpy as np
import pandas as pd
import pytest

from core.exceptions import InsufficientDataError
from data.features import FeatureEngineer
from quant.factors import FactorExtractor


def _make_price_df(n: int = 300) -> pd.DataFrame:
    dates = pd.date_range("2023-01-01", periods=n, freq="D")
    close = 100 + np.cumsum(np.random.normal(0.05, 1, n))
    return pd.DataFrame(
        {
            "Open": close - 0.3,
            "High": close + 0.8,
            "Low": close - 0.8,
            "Close": close,
            "Adj Close": close,
            "Volume": np.random.randint(1_000_000, 3_000_000, n),
        },
        index=dates,
    )


def test_feature_engineer_raises_on_insufficient_data():
    df = _make_price_df(10)
    engineer = FeatureEngineer()
    with pytest.raises(InsufficientDataError):
        engineer.compute_all("TEST", df)


def test_feature_engineer_computes_expected_columns():
    df = _make_price_df(300)
    engineer = FeatureEngineer()
    result = engineer.compute_all("TEST", df)
    expected_cols = {
        "momentum_3m", "momentum_6m", "momentum_12m",
        "volatility_60d", "rsi_14", "macd", "macd_signal",
        "macd_hist", "bollinger_pct_b", "ma_50", "ma_200", "beta",
    }
    assert expected_cols.issubset(set(result.columns))


def test_rsi_bounded_between_0_and_100():
    df = _make_price_df(300)
    engineer = FeatureEngineer()
    result = engineer.compute_all("TEST", df)
    rsi = result["rsi_14"].dropna()
    assert (rsi >= 0).all() and (rsi <= 100).all()


def test_factor_extractor_returns_all_six_factors():
    df = _make_price_df(300)
    engineer = FeatureEngineer()
    features_df = engineer.compute_all("TEST", df)

    extractor = FactorExtractor()
    fundamentals = {
        "trailing_pe": 18.5,
        "fcf_yield": 0.05,
        "revenue_growth": 0.12,
        "roe": 0.22,
        "profit_margin": 0.15,
    }
    raw = extractor.extract("TEST", features_df, fundamentals)

    assert raw.value is not None
    assert raw.growth is not None
    assert raw.quality is not None
    assert raw.momentum is not None
    assert raw.risk is not None
    assert raw.technical is not None
