"""
Simulateur de backtest réaliste pour StockInvest Pro.

Stratégie : acheter les Top-N scores quantitatifs, rééquilibrage
périodique, frais de transaction et slippage configurables, comparaison
avec un benchmark (S&P 500).
"""

import pandas as pd

from core.enums import RebalanceFrequency
from core.exceptions import BacktestError
from core.models import BacktestResult
from backtest.metrics import PerformanceMetrics
from utils.logger import logger

REBALANCE_DAYS = {
    RebalanceFrequency.MONTHLY: 21,
    RebalanceFrequency.QUARTERLY: 63,
    RebalanceFrequency.YEARLY: 252,
}


class BacktestEngine:
    """
    Simule une stratégie 'Top-N score quantitatif' sur historique de prix.

    Le moteur ne recalcule PAS les scores quant à chaque date (ce serait
    du look-ahead bias) : il consomme une série de scores déjà datés,
    fournie par l'appelant (via un score_history pré-calculé).
    """

    def __init__(
        self,
        top_n: int = 10,
        rebalance_frequency: RebalanceFrequency = RebalanceFrequency.QUARTERLY,
        transaction_cost_bps: float = 10.0,  # 0.10% par transaction
        slippage_bps: float = 5.0,  # 0.05%
        initial_capital: float = 100_000.0,
    ) -> None:
        self.top_n = top_n
        self.rebalance_frequency = rebalance_frequency
        self.transaction_cost_bps = transaction_cost_bps
        self.slippage_bps = slippage_bps
        self.initial_capital = initial_capital
        self.metrics = PerformanceMetrics()

    def run(
        self,
        price_data: dict[str, pd.DataFrame],
        score_history: pd.DataFrame,
        benchmark_prices: pd.Series,
        strategy_name: str = "Top-N Quant Score",
    ) -> BacktestResult:
        """
        Args:
            price_data: {ticker: DataFrame OHLCV nettoyé}.
            score_history: DataFrame indexé par date, colonnes = tickers,
                valeurs = score quant à cette date (déjà calculé hors ligne,
                sans look-ahead bias).
            benchmark_prices: Series de prix du benchmark, même index temporel.
            strategy_name: nom affiché dans les résultats.

        Returns:
            BacktestResult avec toutes les métriques + equity curve.
        """
        if score_history.empty:
            raise BacktestError("score_history est vide, impossible de lancer le backtest")

        dates = score_history.index.sort_values()
        rebalance_step = REBALANCE_DAYS[self.rebalance_frequency]
        rebalance_dates = dates[::rebalance_step]

        portfolio_value = self.initial_capital
        equity_curve: dict[str, float] = {}
        current_holdings: dict[str, float] = {}  # ticker -> nb de parts

        daily_dates = dates
        for i, date in enumerate(daily_dates):
            if date in rebalance_dates or i == 0:
                current_holdings, portfolio_value = self._rebalance(
                    date, score_history, price_data, current_holdings, portfolio_value
                )

            portfolio_value = self._mark_to_market(date, current_holdings, price_data, portfolio_value)
            equity_curve[date.isoformat()] = portfolio_value

        equity_series = pd.Series(equity_curve.values(), index=pd.to_datetime(list(equity_curve.keys())))

        benchmark_aligned = benchmark_prices.reindex(equity_series.index).ffill()
        benchmark_return = self.metrics.total_return(benchmark_aligned)

        result = BacktestResult(
            strategy_name=strategy_name,
            cagr=self.metrics.cagr(equity_series),
            sharpe_ratio=self.metrics.sharpe_ratio(equity_series),
            max_drawdown=self.metrics.max_drawdown(equity_series),
            volatility=self.metrics.volatility(equity_series),
            total_return=self.metrics.total_return(equity_series),
            benchmark_return=benchmark_return,
            equity_curve=equity_curve,
        )
        logger.info(
            f"Backtest '{strategy_name}' terminé: CAGR={result.cagr:.1%} "
            f"Sharpe={result.sharpe_ratio:.2f} MaxDD={result.max_drawdown:.1%}"
        )
        return result

    def _rebalance(
        self,
        date: pd.Timestamp,
        score_history: pd.DataFrame,
        price_data: dict[str, pd.DataFrame],
        current_holdings: dict[str, float],
        portfolio_value: float,
    ) -> tuple[dict[str, float], float]:
        """Vend tout, applique frais+slippage, rachète le Top-N équipondéré."""
        # Liquidation (frais/slippage appliqués sur le montant vendu)
        liquidation_cost = portfolio_value * (self.transaction_cost_bps + self.slippage_bps) / 10_000
        portfolio_value -= liquidation_cost if current_holdings else 0.0

        scores_today = score_history.loc[date].dropna()
        top_tickers = scores_today.sort_values(ascending=False).head(self.top_n).index.tolist()
        available_tickers = [t for t in top_tickers if t in price_data and date in price_data[t].index]

        if not available_tickers:
            return {}, portfolio_value

        allocation_per_ticker = portfolio_value / len(available_tickers)
        purchase_cost = portfolio_value * (self.transaction_cost_bps + self.slippage_bps) / 10_000
        portfolio_value -= purchase_cost

        new_holdings = {}
        for ticker in available_tickers:
            price = price_data[ticker].loc[date, "Adj Close"]
            if price > 0:
                new_holdings[ticker] = allocation_per_ticker / price

        return new_holdings, portfolio_value

    def _mark_to_market(
        self,
        date: pd.Timestamp,
        holdings: dict[str, float],
        price_data: dict[str, pd.DataFrame],
        fallback_value: float,
    ) -> float:
        """Valorise le portefeuille au prix du jour."""
        if not holdings:
            return fallback_value

        total = 0.0
        for ticker, shares in holdings.items():
            df = price_data.get(ticker)
            if df is not None and date in df.index:
                total += shares * df.loc[date, "Adj Close"]
            else:
                # dernier prix connu si le titre n'a pas coté ce jour précis
                prior = df[df.index <= date] if df is not None else None
                if prior is not None and not prior.empty:
                    total += shares * prior["Adj Close"].iloc[-1]
        return total if total > 0 else fallback_value
