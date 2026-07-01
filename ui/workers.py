"""
Workers QThread : exécutent l'orchestrateur en arrière-plan pour ne
jamais geler l'interface Qt pendant les appels réseau/calculs lourds.
"""

from PySide6.QtCore import QThread, Signal

from core.orchestrator import MarketOrchestrator, UniverseAnalysisResult
from utils.logger import logger


class UniverseAnalysisWorker(QThread):
    """
    Lance analyze_universe() sur un thread séparé.

    Signaux :
        progress(int done, int total, str ticker) — avancement.
        finished_ok(UniverseAnalysisResult) — succès.
        failed(str message) — erreur fatale non récupérable.
    """

    progress = Signal(int, int, str)
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, orchestrator: MarketOrchestrator, tickers: list[str]) -> None:
        super().__init__()
        self.orchestrator = orchestrator
        self.tickers = tickers

    def run(self) -> None:
        try:
            result = self.orchestrator.analyze_universe(
                self.tickers,
                progress_callback=lambda done, total, ticker: self.progress.emit(done, total, ticker),
            )
            self.finished_ok.emit(result)
        except Exception as exc:
            logger.exception("Échec de l'analyse d'univers dans le worker")
            self.failed.emit(str(exc))


class WatchlistQuotesWorker(QThread):
    """Rafraîchit prix + variation % pour le ticker tape / market watch en arrière-plan."""

    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, orchestrator: MarketOrchestrator, tickers: list[str]) -> None:
        super().__init__()
        self.orchestrator = orchestrator
        self.tickers = tickers

    def run(self) -> None:
        try:
            quotes = self.orchestrator.get_watchlist_quotes(self.tickers)
            self.finished_ok.emit(quotes)
        except Exception as exc:
            logger.exception("Échec du rafraîchissement watchlist dans le worker")
            self.failed.emit(str(exc))


class DeepDiveWorker(QThread):
    """Construit sentiment + résumé IA pour un ticker en arrière-plan."""

    finished_ok = Signal(object)  # tuple[SentimentResult, CompanySummary]
    failed = Signal(str)

    def __init__(self, orchestrator: MarketOrchestrator, ticker: str, quant_score, headlines=None) -> None:
        super().__init__()
        self.orchestrator = orchestrator
        self.ticker = ticker
        self.quant_score = quant_score
        self.headlines = headlines or []

    def run(self) -> None:
        try:
            result = self.orchestrator.build_deep_dive(self.ticker, self.quant_score, self.headlines)
            if result is None:
                self.failed.emit(f"Impossible de compléter le Deep Dive pour {self.ticker}")
                return
            self.finished_ok.emit(result)
        except Exception as exc:
            logger.exception(f"Échec Deep Dive worker pour {self.ticker}")
            self.failed.emit(str(exc))


class TickerSearchWorker(QThread):
    """
    Résout un texte libre (nom d'entreprise ou fragment) vers une liste de
    tickers candidats, en arrière-plan pour ne pas bloquer la saisie clavier.

    Chaque frappe déclenche potentiellement un nouveau worker ; l'appelant
    (SearchBarWidget) est responsable d'annuler/ignorer les résultats
    obsolètes si l'utilisateur a continué à taper entre-temps (voir
    request_id ci-dessous).
    """

    finished_ok = Signal(list, str)  # (résultats, request_id)
    failed = Signal(str, str)  # (message, request_id)

    def __init__(self, orchestrator: MarketOrchestrator, query: str, request_id: str) -> None:
        super().__init__()
        self.orchestrator = orchestrator
        self.query = query
        self.request_id = request_id

    def run(self) -> None:
        try:
            results = self.orchestrator.search_ticker(self.query)
            self.finished_ok.emit(results, self.request_id)
        except Exception as exc:
            logger.warning(f"Échec de la recherche de ticker '{self.query}': {exc}")
            self.failed.emit(str(exc), self.request_id)