"""
Feature engineering pour StockInvest Pro.

Calcule momentum, volatilité, beta dynamique et indicateurs techniques
à partir d'un DataFrame OHLCV nettoyé.
"""

import numpy as np
import pandas as pd

from core.exceptions import InsufficientDataError
from utils.logger import logger


class FeatureEngineer:
    """Calcule l'ensemble des features quantitatives et techniques."""

    def compute_all(
        self, ticker: str, df: pd.DataFrame, benchmark_df: pd.DataFrame | None = None
    ) -> pd.DataFrame:
        """
        Ajoute toutes les colonnes de features au DataFrame de prix.

        Args:
            ticker: symbole, utilisé uniquement pour les logs/erreurs.
            df: DataFrame OHLCV nettoyé, indexé par date croissante.
            benchmark_df: DataFrame OHLCV du benchmark (ex: S&P 500) pour le beta.
                Si None, la colonne 'beta' sera NaN.

        Returns:
            Le DataFrame enrichi de toutes les colonnes de features.
        """
        if len(df) < 20:
            raise InsufficientDataError(ticker, required=20, available=len(df))

        out = df.copy()
        out = self._add_momentum(out)
        out = self._add_volatility(out)
        out = self._add_technical_indicators(out)
        if benchmark_df is not None:
            out = self._add_beta(out, benchmark_df)
        else:
            out["beta"] = np.nan

        logger.debug(f"Features calculées pour {ticker}: {len(out.columns)} colonnes")
        return out

    def _add_momentum(self, df: pd.DataFrame) -> pd.DataFrame:
        """Momentum 3/6/12 mois basé sur ~21 jours de bourse par mois."""
        df["momentum_3m"] = df["Adj Close"].pct_change(63)
        df["momentum_6m"] = df["Adj Close"].pct_change(126)
        df["momentum_12m"] = df["Adj Close"].pct_change(252)
        return df

    def _add_volatility(self, df: pd.DataFrame) -> pd.DataFrame:
        """Volatilité rolling 60 jours, annualisée (racine de 252)."""
        daily_returns = df["Adj Close"].pct_change()
        df["volatility_60d"] = daily_returns.rolling(60).std() * np.sqrt(252)
        return df

    def _add_beta(self, df: pd.DataFrame, benchmark_df: pd.DataFrame) -> pd.DataFrame:
        """Beta dynamique = covariance glissante / variance glissante (fenêtre 60j)."""
        stock_returns = df["Adj Close"].pct_change()
        bench_returns = benchmark_df["Adj Close"].pct_change().reindex(df.index)

        rolling_cov = stock_returns.rolling(60).cov(bench_returns)
        rolling_var = bench_returns.rolling(60).var()
        df["beta"] = rolling_cov / rolling_var.replace(0, np.nan)
        return df

    def _add_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df["rsi_14"] = self._rsi(df["Adj Close"], period=14)
        macd, macd_signal, macd_hist = self._macd(df["Adj Close"])
        df["macd"] = macd
        df["macd_signal"] = macd_signal
        df["macd_hist"] = macd_hist
        df["bollinger_pct_b"] = self._bollinger_pct_b(df["Adj Close"])
        df["ma_50"] = df["Adj Close"].rolling(50).mean()
        df["ma_200"] = df["Adj Close"].rolling(200).mean()
        return df

    @staticmethod
    def _rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """RSI classique (Wilder), échelle 0-100."""
        delta = prices.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50.0)  # zone neutre si indéterminé

    @staticmethod
    def _macd(
        prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """MACD standard 12/26/9."""
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    @staticmethod
    def _bollinger_pct_b(prices: pd.Series, period: int = 20, n_std: float = 2.0) -> pd.Series:
        """%B de Bollinger : position du prix dans la bande (0 = bande basse, 1 = bande haute)."""
        rolling_mean = prices.rolling(period).mean()
        rolling_std = prices.rolling(period).std()
        upper = rolling_mean + n_std * rolling_std
        lower = rolling_mean - n_std * rolling_std
        band_width = (upper - lower).replace(0, np.nan)
        return (prices - lower) / band_width


class FundamentalFeatureEngineer:
    """Calcule les features fondamentales dérivées à partir d'un snapshot."""

    def compute(self, fundamentals: dict, market_cap: float | None) -> dict[str, float | None]:
        """
        Args:
            fundamentals: dict issu de FundamentalsSnapshot.__dict__ ou équivalent.
            market_cap: capitalisation boursière courante.

        Returns:
            dict avec per, roe, fcf_yield, revenue_growth, profit_margin.
        """
        fcf = fundamentals.get("free_cash_flow")
        fcf_yield = (fcf / market_cap) if fcf and market_cap else None

        return {
            "per": fundamentals.get("trailing_pe"),
            "roe": fundamentals.get("return_on_equity"),
            "fcf_yield": fcf_yield,
            "revenue_growth": fundamentals.get("revenue_growth"),
            "profit_margin": fundamentals.get("profit_margins"),
        }
