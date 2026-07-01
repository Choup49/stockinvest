"""
Fetcher Yahoo Finance pour StockInvest Pro.

Responsabilité unique : interroger yfinance et retourner des données brutes
structurées. Aucune logique de nettoyage ou de calcul ici.
"""

import pandas as pd
import yfinance as yf

from core.enums import Sector
from core.exceptions import DataFetchError, InvalidTickerError
from core.models import CompanyInfo, FundamentalsSnapshot
from utils.logger import logger


class YahooFinanceFetcher:
    """Wrapper autour de yfinance exposant une interface stable et typée."""

    def __init__(self, request_timeout: int = 15) -> None:
        self.request_timeout = request_timeout

    def fetch_price_history(
        self,
        ticker: str,
        period: str = "2y",
        interval: str = "1d",
        auto_adjust: bool = False,
    ) -> pd.DataFrame:
        """
        Récupère l'historique de prix et volumes pour un ticker.

        auto_adjust=False permet à data/cleaner.py de gérer explicitement
        le cas où Adj Close est absent, comme requis par le cahier des charges.
        """
        logger.debug(f"Fetching price history: {ticker} | period={period} interval={interval}")
        try:
            yf_ticker = yf.Ticker(ticker)
            df = yf_ticker.history(period=period, interval=interval, auto_adjust=auto_adjust)
        except Exception as exc:
            raise DataFetchError(ticker, f"erreur réseau/API: {exc}") from exc

        if df is None or df.empty:
            raise InvalidTickerError(ticker, "aucune donnée de prix retournée")

        df.index.name = "Date"
        logger.info(
            f"OK {ticker}: {len(df)} lignes ({df.index.min().date()} -> {df.index.max().date()})"
        )
        return df

    def fetch_company_info(self, ticker: str) -> CompanyInfo:
        """Récupère les métadonnées d'entreprise (secteur, market cap, pays...)."""
        logger.debug(f"Fetching company info: {ticker}")
        try:
            info = yf.Ticker(ticker).info
        except Exception as exc:
            raise DataFetchError(ticker, f"erreur réseau/API: {exc}") from exc

        if not info or (info.get("regularMarketPrice") is None and info.get("longName") is None):
            raise InvalidTickerError(ticker, "métadonnées entreprise indisponibles")

        return CompanyInfo(
            ticker=ticker,
            name=info.get("longName") or info.get("shortName") or ticker,
            sector=Sector.from_raw(info.get("sector")),
            industry=info.get("industry"),
            country=info.get("country"),
            market_cap=info.get("marketCap"),
            currency=info.get("currency"),
            exchange=info.get("exchange"),
        )

    def fetch_fundamentals(self, ticker: str) -> FundamentalsSnapshot:
        """Récupère un snapshot des ratios fondamentaux principaux."""
        logger.debug(f"Fetching fundamentals: {ticker}")
        try:
            info = yf.Ticker(ticker).info
        except Exception as exc:
            raise DataFetchError(ticker, f"erreur réseau/API: {exc}") from exc

        if not info:
            raise InvalidTickerError(ticker, "fondamentaux indisponibles")

        return FundamentalsSnapshot(
            ticker=ticker,
            trailing_pe=info.get("trailingPE"),
            forward_pe=info.get("forwardPE"),
            return_on_equity=info.get("returnOnEquity"),
            free_cash_flow=info.get("freeCashflow"),
            revenue_growth=info.get("revenueGrowth"),
            profit_margins=info.get("profitMargins"),
            total_revenue=info.get("totalRevenue"),
        )

    def fetch_batch_price_history(
        self, tickers: list[str], period: str = "2y", interval: str = "1d"
    ) -> dict[str, pd.DataFrame]:
        """Récupère l'historique pour plusieurs tickers, isole les échecs individuels."""
        results: dict[str, pd.DataFrame] = {}
        for ticker in tickers:
            try:
                results[ticker] = self.fetch_price_history(ticker, period=period, interval=interval)
            except DataFetchError as exc:
                logger.warning(f"Batch fetch: {ticker} ignoré — {exc.reason}")
        logger.info(f"Batch terminé: {len(results)}/{len(tickers)} tickers récupérés")
        return results
