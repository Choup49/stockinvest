"""Fenêtre principale StockInvest Pro : layout terminal (top bar, gauche, centre, droite, bas)."""

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from core.enums import MarketRegime
from core.models import QuantScore
from core.orchestrator import MarketOrchestrator, UniverseAnalysisResult
from data.repository import MarketDataRepository
from ui.pages.command_center import CommandCenterPage
from ui.pages.deep_dive import DeepDivePage
from ui.pages.quant_engine import QuantEnginePage
from ui.pages.simulator import SimulatorPage
from ui.theme import build_qss
from ui.widgets.chart_view import ChartViewWidget
from ui.widgets.market_watch import MarketWatchWidget
from ui.widgets.quant_hud import QuantHudWidget
from ui.widgets.search_bar import SearchBarWidget
from ui.widgets.ticker_tape import TickerTapeWidget
from ui.workers import DeepDiveWorker, UniverseAnalysisWorker, WatchlistQuotesWorker
from utils.logger import logger


class MainWindow(QMainWindow):
    """
    Fenêtre principale : assemble top bar, market watch (gauche), chart
    (centre), quant HUD (droite), et les 4 pages en onglets (bas).

    Toute la logique métier (fetch, nettoyage, scoring...) transite par
    MarketOrchestrator, exécuté dans des QThread dédiés pour ne jamais
    geler l'interface.
    """

    def __init__(
        self,
        repository: MarketDataRepository,
        orchestrator: MarketOrchestrator,
        theme_colors: dict[str, str],
        default_watchlist: list[str],
    ) -> None:
        super().__init__()
        self.repository = repository
        self.orchestrator = orchestrator
        self.default_watchlist = default_watchlist

        self._latest_universe_result: UniverseAnalysisResult | None = None
        self._active_worker = None  # référence forte pour éviter le GC pendant l'exécution

        self.setWindowTitle("StockInvest Pro — Terminal Quantitatif")
        self.resize(1600, 950)
        self.setStyleSheet(build_qss(**{
            "background": theme_colors.get("background", "#0B0C10"),
            "surface": theme_colors.get("surface", "#15171C"),
            "border": theme_colors.get("border", "#2A2D35"),
        }))

        self._build_ui()
        self._start_initial_load()

    def _build_ui(self) -> None:
        central = QWidget()
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # --- TOP BAR ---
        top_bar = QWidget()
        top_bar_layout = QHBoxLayout(top_bar)

        # Barre de recherche avec autocomplétion nom d'entreprise -> ticker
        # (ex: taper "Apple" propose "AAPL — Apple Inc." dans une liste déroulante).
        self.search_bar = SearchBarWidget(self.orchestrator)
        self.search_bar.ticker_chosen.connect(self._on_ticker_selected)

        self.ticker_tape = TickerTapeWidget()
        top_bar_layout.addWidget(self.search_bar, stretch=1)
        top_bar_layout.addWidget(self.ticker_tape, stretch=3)

        # --- ZONE CENTRALE (gauche / centre / droite) ---
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.market_watch = MarketWatchWidget()
        self.chart_view = ChartViewWidget()
        self.quant_hud = QuantHudWidget()

        main_splitter.addWidget(self.market_watch)
        main_splitter.addWidget(self.chart_view)
        main_splitter.addWidget(self.quant_hud)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 3)
        main_splitter.setStretchFactor(2, 1)

        # --- BAS : onglets ---
        self.tabs = QTabWidget()
        self.command_center_page = CommandCenterPage()
        self.deep_dive_page = DeepDivePage()
        self.quant_engine_page = QuantEnginePage()
        self.simulator_page = SimulatorPage()

        self.tabs.addTab(self.command_center_page, "Command Center")
        self.tabs.addTab(self.deep_dive_page, "Deep Dive")
        self.tabs.addTab(self.quant_engine_page, "Quant Engine")
        self.tabs.addTab(self.simulator_page, "Simulator")

        vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        vertical_splitter.addWidget(main_splitter)
        vertical_splitter.addWidget(self.tabs)
        vertical_splitter.setStretchFactor(0, 3)
        vertical_splitter.setStretchFactor(1, 2)

        root_layout.addWidget(top_bar)
        root_layout.addWidget(vertical_splitter)

        self.setCentralWidget(central)

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_label = QLabel("Prêt")
        self._status_bar.addWidget(self._status_label)

        self._connect_signals()
        self._connect_simulator()

    def _connect_signals(self) -> None:
        self.market_watch.ticker_selected.connect(self._on_ticker_selected)
        self.quant_engine_page.table.row_selected.connect(
            lambda row: self._on_ticker_selected(row.get("ticker", ""))
        )

    def _connect_simulator(self) -> None:
        self.simulator_page.run_requested.connect(self._on_backtest_requested)

    # ------------------------------------------------------------------
    # CHARGEMENT INITIAL — analyse de la watchlist par défaut au démarrage
    # ------------------------------------------------------------------

    def _start_initial_load(self) -> None:
        self._status_label.setText(f"Analyse de {len(self.default_watchlist)} tickers en cours...")

        self._active_worker = UniverseAnalysisWorker(self.orchestrator, self.default_watchlist)
        self._active_worker.progress.connect(self._on_analysis_progress)
        self._active_worker.finished_ok.connect(self._on_universe_analysis_done)
        self._active_worker.failed.connect(self._on_worker_failed)
        self._active_worker.start()

        # Rafraîchissement léger du ticker tape en parallèle (quotes rapides)
        self._quotes_worker = WatchlistQuotesWorker(self.orchestrator, self.default_watchlist)
        self._quotes_worker.finished_ok.connect(self._on_quotes_ready)
        self._quotes_worker.start()

    def _on_analysis_progress(self, done: int, total: int, ticker: str) -> None:
        self._status_label.setText(f"Analyse en cours ({done}/{total}) : {ticker}")

    def _on_quotes_ready(self, quotes: dict[str, tuple[float, float]]) -> None:
        self.ticker_tape.update_quotes(quotes)
        watch_rows = [
            {"ticker": t, "price": price, "change_pct": chg} for t, (price, chg) in quotes.items()
        ]
        self.market_watch.update_watchlist(watch_rows)

    def _on_universe_analysis_done(self, result: UniverseAnalysisResult) -> None:
        self._latest_universe_result = result
        n_ok = len(result.quant_scores)
        n_failed = len(result.failed_tickers)
        self._status_label.setText(f"Analyse terminée : {n_ok} tickers scorés, {n_failed} échoués")
        logger.info(f"Chargement initial terminé: {n_ok} OK / {n_failed} échoués")

        self._populate_quant_engine(result)
        self._populate_command_center(result)

    def _on_worker_failed(self, message: str) -> None:
        self._status_label.setText(f"Erreur : {message}")
        logger.error(f"Worker en échec: {message}")

    # ------------------------------------------------------------------
    # POPULATION DES PAGES À PARTIR DU RÉSULTAT D'ANALYSE
    # ------------------------------------------------------------------

    def _populate_quant_engine(self, result: UniverseAnalysisResult) -> None:
        rows = []
        for ticker, score in result.quant_scores.items():
            pr = result.ticker_results.get(ticker)
            company = pr.company if pr else None
            rows.append(
                {
                    "ticker": ticker,
                    "name": company.name if company else ticker,
                    "sector": company.sector.value if company else "Unknown",
                    "country": company.country if company else None,
                    "global_score": score.global_score,
                }
            )
            # Ajoute explicitement chaque facteur pour le tableau (colonnes Value/Growth/...)
            from core.enums import FactorType

            last_row = rows[-1]
            for factor_type in FactorType:
                fs = score.factor_scores.get(factor_type)
                last_row[factor_type.value] = fs.zscore if fs else 0.0

        self.quant_engine_page.load_scores(rows)

    def _populate_command_center(self, result: UniverseAnalysisResult) -> None:
        sector_perf: dict[str, list[float]] = {}
        for ticker, score in result.quant_scores.items():
            sector_perf.setdefault(score.sector.value, []).append(score.global_score - 50)

        avg_sector_perf = {
            sector: sum(vals) / len(vals) for sector, vals in sector_perf.items() if vals
        }
        self.command_center_page.update_sector_heatmap(avg_sector_perf)

        avg_score = (
            sum(s.global_score for s in result.quant_scores.values()) / len(result.quant_scores)
            if result.quant_scores
            else 50.0
        )
        regime = (
            MarketRegime.BULL if avg_score > 55
            else MarketRegime.BEAR if avg_score < 45
            else MarketRegime.SIDEWAYS
        )
        self.command_center_page.update_market_regime(regime, volatility=0.18)

        movers = sorted(
            (
                {"ticker": t, "prix": 0.0, "var_pct": s.global_score - 50}
                for t, s in result.quant_scores.items()
            ),
            key=lambda r: abs(r["var_pct"]),
            reverse=True,
        )[:10]
        self.command_center_page.update_top_movers(movers)

    # ------------------------------------------------------------------
    # SÉLECTION D'UN TICKER (market watch, quant engine, barre de recherche)
    # ------------------------------------------------------------------

    def _on_ticker_selected(self, ticker: str) -> None:
        """
        Point d'entrée central quand un ticker est sélectionné n'importe où
        dans l'UI (market watch, quant engine, ou résolution nom -> ticker
        via la barre de recherche) : recharge le chart depuis la base, lance
        le Deep Dive complet (sentiment + résumé IA) en arrière-plan, et
        bascule l'onglet.
        """
        if not ticker:
            return
        ticker = ticker.strip().upper()
        logger.debug(f"Ticker sélectionné dans l'UI: {ticker}")

        df = self.repository.get_price_history(ticker)
        if not df.empty:
            self.chart_view.plot(df)

        self.tabs.setCurrentWidget(self.deep_dive_page)

        quant_score = (
            self._latest_universe_result.quant_scores.get(ticker)
            if self._latest_universe_result
            else None
        )
        if quant_score is None:
            self._status_label.setText(f"{ticker} : pas encore scoré, analyse en cours...")
            self._active_worker = UniverseAnalysisWorker(self.orchestrator, [ticker])
            self._active_worker.finished_ok.connect(
                lambda result, t=ticker: self._on_single_ticker_scored(t, result)
            )
            self._active_worker.failed.connect(self._on_worker_failed)
            self._active_worker.start()
            return

        self.quant_hud.update_score(quant_score)
        self._launch_deep_dive_worker(ticker, quant_score)

    def _on_single_ticker_scored(self, ticker: str, result: UniverseAnalysisResult) -> None:
        score = result.quant_scores.get(ticker)
        if score is None:
            self._status_label.setText(f"{ticker} : impossible à scorer (données insuffisantes)")
            return
        self.quant_hud.update_score(score)
        self._launch_deep_dive_worker(ticker, score)

    def _launch_deep_dive_worker(self, ticker: str, quant_score: QuantScore) -> None:
        self._deep_dive_worker = DeepDiveWorker(self.orchestrator, ticker, quant_score)
        self._deep_dive_worker.finished_ok.connect(
            lambda payload, t=ticker, s=quant_score: self._on_deep_dive_ready(t, s, payload)
        )
        self._deep_dive_worker.failed.connect(self._on_worker_failed)
        self._deep_dive_worker.start()

    def _on_deep_dive_ready(self, ticker: str, quant_score: QuantScore, payload: tuple) -> None:
        sentiment, summary = payload
        pipeline_result = self.orchestrator.run_ticker_pipeline(ticker)
        if pipeline_result is None:
            return
        self.deep_dive_page.load_company(
            company=pipeline_result.company,
            price_features_df=pipeline_result.features_df,
            fundamentals=pipeline_result.fundamentals,
            quant_score=quant_score,
            sentiment=sentiment,
            summary=summary,
        )

    # ------------------------------------------------------------------
    # SIMULATOR — lance le backtest sur l'univers courant
    # ------------------------------------------------------------------

    def _on_backtest_requested(self, params: dict) -> None:
        if not self._latest_universe_result or not self._latest_universe_result.quant_scores:
            self._status_label.setText("Backtest impossible : aucune analyse d'univers disponible")
            return

        from backtest.engine import BacktestEngine
        import pandas as pd

        result = self._latest_universe_result
        price_data = {t: pr.price_history for t, pr in result.ticker_results.items()}

        # Score history simplifié : score constant dans le temps (pas de recalcul
        # historique dans cette version — amélioration future : scores datés).
        dates = next(iter(price_data.values())).index if price_data else pd.DatetimeIndex([])
        score_history = pd.DataFrame(
            {t: result.quant_scores[t].global_score for t in result.quant_scores if t in price_data},
            index=dates,
        )

        benchmark = (
            result.benchmark_prices
            if result.benchmark_prices is not None
            else pd.Series(100.0, index=dates)
        )

        engine = BacktestEngine(
            top_n=params["top_n"],
            rebalance_frequency=params["rebalance_frequency"],
            transaction_cost_bps=params["transaction_cost_bps"],
            slippage_bps=params["slippage_bps"],
            initial_capital=params["initial_capital"],
        )
        try:
            bt_result = engine.run(price_data, score_history, benchmark, strategy_name="Top-N Quant Score")
            self.simulator_page.display_result(bt_result)
        except Exception as exc:
            logger.exception("Échec du backtest")
            self._status_label.setText(f"Erreur backtest : {exc}")