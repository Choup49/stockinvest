"""
Fenêtre principale StockInvest Pro : layout terminal moderne et responsive.

Responsive (obligatoire) :
    - Large (>= 1400px)  : 3 colonnes Market / Chart / HUD, splitter horizontal.
    - Moyen (>= 900px)   : 2 colonnes Market + Chart, HUD replié en panneau
                           accessible via un bouton bascule dans la top bar.
    - Étroit (< 900px)   : 1 colonne, Market/Chart/HUD empilés verticalement,
                           navigation uniquement par les onglets du bas.

Navigation moderne :
    - Command Palette (Ctrl+K / Cmd+K) pour sauter vers une page ou un ticker
      sans la souris.
    - Sidebar (Market Watch) repliable via un bouton dans la top bar.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.enums import MarketRegime
from core.models import QuantScore
from core.orchestrator import MarketOrchestrator, UniverseAnalysisResult
from data.repository import MarketDataRepository
from ui.pages.command_center import CommandCenterPage
from ui.pages.deep_dive import DeepDivePage
from ui.pages.quant_engine import QuantEnginePage
from ui.pages.simulator import SimulatorPage
from ui.theme import BREAKPOINT_MEDIUM, BREAKPOINT_WIDE, LayoutMode, build_qss
from ui.widgets.chart_view import ChartViewWidget
from ui.widgets.command_palette import CommandPaletteDialog
from ui.widgets.market_watch import MarketWatchWidget
from ui.widgets.quant_hud import QuantHudWidget
from ui.widgets.search_bar import SearchBarWidget
from ui.widgets.ticker_tape import TickerTapeWidget
from ui.workers import DeepDiveWorker, UniverseAnalysisWorker, WatchlistQuotesWorker
from utils.logger import logger

PAGE_ACTION_MAP = {
    "page:command_center": 0,
    "page:deep_dive": 1,
    "page:quant_engine": 2,
    "page:simulator": 3,
}


class MainWindow(QMainWindow):
    """
    Fenêtre principale. Toute la logique métier transite par
    MarketOrchestrator, exécuté dans des QThread suivis dans self._workers
    pour ne jamais être détruits pendant leur exécution.
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
        self._workers: list = []
        self._initial_load_in_progress = True
        self._pending_ticker: str | None = None
        self._current_layout_mode: str | None = None
        self._sidebar_collapsed = False
        self._hud_visible = True

        self.setWindowTitle("StockInvest Pro — Terminal Quantitatif")
        self.resize(1600, 950)
        self.setStyleSheet(build_qss(**{
            "background": theme_colors.get("background", "#0B0C10"),
            "surface": theme_colors.get("surface", "#15171C"),
            "border": theme_colors.get("border", "#2A2D35"),
        }))

        self._build_ui()
        self._setup_command_palette()
        self._start_initial_load()

    # ------------------------------------------------------------------
    # CONSTRUCTION DE L'UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # --- TOP BAR ---
        top_bar = QWidget()
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(12, 8, 12, 8)

        self.sidebar_toggle_btn = QPushButton("☰")
        self.sidebar_toggle_btn.setObjectName("ghost")
        self.sidebar_toggle_btn.setFixedWidth(32)
        self.sidebar_toggle_btn.setToolTip("Afficher/masquer le Market Watch")
        self.sidebar_toggle_btn.clicked.connect(self._toggle_sidebar)

        self.search_bar = SearchBarWidget(self.orchestrator)
        self.search_bar.ticker_chosen.connect(self._on_ticker_selected)

        self.command_palette_btn = QPushButton("⌘K")
        self.command_palette_btn.setObjectName("ghost")
        self.command_palette_btn.setToolTip("Command Palette (Ctrl+K)")
        self.command_palette_btn.clicked.connect(self._open_command_palette)

        self.hud_toggle_btn = QPushButton("HUD")
        self.hud_toggle_btn.setObjectName("ghost")
        self.hud_toggle_btn.setToolTip("Afficher/masquer le panneau Quant HUD")
        self.hud_toggle_btn.clicked.connect(self._toggle_hud)
        self.hud_toggle_btn.hide()  # visible uniquement en mode Medium

        self.ticker_tape = TickerTapeWidget()

        top_bar_layout.addWidget(self.sidebar_toggle_btn)
        top_bar_layout.addWidget(self.search_bar, stretch=1)
        top_bar_layout.addWidget(self.command_palette_btn)
        top_bar_layout.addWidget(self.hud_toggle_btn)
        top_bar_layout.addWidget(self.ticker_tape, stretch=3)

        # --- ZONE CENTRALE ---
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.market_watch = MarketWatchWidget()
        self.chart_view = ChartViewWidget()
        self.quant_hud = QuantHudWidget()

        self.main_splitter.addWidget(self.market_watch)
        self.main_splitter.addWidget(self.chart_view)
        self.main_splitter.addWidget(self.quant_hud)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 3)
        self.main_splitter.setStretchFactor(2, 1)

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

        self.vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        self.vertical_splitter.addWidget(self.main_splitter)
        self.vertical_splitter.addWidget(self.tabs)
        self.vertical_splitter.setStretchFactor(0, 3)
        self.vertical_splitter.setStretchFactor(1, 2)

        root_layout.addWidget(top_bar)
        root_layout.addWidget(self.vertical_splitter)

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
    # COMMAND PALETTE (Ctrl+K / Cmd+K)
    # ------------------------------------------------------------------

    def _setup_command_palette(self) -> None:
        self._command_palette = CommandPaletteDialog(self.orchestrator, parent=self)
        self._command_palette.page_requested.connect(self._on_palette_page_requested)
        self._command_palette.ticker_requested.connect(self._on_ticker_selected)

        # Ctrl+K sous Windows/Linux, Cmd+K sous macOS (QKeySequence gère la
        # traduction automatique via le rôle StandardKey non disponible ici,
        # donc on enregistre explicitement les deux combinaisons usuelles).
        QShortcut(QKeySequence("Ctrl+K"), self, activated=self._open_command_palette)
        QShortcut(QKeySequence("Meta+K"), self, activated=self._open_command_palette)

    def _open_command_palette(self) -> None:
        self._command_palette.show()

    def _on_palette_page_requested(self, action_id: str) -> None:
        index = PAGE_ACTION_MAP.get(action_id)
        if index is not None:
            self.tabs.setCurrentIndex(index)

    # ------------------------------------------------------------------
    # RESPONSIVE — bascule de layout selon la largeur de la fenêtre
    # ------------------------------------------------------------------

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        mode = LayoutMode.from_width(self.width())
        if mode != self._current_layout_mode:
            self._current_layout_mode = mode
            self._apply_layout_mode(mode)

    def _apply_layout_mode(self, mode: str) -> None:
        logger.debug(f"Layout responsive : passage en mode '{mode}' (largeur={self.width()}px)")

        if mode == LayoutMode.WIDE:
            # 3 colonnes classiques
            self.main_splitter.setOrientation(Qt.Orientation.Horizontal)
            self.market_watch.show()
            self.quant_hud.show()
            self.hud_toggle_btn.hide()
            self._sidebar_collapsed = False
            self._hud_visible = True

        elif mode == LayoutMode.MEDIUM:
            # 2 colonnes : Market + Chart. HUD repliable via bouton dédié.
            self.main_splitter.setOrientation(Qt.Orientation.Horizontal)
            self.market_watch.show()
            self.hud_toggle_btn.show()
            self.quant_hud.setVisible(self._hud_visible)

        else:  # NARROW
            # 1 colonne : tout empilé verticalement, navigation par onglets.
            self.main_splitter.setOrientation(Qt.Orientation.Vertical)
            self.market_watch.hide()
            self.quant_hud.hide()
            self.hud_toggle_btn.hide()

    def _toggle_sidebar(self) -> None:
        self._sidebar_collapsed = not self._sidebar_collapsed
        self.market_watch.setVisible(not self._sidebar_collapsed)

    def _toggle_hud(self) -> None:
        self._hud_visible = not self._hud_visible
        self.quant_hud.setVisible(self._hud_visible)

    # ------------------------------------------------------------------
    # GESTION DU CYCLE DE VIE DES THREADS
    # ------------------------------------------------------------------

    def _track_worker(self, worker) -> None:
        self._workers.append(worker)
        worker.finished.connect(lambda w=worker: self._untrack_worker(w))

    def _untrack_worker(self, worker) -> None:
        if worker in self._workers:
            self._workers.remove(worker)

    def closeEvent(self, event) -> None:
        logger.info(f"Fermeture : attente de {len(self._workers)} thread(s) en cours...")
        for worker in list(self._workers):
            worker.quit()
            worker.wait(5000)
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # CHARGEMENT INITIAL
    # ------------------------------------------------------------------

    def _start_initial_load(self) -> None:
        self._initial_load_in_progress = True
        self._status_label.setText(f"Analyse de {len(self.default_watchlist)} tickers en cours...")

        universe_worker = UniverseAnalysisWorker(self.orchestrator, self.default_watchlist)
        universe_worker.progress.connect(self._on_analysis_progress)
        universe_worker.finished_ok.connect(self._on_universe_analysis_done)
        universe_worker.failed.connect(self._on_worker_failed)
        self._track_worker(universe_worker)
        universe_worker.start()

        quotes_worker = WatchlistQuotesWorker(self.orchestrator, self.default_watchlist)
        quotes_worker.finished_ok.connect(self._on_quotes_ready)
        self._track_worker(quotes_worker)
        quotes_worker.start()

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
        self._initial_load_in_progress = False

        n_ok = len(result.quant_scores)
        n_failed = len(result.failed_tickers)
        self._status_label.setText(f"Analyse terminée : {n_ok} tickers scorés, {n_failed} échoués")
        logger.info(f"Chargement initial terminé: {n_ok} OK / {n_failed} échoués")

        self._populate_quant_engine(result)
        self._populate_command_center(result)

        if self._pending_ticker:
            pending = self._pending_ticker
            self._pending_ticker = None
            self._on_ticker_selected(pending)

    def _on_worker_failed(self, message: str) -> None:
        self._initial_load_in_progress = False
        self._status_label.setText(f"Erreur : {message}")
        logger.error(f"Worker en échec: {message}")

    # ------------------------------------------------------------------
    # POPULATION DES PAGES
    # ------------------------------------------------------------------

    def _populate_quant_engine(self, result: UniverseAnalysisResult) -> None:
        from core.enums import FactorType

        rows = []
        for ticker, score in result.quant_scores.items():
            pr = result.ticker_results.get(ticker)
            company = pr.company if pr else None
            row = {
                "ticker": ticker,
                "name": company.name if company else ticker,
                "sector": company.sector.value if company else "Unknown",
                "country": company.country if company else None,
                "global_score": score.global_score,
            }
            for factor_type in FactorType:
                fs = score.factor_scores.get(factor_type)
                row[factor_type.value] = fs.zscore if fs else 0.0
            rows.append(row)

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
    # SÉLECTION D'UN TICKER
    # ------------------------------------------------------------------

    def _on_ticker_selected(self, ticker: str) -> None:
        if not ticker:
            return
        ticker = ticker.strip().upper()

        if self._initial_load_in_progress:
            self._pending_ticker = ticker
            self._status_label.setText(f"{ticker} sera affiché dès la fin du chargement initial...")
            return

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
            worker = UniverseAnalysisWorker(self.orchestrator, [ticker])
            worker.finished_ok.connect(
                lambda result, t=ticker: self._on_single_ticker_scored(t, result)
            )
            worker.failed.connect(self._on_worker_failed)
            self._track_worker(worker)
            worker.start()
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
        worker = DeepDiveWorker(self.orchestrator, ticker, quant_score)
        worker.finished_ok.connect(
            lambda payload, t=ticker, s=quant_score: self._on_deep_dive_ready(t, s, payload)
        )
        worker.failed.connect(self._on_worker_failed)
        self._track_worker(worker)
        worker.start()

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
    # SIMULATOR
    # ------------------------------------------------------------------

    def _on_backtest_requested(self, params: dict) -> None:
        if not self._latest_universe_result or not self._latest_universe_result.quant_scores:
            self._status_label.setText("Backtest impossible : aucune analyse d'univers disponible")
            return

        from backtest.engine import BacktestEngine
        import pandas as pd

        result = self._latest_universe_result
        price_data = {t: pr.price_history for t, pr in result.ticker_results.items()}

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