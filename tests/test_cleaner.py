"""Tests unitaires pour data/cleaner.py."""

import numpy as np
import pandas as pd
import pytest

from core.exceptions import DataQualityError
from data.cleaner import PriceDataCleaner


def _make_valid_df(n: int = 100) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    close = 100 + np.cumsum(np.random.normal(0, 1, n))
    return pd.DataFrame(
        {
            "Open": close - 0.5,
            "High": close + 1,
            "Low": close - 1,
            "Close": close,
            "Adj Close": close,
            "Volume": np.random.randint(1_000_000, 5_000_000, n),
        },
        index=dates,
    )


def test_clean_valid_data_keeps_all_rows():
    df = _make_valid_df(100)
    cleaner = PriceDataCleaner(min_dollar_volume=1000)
    clean_df, report = cleaner.clean("TEST", df)
    assert report.rows_before == 100
    assert report.rows_after == 100
    assert report.rows_dropped == 0


def test_clean_removes_impossible_prices():
    df = _make_valid_df(50)
    df.iloc[10, df.columns.get_loc("Close")] = -5.0  # prix impossible
    cleaner = PriceDataCleaner(min_dollar_volume=1000)
    clean_df, report = cleaner.clean("TEST", df)
    assert report.rows_dropped >= 1
    assert (clean_df["Close"] > 0).all()


def test_clean_fills_adj_close_when_missing():
    df = _make_valid_df(50).drop(columns=["Adj Close"])
    cleaner = PriceDataCleaner(min_dollar_volume=1000)
    clean_df, _ = cleaner.clean("TEST", df)
    assert "Adj Close" in clean_df.columns


def test_clean_raises_when_too_few_rows():
    df = _make_valid_df(10)  # < 30 lignes minimum
    cleaner = PriceDataCleaner(min_dollar_volume=1000)
    with pytest.raises(DataQualityError):
        cleaner.clean("TEST", df)


def test_liquidity_filter_flags_low_volume():
    df = _make_valid_df(100)
    df["Volume"] = 1  # dollar volume quasi nul
    cleaner = PriceDataCleaner(min_dollar_volume=250_000)
    _, report = cleaner.clean("TEST", df)
    assert report.passed_liquidity_filter is False
