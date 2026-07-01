"""
Orchestrateur du pipeline complet StockInvest Pro.

Relie data -> quant -> ai -> persistance en une seule passe pour un
univers de tickers donné. Ne connaît RIEN de Qt : c'est un service pur,
appelable en synchrone (tests, scripts) ou depuis un QThread (UI).
"""

from dataclasses import dataclass, field

import pandas as pd

from ai.anomaly import AnomalyDetector
from ai.sentiment import SentimentAnalyzer, SentimentResult
from ai.summarizer import CompanySummarizer, CompanySummary
from core.enums import Sector
from core.exceptions import DataFetchError, InsufficientDataError, StockInvestProError
from core.models import CompanyInfo, FundamentalsSnapshot, QuantScore
from data.cleaner import PriceDataCleaner
from data.features import FeatureEngineer, FundamentalFeatureEngineer
from data.fetcher import YahooFinanceFetcher
from data.repository import MarketDataRepository
from quant.factors import FactorExtractor, RawFactorValues
from quant.scoring import QuantScoringEngine
from utils.logger import logger

BENCHMARK_TICKER = "^GSPC"  # S&P 500


@dataclass
class TickerPipelineResult:
    """Résultat complet du pipeline pour un seul ticker."""

    ticker: str
    company: CompanyInfo
    price_history: pd.DataFrame  # nettoyé
    features_df: pd.DataFrame  # nettoyé + enrichi
    fundamentals: FundamentalsSnapshot
    error: str | None = None


@dataclass
class UniverseAnalysisResult:
    """Résultat agrégé de l'analyse d'un univers de tickers, prêt pour l'UI."""

    ticker_results: dict[str, TickerPipelineResult] = field(default_factory=dict)
    quant_scores: dict[str, QuantScore] = field(default_factory=dict)
    failed_tickers: dict[str, str] = field(default_factory=dict)  # ticker -> raison
    benchmark_prices: pd.Series | None = None


