"""Métriques de performance pour le backtest engine."""

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252


class PerformanceMetrics:
    """Calcule CAGR, Sharpe, Max Drawdown et volatilité à partir d'une equity curve."""

    @staticmethod
    def cagr(equity_curve: pd.Series) -> float:
        """Compound Annual Growth Rate."""
        if len(equity_curve) < 2:
            return 0.0
        n_years = len(equity_curve) / TRADING_DAYS_PER_YEAR
        if n_years <= 0:
            return 0.0
        total_return = equity_curve.iloc[-1] / equity_curve.iloc[0]
        if total_return <= 0:
            return -1.0
        return float(total_return ** (1 / n_years) - 1)

    @staticmethod
    def sharpe_ratio(equity_curve: pd.Series, risk_free_rate: float = 0.02) -> float:
        """Sharpe ratio annualisé, rendements journaliers."""
        daily_returns = equity_curve.pct_change().dropna()
        if daily_returns.std() == 0 or daily_returns.empty:
            return 0.0
        excess_daily = daily_returns - (risk_free_rate / TRADING_DAYS_PER_YEAR)
        return float(np.sqrt(TRADING_DAYS_PER_YEAR) * excess_daily.mean() / daily_returns.std())

    @staticmethod
    def max_drawdown(equity_curve: pd.Series) -> float:
        """Max drawdown, valeur négative (ex: -0.23 = -23%)."""
        running_max = equity_curve.cummax()
        drawdown = (equity_curve - running_max) / running_max
        return float(drawdown.min()) if not drawdown.empty else 0.0

    @staticmethod
    def volatility(equity_curve: pd.Series) -> float:
        """Volatilité annualisée des rendements journaliers."""
        daily_returns = equity_curve.pct_change().dropna()
        return float(daily_returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR))

    @staticmethod
    def total_return(equity_curve: pd.Series) -> float:
        if len(equity_curve) < 2 or equity_curve.iloc[0] == 0:
            return 0.0
        return float(equity_curve.iloc[-1] / equity_curve.iloc[0] - 1)