class MarketOrchestrator:
    """
    Point d'entrée unique du pipeline métier. Construit toutes les
    couches internes (fetcher, cleaner, ...) et expose des méthodes
    haut niveau consommées par l'UI (ou des scripts/tests).
    """

    def __init__(
        self,
        repository: MarketDataRepository,
        min_dollar_volume: float = 250_000.0,
        default_period: str = "2y",
        use_openai: bool = False,
        openai_api_key: str | None = None,
    ) -> None:
        self.repository = repository
        self.default_period = default_period

        self.fetcher = YahooFinanceFetcher()
        self.cleaner = PriceDataCleaner(min_dollar_volume=min_dollar_volume)
        self.feature_engineer = FeatureEngineer()
        self.fundamental_engineer = FundamentalFeatureEngineer()
        self.factor_extractor = FactorExtractor()
        self.scoring_engine = QuantScoringEngine()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.anomaly_detector = AnomalyDetector()
        self.summarizer = CompanySummarizer(use_openai=use_openai, openai_api_key=openai_api_key)

        self._benchmark_cache: pd.DataFrame | None = None

    # ------------------------------------------------------------------
    # PIPELINE PAR TICKER (fetch -> clean -> features -> persistance)
    # ------------------------------------------------------------------

    def run_ticker_pipeline(self, ticker: str) -> TickerPipelineResult | None:
        """
        Exécute fetch -> clean -> features -> persistance pour un ticker.
        Retourne None si le ticker doit être exclu (erreur fatale), et
        loggue la raison plutôt que de faire planter tout le batch.
        """
        try:
            company = self.fetcher.fetch_company_info(ticker)
            fundamentals = self.fetcher.fetch_fundamentals(ticker)
            raw_prices = self.fetcher.fetch_price_history(ticker, period=self.default_period)
        except DataFetchError as exc:
            logger.warning(f"Pipeline {ticker}: échec fetch — {exc.reason}")
            return None

        try:
            clean_prices, quality_report = self.cleaner.clean(ticker, raw_prices)
        except StockInvestProError as exc:
            logger.warning(f"Pipeline {ticker}: échec nettoyage — {exc}")
            return None

        if not quality_report.passed_liquidity_filter:
            logger.info(f"Pipeline {ticker}: exclu, sous le seuil de liquidité")
            return None

        benchmark_df = self._get_benchmark_prices()
        try:
            features_df = self.feature_engineer.compute_all(ticker, clean_prices, benchmark_df)
        except InsufficientDataError as exc:
            logger.warning(f"Pipeline {ticker}: {exc}")
            return None

        # Persistance
        company_id = self.repository.upsert_company(company)
        self.repository.save_price_history(company_id, clean_prices)
        self.repository.save_quality_report(quality_report)

        return TickerPipelineResult(
            ticker=ticker,
            company=company,
            price_history=clean_prices,
            features_df=features_df,
            fundamentals=fundamentals,
        )

    def _get_benchmark_prices(self) -> pd.DataFrame:
        """Récupère (et cache en mémoire) l'historique du benchmark S&P 500."""
        if self._benchmark_cache is None:
            try:
                self._benchmark_cache = self.fetcher.fetch_price_history(
                    BENCHMARK_TICKER, period=self.default_period
                )
            except DataFetchError as exc:
                logger.warning(f"Benchmark indisponible: {exc.reason}, beta sera neutre")
                self._benchmark_cache = pd.DataFrame()
        return self._benchmark_cache

    # ------------------------------------------------------------------
    # ANALYSE D'UN UNIVERS COMPLET (scoring sectoriel groupé)
    # ------------------------------------------------------------------

    def analyze_universe(self, tickers: list[str], progress_callback=None) -> UniverseAnalysisResult:
        """
        Exécute le pipeline pour chaque ticker, groupe par secteur pour le
        scoring (comparaison sectorielle obligatoire), puis persiste les scores.

        Args:
            tickers: liste de symboles à analyser.
            progress_callback: callable(done: int, total: int, ticker: str) optionnel,
                appelé après chaque ticker traité — utile pour une barre de progression Qt.
        """
        result = UniverseAnalysisResult()
        result.benchmark_prices = self._safe_benchmark_series()

        total = len(tickers)
        for i, ticker in enumerate(tickers, start=1):
            pipeline_result = self.run_ticker_pipeline(ticker)
            if pipeline_result is None:
                result.failed_tickers[ticker] = "échec pipeline (fetch/nettoyage/liquidité/données insuffisantes)"
            else:
                result.ticker_results[ticker] = pipeline_result

            if progress_callback:
                progress_callback(i, total, ticker)

        # Groupement par secteur pour respecter la comparaison sectorielle
        by_sector: dict[Sector, dict[str, RawFactorValues]] = {}
        for ticker, pr in result.ticker_results.items():
            fund_features = self.fundamental_engineer.compute(
                pr.fundamentals.__dict__, pr.company.market_cap
            )
            raw = self.factor_extractor.extract(ticker, pr.features_df, fund_features)
            by_sector.setdefault(pr.company.sector, {})[ticker] = raw

        for sector, universe in by_sector.items():
            sector_scores = self.scoring_engine.score_universe(sector, universe)
            result.quant_scores.update(sector_scores)

            for ticker, score in sector_scores.items():
                pr = result.ticker_results[ticker]
                company_id = self.repository.upsert_company(pr.company)
                self.repository.save_quant_score(company_id, score)

        logger.info(
            f"Analyse univers terminée: {len(result.quant_scores)} scorés, "
            f"{len(result.failed_tickers)} échoués sur {total}"
        )
        return result

    def _safe_benchmark_series(self) -> pd.Series | None:
        df = self._get_benchmark_prices()
        if df is None or df.empty:
            return None
        return df["Adj Close"]

    # ------------------------------------------------------------------
    # DEEP DIVE : analyse complète d'un seul ticker (sentiment + résumé IA)
    # ------------------------------------------------------------------

    def build_deep_dive(
        self, ticker: str, quant_score: QuantScore, headlines: list[str] | None = None
    ) -> tuple[SentimentResult, CompanySummary] | None:
        """
        Complète l'analyse d'un ticker déjà scoré avec sentiment + résumé IA,
        pour alimenter la page Deep Dive.
        """
        pipeline_result = self.run_ticker_pipeline(ticker)
        if pipeline_result is None:
            return None

        sentiment = self.sentiment_analyzer.analyze(
            ticker, headlines or [], pipeline_result.price_history
        )
        summary = self.summarizer.summarize(pipeline_result.company, quant_score, headlines)
        return sentiment, summary

    # ------------------------------------------------------------------
    # RECHERCHE — résolution nom d'entreprise -> ticker
    # ------------------------------------------------------------------

    def search_ticker(self, query: str, max_results: int = 8):
        """
        Résout un texte libre (nom d'entreprise ou fragment de ticker) vers
        une liste de tickers candidats, pour alimenter la barre de recherche.

        Simple proxy vers le fetcher : aucune logique métier supplémentaire
        n'est nécessaire ici, mais on passe par l'orchestrateur pour que
        l'UI n'ait jamais à importer data/fetcher.py directement.
        """
        return self.fetcher.search_ticker(query, max_results=max_results)

    # ------------------------------------------------------------------
    # WATCHLIST / MARKET WATCH (léger, pas de features complètes)
    # ------------------------------------------------------------------

    def get_watchlist_quotes(self, tickers: list[str]) -> dict[str, tuple[float, float]]:
        """
        Récupère prix + variation % du jour pour une liste de tickers,
        sans passer par tout le pipeline (utilisé pour le ticker tape / market watch).

        Returns:
            {ticker: (prix, variation_pct)}
        """
        quotes: dict[str, tuple[float, float]] = {}
        for ticker in tickers:
            try:
                df = self.fetcher.fetch_price_history(ticker, period="5d")
            except DataFetchError as exc:
                logger.warning(f"Watchlist: {ticker} ignoré — {exc.reason}")
                continue
            if len(df) < 2:
                continue
            last_close = float(df["Close"].iloc[-1])
            prev_close = float(df["Close"].iloc[-2])
            change_pct = ((last_close / prev_close) - 1) * 100 if prev_close else 0.0
            quotes[ticker] = (last_close, change_pct)
        return quotes